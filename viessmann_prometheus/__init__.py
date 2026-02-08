"""
Viessmann prometheus exporter package
uses FastAPI to expose URL required for Viessmann Developer API oauth and metrics endpoint to allow fetch prometheus metrics for oauth based login, 
Exports:
- viessmann_prometheus

"""
__version__ = "0.1.0"
__author__ = "Andris Zbitkovskis"


from .viessmann_prometheus import app

__all__ = ["app"]

