
from typing import Any, Dict, List, Tuple
import logging

from prometheus_client import Gauge, Counter
from time import perf_counter_ns 

from .specs import MetricRule, MetricConfig
from .utils import now_ts, short_feature, iso_to_unix

MetricLabelValues = Dict[str, str]
MetricValues = Tuple[MetricLabelValues,float]

logger = logging.getLogger(__name__)

class ViessmannMetrics:
    """
    ViessmannMetrics exports Viessmann IoT energy consumption data to Prometheus.

    The class processes Viessmann feature
    payloads and exposes period-aggregated consumption values
    (e.g. day, month, year) as Prometheus Gauges based on configuration within metrics.yaml

    Design principles:
    - Uses Gauges because Viessmann values are pre-aggregated and reset by period
    - One Prometheus time series per (feature, period)
    - Metric structure (names and labels) is fixed at startup
    - Supports multiple features (e.g. DHW, heating) via labels
    - Safe for single-process exporters using the default Prometheus registry

    Example exported metric:
      viessmann_heating_power_consumption_kwh{
        installation_id='123456...',
        gateway_id='123456...',
        device_id='0',
        feature='dhw',
        period='month'
      } 1.2

    The class does NOT:
    - calculate deltas
    - reset counters
    - mutate metric schemas at runtime

    It is intended to be instantiated once per process and reused as a singleton.
    """
    VIESSSMANN_INTERNAL_COUNTERS: Dict[str, Any] = {
        'viessmann_heating_collector_api_requests': {
           'metric_help': 'API requests to Viessmann API server',
           'base_labels': ['request', 'status_code']
        }
    }
    VIESSSMANN_INTERNAL_GAUGES: Dict[str, Any] = {
        'viessmann_heating_collector_metrics_stats': {
           'metric_help': 'Metrics stats while processing response',
           'base_labels': ['request','type']
        },
        'viessmann_heating_collector_data_timestamp': {
            'metric_help': 'Unix timestamp of the last successful metrics refresh',
            'base_labels': ['request','type']
        },
    }

    _gauges: dict[str, Gauge]
    _counters: dict[str, Counter]
    _dynamic_counters_count: int
    _dynamic_gauges_count: int
    _dynamic_collectable_gauges_count: int
    _last_dynamic_gauges_count: int
    _stats: Dict[str, Any]

    def __init__(self):
        """
        Viessmann Developer API's free tier has a limited scope of API calls per day ~1400
        counters purpose collect metrics for API calls
        """
        self._gauges: dict[str, Gauge] = {}
        self._counters: dict[str, Counter] = {}
        self._dynamic_counters_count = 0
        self._dynamic_gauges_count = 0
        self._dynamic_collectable_gauges_count = 0
        self._counters_count = 0
        self._gauges_count = 0
        self._last_dynamic_gauges_count = 0
        self._stats = {}

    def _add_gauge(self, name: str, help: str, labels: list[str]):
        if name not in self._gauges:
            self._gauges_count = self._gauges_count + 1
            self._gauges[name] = Gauge(name, help, labels)

    def _add_counter(self, name: str, help: str, labels: list[str]):
        if name not in self._counters:
            self._counters_count = self._counters_count + 1
            self._counters[name] = Counter(name, help, labels)

    def inc_requests_counter(self, request: str, status_code: int) -> None:
        """
         Increase Viessmann API requests counters 
        """
        cnt: Counter = self._counters.get('viessmann_api_requests')
        cnt.labels(request= request, status_code=status_code).inc()

    def get_gauge(self, name: str) -> Gauge:
        """
        Return a registered Prometheus Gauge by name.
        """

        if name not in self._gauges:
            raise ValueError(f'Cant find the gauge {name}')
        return self._gauges['name']

    def set_gauge_value(self, name: str, labels: Dict[str, str], value: float):
        """
        Sets a value to registered Prometheus Gauge by labels.
        """
        if name not in self._gauges:
            raise ValueError(f'Cant find the gauge {name} labels {labels}')
        g = self._gauges['name']
        g.labels(**labels).set(value)

    def get_value_by_path(self, payload: Dict[str, Any], path: str, default: str = 'unknown') -> str:
        """
        Get value from nested dict using dot-separated path.
        """
        current = payload

        for key in path.split('.'):
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
            if current is default:
                return default
        return current

    def compose_metric_labels(self, payload: Dict[str, Any], rule: MetricRule) -> Dict[str, str]:
        """
        Compose labels with assigned values for metric
        """

        result: Dict[str, Any] = {}
        base_labels: List[Dict[str, Any]] = payload.get('base_labels')
        feature_labels: List[str] = rule.feature_labels

        for item in base_labels:
            label = next(iter(item))
            path = item.get(label)['source']
            value = self.get_value_by_path(payload, path)

            result[label] = value

        for item in feature_labels:
            label = next(iter(item))
            path = item[label].get('source','')
            value = self.get_value_by_path(payload, path)

            result[label] = value

        if rule.include_feature_label:
            result['feature'] = short_feature(rule.feature, rule.feature_idx)

        return result

    def init_metrics(self, metrics_rules: Dict[str, List[MetricRule]], config: MetricConfig):
        """
        Initialise metrics from exporter configuration
        """

        # Add internal viessmann collector Counters
        for mkey, mvalue in self.VIESSSMANN_INTERNAL_COUNTERS.items():
            self._add_counter(mkey, mvalue.get('metric_help'), mvalue.get('base_labels'))

        # Add internal viessmann collector Gauges
        for mkey, mvalue in self.VIESSSMANN_INTERNAL_GAUGES.items():
            self._add_gauge(mkey, mvalue.get('metric_help'), mvalue.get('base_labels'))

        # Add Gauges based on configuration
        if not bool(metrics_rules):
            raise ValueError(f'Invalid Metrics Rules structure in {metrics_rules}')

        # Normalize base labels to Prometheus Metrics format, remove labels source definition
        base_labels: list = []
        for item in config.base_labels:
            for key, value in item.items():
                base_labels.append(key)

        if not bool(base_labels):
            raise ValueError(f'Invalid base labels in config in {config}')

        for key, rule in metrics_rules.items():
            feature_labels = []
            for item in rule[0].feature_labels:
                for lkey, lvalue in item.items():
                    feature_labels.append(lkey)

            if rule[0].include_feature_label:
                feature_labels.append('feature')

            self._dynamic_gauges_count = self._dynamic_gauges_count + 1
            length = 0
            for r in rule:
                length = length + 1
                self._dynamic_collectable_gauges_count = self._dynamic_collectable_gauges_count + len(r.properties)

            self._add_gauge(key, rule[0].metric_help,
                            base_labels+feature_labels)

    def update_metrics(self, payload: dict, metrics_rules: dict, config: MetricConfig):
        """
        Update metrics using dictionary based on Viessmann request results
        """
        # ANCHOR - TBD add time consumption, collected uncollected metrics for collector feature use stats

        tsb = perf_counter_ns()
        tse = 0

        self._last_dynamic_gauges_count = 0

        if not bool(metrics_rules):
            raise ValueError(f'Invalid Metrics Rules structure in {metrics_rules}')

        base_labels: list = config.base_labels
        if not bool(base_labels):
            raise ValueError(f'Invalid base labels in config in {config}')

        # Process payload data, add metrics based on configuration
        self._last_dynamic_gauges_count = 0

        api_ts: int = 0
        col_ts: int = now_ts()

        for item in payload.get('data', []):
            for key, rules in metrics_rules.items():
                # iterate trough metrics defined within dict format
                #    e.g. {'viessmann_heating_gas_consumption_cbm': [MetricRule,MetricRule]}
                
                for mr in rules:
                    # Filter payload for defined within fetch rules
                    # MetricRule(feature='heating.gas.consumption.summary.dhw' ...
                    
                    # operate only features defined within fetch rules
                    if item.get('feature') == mr.feature:
                        # find latest timestamp data on api server  
                        feature_api_ts = iso_to_unix(item.get('timestamp'))
                        if api_ts < feature_api_ts : 
                            api_ts = feature_api_ts

                        g = self._gauges.get(key)
                        item_properties = item.get('properties')

                        for mrp_property in mr.properties:
                            # iterate trough config payload properties
                            # MetricRule(...properties={'currentDay': 'day'},...

                            property_item = item_properties.get(mrp_property.get('value'))
                            # ANCHOR - TBD get value key from metric rules, adjust value type
                            labels: Dict[str, str] = {}
                            values_payload: Dict[str, Any] = {}
                            values_payload['config'] = config.to_dict()
                            values_payload['base_labels'] = config.base_labels
                            values_payload['property'] = mrp_property
                            values_payload['payload'] = item

                            labels: dict = self.compose_metric_labels(values_payload, mr)

                            value = property_item.get('value')

                            if value is not None:
                                g.labels(**labels).set(float(value))
                                self._last_dynamic_gauges_count = self._last_dynamic_gauges_count + 1
                            else:
                                raise ValueError('Cant get value for {} : {}'.format(key, mr.feature))
        tse = perf_counter_ns()
        
        msg: Gauge = self._gauges['viessmann_heating_collector_metrics_stats']
        msg.labels(request='features', type='collected').set(self._last_dynamic_gauges_count)
        msg.labels(request='features', type='uncollectable').set(
            self._last_dynamic_gauges_count-self._last_dynamic_gauges_count)

        self._gauges['viessmann_heating_collector_data_timestamp'].labels(
            request='features', type='api').set(api_ts)
        self._gauges['viessmann_heating_collector_data_timestamp'].labels(
            request='features', type='collector').set(col_ts)
        



VIESSSMANN_METRICS = ViessmannMetrics()
"""Default  ViessmannMetrics instance to expose single instance of metrics"""
