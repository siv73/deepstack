"""The request id as a ContextVar, added to every log record by a logging filter."""

import contextvars
import logging

request_id = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id.get()  # read in whatever context the log call runs in
        return True


class Lines(logging.Handler):
    """Keeps formatted lines in a list, so programs and tests can print or check them."""

    def __init__(self):
        super().__init__()
        self.lines = []
        self.addFilter(RequestIdFilter())
        self.setFormatter(logging.Formatter("[%(request_id)s] %(name)s: %(message)s"))

    def emit(self, record):
        self.lines.append(self.format(record))


def capture(*names):
    """Send INFO records of the named loggers to one Lines handler and return it."""
    handler = Lines()
    for name in names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.propagate = False
    return handler
