
from typing import Dict, List, Any

import os
import logging
import json
import yaml


from .specs import MetricRule, MetricConfig

logger = logging.getLogger(__name__)


class ViessmannMetricsService:
    """
    Manages metric configuration, rules, and runtime statistics
    for Viessmann metrics collection. Provides metric update.
    """
    config: MetricConfig
    metrics_rules: Dict[str, List[MetricRule]] = {}
    config_file_path: str
    stats_file_path: str
    last_stats: Dict[str, Any]

    def __init__(self, config_path: str, stats_path: str = ''):
        self.config_file_path = config_path
        self.config = self.load_config(self.config_file_path)
        self.metrics_rules = self.load_metric_rules(self.config_file_path)
        if stats_path:
            self.stats_file_path = stats_path

    @staticmethod
    def load_config(path: str) -> MetricConfig:
        """
        Load feature → MetricConfig from configuration YAML file.
        """
        mc: MetricConfig

        if not os.path.exists(path):
            raise ValueError(f'Config file {path} does not exists')

        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg: Dict[str, Any] = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML structure in {path}: {e}") from e

        c: Dict[str, Any] = cfg.get('config', {})

        if not bool(c):
            raise ValueError(f'Cant find config section within YAML file {path}')

        mc = MetricConfig(
            installation=c.get('installation', {}),
            features_stats_output=c.get('features_stats_output', ''),
            installations_fetch=c.get('installations_fetch', False),
            base_labels=c.get('base_labels', []),
            installations_fetch_period=c.get('installations_fetch_period', 86400),
            installations_last_fetch=0,
            update_config_file=c.get('update_config_file', False)
            )
        logger.debug(f'Metrics config: {mc}')
        return mc

    @staticmethod
    def load_metric_rules(path: str) -> Dict[str, List[MetricRule]]:
        """
        Load MetricRule mapping from YAML config file.
        """
        mrresult: Dict[str, List[MetricRule]] = {}

        if not os.path.exists(path):
            raise ValueError(f'Config file {path} does not exists')

        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)

        features = cfg.get('features', {})

        if features is None:
            raise ValueError(f'Config file {path} does not contains features to collect')

        for f in features:
            mr = MetricRule(feature=f.get('feature'),
                            data_key=f.get('data_key','value'),
                            metric_name=f.get('metric_name'),
                            metric_help=f.get('metric_help'),
                            properties=f.get('properties'),
                            feature_labels=f.get('feature_labels'),
                            feature_idx=f.get('feature_idx',-1),
                            include_feature_label=f.get('include_feature_label',False))
            logger.debug(f'Metrics rule: {mr}')

            r = mrresult.get(mr.metric_name)

            if r is None:
                mrresult[mr.metric_name] = [mr]
            else:
                mrresult[mr.metric_name] = r+[mr]

        return mrresult

    def load_features_stats(self, path: str) -> Dict[str, Any]:
        """
        Load statistics from pre requested features file
        """
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def update_features_stats(self):
        """
        Returns statistics from the last metrics update iteration
        """
        self.last_stats = self.load_features_stats(self.stats_file_path)
