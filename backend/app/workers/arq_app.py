"""
Arq worker settings.

PIIScrubber is initialized once per worker process (expensive spaCy model load)
and stored in the Arq context dictionary so all jobs in the process reuse it.
"""
import logging

from arq.connections import RedisSettings

from app.config import settings
from app.logging import configure_logging, log_json
from app.workers.analysis_tasks import run_analysis

configure_logging()
logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    log_json(logger, "worker_startup")
    # Initialize the PII scrubber singleton — expensive, done once per process
    from app.services.pii_scrubber import PIIScrubber
    ctx["pii_scrubber"] = PIIScrubber()


async def shutdown(ctx: dict) -> None:
    log_json(logger, "worker_shutdown")


class WorkerSettings:
    functions = [run_analysis]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 1800     # 30 minutes hard cap
    keep_result = 3600     # keep result 1h for inspection
    on_startup = startup
    on_shutdown = shutdown
