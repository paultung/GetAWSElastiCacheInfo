"""CSV formatter for ElastiCache information."""

import csv
import io
from typing import List

from elasticache_info.aws.models import ElastiCacheInfo
from elasticache_info.formatters.base import BaseFormatter


class CSVFormatter(BaseFormatter):
    """CSV output formatter."""

    def format(self, data: List[ElastiCacheInfo], fields: List[str]) -> str:
        """Format ElastiCache information as CSV.

        Args:
            data: List of ElastiCacheInfo objects
            fields: List of field names to include in output

        Returns:
            CSV formatted string
        """
        if not data:
            return ""

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        header = [self._format_field_name(field) for field in fields]
        writer.writerow(header)

        # Write data rows
        for item in data:
            row = [getattr(item, field, "") for field in fields]
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def _format_field_name(field: str) -> str:
        """Convert field name to display format.

        Args:
            field: Field name (e.g., "node_type")

        Returns:
            Display name (e.g., "Node Type")
        """
        return field.replace("_", " ").title()
