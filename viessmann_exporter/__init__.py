"""
Viessmann prometheus exporter package
uses FastAPI to expose URL required for Viessmann Developer API oauth and metrics endpoint to allow fetch prometheus metrics for oauth based login, 
Exports:
- main

"""
__version__ = "0.3.0"
__author__ = "Andris Zbitkovskis"


from .main import app

__all__ = ["app"]

