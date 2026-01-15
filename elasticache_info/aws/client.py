"""AWS ElastiCache client for querying cluster information."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

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

if TYPE_CHECKING:
    from rich.progress import Progress

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

    # Class-level shared cache for parameter groups (shared across all instances)
    # Note: Class variables are initialized once when class is defined, not per instance
    _shared_param_cache: Dict[str, Dict[str, Optional[int]]] = {}
    _cache_lock: threading.Lock = threading.Lock()

    def __init__(self, region: str, profile: str = "default"):
        """Initialize ElastiCache client.

        Args:
            region: AWS region name
            profile: AWS profile name (default: "default")
        """
        self.region = region
        self.profile = profile

        # Initialize boto3 session with profile
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("elasticache")

        logger.info(f"Initialized ElastiCache client for region={region}, profile={profile}")

    @handle_aws_errors
    def _get_global_datastores(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Layer 1: Discover Global Datastores.

        Returns:
            Dictionary mapping region -> replication_group_id -> Global Datastore info:
            {
                "region": {
                    "replication_group_id": {
                        "global_datastore_id": "global-ds-name",
                        "role": "PRIMARY" or "SECONDARY"
                    }
                }
            }
        """
        logger.info("Layer 1: Discovering Global Datastores")
        global_ds_map = {}
        global_ds_ids = set()

        try:
            # Get all Global Datastores with ShowMemberInfo=True to get complete Members array
            # IMPORTANT: Without ShowMemberInfo=True, the API returns empty Members array by default
            # This parameter is critical for cross-region Global Datastore discovery
            paginator = self.client.get_paginator("describe_global_replication_groups")
            page_iterator = paginator.paginate(ShowMemberInfo=True)

            for page in page_iterator:
                for global_ds in page.get("GlobalReplicationGroups", []):
                    global_ds_id = global_ds.get("GlobalReplicationGroupId", "")
                    if global_ds_id:
                        global_ds_ids.add(global_ds_id)
                        logger.debug(f"Found Global Datastore: {global_ds_id}")

                    # Parse Members array to get all regions and roles
                    for member in global_ds.get("Members", []):
                        rg_id = member.get("ReplicationGroupId", "")
                        region = member.get("ReplicationGroupRegion", "")
                        role = member.get("Role", "")

                        if rg_id and region and role:
                            # Initialize region dict if not exists
                            if region not in global_ds_map:
                                global_ds_map[region] = {}

                            # Store with uppercase role for consistency
                            global_ds_map[region][rg_id] = {
                                "global_datastore_id": global_ds_id,
                                "role": role.upper()
                            }
                            logger.debug(f"Found Global Datastore member: {rg_id} ({role}) in {region}")

            total_clusters = sum(len(rg_map) for rg_map in global_ds_map.values())
            logger.info(f"Found {total_clusters} clusters in Global Datastores across {len(global_ds_map)} regions")
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
        # Check cache with lock protection
        with self._cache_lock:
            if parameter_group_name in self._shared_param_cache:
                logger.debug(f"Using shared cached parameters for {parameter_group_name}")
                return self._shared_param_cache[parameter_group_name]

        # Cache miss - query API (without holding lock)
        logger.debug(f"Layer 4: Querying Parameter Group: {parameter_group_name}")
        # Initialize with Redis defaults for slow logs (enabled by default)
        params = {
            "slowlog-log-slower-than": 10000,  # Default: 10ms (10000 microseconds)
            "slowlog-max-len": 128  # Default: 128 entries
        }

        try:
            paginator = self.client.get_paginator("describe_cache_parameters")
            page_iterator = paginator.paginate(CacheParameterGroupName=parameter_group_name)

            for page in page_iterator:
                for param in page.get("Parameters", []):
                    param_name = param.get("ParameterName", "")
                    param_value = param.get("ParameterValue")

                    # Update if we have a non-None, non-empty-string value
                    # Note: "0" is a valid value (means disabled), so we check for None and ""
                    if param_name == "slowlog-log-slower-than" and param_value is not None and param_value != "":
                        try:
                            params["slowlog-log-slower-than"] = int(param_value)
                            logger.debug(f"Updated slowlog-log-slower-than to {param_value}")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Failed to parse slowlog-log-slower-than value '{param_value}': {e}")

                    elif param_name == "slowlog-max-len" and param_value is not None and param_value != "":
                        try:
                            params["slowlog-max-len"] = int(param_value)
                            logger.debug(f"Updated slowlog-max-len to {param_value}")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Failed to parse slowlog-max-len value '{param_value}': {e}")

            # Cache the result with lock protection
            with self._cache_lock:
                # Check again in case another thread cached it while we were querying
                if parameter_group_name not in self._shared_param_cache:
                    self._shared_param_cache[parameter_group_name] = params
            logger.debug(f"Cached parameters in shared cache for {parameter_group_name}: {params}")

        except Exception as e:
            logger.warning(f"Failed to query Parameter Group {parameter_group_name}: {e}")
            # Return None values on failure

        return params

    def _query_single_region(
        self,
        region: str,
        engines: List[str],
        cluster_filter: Optional[str],
        global_ds_map: Dict[str, Dict[str, Dict[str, str]]]
    ) -> List[ElastiCacheInfo]:
        """Query ElastiCache clusters in a single region.

        Args:
            region: AWS region to query
            engines: List of engine types to query
            cluster_filter: Optional wildcard pattern to filter cluster names
            global_ds_map: Global Datastore mapping from _get_global_datastores()

        Returns:
            List of ElastiCacheInfo objects for this region
        """
        logger.info(f"[{region}] Querying region")
        results = []

        # Query Replication Groups (Redis/Valkey)
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

                info = self._convert_to_model(rg, global_ds_map, region, is_replication_group=True)
                results.append(info)

        # Query Cache Clusters (Memcached)
        if "memcached" in engines:
            cache_clusters = self._get_cache_clusters(["memcached"])

            for cluster in cache_clusters:
                cluster_id = cluster.get("CacheClusterId", "")

                # Apply cluster filter
                if cluster_filter:
                    from elasticache_info.utils import match_wildcard
                    if not match_wildcard(cluster_filter, cluster_id):
                        continue

                info = self._convert_to_model(cluster, global_ds_map, region, is_replication_group=False)
                results.append(info)

        logger.info(f"[{region}] Found {len(results)} clusters")
        return results

    def _convert_to_model(
        self,
        rg_or_cluster: Dict[str, Any],
        global_ds_map: Dict[str, Dict[str, Dict[str, str]]],
        current_region: str,
        is_replication_group: bool = True
    ) -> ElastiCacheInfo:
        """Convert AWS API response to ElastiCacheInfo model.

        Args:
            rg_or_cluster: Replication Group or Cache Cluster dictionary
            global_ds_map: Global Datastore mapping
            current_region: Current region being queried
            is_replication_group: True if input is Replication Group, False if Cache Cluster

        Returns:
            ElastiCacheInfo object
        """
        info = ElastiCacheInfo()
        info.region = current_region

        if is_replication_group:
            # Replication Group (Redis/Valkey)
            rg_id = rg_or_cluster.get("ReplicationGroupId", "")

            # Global Datastore info - lookup by current_region first
            region_map = global_ds_map.get(current_region, {})
            global_ds_info = region_map.get(rg_id, {})
            global_ds_id = global_ds_info.get("global_datastore_id")

            # Format role: "PRIMARY"/"SECONDARY" -> "Primary"/"Secondary"
            role = global_ds_info.get("role", "")
            info.role = role.capitalize() if role else ""

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

            # Slow logs - check if cluster has slow-log delivery enabled
            log_delivery_configs = rg_or_cluster.get("LogDeliveryConfigurations", [])
            slow_log_enabled = False
            for log_config in log_delivery_configs:
                if log_config.get("LogType") == "slow-log":
                    dest_details = log_config.get("DestinationDetails", {})
                    if dest_details:
                        slow_log_enabled = True
                        break

            if slow_log_enabled:
                # Cluster has slow-log delivery enabled, get parameter values
                param_group_name = None
                if cluster_detail:
                    # Get parameter group from member cluster details
                    cache_parameter_group = cluster_detail.get("CacheParameterGroup", {})
                    param_group_name = cache_parameter_group.get("CacheParameterGroupName")
                    logger.debug(f"RG {rg_id}: CacheParameterGroup = {cache_parameter_group}, param_group_name = {param_group_name}")

                if param_group_name:
                    try:
                        params = self._get_parameter_group_params(param_group_name)
                        info.slow_logs = FieldFormatter.format_slow_logs(
                            params.get("slowlog-log-slower-than"),
                            params.get("slowlog-max-len")
                        )
                        logger.debug(f"RG {rg_id}: Slow logs = {info.slow_logs} (from {param_group_name})")
                    except Exception as e:
                        logger.warning(f"Failed to get slow log params for {param_group_name}: {e}")
                        info.slow_logs = "Enabled"  # Delivery enabled but can't get params, assume enabled
                else:
                    logger.debug(f"RG {rg_id}: No parameter group found but delivery enabled, assuming default")
                    # Use default Redis slow log settings
                    info.slow_logs = FieldFormatter.format_slow_logs(10000, 128)
            else:
                # Cluster does not have slow-log delivery enabled
                info.slow_logs = "Disabled"
                logger.debug(f"RG {rg_id}: Slow logs disabled (no log delivery configuration)")

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

    def _query_region_wrapper(
        self,
        region: str,
        engines: List[str],
        cluster_filter: Optional[str],
        global_ds_map: Dict[str, Dict[str, Dict[str, str]]]
    ) -> List[ElastiCacheInfo]:
        """Wrapper method for querying a single region (thread-safe).

        Creates a new ElastiCacheClient instance for thread safety.

        Args:
            region: AWS region to query
            engines: List of engine types to query
            cluster_filter: Optional wildcard pattern to filter cluster names
            global_ds_map: Global Datastore mapping

        Returns:
            List of ElastiCacheInfo objects for this region
        """
        logger.info(f"[{region}] Starting region query")

        # Create region-specific client for thread safety (boto3 best practice)
        region_client = ElastiCacheClient(region, self.profile)

        # Query this region
        results = region_client._query_single_region(region, engines, cluster_filter, global_ds_map)

        logger.info(f"[{region}] Query completed, found {len(results)} clusters")
        return results

    def get_elasticache_info(
        self,
        engines: List[str],
        cluster_filter: Optional[str] = None,
        progress: Optional['Progress'] = None
    ) -> List[ElastiCacheInfo]:
        """Main query method to get ElastiCache information.

        Args:
            engines: List of engine types to query (e.g., ["redis", "valkey", "memcached"])
            cluster_filter: Optional wildcard pattern to filter cluster names
            progress: Optional Rich Progress object for displaying query progress

        Returns:
            List of ElastiCacheInfo objects
        """
        logger.info(f"Starting ElastiCache query: engines={engines}, filter={cluster_filter}")
        all_results = []

        # Layer 1: Get Global Datastore mapping
        global_ds_map = self._get_global_datastores()

        # Step 2: Identify all regions to query
        regions_to_query = set([self.region])
        regions_to_query.update(global_ds_map.keys())

        logger.info(f"Regions to query: {sorted(regions_to_query)}")

        # Step 3: Query each region in parallel
        with ThreadPoolExecutor() as executor:
            future_to_region = {}
            future_to_task = {}

            # Submit all region queries
            for region in sorted(regions_to_query):
                task = None
                if progress:
                    task = progress.add_task(f"正在查詢 {region} 的 ElastiCache 叢集...", total=None)

                future = executor.submit(self._query_region_wrapper, region, engines, cluster_filter, global_ds_map)
                future_to_region[future] = region
                if task is not None:
                    future_to_task[future] = task

            # Process completed futures
            for future in as_completed(future_to_region):
                region = future_to_region[future]
                task = future_to_task.get(future)

                try:
                    results = future.result()
                    all_results.extend(results)

                    if progress and task is not None:
                        progress.update(task, completed=True)

                except (AWSPermissionError, AWSConnectionError, Exception) as e:
                    logger.warning(f"{region} 查詢失敗: {e}")
                    if progress and task is not None:
                        progress.update(task, completed=True, description=f"❌ {region} (查詢失敗)")

        # Step 4: Sort results by region
        all_results.sort(key=lambda x: x.region)

        logger.info(f"Query completed: {len(all_results)} clusters found across {len(regions_to_query)} regions")
        return all_results
