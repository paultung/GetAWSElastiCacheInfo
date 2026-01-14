"""Utility functions for ElastiCache Info CLI."""

import fnmatch
import logging
import os
from pathlib import Path
from typing import List


# Valid field names (CLI parameter format with hyphens)
VALID_FIELDS = [
    "region",
    "type",
    "name",
    "role",
    "node-type",
    "engine-version",
    "cluster-mode",
    "shards",
    "nodes",
    "multi-az",
    "auto-failover",
    "encryption-transit",
    "encryption-rest",
    "slow-logs",
    "engine-logs",
    "maintenance-window",
    "auto-upgrade",
    "backup",
]

# Field name mapping: CLI parameter (hyphen) -> dataclass field (underscore)
FIELD_MAPPING = {
    "region": "region",
    "type": "type",
    "name": "name",
    "role": "role",
    "node-type": "node_type",
    "engine-version": "engine_version",
    "cluster-mode": "cluster_mode",
    "shards": "shards",
    "nodes": "nodes",
    "multi-az": "multi_az",
    "auto-failover": "auto_failover",
    "encryption-transit": "encryption_transit",
    "encryption-rest": "encryption_rest",
    "slow-logs": "slow_logs",
    "engine-logs": "engine_logs",
    "maintenance-window": "maintenance_window",
    "auto-upgrade": "auto_upgrade",
    "backup": "backup",
}


def match_wildcard(pattern: str, text: str) -> bool:
    """Match text against wildcard pattern.

    Args:
        pattern: Wildcard pattern (e.g., "prod-*")
        text: Text to match

    Returns:
        True if text matches pattern, False otherwise
    """
    return fnmatch.fnmatch(text, pattern)


def ensure_output_dir(path: str) -> str:
    """Ensure output directory exists.

    Args:
        path: Output file path or directory path

    Returns:
        Absolute path with directory created
    """
    path_obj = Path(path)

    # If path is a directory or ends with /, ensure it exists
    if path.endswith("/") or path_obj.is_dir():
        path_obj.mkdir(parents=True, exist_ok=True)
        return str(path_obj.absolute())

    # If path is a file, ensure parent directory exists
    parent_dir = path_obj.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    return str(path_obj.absolute())


def parse_engines(engine_str: str) -> List[str]:
    """Parse engine parameter string.

    Args:
        engine_str: Comma-separated engine types (e.g., "redis,valkey,memcached")

    Returns:
        List of engine types in lowercase
    """
    engines = [e.strip().lower() for e in engine_str.split(",")]

    # Validate engines
    valid_engines = {"redis", "valkey", "memcached"}
    invalid_engines = [e for e in engines if e not in valid_engines]

    if invalid_engines:
        raise ValueError(
            f"無效的引擎類型：{', '.join(invalid_engines)}。"
            f"有效引擎：redis, valkey, memcached"
        )

    return engines


def parse_info_types(info_type_str: str) -> List[str]:
    """Parse info-type parameter string.

    Args:
        info_type_str: Comma-separated field names or "all"

    Returns:
        List of field names in dataclass format (with underscores)

    Raises:
        ValueError: If invalid field names are provided
    """
    if info_type_str.lower() == "all":
        # Return all fields in dataclass format
        return list(FIELD_MAPPING.values())

    # Split and validate fields
    requested_fields = [f.strip().lower() for f in info_type_str.split(",")]
    invalid_fields = [f for f in requested_fields if f not in VALID_FIELDS]

    if invalid_fields:
        raise ValueError(
            f"無效的欄位名稱：{', '.join(invalid_fields)}。\n"
            f"有效欄位：{', '.join(VALID_FIELDS)}"
        )

    # Convert to dataclass format
    return [FIELD_MAPPING[f] for f in requested_fields]


def setup_logger(verbose: bool = False) -> logging.Logger:
    """Setup logger with appropriate level.

    Args:
        verbose: Enable DEBUG level logging

    Returns:
        Configured logger
    """
    logger = logging.getLogger("elasticache_info")

    # Set level
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler (stderr)
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(handler)

    return logger
