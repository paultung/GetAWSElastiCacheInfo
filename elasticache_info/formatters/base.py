"""Base formatter interface for output formats."""

from abc import ABC, abstractmethod
from typing import List

from elasticache_info.aws.models import ElastiCacheInfo


class BaseFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def format(self, data: List[ElastiCacheInfo], fields: List[str]) -> str:
        """Format ElastiCache information data.

        Args:
            data: List of ElastiCacheInfo objects
            fields: List of field names to include in output

        Returns:
            Formatted string output
        """
        pass
