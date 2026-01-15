"""Markdown formatter for ElastiCache information."""

from typing import List

from elasticache_info.aws.models import ElastiCacheInfo
from elasticache_info.formatters.base import BaseFormatter


class MarkdownFormatter(BaseFormatter):
    """Markdown table output formatter."""

    # Numeric fields that should be right-aligned
    NUMERIC_FIELDS = {"shards", "nodes"}

    def format(self, data: List[ElastiCacheInfo], fields: List[str]) -> str:
        """Format ElastiCache information as Markdown table.

        Args:
            data: List of ElastiCacheInfo objects
            fields: List of field names to include in output

        Returns:
            Markdown table formatted string
        """
        if not data:
            return ""

        lines = []

        # Header row
        header = [self._format_field_name(field) for field in fields]
        lines.append("| " + " | ".join(header) + " |")

        # Separator row with alignment
        separators = []
        for field in fields:
            if field in self.NUMERIC_FIELDS:
                separators.append("---:")  # Right-align for numeric fields
            else:
                separators.append("---")   # Left-align for other fields
        lines.append("| " + " | ".join(separators) + " |")

        # Data rows
        for item in data:
            row = [str(getattr(item, field, "")) for field in fields]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    @staticmethod
    def _format_field_name(field: str) -> str:
        """Convert field name to display format.

        Args:
            field: Field name (e.g., "node_type")

        Returns:
            Display name (e.g., "Node Type")
        """
        return field.replace("_", " ").title()
