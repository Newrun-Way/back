import logging

def setup_logging(log_level: str = "INFO"):
    """
    Configures basic logging for the application.
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )
    logging.getLogger("uvicorn").propagate = True
    logging.getLogger("uvicorn.access").propagate = True
