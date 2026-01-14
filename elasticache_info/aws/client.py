"""AWS ElastiCache client for querying cluster information."""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from elasticache_info.aws.exceptions import (
    AWSAPIError,
    AWSConnectionError,
    AWSCredentialsError,
    AWSInvalidParameterError,
    AWSPermissionError,
)
from elasticache_info.aws.models import ElastiCacheInfo
from elasticache_info.field_formatter import FieldFormatter

logger = logging.getLogger(__name__)


def handle_aws_errors(func: Callable) -> Callable:
    """Decorator to handle AWS API errors with retry logic.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                # Handle throttling with retry
                if error_code in ["Throttling", "RequestLimitExceeded"]:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"API throttled, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue

                # Handle permission errors
                if error_code in ["AccessDenied", "UnauthorizedOperation"]:
                    operation = func.__name__
                    raise AWSPermissionError(operation, e)

                # Handle invalid parameters
                if error_code == "InvalidParameterValue":
                    raise AWSInvalidParameterError("unknown", "unknown", e)

                # General API error
                operation = func.__name__
                raise AWSAPIError(operation, error_code, error_message, e)

            except NoCredentialsError as e:
                raise AWSCredentialsError(e)

            except BotoCoreError as e:
                # Extract region from args if available
                region = "unknown"
                if args and hasattr(args[0], "region"):
                    region = args[0].region
                raise AWSConnectionError(region, e)

        # Should not reach here, but just in case
        return func(*args, **kwargs)

    return wrapper


class ElastiCacheClient:
    """Client for querying AWS ElastiCache information.

    Implements a 4-layer query architecture:
    - Layer 1: Global Datastore Discovery
    - Layer 2: Replication Group Enumeration
    - Layer 3: Cache Cluster Details
    - Layer 4: Parameter Group Queries
    """

    def __init__(self, region: str, profile: str = "default"):
        """Initialize ElastiCache client.

        Args:
            region: AWS region name
            profile: AWS profile name (default: "default")
        """
        self.region = region
        self.profile = profile
        self._param_cache: Dict[str, Dict[str, str]] = {}

        # Initialize boto3 session with profile
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("elasticache")

        logger.info(f"Initialized ElastiCache client for region={region}, profile={profile}")

    @handle_aws_errors
    def _get_global_datastores(self) -> Dict[str, Dict[str, str]]:
        """Layer 1: Discover Global Datastores.

        Returns:
            Dictionary mapping replication_group_id to Global Datastore info:
            {
                "replication_group_id": {
                    "global_datastore_id": "global-ds-name",
                    "role": "Primary" or "Secondary"
                }
            }
        """
        logger.info("Layer 1: Discovering Global Datastores")
        global_ds_map = {}

        try:
            paginator = self.client.get_paginator("describe_global_replication_groups")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for global_ds in page.get("GlobalReplicationGroups", []):
                    global_ds_id = global_ds.get("GlobalReplicationGroupId", "")

                    # Map primary member
                    primary_rg_id = global_ds.get("GlobalNodeGroups", [{}])[0].get(
                        "PrimaryReplicationGroupId", ""
                    )
                    if primary_rg_id:
                        global_ds_map[primary_rg_id] = {
                            "global_datastore_id": global_ds_id,
                            "role": "Primary"
                        }

                    # Map secondary members
                    for member in global_ds.get("Members", []):
                        rg_id = member.get("ReplicationGroupId", "")
                        role = member.get("Role", "")
                        if rg_id and rg_id != primary_rg_id:
                            global_ds_map[rg_id] = {
                                "global_datastore_id": global_ds_id,
                                "role": "Secondary"
                            }

            logger.info(f"Found {len(global_ds_map)} clusters in Global Datastores")
        except Exception as e:
            logger.warning(f"Failed to query Global Datastores: {e}")
            # Return empty dict on failure - graceful degradation

        return global_ds_map

    @handle_aws_errors
    def _get_replication_groups(self, engine_filter: List[str]) -> List[Dict[str, Any]]:
        """Layer 2: Enumerate Replication Groups.

        Args:
            engine_filter: List of engine types to filter (e.g., ["redis", "valkey"])

        Returns:
            List of replication group dictionaries
        """
        logger.info(f"Layer 2: Enumerating Replication Groups (engines={engine_filter})")
        replication_groups = []

        paginator = self.client.get_paginator("describe_replication_groups")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            for rg in page.get("ReplicationGroups", []):
                # Filter by engine
                cache_node_type = rg.get("CacheNodeType", "")

                # Get first cluster to determine engine
                node_groups = rg.get("NodeGroups", [])
                if node_groups:
                    primary_endpoint = node_groups[0].get("PrimaryEndpoint", {})
                    # Engine is not directly in RG, we'll get it from cluster details
                    # For now, include all if redis or valkey in filter
                    if "redis" in engine_filter or "valkey" in engine_filter:
                        replication_groups.append(rg)

        logger.info(f"Found {len(replication_groups)} Replication Groups")
        return replication_groups

    @handle_aws_errors
    def _get_cache_clusters(self, engine_filter: List[str]) -> List[Dict[str, Any]]:
        """Layer 3: Get Cache Cluster Details.

        Args:
            engine_filter: List of engine types to filter (e.g., ["memcached"])

        Returns:
            List of cache cluster dictionaries
        """
        logger.info(f"Layer 3: Getting Cache Cluster Details (engines={engine_filter})")
        cache_clusters = []

        paginator = self.client.get_paginator("describe_cache_clusters")
        page_iterator = paginator.paginate(ShowCacheNodeInfo=True)

        for page in page_iterator:
            for cluster in page.get("CacheClusters", []):
                engine = cluster.get("Engine", "").lower()

                # Filter by engine
                if engine in engine_filter:
                    cache_clusters.append(cluster)

        logger.info(f"Found {len(cache_clusters)} Cache Clusters")
        return cache_clusters

    @handle_aws_errors
    def _get_parameter_group_params(self, parameter_group_name: str) -> Dict[str, Optional[int]]:
        """Layer 4: Query Parameter Group parameters.

        Args:
            parameter_group_name: Parameter group name

        Returns:
            Dictionary with slow log parameters:
            {
                "slowlog-log-slower-than": int or None,
                "slowlog-max-len": int or None
            }
        """
        # Check cache first
        if parameter_group_name in self._param_cache:
            logger.debug(f"Using cached parameters for {parameter_group_name}")
            return self._param_cache[parameter_group_name]

        logger.debug(f"Layer 4: Querying Parameter Group: {parameter_group_name}")
        params = {
            "slowlog-log-slower-than": None,
            "slowlog-max-len": None
        }

        try:
            paginator = self.client.get_paginator("describe_cache_parameters")
            page_iterator = paginator.paginate(CacheParameterGroupName=parameter_group_name)

            for page in page_iterator:
                for param in page.get("Parameters", []):
                    param_name = param.get("ParameterName", "")
                    param_value = param.get("ParameterValue")

                    if param_name == "slowlog-log-slower-than" and param_value:
                        try:
                            params["slowlog-log-slower-than"] = int(param_value)
                        except (ValueError, TypeError):
                            pass

                    elif param_name == "slowlog-max-len" and param_value:
                        try:
                            params["slowlog-max-len"] = int(param_value)
                        except (ValueError, TypeError):
                            pass

            # Cache the result
            self._param_cache[parameter_group_name] = params
            logger.debug(f"Cached parameters for {parameter_group_name}: {params}")

        except Exception as e:
            logger.warning(f"Failed to query Parameter Group {parameter_group_name}: {e}")
            # Return None values on failure

        return params

    def _convert_to_model(
        self,
        rg_or_cluster: Dict[str, Any],
        global_ds_map: Dict[str, Dict[str, str]],
        is_replication_group: bool = True
    ) -> ElastiCacheInfo:
        """Convert AWS API response to ElastiCacheInfo model.

        Args:
            rg_or_cluster: Replication Group or Cache Cluster dictionary
            global_ds_map: Global Datastore mapping
            is_replication_group: True if input is Replication Group, False if Cache Cluster

        Returns:
            ElastiCacheInfo object
        """
        info = ElastiCacheInfo()
        info.region = self.region

        if is_replication_group:
            # Replication Group (Redis/Valkey)
            rg_id = rg_or_cluster.get("ReplicationGroupId", "")

            # Global Datastore info
            global_ds_info = global_ds_map.get(rg_id, {})
            global_ds_id = global_ds_info.get("global_datastore_id")
            info.role = global_ds_info.get("role", "")
            info.name = FieldFormatter.format_cluster_name(global_ds_id, rg_id)

            # Engine type, version, and maintenance window - need to get from member clusters
            member_clusters = rg_or_cluster.get("MemberClusters", [])
            cluster_detail = None
            if member_clusters:
                # Get first member cluster details
                try:
                    cluster_detail = self.client.describe_cache_clusters(
                        CacheClusterId=member_clusters[0]
                    )["CacheClusters"][0]
                    engine = cluster_detail.get("Engine", "redis")
                    info.type = engine.capitalize()
                except Exception:
                    info.type = "Redis"  # Default assumption
            else:
                info.type = "Redis"

            # Node type
            info.node_type = rg_or_cluster.get("CacheNodeType", "")

            # Engine version - get from member cluster if available
            if cluster_detail:
                info.engine_version = cluster_detail.get("EngineVersion", "")
                logger.debug(f"RG {rg_id}: EngineVersion from member cluster = '{info.engine_version}'")
            else:
                info.engine_version = rg_or_cluster.get("EngineVersion", "")
                logger.debug(f"RG {rg_id}: EngineVersion from RG (fallback) = '{info.engine_version}'")

            # Cluster mode
            cluster_enabled = rg_or_cluster.get("ClusterEnabled", False)
            info.cluster_mode = "Enabled" if cluster_enabled else "Disabled"

            # Shards and nodes
            node_groups = rg_or_cluster.get("NodeGroups", [])
            info.shards = len(node_groups)
            info.nodes = sum(
                len(ng.get("NodeGroupMembers", [])) for ng in node_groups
            )

            # Multi-AZ
            multi_az = rg_or_cluster.get("MultiAZ", "")
            info.multi_az = FieldFormatter.format_enabled_disabled(
                multi_az == "enabled" if multi_az else None
            )

            # Auto-failover
            auto_failover = rg_or_cluster.get("AutomaticFailover", "")
            info.auto_failover = FieldFormatter.format_enabled_disabled(
                auto_failover == "enabled" if auto_failover else None
            )

            # Encryption
            transit_encryption = rg_or_cluster.get("TransitEncryptionEnabled")
            info.encryption_transit = FieldFormatter.format_enabled_disabled(transit_encryption)

            at_rest_encryption = rg_or_cluster.get("AtRestEncryptionEnabled")
            info.encryption_rest = FieldFormatter.format_enabled_disabled(at_rest_encryption)

            # Engine logs
            log_delivery_configs = rg_or_cluster.get("LogDeliveryConfigurations", [])
            engine_log_enabled = False
            for log_config in log_delivery_configs:
                if log_config.get("LogType") == "engine-log":
                    dest_details = log_config.get("DestinationDetails", {})
                    if dest_details:
                        engine_log_enabled = True
                        break
            info.engine_logs = "Enabled" if engine_log_enabled else "Disabled"

            # Maintenance window - get from member cluster if available
            if cluster_detail:
                maintenance_window = cluster_detail.get("PreferredMaintenanceWindow", "")
                logger.debug(f"RG {rg_id}: PreferredMaintenanceWindow from member cluster = '{maintenance_window}'")
            else:
                maintenance_window = rg_or_cluster.get("PreferredMaintenanceWindow", "")
                logger.debug(f"RG {rg_id}: PreferredMaintenanceWindow from RG (fallback) = '{maintenance_window}'")
            info.maintenance_window = FieldFormatter.format_maintenance_window(maintenance_window)

            # Auto upgrade
            auto_upgrade = rg_or_cluster.get("AutoMinorVersionUpgrade")
            info.auto_upgrade = FieldFormatter.format_enabled_disabled(auto_upgrade)

            # Backup
            snapshot_window = rg_or_cluster.get("SnapshotWindow")
            snapshot_retention = rg_or_cluster.get("SnapshotRetentionLimit")
            info.backup = FieldFormatter.format_backup(snapshot_window, snapshot_retention)

            # Slow logs - query Parameter Group
            cache_parameter_group = rg_or_cluster.get("CacheParameterGroup", {})
            param_group_name = cache_parameter_group.get("CacheParameterGroupName")
            if param_group_name:
                try:
                    params = self._get_parameter_group_params(param_group_name)
                    info.slow_logs = FieldFormatter.format_slow_logs(
                        params.get("slowlog-log-slower-than"),
                        params.get("slowlog-max-len")
                    )
                except Exception as e:
                    logger.warning(f"Failed to get slow log params: {e}")
                    info.slow_logs = "Disabled"
            else:
                info.slow_logs = "Disabled"

        else:
            # Cache Cluster (Memcached or standalone Redis)
            cluster_id = rg_or_cluster.get("CacheClusterId", "")
            info.name = cluster_id
            info.role = ""

            # Engine type
            engine = rg_or_cluster.get("Engine", "")
            info.type = engine.capitalize()

            # Node type
            info.node_type = rg_or_cluster.get("CacheNodeType", "")

            # Engine version
            info.engine_version = rg_or_cluster.get("EngineVersion", "")

            # Cluster mode (Memcached doesn't have cluster mode)
            info.cluster_mode = "N/A"

            # Nodes
            info.shards = 0
            info.nodes = rg_or_cluster.get("NumCacheNodes", 0)

            # Multi-AZ (Memcached doesn't support Multi-AZ)
            preferred_az = rg_or_cluster.get("PreferredAvailabilityZone")
            info.multi_az = "Disabled" if preferred_az else "N/A"

            # Auto-failover (Memcached doesn't support)
            info.auto_failover = "N/A"

            # Encryption (Memcached doesn't support encryption)
            info.encryption_transit = "N/A"
            info.encryption_rest = "N/A"

            # Logs
            info.engine_logs = "N/A"
            info.slow_logs = "N/A"

            # Maintenance window
            maintenance_window = rg_or_cluster.get("PreferredMaintenanceWindow", "")
            info.maintenance_window = FieldFormatter.format_maintenance_window(maintenance_window)

            # Auto upgrade
            auto_upgrade = rg_or_cluster.get("AutoMinorVersionUpgrade")
            info.auto_upgrade = FieldFormatter.format_enabled_disabled(auto_upgrade)

            # Backup (Memcached doesn't support backup)
            info.backup = "N/A"

        return info

    def get_elasticache_info(
        self,
        engines: List[str],
        cluster_filter: Optional[str] = None
    ) -> List[ElastiCacheInfo]:
        """Main query method to get ElastiCache information.

        Args:
            engines: List of engine types to query (e.g., ["redis", "valkey", "memcached"])
            cluster_filter: Optional wildcard pattern to filter cluster names

        Returns:
            List of ElastiCacheInfo objects
        """
        logger.info(f"Starting ElastiCache query: engines={engines}, filter={cluster_filter}")
        results = []

        # Layer 1: Get Global Datastore mapping
        global_ds_map = self._get_global_datastores()

        # Layer 2 & 3: Query Replication Groups (Redis/Valkey)
        if "redis" in engines or "valkey" in engines:
            rg_engines = [e for e in engines if e in ["redis", "valkey"]]
            replication_groups = self._get_replication_groups(rg_engines)

            for rg in replication_groups:
                rg_id = rg.get("ReplicationGroupId", "")

                # Apply cluster filter
                if cluster_filter:
                    from elasticache_info.utils import match_wildcard
                    if not match_wildcard(cluster_filter, rg_id):
                        continue

                info = self._convert_to_model(rg, global_ds_map, is_replication_group=True)
                results.append(info)

        # Layer 3: Query Cache Clusters (Memcached)
        if "memcached" in engines:
            cache_clusters = self._get_cache_clusters(["memcached"])

            for cluster in cache_clusters:
                cluster_id = cluster.get("CacheClusterId", "")

                # Apply cluster filter
                if cluster_filter:
                    from elasticache_info.utils import match_wildcard
                    if not match_wildcard(cluster_filter, cluster_id):
                        continue

                info = self._convert_to_model(cluster, global_ds_map, is_replication_group=False)
                results.append(info)

        logger.info(f"Query completed: {len(results)} clusters found")
        return results
