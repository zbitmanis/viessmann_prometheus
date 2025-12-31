
import time
from typing import Any, Mapping, Dict

from prometheus_client import Gauge, Counter

from .specs import MetricRule, MetricConfig
from .utils import now_ts, short_feature

from pprint import pprint


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
    VIESSSMANN_INTERNAL_COUNTERS = {
        'viessmann_api_requests': {
           'metric_help': 'API requests to Viessmann API server',
           'base_labels': ['client_id']
        },
        'viessmann_auth_requests': {
           'metric_help': 'API requests to Viessmann API server',
           'base_labels': ['client_id',
                           'type']
        },
        'viessmann_metrics': {
           'metric_help': 'Metrics stats while processing response',
           'base_labels': ['type']
        }
    }
    VIESSSMANN_INTERNAL_GAUGES = {
        'viessmann_api_request_duration': {
           'metric_help': 'API request to Viessmann API server duration',
           'base_labels': ['client_id',
                           'type']
        },
        'viessmann_auth_request_duration': {
           'metric_help': 'API request for Viessmann OAuth requests',
           'base_labels': ['client_id',
                           'endpoint',
                           'type']
        },
        'viessmann_collector_processing_duration': {
           'metric_help': 'Time spent to process collected features from API server',
           'base_labels': ['installation_id',
                           'gateway_id',
                           'device_id',
                           'operation']
        }
    }

    _gauges: dict[str, Gauge]
    _counters: dict[str, Counter]
    _dynamic_counters_count: int
    _dynamic_gauges_count: int
    _dynamic_collectable_gauges_count: int
    _last_dynamic_gauges_count: int
    _stats: dict

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
        #self._stats['collected'] = 0
        #self._stats['uncollectable'] = 0
        #self._stats['last_update_time'] = 0

    def _add_gauge(self, name: str, help: str, labels: list[str]):
        if name not in self._gauges:
            self._gauges_count = self._gauges_count + 1
            self._gauges[name] = Gauge(name, help, labels)

    def _add_counter(self, name: str, help: str, labels: list[str]):
        if name not in self._counters:
            self._counters_count = self._counters_count + 1
            self._counters[name] = Counter(name, help, labels)

    def get_gauge(self, name: str):
        if name not in self._gauges:
            raise ValueError('Cant find the gauge {}'.format(name))
        else:
            return self._gauges.get('name')

    def set_gauge_value(self, name: str, labels: list[str], value):
        if name in self._gauges:
            g = _gauges.get('name')
            g.labels(**labels).set(value)
        else:
            raise ValueError(f'Cant find the gauge {name} labels {labels}')

    def get_value_by_path(self, payload: Dict[str, Any], path: str, default=None):
        """
        Get value from nested dict using dot-separated path.
        """
        # ANCHOR -  Create custom dictionary adding payload, rules and config keys
        # to gather values from path
        # source: Mapping[str, Any]
        current = payload
        #gen_source, gen_path = self.get_value_source(path)
        
        for key in path.split('.'):
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
            if current is default:
                return default
        return current

    def compose_metric_labels(self, payload: Dict[str, Any], rule: MetricRule)->Dict[str,str]:
        """
        Compose labels with assigned values for metric

        :param payload: Feature data to be used for label values
        :param metrics_rules:  Metrics rules for labels values
        :param config: Collector configuration
        :return: Dictionary of labels with values
        """

        result: dict = {}
        base_labels: list =  payload.get('base_labels')
        feature_labels: list = rule.feature_labels#payload.get('feature_labels')

        for item in base_labels:
            label = next(iter(item))
            path = item[label].get('source')
            value=self.get_value_by_path(payload, path)
            
            result[label] = value
        
        for item in feature_labels:
            label = next(iter(item))
            path = item[label].get('source')
            value=self.get_value_by_path(payload, path)
        
            result[label] = value
            
        if rule.include_feature_label:
            result['feature']=short_feature(rule.feature)

        return result

    def init_metrics(self, metrics_rules: dict, config: MetricConfig):
        """
        Iniitilaise metrics from exporter configuration
        """

        # Add internal viessmann collector Counters
        for ckey, cvalue in self.VIESSSMANN_INTERNAL_COUNTERS.items():
            self._add_counter(ckey, cvalue.get('metric_help'), cvalue.get('base_labels'))

        # Add internal viessmann collector Gauges
        for gkey, gvalue in self.VIESSSMANN_INTERNAL_GAUGES.items():
            self._add_gauge(gkey, gvalue.get('metric_help'), gvalue.get('base_labels'))

        # Add Gauges based on configuration
        if not isinstance(metrics_rules, dict):
            raise ValueError(f'Invalid Metrics Rules structure in {metrics_rules}')

        # Normalize base labels to Prometheus Metrics format, remove labels source definition
        base_labels = []
        for item in config.base_labels:
            for key, value in item.items():
                base_labels.append(key)


        if not isinstance(base_labels, list):
            raise ValueError(f'Invalid base labels in config in {config}')

        for key, rule in metrics_rules.items():
            feature_labels = []
            for item in rule[0].feature_labels:
                for lkey, lvalue in item.items():
                    feature_labels.append(lkey)

            if(rule[0].include_feature_label):
                    feature_labels.append('feature')

            self._dynamic_gauges_count = self._dynamic_gauges_count + 1
            length = 0
            for r in rule:
              length = length + 1  
              self._dynamic_collectable_gauges_count = self._dynamic_collectable_gauges_count + len(r.properties)
            # print('rules_count: {} len: {}'.format(
            #     length, self._dynamic_collectable_gauges_count))
            # pprint(rule)

            self._add_gauge(key, rule[0].metric_help,
                            base_labels+feature_labels)

    def update_metrics(self, payload: dict, metrics_rules: dict, config: MetricConfig):
        """
        Update metrics using dictionary based on Viessmann request results
        """
        # ANCHOR - TBD add time consumption, collected uncollected metrics for collector feature use stats

        tsb = now_ts()
        tse = 0

        self._last_dynamic_gauges_count = 0

        if not isinstance(metrics_rules, dict):
            raise ValueError(f'Invalid Metrics Rules structure in {metrics_rules}')

        base_labels: list = config.base_labels
        if not isinstance(base_labels, list):
            raise ValueError(f'Invalid base labels in config in {config}')

        # Process payload data, add metrics based on configuration
        self._last_dynamic_gauges_count = 0

        for item in payload.get('data', []):
            for key, rules in metrics_rules.items():
                """ iterate trough metrics defined within dict format
                    e.g. {'viessmann_heating_gas_consumption_cbm': [MetricRule,MetricRule]}
                """
                for mr in rules:
                    """ Filter payload for defined within fetch rules
                        MetricRule(feature='heating.gas.consumption.summary.dhw' ...
                    """
                    if item.get('feature') == mr.feature:
                        """ operate only features defined within fetch rules
                        """
                        g = self._gauges.get(key)
                        item_properties = item.get('properties')

                        for mrp_property in mr.properties:
                            """ iterate trough config payload properties
                                MetricRule(...properties={'currentDay': 'day'},...
                            """
                            property_item = item_properties.get(mrp_property.get('value'))
                            # ANCHOR - TBD get value key from metric rules, adjust value type
                            labels:dict = {}
                            values_payload:dict = {}
                            values_payload['config'] = config.to_dict()
                            values_payload['base_labels'] = config.base_labels
                            values_payload['property'] =  mrp_property
                            values_payload['payload'] = item
                            
                            labels: dict = self.compose_metric_labels(values_payload,mr)
                            
                            value = property_item.get('value')

                            if value is not None:
                                g.labels(**labels).set(float(value))
                                self._last_dynamic_gauges_count = self._last_dynamic_gauges_count + 1
                            else:
                                raise ValueError('Cant get value for {} : {}'.format(key, mr.feature))
        tse = now_ts()

        self._stats['collected'] = self._last_dynamic_gauges_count
        # ANCHOR - update instead of gauges use metrics with labels - single gauge contain arr of features
        self._stats['uncollectable'] = self._dynamic_collectable_gauges_count - \
            self._last_dynamic_gauges_count
        self._stats['last_update_time']=tse
        self._stats['time_used_to_process_metrics']=tse-tsb

    def get_stats(self)->Dict[str,Any]:
        return self._stats

VIESSSMANN_METRICS = ViessmannMetrics()
"""Default  ViessmannMetrics instance to expose single instance of metrics"""
