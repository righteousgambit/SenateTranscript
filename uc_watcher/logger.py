import logging
import sys

def setup_logging(log_level):
    """
    Configure logging with the specified level.
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    # First, clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Configure logging with a more detailed format
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    
    # Set the level on both the handler and the root logger
    handler.setLevel(numeric_level)
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)
    
    # Ensure all loggers inherit the correct level
    logging.getLogger('uc_watcher').setLevel(numeric_level)
    
    # Set specific module levels
    logging.getLogger('uc_watcher.transcribe').setLevel(logging.INFO)  # Always show transcription progress
    logging.getLogger('ffmpeg_progress').setLevel(logging.ERROR)  # Reduce FFmpeg noise
    
    # Test all log levels to verify configuration
    test_logger = logging.getLogger('uc_watcher.setup')
    test_logger.debug("Setup: DEBUG test message")
    test_logger.info("Setup: INFO test message")
    test_logger.warning("Setup: WARNING test message")
    test_logger.error("Setup: ERROR test message")
    
    # Disable buffering on the stdout handler
    handler.flush()
    handler.stream.flush()
    
    # Log the initial setup
    root_logger.info("Logging initialized at level: %s", log_level) 