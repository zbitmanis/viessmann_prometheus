from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Tuple, Optional


@dataclass
class MetricRule:
    """Defines the dynamic logic and processing rules for populating a metric.
    """
    feature: str
    metric_name: str
    metric_help: str
    properties: list = field(default_factory=lambda: [])
    feature_labels: list = field(default_factory=lambda: [])
    include_feature_label: bool = True
    enabled: bool = False
    running: bool = False
    unit: str = ""

    def to_dict(self) -> dict:
        result: dict = {};
        
        result["feature"] = self.feature
        result["metric_name"] = self.metric_name
        result["metric_help"] = self.metric_help
        result["properties"] = self.properties
        result["feature_labels"] = self.feature_labels
        result["include_feature_label"] = self.include_feature_label
        result["enabled"] = self.enabled
        result["running"] = self.running
        result["unit"] = self.unit

        return result


@dataclass
class MetricConfig:
    """ Defines the static properties and schema of a Prometheus metric.
    """
    installations: dict
    features_stats_output: str
    installations_fetch: bool
    base_labels: list
    installations_fetch_period: int = 86400
    installations_last_fetch: int = 0
    update_config_file: bool = False

    def to_dict(self) -> dict:
        """
        Turns MetricConf to dictionary to use for generic labels values       
        :param self: Description
        :return: Description
        :rtype: dict
        """
        result: dict = {} 

        result["installations"] = self.installations
        result["features_stats_output"] = self.features_stats_output
        result["installations_fetch"] = self.installations_fetch
        result["base_labels"] = self.base_labels
        result["installations_fetch_period"] = self.installations_fetch_period
        result["installations_last_fetch"] = self.installations_last_fetch
        result["update_config_file"] = self.update_config_file

        return result


@dataclass
class MetricSpec:
    property_name: str
    period_label: str
    unit_expected: str = "kilowattHour"
    value_key: str = "value"


class FeatureSpecs(Enum):
    POWER = (
        MetricSpec("currentDay", "day",),
        MetricSpec("lastSevenDays", "7d"),
        MetricSpec("currentMonth", "month"),
        MetricSpec("lastMonth", "last_month"),
        MetricSpec("currentYear", "year"),
        MetricSpec("lastYear", "last_year"),
    )

    GAS = (
        MetricSpec("currentDay", "day", "cubicMeter"),
        MetricSpec("lastSevenDays", "7d", "cubicMeter"),
        MetricSpec("currentMonth", "month", "cubicMeter"),
        MetricSpec("lastMonth", "last_month", "cubicMeter"),
        MetricSpec("currentYear", "year", "cubicMeter"),
        MetricSpec("lastYear", "last_year", "cubicMeter"),
    )
