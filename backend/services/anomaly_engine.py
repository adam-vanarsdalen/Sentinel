"""Anomaly engine service — thin wrapper over layer6_anomaly for use by pipeline."""
from layers.layer6_anomaly import layer6_detect

__all__ = ["layer6_detect"]
