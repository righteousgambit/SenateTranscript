import argparse

def parse_arguments():
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(description="Senate Stream Recorder")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)"
    )
    parser.add_argument(
        "--notifications",
        action="store_true",
        help="Enable system notifications for stream events and unanimous consent"
    )
    return parser.parse_args() 