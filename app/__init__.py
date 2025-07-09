import logging.config

# Set up logging
from app.config import LOGGING_CONFIG

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
logger.info("Initializing Hypno-AI application")
