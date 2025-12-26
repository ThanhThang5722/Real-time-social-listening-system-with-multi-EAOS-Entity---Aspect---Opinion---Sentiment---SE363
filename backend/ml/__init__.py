"""
EAOS Multi-Label Model Package

Components:
- eaos_model: Model architecture, loading, inference
- spark_inference: Distributed inference with PySpark + PandasUDF
"""

from .eaos_model import (
    MultiEAOSModel,
    EAOSInference,
    load_model,
    create_inference,
    ASPECT_MAP,
    SENTIMENT_MAP
)

__all__ = [
    "MultiEAOSModel",
    "EAOSInference",
    "load_model",
    "create_inference",
    "ASPECT_MAP",
    "SENTIMENT_MAP",
]
