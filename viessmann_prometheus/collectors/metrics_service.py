
from typing import Dict, List, Any 

import os
import logging
import json
import yaml


from .specs import MetricRule, MetricConfig

logger = logging.getLogger(__name__)


class ViessmannMetricsService:
    config: MetricConfig
    metrics_rules: Dict[str, MetricRule]
    config_file_path: str
    stats_file_path: str
    last_stats: Dict[str,Any]

    def __init__(self, config_path: str, stats_path = None):
        self.config_file_path = config_path
        self.config = self.load_config(self.config_file_path)
        self.metrics_rules = self.load_metric_rules(self.config_file_path)
        if stats_path is not None: 
            self.stats_file_path = stats_path

    @staticmethod
    def load_config(path: str) -> Dict[str,MetricConfig]:
        """
        Load feature → MetricConfig from configuration YAML file.
        """
        mc: MetricConfig

        if not os.path.exists(path):
            ValueError('Config file {} does not exists'.format(path))
        
        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)

        if not isinstance(cfg, dict):
            raise ValueError('Invalid YAML root structure in {}'.format(path)) 
        
        c = cfg.get('config', {})

        if c is not None:
            mc = MetricConfig(
            installation=c.get('installation'),
            features_stats_output=c.get('features_stats_output'),
            installations_fetch=c.get('installations_fetch'),
            base_labels=c.get('base_labels'),
            installations_fetch_period=c.get('installations_fetch_period'),
            installations_last_fetch=0,
            update_config_file=c.get('update_config_file')
            )
        return mc 

    @staticmethod
    def load_metric_rules(path: str) -> Dict[str,List[MetricRule]]:
        """
        Load MetricRule mapping from YAML config file.
        """
        mrresult: dict = {}

        if not os.path.exists(path):
            ValueError('Config file {} does not exists'.format(path))

        with open(path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        
        features = cfg.get('features', {})
        
        if features is None:
            raise ValueError(f'Config file {path} does not contains features to collect')

        for f in features:
            mr = MetricRule(f.get('feature'),
                            f.get('metric_name'),
                            f.get('metric_help'),
                            f.get('properties'),
                            f.get('feature_labels'),
                            f.get('include_feature_label')
                            )
            
            r = mrresult.get(mr.metric_name)
        
            if r is None:
                mrresult[mr.metric_name]=[mr]
            else:       
                mrresult[mr.metric_name]=r+[mr]

        return mrresult       

    def load_features_stats(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def update_features_stats(self):
        self.last_stats = self.load_features_stats(self.stats_file_path)
