"""DB-backed runtime reconciler. Safe to run multiple processes with PostgreSQL row locks."""

import logging
import signal
import time

from dx_platform.config import Settings
from dx_platform.database import make_engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Run
from .workflow import advance

logger = logging.getLogger("dx.core.worker")
stopping = False


def tick(engine):
    with Session(engine) as db:
        rows = list(
            db.scalars(
                select(Run)
                .where(Run.state.in_(["queued", "running"]))
                .with_for_update(skip_locked=True)
                .limit(20)
            )
        )
        for run in rows:
            advance(db, run.id)
        db.commit()
    # Core events are retained for inspection. No external event subscriber is enabled in this pilot.
    # Do not mark events sent without an acknowledged delivery; events remain pending by design.


def main():
    global stopping
    logging.basicConfig(level=logging.INFO)
    engine = make_engine(Settings(service_name="core").database_url)

    def stop(*_):
        global stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        try:
            tick(engine)
        except Exception as exc:
            logger.error("reconcile_failed type=%s", type(exc).__name__)
        time.sleep(2)


if __name__ == "__main__":
    main()
