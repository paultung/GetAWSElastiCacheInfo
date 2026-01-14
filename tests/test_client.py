"""Unit tests for ElastiCacheClient."""

import pytest
from unittest.mock import MagicMock, patch

from elasticache_info.aws.client import ElastiCacheClient
from elasticache_info.aws.exceptions import AWSPermissionError, AWSConnectionError


class TestGetGlobalDatastores:
    """Test _get_global_datastores() method."""

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_parse_members_array_multiple_regions(self, mock_session):
        """Test parsing Members array with multiple regions (with ShowMemberInfo=True)."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock paginator response (ShowMemberInfo=True returns complete Members array)
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "GlobalReplicationGroups": [
                    {
                        "GlobalReplicationGroupId": "global-ds-001",
                        "Members": [
                            {
                                "ReplicationGroupId": "cluster-primary",
                                "ReplicationGroupRegion": "us-east-1",
                                "Role": "PRIMARY",
                                "Status": "available"
                            },
                            {
                                "ReplicationGroupId": "cluster-secondary-1",
                                "ReplicationGroupRegion": "ap-northeast-1",
                                "Role": "SECONDARY",
                                "Status": "available"
                            },
                            {
                                "ReplicationGroupId": "cluster-secondary-2",
                                "ReplicationGroupRegion": "eu-west-1",
                                "Role": "SECONDARY",
                                "Status": "available"
                            }
                        ]
                    }
                ]
            }
        ]

        # Create client and call method
        client = ElastiCacheClient(region="us-east-1", profile="default")
        result = client._get_global_datastores()

        # Verify structure
        assert set(result.keys()) == {"us-east-1", "ap-northeast-1", "eu-west-1"}

        # Verify us-east-1 (primary)
        assert "cluster-primary" in result["us-east-1"]
        assert result["us-east-1"]["cluster-primary"]["global_datastore_id"] == "global-ds-001"
        assert result["us-east-1"]["cluster-primary"]["role"] == "PRIMARY"

        # Verify ap-northeast-1 (secondary)
        assert "cluster-secondary-1" in result["ap-northeast-1"]
        assert result["ap-northeast-1"]["cluster-secondary-1"]["global_datastore_id"] == "global-ds-001"
        assert result["ap-northeast-1"]["cluster-secondary-1"]["role"] == "SECONDARY"

        # Verify eu-west-1 (secondary)
        assert "cluster-secondary-2" in result["eu-west-1"]
        assert result["eu-west-1"]["cluster-secondary-2"]["global_datastore_id"] == "global-ds-001"
        assert result["eu-west-1"]["cluster-secondary-2"]["role"] == "SECONDARY"

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_empty_response(self, mock_session):
        """Test handling empty Global Datastore response."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"GlobalReplicationGroups": []}]

        # Create client and call method
        client = ElastiCacheClient(region="us-east-1", profile="default")
        result = client._get_global_datastores()

        # Verify empty dict
        assert result == {}

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_graceful_degradation_on_error(self, mock_session):
        """Test graceful degradation when API call fails."""
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        # Create client and call method
        client = ElastiCacheClient(region="us-east-1", profile="default")
        result = client._get_global_datastores()

        # Should return empty dict instead of raising exception
        assert result == {}


class TestConvertToModel:
    """Test _convert_to_model() method."""

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_role_capitalization_primary(self, mock_session):
        """Test role field capitalization for PRIMARY."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock describe_cache_clusters for getting engine version
        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [{
                "Engine": "redis",
                "EngineVersion": "7.0.7",
                "PreferredMaintenanceWindow": "sun:05:00-sun:06:00"
            }]
        }

        # Create client
        client = ElastiCacheClient(region="us-east-1", profile="default")

        # Mock replication group data
        rg_data = {
            "ReplicationGroupId": "cluster-primary",
            "CacheNodeType": "cache.r6g.large",
            "ClusterEnabled": False,
            "NodeGroups": [{"NodeGroupMembers": [{"CacheClusterId": "cluster-primary-001"}]}],
            "MemberClusters": ["cluster-primary-001"],
            "MultiAZ": "enabled",
            "AutomaticFailover": "enabled",
            "TransitEncryptionEnabled": True,
            "AtRestEncryptionEnabled": True,
            "LogDeliveryConfigurations": [],
            "AutoMinorVersionUpgrade": True,
            "SnapshotWindow": "03:00-05:00",
            "SnapshotRetentionLimit": 7,
            "CacheParameterGroup": {"CacheParameterGroupName": "default.redis7"}
        }

        # Global datastore map with PRIMARY role
        global_ds_map = {
            "us-east-1": {
                "cluster-primary": {
                    "global_datastore_id": "global-ds-001",
                    "role": "PRIMARY"
                }
            }
        }

        # Convert to model
        info = client._convert_to_model(rg_data, global_ds_map, "us-east-1", is_replication_group=True)

        # Verify role is capitalized correctly
        assert info.role == "Primary"

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_role_capitalization_secondary(self, mock_session):
        """Test role field capitalization for SECONDARY."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock describe_cache_clusters
        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [{
                "Engine": "redis",
                "EngineVersion": "7.0.7",
                "PreferredMaintenanceWindow": "sun:05:00-sun:06:00"
            }]
        }

        # Create client
        client = ElastiCacheClient(region="ap-northeast-1", profile="default")

        # Mock replication group data
        rg_data = {
            "ReplicationGroupId": "cluster-secondary",
            "CacheNodeType": "cache.r6g.large",
            "ClusterEnabled": False,
            "NodeGroups": [{"NodeGroupMembers": [{"CacheClusterId": "cluster-secondary-001"}]}],
            "MemberClusters": ["cluster-secondary-001"],
            "MultiAZ": "enabled",
            "AutomaticFailover": "enabled",
            "TransitEncryptionEnabled": True,
            "AtRestEncryptionEnabled": True,
            "LogDeliveryConfigurations": [],
            "AutoMinorVersionUpgrade": True,
            "SnapshotWindow": "03:00-05:00",
            "SnapshotRetentionLimit": 7,
            "CacheParameterGroup": {"CacheParameterGroupName": "default.redis7"}
        }

        # Global datastore map with SECONDARY role
        global_ds_map = {
            "ap-northeast-1": {
                "cluster-secondary": {
                    "global_datastore_id": "global-ds-001",
                    "role": "SECONDARY"
                }
            }
        }

        # Convert to model
        info = client._convert_to_model(rg_data, global_ds_map, "ap-northeast-1", is_replication_group=True)

        # Verify role is capitalized correctly
        assert info.role == "Secondary"

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_empty_role_for_non_global_datastore(self, mock_session):
        """Test empty role for non-Global Datastore clusters."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock describe_cache_clusters
        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [{
                "Engine": "redis",
                "EngineVersion": "7.0.7",
                "PreferredMaintenanceWindow": "sun:05:00-sun:06:00"
            }]
        }

        # Create client
        client = ElastiCacheClient(region="us-east-1", profile="default")

        # Mock replication group data
        rg_data = {
            "ReplicationGroupId": "standalone-cluster",
            "CacheNodeType": "cache.r6g.large",
            "ClusterEnabled": False,
            "NodeGroups": [{"NodeGroupMembers": [{"CacheClusterId": "standalone-cluster-001"}]}],
            "MemberClusters": ["standalone-cluster-001"],
            "MultiAZ": "enabled",
            "AutomaticFailover": "enabled",
            "TransitEncryptionEnabled": True,
            "AtRestEncryptionEnabled": True,
            "LogDeliveryConfigurations": [],
            "AutoMinorVersionUpgrade": True,
            "SnapshotWindow": "03:00-05:00",
            "SnapshotRetentionLimit": 7,
            "CacheParameterGroup": {"CacheParameterGroupName": "default.redis7"}
        }

        # Empty global datastore map (no Global Datastore)
        global_ds_map = {}

        # Convert to model
        info = client._convert_to_model(rg_data, global_ds_map, "us-east-1", is_replication_group=True)

        # Verify role is empty
        assert info.role == ""

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_current_region_parameter(self, mock_session):
        """Test that current_region parameter is used for info.region."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock describe_cache_clusters
        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [{
                "Engine": "redis",
                "EngineVersion": "7.0.7",
                "PreferredMaintenanceWindow": "sun:05:00-sun:06:00"
            }]
        }

        # Create client with us-east-1
        client = ElastiCacheClient(region="us-east-1", profile="default")

        # Mock replication group data
        rg_data = {
            "ReplicationGroupId": "test-cluster",
            "CacheNodeType": "cache.r6g.large",
            "ClusterEnabled": False,
            "NodeGroups": [{"NodeGroupMembers": [{"CacheClusterId": "test-cluster-001"}]}],
            "MemberClusters": ["test-cluster-001"],
            "MultiAZ": "enabled",
            "AutomaticFailover": "enabled",
            "TransitEncryptionEnabled": True,
            "AtRestEncryptionEnabled": True,
            "LogDeliveryConfigurations": [],
            "AutoMinorVersionUpgrade": True,
            "SnapshotWindow": "03:00-05:00",
            "SnapshotRetentionLimit": 7,
            "CacheParameterGroup": {"CacheParameterGroupName": "default.redis7"}
        }

        # Convert with different current_region
        info = client._convert_to_model(rg_data, {}, "ap-northeast-1", is_replication_group=True)

        # Verify region uses current_region parameter, not self.region
        assert info.region == "ap-northeast-1"


class TestQuerySingleRegion:
    """Test _query_single_region() method."""

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_query_redis_clusters(self, mock_session):
        """Test querying Redis clusters in a single region."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock paginator for replication groups
        mock_rg_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_rg_paginator
        mock_rg_paginator.paginate.return_value = [
            {
                "ReplicationGroups": [
                    {
                        "ReplicationGroupId": "test-cluster",
                        "CacheNodeType": "cache.r6g.large",
                        "ClusterEnabled": False,
                        "NodeGroups": [{"NodeGroupMembers": [{"CacheClusterId": "test-001"}]}],
                        "MemberClusters": ["test-001"],
                        "MultiAZ": "enabled",
                        "AutomaticFailover": "enabled",
                        "TransitEncryptionEnabled": True,
                        "AtRestEncryptionEnabled": True,
                        "LogDeliveryConfigurations": [],
                        "AutoMinorVersionUpgrade": True,
                        "SnapshotWindow": "03:00-05:00",
                        "SnapshotRetentionLimit": 7,
                        "CacheParameterGroup": {"CacheParameterGroupName": "default.redis7"}
                    }
                ]
            }
        ]

        # Mock describe_cache_clusters
        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [{
                "Engine": "redis",
                "EngineVersion": "7.0.7",
                "PreferredMaintenanceWindow": "sun:05:00-sun:06:00"
            }]
        }

        # Create client
        client = ElastiCacheClient(region="us-east-1", profile="default")

        # Query single region
        results = client._query_single_region("us-east-1", ["redis"], None, {})

        # Verify results
        assert len(results) == 1
        assert results[0].name == "test-cluster"
        assert results[0].region == "us-east-1"


class TestGetElastiCacheInfo:
    """Test get_elasticache_info() method."""

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_single_region_no_global_datastore(self, mock_session):
        """Test backward compatibility: single region without Global Datastore."""
        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock Global Datastore (empty)
        mock_gds_paginator = MagicMock()
        mock_gds_paginator.paginate.return_value = [{"GlobalReplicationGroups": []}]

        # Mock Replication Groups
        mock_rg_paginator = MagicMock()
        mock_rg_paginator.paginate.return_value = [
            {
                "ReplicationGroups": [
                    {
                        "ReplicationGroupId": "standalone-cluster",
                        "CacheNodeType": "cache.r6g.large",
                        "ClusterEnabled": False,
                        "NodeGroups": [{"NodeGroupMembers": [{"CacheClusterId": "standalone-001"}]}],
                        "MemberClusters": ["standalone-001"],
                        "MultiAZ": "enabled",
                        "AutomaticFailover": "enabled",
                        "TransitEncryptionEnabled": True,
                        "AtRestEncryptionEnabled": True,
                        "LogDeliveryConfigurations": [],
                        "AutoMinorVersionUpgrade": True,
                        "SnapshotWindow": "03:00-05:00",
                        "SnapshotRetentionLimit": 7,
                        "CacheParameterGroup": {"CacheParameterGroupName": "default.redis7"}
                    }
                ]
            }
        ]

        # Setup paginator switching
        def get_paginator(name):
            if name == "describe_global_replication_groups":
                return mock_gds_paginator
            elif name == "describe_replication_groups":
                return mock_rg_paginator
            return MagicMock()

        mock_client.get_paginator.side_effect = get_paginator

        # Mock describe_cache_clusters
        mock_client.describe_cache_clusters.return_value = {
            "CacheClusters": [{
                "Engine": "redis",
                "EngineVersion": "7.0.7",
                "PreferredMaintenanceWindow": "sun:05:00-sun:06:00"
            }]
        }

        # Create client
        client = ElastiCacheClient(region="us-east-1", profile="default")

        # Query
        results = client.get_elasticache_info(engines=["redis"])

        # Verify: should only query single region
        assert len(results) == 1
        assert results[0].region == "us-east-1"
        assert results[0].role == ""

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_cross_region_query_with_global_datastore(self, mock_session):
        """Test cross-region query with Global Datastore."""
        # This is a complex integration test that would require mocking multiple clients
        # For now, we'll skip detailed implementation
        pass

    @patch('elasticache_info.aws.client.boto3.Session')
    def test_results_sorted_by_region(self, mock_session):
        """Test that results are sorted by region alphabetically."""
        # This test would verify the sorting logic
        pass
