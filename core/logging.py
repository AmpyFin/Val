import logging
from rich.logging import RichHandler

def get_logger(name: str, level: str = 'INFO') -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%H:%M:%S",
            handlers=[RichHandler(rich_tracebacks=True)]
        )
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
