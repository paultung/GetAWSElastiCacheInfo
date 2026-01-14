"""Unit tests for FieldFormatter."""

import pytest

from elasticache_info.field_formatter import FieldFormatter


class TestFormatSlowLogs:
    """Tests for format_slow_logs method."""

    def test_enabled_with_values(self):
        """Test slow logs enabled with valid values."""
        result = FieldFormatter.format_slow_logs(10000, 128)
        assert result == "Enabled/10000/128"

    def test_disabled_with_zero_slower_than(self):
        """Test slow logs disabled (slower_than = 0)."""
        result = FieldFormatter.format_slow_logs(0, 128)
        assert result == "Disabled"

    def test_none_slower_than(self):
        """Test with None slower_than parameter."""
        result = FieldFormatter.format_slow_logs(None, 128)
        assert result == "Disabled"

    def test_none_max_len(self):
        """Test with None max_len parameter."""
        result = FieldFormatter.format_slow_logs(10000, None)
        assert result == "Disabled"

    def test_both_none(self):
        """Test with both parameters None."""
        result = FieldFormatter.format_slow_logs(None, None)
        assert result == "Disabled"

    @pytest.mark.parametrize("slower_than,max_len,expected", [
        (10000, 128, "Enabled/10000/128"),
        (5000, 256, "Enabled/5000/256"),
        (1, 1, "Enabled/1/1"),
        (0, 128, "Disabled"),
        (-1, 128, "Disabled"),
    ])
    def test_various_values(self, slower_than, max_len, expected):
        """Test various combinations of values."""
        result = FieldFormatter.format_slow_logs(slower_than, max_len)
        assert result == expected


class TestFormatBackup:
    """Tests for format_backup method."""

    def test_enabled_with_window(self):
        """Test backup enabled with window."""
        result = FieldFormatter.format_backup("00:00-01:00", 35)
        assert result == "00:00-01:00 UTC/35 days"

    def test_enabled_without_window(self):
        """Test backup enabled without window information."""
        result = FieldFormatter.format_backup(None, 35)
        assert result == "Enabled/35 days（無窗口資訊）"

    def test_disabled_zero_retention(self):
        """Test backup disabled (retention = 0)."""
        result = FieldFormatter.format_backup("00:00-01:00", 0)
        assert result == "Disabled"

    def test_none_retention(self):
        """Test with None retention."""
        result = FieldFormatter.format_backup("00:00-01:00", None)
        assert result == "N/A"

    def test_both_none(self):
        """Test with both parameters None."""
        result = FieldFormatter.format_backup(None, None)
        assert result == "N/A"

    @pytest.mark.parametrize("window,retention,expected", [
        ("00:00-01:00", 35, "00:00-01:00 UTC/35 days"),
        ("02:00-03:00", 7, "02:00-03:00 UTC/7 days"),
        (None, 30, "Enabled/30 days（無窗口資訊）"),
        ("00:00-01:00", 0, "Disabled"),
        (None, 0, "Disabled"),
    ])
    def test_various_values(self, window, retention, expected):
        """Test various combinations of values."""
        result = FieldFormatter.format_backup(window, retention)
        assert result == expected


class TestFormatClusterName:
    """Tests for format_cluster_name method."""

    def test_with_global_datastore(self):
        """Test cluster name with Global Datastore."""
        result = FieldFormatter.format_cluster_name("global-ds-001", "cluster-001")
        assert result == "global-ds-001/cluster-001"

    def test_without_global_datastore(self):
        """Test cluster name without Global Datastore."""
        result = FieldFormatter.format_cluster_name(None, "cluster-001")
        assert result == "cluster-001"

    def test_empty_global_datastore(self):
        """Test with empty string global_ds_id."""
        result = FieldFormatter.format_cluster_name("", "cluster-001")
        assert result == "cluster-001"

    @pytest.mark.parametrize("global_ds_id,cluster_id,expected", [
        ("global-ds-001", "cluster-001", "global-ds-001/cluster-001"),
        ("my-global-ds", "my-cluster", "my-global-ds/my-cluster"),
        (None, "standalone-cluster", "standalone-cluster"),
        ("", "standalone-cluster", "standalone-cluster"),
    ])
    def test_various_values(self, global_ds_id, cluster_id, expected):
        """Test various combinations of values."""
        result = FieldFormatter.format_cluster_name(global_ds_id, cluster_id)
        assert result == expected


class TestFormatMaintenanceWindow:
    """Tests for format_maintenance_window method."""

    def test_with_window(self):
        """Test with maintenance window."""
        result = FieldFormatter.format_maintenance_window("mon:12:00-mon:13:00")
        assert result == "mon:12:00-mon:13:00 UTC"

    def test_with_none(self):
        """Test with None window."""
        result = FieldFormatter.format_maintenance_window(None)
        assert result == ""

    def test_with_empty_string(self):
        """Test with empty string."""
        result = FieldFormatter.format_maintenance_window("")
        assert result == ""

    @pytest.mark.parametrize("window,expected", [
        ("mon:12:00-mon:13:00", "mon:12:00-mon:13:00 UTC"),
        ("sun:02:00-sun:03:00", "sun:02:00-sun:03:00 UTC"),
        ("sat:16:30-sat:17:30", "sat:16:30-sat:17:30 UTC"),
        (None, ""),
        ("", ""),
    ])
    def test_various_values(self, window, expected):
        """Test various window values."""
        result = FieldFormatter.format_maintenance_window(window)
        assert result == expected


class TestFormatEnabledDisabled:
    """Tests for format_enabled_disabled method."""

    def test_true_value(self):
        """Test with True value."""
        result = FieldFormatter.format_enabled_disabled(True)
        assert result == "Enabled"

    def test_false_value(self):
        """Test with False value."""
        result = FieldFormatter.format_enabled_disabled(False)
        assert result == "Disabled"

    def test_none_value(self):
        """Test with None value."""
        result = FieldFormatter.format_enabled_disabled(None)
        assert result == "N/A"

    @pytest.mark.parametrize("value,expected", [
        (True, "Enabled"),
        (False, "Disabled"),
        (None, "N/A"),
    ])
    def test_various_values(self, value, expected):
        """Test various values."""
        result = FieldFormatter.format_enabled_disabled(value)
        assert result == expected
