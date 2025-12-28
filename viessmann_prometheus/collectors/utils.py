import time

from specs import FeatureSpecs


def get_short_feature(feature: str, default = "unknown") -> str:
    """
    Turn:
        heating.power.consumption.summary.dhw -> dhw
        heating.power.consumption.summary.heating -> heating
    Fallback: last token after '.'
    """
    if not feature:
        return "unknown"
    return feature.split(".")[-1].strip() or default

def get_feature_enum(feature: str) -> FeatureSpecs:
    """
    Returns feature properties specs from

    :param feature: type of the feature supported feature types("gas","power")
    """

    if feature == ("gas"):
        return FeatureSpecs.GAS
    if feature == ("power"):
        return FeatureSpecs.POWER
    raise ValueError(f"Unsupported feature: {feature}")


def now_ts() -> int:
    """
    Returns current timestamp
    """
    return int(time.time())
