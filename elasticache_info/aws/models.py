"""Data models for ElastiCache information."""

from dataclasses import dataclass


@dataclass
class ElastiCacheInfo:
    """ElastiCache cluster information model.

    Contains 18 configurable fields for ElastiCache cluster details.
    """

    region: str = ""
    type: str = ""
    name: str = ""
    role: str = ""
    node_type: str = ""
    engine_version: str = ""
    cluster_mode: str = ""
    shards: int = 0
    nodes: int = 0
    multi_az: str = ""
    auto_failover: str = ""
    encryption_transit: str = ""
    encryption_rest: str = ""
    slow_logs: str = ""
    engine_logs: str = ""
    maintenance_window: str = ""
    auto_upgrade: str = ""
    backup: str = ""
