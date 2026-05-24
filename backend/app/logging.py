import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import settings


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
    )
    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def log_json(logger: logging.Logger, event: str, **kwargs: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **kwargs,
    }
    logger.info(json.dumps(payload))
