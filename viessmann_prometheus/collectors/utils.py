import time
from datetime import datetime

from .specs import FeatureSpecs


def short_feature(feature: str,
                  feature_idx: int = -1,
                  delimiter: str = '.',
                  default: str = 'unknown') -> str:
    """
    Turn:
        heating.power.consumption.summary.dhw -> dhw
        heating.power.consumption.summary.heating -> heating
    Fallback: last token after '.'
    """
    if not feature:
        return default

    return feature.split(delimiter)[feature_idx].strip() or default


def get_feature_enum(feature: str) -> FeatureSpecs:
    """
    Returns feature properties specs from

    :param feature: type of the feature supported feature types('gas','power')
    """

    if feature == ('gas'):
        return FeatureSpecs.GAS
    if feature == ('power'):
        return FeatureSpecs.POWER
    raise ValueError(f'Unsupported feature: {feature}')


def now_ts() -> int:
    """
    Returns current timestamp
    """
    return int(time.time())


def iso_to_unix(iso: str, local_tz: bool = True) -> int:
    """
    Convert ISO-8601 Zulu timestamp (e.g. '2025-12-19T19:25:11.887Z') to Unix.
    """
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))

    if local_tz:
        dt = dt.astimezone()  # system local TZ

    return int(dt.timestamp())
