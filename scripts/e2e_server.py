"""Disposable browser harness: real API/RQ SimpleWorker, in-memory Redis, demo model."""
import logging
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="review-e2e-") as directory:
        os.environ.update(DATABASE_URL=f"sqlite:///{directory}/reviews.db",
                          DASHBOARD_TOKEN="browser-test-token", REVIEW_MODE="demo")
        import fakeredis
        import uvicorn
        from rq import Queue, SimpleWorker

        from review_agent import api, jobs
        from review_agent.storage import session_factory

        redis = fakeredis.FakeRedis()
        jobs.connection = lambda: redis
        api.connection = lambda: redis
        session_factory()
        server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=8765, log_level="warning"))
        threading.Thread(target=server.run, daemon=True).start()
        queue = Queue("reviews", connection=redis)
        logging.getLogger("rq.worker").setLevel(logging.WARNING)
        while True:
            jobs.dispatch_once()
            if queue.count:
                SimpleWorker([queue], connection=redis).work(burst=True, logging_level="WARNING")
            time.sleep(0.2)


if __name__ == "__main__":
    main()
