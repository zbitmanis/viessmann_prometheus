import logging
import logging.config
import yaml
from pathlib import Path


def setup_logging(config_path: str) -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured
    
    path = ''
    if not isinstance(config_path, Path):
       path = Path(path)

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    logging.config.dictConfig(config)