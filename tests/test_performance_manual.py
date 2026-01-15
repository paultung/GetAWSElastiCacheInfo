"""Manual performance tests for ElastiCache client.

These tests are meant to be run manually to verify performance improvements.
They require actual AWS credentials and will make real API calls.

Run with:
    pytest tests/test_performance_manual.py::test_parallel_query_performance -v -s
"""

import pytest
import time
from elasticache_info.aws.client import ElastiCacheClient


@pytest.mark.skip(reason="Manual performance test - run with: pytest tests/test_performance_manual.py::test_parallel_query_performance -v -s")
def test_parallel_query_performance():
    """Manual test to verify performance improvement.

    Expected: 3 regions should complete in ~2-3 seconds (vs 6-9 seconds in Phase 1)

    This test requires:
    1. Valid AWS credentials configured
    2. At least one Global Datastore spanning multiple regions
    3. Or manually modify to test specific regions
    """
    client = ElastiCacheClient(region="eu-central-1", profile="default")

    start = time.time()
    results = client.get_elasticache_info(engines=["redis"])
    elapsed = time.time() - start

    regions = sorted(set(r.region for r in results))

    print("\n" + "=" * 60)
    print("Performance Test Results:")
    print("=" * 60)
    print(".2f")
    print(f"Clusters found: {len(results)}")
    print(f"Regions queried: {len(regions)} - {', '.join(regions)}")
    print("=" * 60)

    # Performance expectations:
    # - With Global Datastore: 3+ regions in 2-3 seconds
    # - Single region: < 1 second
    # - Multiple regions without Global Datastore: ~1 second per region

    # No assertion - just for manual verification
    # Expected improvements from Phase 1:
    # - 3 regions: 6-9s → 2-3s (parallel execution)
    # - API calls reduced by 10-20% (shared cache)


@pytest.mark.skip(reason="Manual cache sharing test - requires multiple regions with same parameter groups")
def test_shared_cache_api_call_reduction():
    """Manual test to verify shared cache reduces API calls.

    This test demonstrates that the same parameter group queried from
    multiple regions only results in one API call.
    """
    # Clear any existing cache
    ElastiCacheClient._shared_param_cache.clear()

    # Create clients for different regions
    client1 = ElastiCacheClient(region="us-east-1", profile="default")
    client2 = ElastiCacheClient(region="eu-west-1", profile="default")

    # This would require monitoring CloudTrail or AWS API call logs
    # to verify that describe_cache_parameters is only called once
    # for the same parameter group across different regions

    print("To verify cache sharing:")
    print("1. Clear shared cache: ElastiCacheClient._shared_param_cache.clear()")
    print("2. Query same parameter group from multiple regions")
    print("3. Check CloudTrail logs - should see only 1 describe_cache_parameters call")
    print("4. Query again - should see 0 API calls (cache hit)")


@pytest.mark.skip(reason="Manual thread logging test - run to see region-prefixed logs")
def test_thread_logging_visibility():
    """Manual test to verify thread logging with region prefixes.

    Run this test to see that log messages include [region] prefixes
    showing which thread/region generated each log message.
    """
    client = ElastiCacheClient(region="us-east-1", profile="default")

    print("Running query to see thread logging with region prefixes...")
    results = client.get_elasticache_info(engines=["redis"])

    print(f"Query completed. Check logs above for [region] prefixes in thread logs.")
    print(f"Found {len(results)} clusters across {len(set(r.region for r in results))} regions")