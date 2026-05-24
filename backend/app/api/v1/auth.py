"""
Clerk webhook handler — syncs user creation/deletion events to the app DB.
"""
import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.errors import error_payload
from app.logging import log_json
from app.models import User

from fastapi import Depends

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post("/webhooks/clerk")
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive and process Clerk webhook events."""
    payload = await request.body()
    headers = dict(request.headers)

    # Verify svix signature
    if settings.clerk_webhook_secret:
        try:
            from svix.webhooks import Webhook, WebhookVerificationError
            wh = Webhook(settings.clerk_webhook_secret)
            event = wh.verify(payload, headers)
        except Exception as e:
            log_json(logger, "webhook_verification_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_payload("INVALID_SIGNATURE", "Webhook signature verification failed"),
            )
    else:
        import json
        event = json.loads(payload)
        log_json(logger, "webhook_signature_skipped", reason="CLERK_WEBHOOK_SECRET not set")

    event_type = event.get("type")
    data = event.get("data", {})

    if event_type == "user.created":
        clerk_user_id = data.get("id")
        emails = data.get("email_addresses", [])
        email = emails[0].get("email_address", "") if emails else ""

        result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
        existing = result.scalar_one_or_none()
        if not existing:
            user = User(clerk_user_id=clerk_user_id, email=email)
            db.add(user)
            await db.commit()
            log_json(logger, "user_created_via_webhook", clerk_user_id=clerk_user_id)

    elif event_type == "user.deleted":
        clerk_user_id = data.get("id")
        result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
        user = result.scalar_one_or_none()
        if user:
            await db.delete(user)
            await db.commit()
            log_json(logger, "user_deleted_via_webhook", clerk_user_id=clerk_user_id)

    return {"ok": True}
