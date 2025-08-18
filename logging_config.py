import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[%(levelname)s] %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False
        },
        "auth.utils": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False
        },
        "auth.routes": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False
        },
    }
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)


if not logging.getLogger().handlers:
    setup_logging()
