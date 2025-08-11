import logging
import logging.config
import os

LOG_FILE = "app.log"


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {"format": "[%(levelname)s] %(message)s"},
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
        "": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "auth.utils": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "auth.routes": {"handlers": ["console"], "level": "INFO", "propagate": False},
    }
}


def setup_logging():
    if "pytest" not in os.getenv("_", ""):
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8"):
                pass
        LOGGING_CONFIG["handlers"]["file"] = {
            "class": "logging.FileHandler",
            "formatter": "standard",
            "level": "DEBUG",
            "filename": LOG_FILE,
            "encoding": "utf-8",
        }
        LOGGING_CONFIG["loggers"][""]["handlers"].append("file")

    logging.config.dictConfig(LOGGING_CONFIG)


if not logging.getLogger().handlers:
    setup_logging()
