"""Unit tests for output formatters."""

import pytest

from elasticache_info.aws.models import ElastiCacheInfo
from elasticache_info.formatters.csv_formatter import CSVFormatter
from elasticache_info.formatters.markdown_formatter import MarkdownFormatter


@pytest.fixture
def sample_data():
    """Create sample ElastiCacheInfo data for testing."""
    return [
        ElastiCacheInfo(
            region="us-east-1",
            type="Redis",
            name="cluster-001",
            role="Primary",
            node_type="cache.r6g.large",
            engine_version="7.0",
            cluster_mode="Enabled",
            shards=3,
            nodes=6,
            multi_az="Enabled",
            auto_failover="Enabled",
            encryption_transit="Enabled",
            encryption_rest="Enabled",
            slow_logs="Enabled/10000/128",
            engine_logs="Enabled",
            maintenance_window="sun:05:00-sun:06:00",
            auto_upgrade="Enabled",
            backup="00:00-01:00/35 days",
        ),
        ElastiCacheInfo(
            region="us-east-1",
            type="Memcached",
            name="memcached-001",
            role="",
            node_type="cache.t3.medium",
            engine_version="1.6.17",
            cluster_mode="N/A",
            shards=0,
            nodes=3,
            multi_az="N/A",
            auto_failover="N/A",
            encryption_transit="N/A",
            encryption_rest="N/A",
            slow_logs="N/A",
            engine_logs="N/A",
            maintenance_window="mon:03:00-mon:04:00",
            auto_upgrade="Enabled",
            backup="N/A",
        ),
    ]


class TestCSVFormatter:
    """Tests for CSVFormatter."""

    def test_format_all_fields(self, sample_data):
        """Test CSV formatting with all fields."""
        formatter = CSVFormatter()
        fields = [
            "region", "type", "name", "role", "node_type", "engine_version",
            "cluster_mode", "shards", "nodes"
        ]

        result = formatter.format(sample_data, fields)

        # Check header
        assert "Region,Type,Name,Role,Node Type,Engine Version,Cluster Mode,Shards,Nodes" in result

        # Check data rows
        assert "us-east-1,Redis,cluster-001,Primary,cache.r6g.large,7.0,Enabled,3,6" in result
        assert "us-east-1,Memcached,memcached-001,,cache.t3.medium,1.6.17,N/A,0,3" in result

    def test_format_selected_fields(self, sample_data):
        """Test CSV formatting with selected fields only."""
        formatter = CSVFormatter()
        fields = ["region", "type", "name"]

        result = formatter.format(sample_data, fields)

        # Check header
        assert "Region,Type,Name" in result

        # Check data rows
        assert "us-east-1,Redis,cluster-001" in result
        assert "us-east-1,Memcached,memcached-001" in result

        # Should not contain other fields
        assert "cache.r6g.large" not in result

    def test_format_empty_data(self):
        """Test CSV formatting with empty data."""
        formatter = CSVFormatter()
        fields = ["region", "type", "name"]

        result = formatter.format([], fields)

        assert result == ""

    def test_format_field_name_conversion(self):
        """Test field name conversion (underscore to title case)."""
        formatter = CSVFormatter()

        assert formatter._format_field_name("region") == "Region"
        assert formatter._format_field_name("node_type") == "Node Type"
        assert formatter._format_field_name("engine_version") == "Engine Version"
        assert formatter._format_field_name("multi_az") == "Multi Az"


class TestMarkdownFormatter:
    """Tests for MarkdownFormatter."""

    def test_format_all_fields(self, sample_data):
        """Test Markdown formatting with all fields."""
        formatter = MarkdownFormatter()
        fields = [
            "region", "type", "name", "shards", "nodes"
        ]

        result = formatter.format(sample_data, fields)

        # Check header row
        assert "| Region | Type | Name | Shards | Nodes |" in result

        # Check separator row with alignment
        assert "| --- | --- | --- | ---: | ---: |" in result

        # Check data rows
        assert "| us-east-1 | Redis | cluster-001 | 3 | 6 |" in result
        assert "| us-east-1 | Memcached | memcached-001 | 0 | 3 |" in result

    def test_format_selected_fields(self, sample_data):
        """Test Markdown formatting with selected fields only."""
        formatter = MarkdownFormatter()
        fields = ["region", "type", "name"]

        result = formatter.format(sample_data, fields)

        # Check header row
        assert "| Region | Type | Name |" in result

        # Check separator row
        assert "| --- | --- | --- |" in result

        # Check data rows
        assert "| us-east-1 | Redis | cluster-001 |" in result
        assert "| us-east-1 | Memcached | memcached-001 |" in result

    def test_format_numeric_alignment(self, sample_data):
        """Test that numeric fields are right-aligned."""
        formatter = MarkdownFormatter()
        fields = ["name", "shards", "nodes"]

        result = formatter.format(sample_data, fields)

        # Check separator row - numeric fields should have ---:
        lines = result.split("\n")
        separator_line = lines[1]

        assert "| --- | ---: | ---: |" in separator_line

    def test_format_empty_data(self):
        """Test Markdown formatting with empty data."""
        formatter = MarkdownFormatter()
        fields = ["region", "type", "name"]

        result = formatter.format([], fields)

        assert result == ""

    def test_format_field_name_conversion(self):
        """Test field name conversion (underscore to title case)."""
        formatter = MarkdownFormatter()

        assert formatter._format_field_name("region") == "Region"
        assert formatter._format_field_name("node_type") == "Node Type"
        assert formatter._format_field_name("engine_version") == "Engine Version"
        assert formatter._format_field_name("multi_az") == "Multi Az"

    def test_numeric_fields_constant(self):
        """Test that NUMERIC_FIELDS constant is correctly defined."""
        formatter = MarkdownFormatter()

        assert "shards" in formatter.NUMERIC_FIELDS
        assert "nodes" in formatter.NUMERIC_FIELDS
        assert "region" not in formatter.NUMERIC_FIELDS
        assert "type" not in formatter.NUMERIC_FIELDS


class TestFormatterComparison:
    """Tests comparing CSV and Markdown formatters."""

    def test_both_formatters_handle_same_data(self, sample_data):
        """Test that both formatters can handle the same data."""
        csv_formatter = CSVFormatter()
        md_formatter = MarkdownFormatter()
        fields = ["region", "type", "name"]

        csv_result = csv_formatter.format(sample_data, fields)
        md_result = md_formatter.format(sample_data, fields)

        # Both should produce non-empty output
        assert len(csv_result) > 0
        assert len(md_result) > 0

        # Both should contain the same data values
        assert "us-east-1" in csv_result
        assert "us-east-1" in md_result
        assert "Redis" in csv_result
        assert "Redis" in md_result
        assert "cluster-001" in csv_result
        assert "cluster-001" in md_result
