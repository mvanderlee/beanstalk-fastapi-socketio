import logging
import os
import sys

from gunicorn.glogging import Logger
from loguru import logger

LOG_LEVEL = logging.INFO


# region - Logging initializing
# This way we capture all gunicorn and uvicorn logs and handle them in loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


intercept_handler = InterceptHandler()
logging.root.setLevel(LOG_LEVEL)

seen = set()
for name in [
    *logging.root.manager.loggerDict.keys(),
    "gunicorn",
    "gunicorn.access",
    "gunicorn.error",
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
]:
    if name not in seen:
        seen.add(name.split(".")[0])
        logging.getLogger(name).handlers = [intercept_handler]


# Keep human readable logs on stdout, but add JSON logs on stderr.
# This will allow us to be able to read `docker logs` But forward stderr to Elasticsearch or OpenSearch
class HumanFormatter:
    '''
        Ensure vertical alignment.
        The default formatter is unable to vertically align log messages because the length of {name}, {function} and {line} are not fixed.
        Source: https://loguru.readthedocs.io/en/stable/resources/recipes.html#dynamically-formatting-messages-to-properly-align-values-with-padding
    '''

    def __init__(self):
        self.padding = 40
        # Formatted this way to prevent new-line characters from being added
        self.fmt = (
            "<green>{{time:YYYY-MM-DD HH:mm:ss.SSS}}</green> | "
            "<level>{{level: <8}}</level> | "
            "<cyan>{{name}}</cyan>:<cyan>{{function}}</cyan>:<cyan>{{line}}</cyan>{padding} | "
            "<level>{{message}}</level> <magenta>{{extra}}</magenta>"
            "\n{{exception}}"  # new line at the end is required. Otherwise it won't flush properly!
        )

    def format(self, record):
        length = len("{name}:{function}:{line}".format(**record))
        self.padding = max(self.padding, length)
        return self.fmt.format(padding=" " * (self.padding - length))


logger.remove()
logger.add(sys.stdout, colorize=True, serialize=False, format=HumanFormatter().format)
logger.add(sys.stderr, colorize=False, serialize=True, format="{message}")
# endregion


class StubbedGunicornLogger(Logger):
    def setup(self, cfg):
        handler = logging.NullHandler()
        self.error_logger = logging.getLogger("gunicorn.error")
        self.error_logger.addHandler(handler)
        self.access_logger = logging.getLogger("gunicorn.access")
        self.access_logger.addHandler(handler)
        self.error_logger.setLevel(LOG_LEVEL)
        self.access_logger.setLevel(LOG_LEVEL)


if os.environ.get('MODE') == 'dev':
    reload = True

bind = '0.0.0.0:5000'
workers = 1

worker_class = 'uvicorn.workers.UvicornWorker'
logger_class = StubbedGunicornLogger

# https://docs.gunicorn.org/en/stable/faq.html#how-do-i-avoid-gunicorn-excessively-blocking-in-os-fchmod
worker_tmp_dir = '/dev/shm'
