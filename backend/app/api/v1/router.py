from fastapi import APIRouter

from app.api.v1 import auth, jobs, reports, sources

router = APIRouter()
router.include_router(auth.router)
router.include_router(sources.router)
router.include_router(jobs.router)
router.include_router(reports.router)
