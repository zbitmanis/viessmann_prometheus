import logging
import logging.config
import yaml
from pathlib import Path


def setup_logging(config_path: str) -> None:
    """
    Setup logging configuration
    """
    print(f'logging config path {config_path}')
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    path: Path = Path(config_path)

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    logging.config.dictConfig(config)
