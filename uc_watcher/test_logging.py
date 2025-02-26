#! /usr/bin/env python3
# test_logging.py
from logger import setup_logging
import logging

setup_logging("DEBUG")
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")