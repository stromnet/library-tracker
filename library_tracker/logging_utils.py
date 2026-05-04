from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator


def configure_logging(verbose: bool = False) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@contextmanager
def timed(logger: logging.Logger, message: str) -> Iterator[None]:
    start = time.perf_counter()
    logger.info("START %s", message)
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        logger.info("DONE %s in %.2fs", message, duration)
