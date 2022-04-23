import logging

from app import config

logging.basicConfig(level=config.LOG_LEVEL)


def main() -> str:
    logging.info("Hello, World!")
    return config.RETURN_VALUE
