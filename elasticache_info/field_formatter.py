"""Field formatters for complex ElastiCache fields."""

from typing import Optional


class FieldFormatter:
    """Formatter for complex ElastiCache fields.

    Handles formatting of composite fields like slow logs, backup settings,
    and cluster names with Global Datastore information.
    """

    @staticmethod
    def format_slow_logs(slower_than: Optional[int], max_len: Optional[int]) -> str:
        """Format slow logs field.

        Args:
            slower_than: slowlog-log-slower-than parameter value
            max_len: slowlog-max-len parameter value

        Returns:
            Formatted string:
            - "Enabled/{slower_than}/{max_len}" if enabled
            - "Disabled" if disabled or parameters are None
        """
        if slower_than is None or max_len is None:
            return "Disabled"

        if slower_than > 0:
            return f"Enabled/{slower_than}/{max_len}"

        return "Disabled"

    @staticmethod
    def format_backup(window: Optional[str], retention_days: Optional[int]) -> str:
        """Format backup field.

        Args:
            window: Snapshot window (e.g., "00:00-01:00")
            retention_days: Snapshot retention period in days

        Returns:
            Formatted string:
            - "{window} UTC/{retention_days} days" if enabled with window
            - "Enabled/{retention_days} days（無窗口資訊）" if enabled without window
            - "Disabled" if disabled
            - "N/A" if parameters are None
        """
        if retention_days is None:
            return "N/A"

        if retention_days > 0:
            if window is not None:
                return f"{window} UTC/{retention_days} days"
            else:
                return f"Enabled/{retention_days} days（無窗口資訊）"

        return "Disabled"

    @staticmethod
    def format_cluster_name(global_ds_id: Optional[str], cluster_id: str) -> str:
        """Format cluster name with Global Datastore information.

        Args:
            global_ds_id: Global Datastore ID (if applicable)
            cluster_id: Cluster/Replication Group ID

        Returns:
            Formatted string:
            - "{global_ds_id}/{cluster_id}" if part of Global Datastore
            - "{cluster_id}" otherwise
        """
        if global_ds_id:
            return f"{global_ds_id}/{cluster_id}"
        return cluster_id

    @staticmethod
    def format_maintenance_window(window: Optional[str]) -> str:
        """Format maintenance window field.

        Args:
            window: Maintenance window (e.g., "mon:12:00-mon:13:00")

        Returns:
            Formatted string:
            - "{window} UTC" if window is provided
            - Empty string if window is None or empty
        """
        if window:
            return f"{window} UTC"
        return ""

    @staticmethod
    def format_enabled_disabled(value: Optional[bool]) -> str:
        """Format boolean value as Enabled/Disabled.

        Args:
            value: Boolean value

        Returns:
            "Enabled" if True, "Disabled" if False, "N/A" if None
        """
        if value is None:
            return "N/A"
        return "Enabled" if value else "Disabled"
