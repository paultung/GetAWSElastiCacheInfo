---
title: 'Phase 2: 實作 Global Datastore 並行查詢與快取共享'
slug: 'parallel-query-shared-cache'
created: '2026-01-14'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.8+', 'boto3>=1.28.0', 'concurrent.futures', 'threading', 'rich>=13.0.0', 'pytest>=7.4.0', 'moto[elasticache]>=4.2.0']
files_to_modify: ['elasticache_info/aws/client.py', 'tests/test_client.py', 'tests/test_performance_manual.py (new)']
code_patterns: ['ThreadPoolExecutor Pattern', 'Class-level Shared Cache', 'Lock-Protected Cache Access', 'threading.Lock Pattern', '4-Layer Query Architecture', 'Decorator Pattern (@handle_aws_errors)', 'Thread Logging with Region Prefix']
test_patterns: ['pytest with parametrize', 'Class-based test organization', 'moto for AWS mocking', 'unittest.mock.patch for boto3', 'Real ThreadPoolExecutor in tests']
---

# Tech-Spec: Phase 2: 實作 Global Datastore 並行查詢與快取共享

**Created:** 2026-01-14

## Overview

### Problem Statement

Phase 1 實作了跨 region 序列查詢功能，但存在效能瓶頸：

1. **序列查詢效能問題**：
   - 當查詢 3 個 regions 時，需要 6-9 秒（每個 region 約 2-3 秒）
   - 查詢是序列執行，無法利用網路 I/O 等待時間
   - 使用者體驗不佳，特別是 Global Datastore 跨越多個 regions 時

2. **重複查詢 Parameter Groups**：
   - 每個 region 的 `ElastiCacheClient` 實例有獨立的 `_param_cache`
   - 相同的 parameter group（例如 `default.redis7`）在不同 regions 會被重複查詢
   - 浪費 API calls 和查詢時間（約 10-20% 的額外開銷）

### Solution

實作並行查詢和快取共享機制，提升跨 region 查詢效能：

1. **使用 ThreadPoolExecutor 並行查詢**：
   - 將序列查詢改為並行查詢，利用網路 I/O 等待時間
   - 每個 thread 建立獨立的 `ElastiCacheClient` 實例（thread-safe）
   - 使用 `concurrent.futures.as_completed()` 處理完成的 futures

2. **實作 Class-level 共享快取**：
   - 新增 class-level `_shared_param_cache` 字典
   - 新增 class-level `_cache_lock` (threading.Lock) 保護讀寫
   - 修改 `_get_parameter_group_params()` 使用共享快取
   - 避免重複查詢相同的 parameter groups

3. **效能目標**：
   - 3 regions 查詢時間從 6-9 秒降到 2-3 秒
   - 減少 10-20% 的 API calls（透過快取共享）

### Scope

**In Scope:**
- 修改 `get_elasticache_info()` 使用 `ThreadPoolExecutor` 並行查詢
- 新增 class-level `_shared_param_cache` 和 `_cache_lock`
- 修改 `_get_parameter_group_params()` 使用共享快取（with lock protection）
- 修改 `__init__()` 初始化 class-level 變數（如果不存在）
- 保持所有現有功能：錯誤處理、進度顯示、向後相容性
- 新增單元測試驗證 thread safety 和快取共享

**Out of Scope:**
- 改變 CLI 參數或輸出格式
- 新增效能測量或 benchmark 工具（效能目標是預估值）
- 改變錯誤處理策略（維持即時 log，不收集 exceptions）
- 修改 `_query_single_region()` 的內部邏輯
- 修改 4-layer query architecture 的其他部分
- 實作 connection pooling 或其他進階優化

## Context for Development

### Codebase Patterns

1. **4-Layer Query Architecture**（`client.py` 第 87-95 行）：
   - Layer 1: Global Datastore Discovery (`_get_global_datastores()`)
   - Layer 2: Replication Group Enumeration (`_get_replication_groups()`)
   - Layer 3: Cache Cluster Details (`_get_cache_clusters()`)
   - Layer 4: Parameter Group Queries (`_get_parameter_group_params()` with caching)
   - **Phase 2 只修改 Layer 4 的快取機制和主查詢方法的並行邏輯**

2. **Decorator Pattern for Error Handling**（`client.py` 第 27-84 行）：
   - `@handle_aws_errors` decorator 統一處理 AWS API 錯誤
   - 實作 exponential backoff retry（最多 3 次）
   - **並行查詢時，每個 thread 的錯誤仍由 decorator 處理**

3. **Instance-level Parameter Cache**（目前實作）：
   - `self._param_cache: Dict[str, Dict[str, str]]` 在 `__init__()` 初始化（第 106 行）
   - 在 `_get_parameter_group_params()` 中使用（第 248-280 行）
   - **Phase 2 改為 class-level shared cache**

4. **Sequential Multi-Region Query**（目前實作，第 563-593 行）：
   - 使用 `for region in sorted(regions_to_query)` 序列查詢
   - 為每個 region 建立獨立的 `ElastiCacheClient(region, self.profile)`
   - 調用 `region_client._query_single_region()` 取得結果
   - **Phase 2 改為 ThreadPoolExecutor 並行查詢**

5. **Progress Indicator Pattern**（`cli.py` 第 131-145 行，`client.py` 第 566-587 行）：
   - 使用 `rich.progress.Progress` with `SpinnerColumn` 和 `TextColumn`
   - 支援多個 tasks 並行更新（Rich Progress 是 thread-safe 的）
   - **Phase 2 保持相同的進度顯示邏輯，但在並行環境中執行**

6. **ThreadPoolExecutor Pattern**（需實作）：
   - 使用 `concurrent.futures.ThreadPoolExecutor` 建立 thread pool
   - 使用 `executor.submit()` 提交 tasks
   - 使用 `as_completed()` 處理完成的 futures
   - 每個 thread 建立獨立的 boto3 session 和 client（thread-safe）

7. **Class-level Shared Cache Pattern**（需實作）：
   - 使用 class variable 儲存共享快取：`_shared_param_cache: Dict[str, Dict[str, Optional[int]]]`
   - 使用 class variable 儲存 lock：`_cache_lock: threading.Lock`
   - 在 `__init__()` 中初始化（如果不存在）
   - 在 `_get_parameter_group_params()` 中使用 `with self._cache_lock:` 保護讀寫

8. **Thread Safety Considerations**：
   - boto3 Session 和 Client 是 **thread-safe for reads**，但建議每個 thread 建立獨立實例
   - Rich Progress 是 **thread-safe**，可以從多個 threads 更新
   - 共享快取需要 `threading.Lock` 保護（dict 的讀寫不是 atomic）

### Files to Reference

| File | Purpose | Lines of Interest |
| ---- | ------- | ----------------- |
| `elasticache_info/aws/client.py` | ElastiCache 查詢邏輯 | 87-594 (ElastiCacheClient class) |
| - `__init__()` | **需修改**：初始化 class-level cache | 97-112 |
| - `_get_parameter_group_params()` | **需修改**：使用共享快取 + lock | 234-287 |
| - `get_elasticache_info()` | **需大幅修改**：實作並行查詢 | 535-593 |
| - `_query_single_region()` | 單一 region 查詢邏輯（不修改） | 289-344 |
| `tests/test_client.py` | ElastiCacheClient 單元測試 | 1-449 (現有測試) |
| - `TestGetGlobalDatastores` | Global Datastore 測試（參考） | 10-114 |
| - **新增 `TestParallelQuery`** | **需新增**：並行查詢測試 | N/A (新類別) |
| - **新增 `TestSharedCache`** | **需新增**：共享快取測試 | N/A (新類別) |
| `pyproject.toml` | 專案配置與依賴 | 1-47 (dependencies) |

### Technical Decisions

1. **並行查詢架構選擇**：
   - **選擇 ThreadPoolExecutor**：適合 I/O-bound 任務（AWS API calls）
   - **不選擇 asyncio**：boto3 不原生支援 async，需要 aioboto3（增加複雜度）
   - **不選擇 multiprocessing**：overhead 太大，且不需要 CPU-bound 並行
   - **Thread pool size**：使用預設（`min(32, os.cpu_count() + 4)`），通常足夠

2. **每個 Thread 的 Client 管理**：
   - 每個 thread 建立獨立的 `ElastiCacheClient` 實例
   - 每個實例有自己的 boto3 session 和 client（避免 thread contention）
   - 共用 class-level `_shared_param_cache`（透過 lock 保護）
   - **不重用初始 region 的 client**：保持程式碼一致性，避免特殊處理

3. **Class-level Cache 實作**：
   - 使用 class variable 而非 instance variable：`ElastiCacheClient._shared_param_cache`
   - Class variables 在類別定義時初始化（`= {}` 和 `= threading.Lock()`），不需要在 `__init__()` 中做任何事
   - 結構：`Dict[str, Dict[str, Optional[int]]]`（與 instance cache 相同）
   - **為何不用 LRU cache？** 因為需要跨 instances 共享，且 parameter groups 數量有限
   - **Cache 生命週期**：存在於整個 process 生命週期，但影響可忽略（每個 entry 約 100 bytes，20 個 parameter groups 約 2KB）

4. **Lock 保護策略（簡化版）**：
   - 使用單一 `threading.Lock` 保護整個 `_shared_param_cache`
   - **Lock 範圍最小化**：只在 cache 讀寫時持有 lock，不在 API call 時持有
   - **Lock 模式**：
     ```python
     # Check cache with lock protection
     with self._cache_lock:
         if parameter_group_name in self._shared_param_cache:
             return self._shared_param_cache[parameter_group_name]

     # API call (不持有 lock)
     params = self._query_api(...)

     # Write to cache with lock protection
     with self._cache_lock:
         # Check again in case another thread cached it while we were querying
         if parameter_group_name not in self._shared_param_cache:
             self._shared_param_cache[parameter_group_name] = params

     return params
     ```
   - **為何不用 double-checked locking？** Python 的 dict 操作不是 atomic，簡化的 pattern 更安全且效能差異可忽略

5. **Future 處理策略**：
   - 使用 `concurrent.futures.as_completed()` 而非 `executor.map()`
   - 優點：可以即時處理完成的 futures，更新進度條
   - 使用 `future.result()` 取得結果，會自動 re-raise exceptions
   - 捕捉個別 future 的 exceptions，記錄 log，繼續處理其他 futures

6. **Progress 更新策略**：
   - 在提交 future 前建立 task：`task = progress.add_task(...)`
   - 將 `(future, task_id, region)` 組合傳遞給 `as_completed()`
   - 使用 dict 追蹤 `{future: (task_id, region)}`
   - 在 future 完成時更新對應的 task

7. **錯誤處理策略（維持 Phase 1）**：
   - 個別 region 查詢失敗不影響其他 regions
   - 使用 `try-except` 捕捉 `future.result()` 的 exceptions
   - 記錄 `logger.warning()`，不拋出異常
   - 更新進度條為失敗狀態：`description=f"❌ {region} (查詢失敗)"`

8. **向後相容性保證**：
   - `get_elasticache_info()` 方法簽名不變
   - 回傳型別維持 `List[ElastiCacheInfo]`
   - 單一 region 查詢（無 Global Datastore）行為相同
   - 所有現有測試應該繼續通過

9. **測試策略**：
   - **單元測試 - 共享快取**：
     - 測試多個 instances 共用同一個 cache
     - 測試 lock 保護（驗證 API 只被呼叫一次）
     - 測試 cache hit/miss 邏輯
   - **單元測試 - 並行查詢**：
     - 使用真的 ThreadPoolExecutor（不 mock），只 mock boto3
     - 驗證每個 region 都被查詢
     - 驗證結果正確聚合和排序
   - **整合測試**（手動）：
     - 在實際 AWS 環境測試並行查詢
     - 驗證效能改善（目視確認時間縮短）
     - 驗證進度條正確顯示

## Implementation Plan

### Tasks

**Task 1: 新增 Class-level 共享快取和 Lock**
   - [ ] 在 `ElastiCacheClient` 類別定義中新增 class variables：
     ```python
     class ElastiCacheClient:
         # Class-level shared cache for parameter groups (shared across all instances)
         # Note: Class variables are initialized once when class is defined, not per instance
         _shared_param_cache: Dict[str, Dict[str, Optional[int]]] = {}
         _cache_lock: threading.Lock = threading.Lock()
     ```
   - [ ] **位置**：在 class docstring 之後，`__init__()` 之前（約第 96 行）
   - [ ] **新增 import**：在檔案頂部加上 `import threading`（約第 4 行，在 `import time` 之後）
   - [ ] **型別提示**：確認 `from typing import Dict, Optional` 已存在（第 6 行）
   - [ ] **不需要修改 `__init__()`**：class variables 已在類別定義時初始化
   - [ ] 單元測試：驗證 class variables 存在且所有 instances 共用

**Task 2: 修改 `_get_parameter_group_params()` 使用共享快取（Lock 保護）**
   - [ ] 實作 lock-protected cache access pattern（取代第 248-287 行）：
     ```python
     # Check cache with lock protection
     with self._cache_lock:
         if parameter_group_name in self._shared_param_cache:
             logger.debug(f"Using shared cached parameters for {parameter_group_name}")
             return self._shared_param_cache[parameter_group_name]

     # Cache miss - query API (without holding lock)
     logger.debug(f"Layer 4: Querying Parameter Group: {parameter_group_name}")
     params = {
         "slowlog-log-slower-than": None,
         "slowlog-max-len": None
     }

     try:
         # Keep existing API call logic (lines 259-277) unchanged:
         # - paginator = self.client.get_paginator("describe_cache_parameters")
         # - page_iterator = paginator.paginate(CacheParameterGroupName=parameter_group_name)
         # - Parse slowlog-log-slower-than and slowlog-max-len from Parameters

         # After API call completes, cache the result with lock protection
         with self._cache_lock:
             # Check again in case another thread cached it while we were querying
             if parameter_group_name not in self._shared_param_cache:
                 self._shared_param_cache[parameter_group_name] = params
         logger.debug(f"Cached parameters in shared cache for {parameter_group_name}: {params}")

     except Exception as e:
         logger.warning(f"Failed to query Parameter Group {parameter_group_name}: {e}")

     return params
     ```
   - [ ] **移除 instance cache**：刪除 `self._param_cache`（第 106 行）
   - [ ] **注意**：雖然使用簡化的 lock pattern（不是 double-checked locking），但在寫入前仍檢查一次，避免覆蓋其他 thread 剛寫入的值
   - [ ] 單元測試：驗證多個 instances 共用快取，驗證 lock 保護避免 race condition

**Task 3: 新增 `_query_region_wrapper()` 輔助方法與 Thread Logging**
   - [ ] **目的**：封裝單一 region 查詢邏輯，供 ThreadPoolExecutor 調用
   - [ ] **方法簽名**：
     ```python
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
     ```
   - [ ] **實作**：
     ```python
     logger.info(f"[{region}] Starting region query")

     # Create region-specific client for thread safety (boto3 best practice)
     region_client = ElastiCacheClient(region, self.profile)

     # Query this region
     results = region_client._query_single_region(region, engines, cluster_filter, global_ds_map)

     logger.info(f"[{region}] Query completed, found {len(results)} clusters")
     return results
     ```
   - [ ] **位置**：在 `get_elasticache_info()` 之前（約第 534 行）
   - [ ] **不處理 exceptions**：讓 exceptions 往上拋給 `as_completed()` 的 `future.result()` 處理
   - [ ] **修改 `_query_single_region()` 的 logging**（第 289-344 行）：
     - [ ] 第 307 行：`logger.info(f"Querying region: {region}")` → `logger.info(f"[{region}] Querying region")`
     - [ ] 第 343 行：`logger.info(f"Found {len(results)} clusters in region {region}")` → `logger.info(f"[{region}] Found {len(results)} clusters")`
     - [ ] 確保所有 logger 呼叫都有 `[{region}]` prefix，保持 thread logging 一致性
   - [ ] 單元測試：驗證方法正確建立 client 並調用 `_query_single_region()`

**Task 4: 重構 `get_elasticache_info()` 實作並行查詢**
   - [ ] **新增 import**：`from concurrent.futures import ThreadPoolExecutor, as_completed`（檔案頂部）
   - [ ] **Step 1-2 不變**：保持 Global Datastore discovery 和 regions identification（第 554-561 行）
   - [ ] **Step 3 改為並行查詢**（取代第 563-588 行）：
     - [ ] 建立 ThreadPoolExecutor：`with ThreadPoolExecutor() as executor:`
     - [ ] 建立 futures dict：`future_to_region = {}`
     - [ ] 建立 task tracking dict：`future_to_task = {}`
     - [ ] 提交所有 region 查詢 tasks：
       ```python
       for region in sorted(regions_to_query):
           task = None
           if progress:
               task = progress.add_task(f"正在查詢 {region} 的 ElastiCache 叢集...", total=None)

           future = executor.submit(self._query_region_wrapper, region, engines, cluster_filter, global_ds_map)
           future_to_region[future] = region
           if task is not None:
               future_to_task[future] = task
       ```
     - [ ] 使用 `as_completed()` 處理完成的 futures：
       ```python
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
       ```
   - [ ] **Step 4 不變**：保持結果排序邏輯（第 590-593 行）
   - [ ] 整合測試：驗證並行查詢正確執行

**Task 5: 清理 Instance-level Cache 相關程式碼**
   - [ ] 從 `__init__()` 移除 `self._param_cache = {}`（第 106 行）
   - [ ] 檢查是否有其他地方使用 `self._param_cache`（應該只有 Task 2 已修改的地方）
   - [ ] **檢查並更新以下 docstrings/comments**（如果提到 instance-level cache）：
     - [ ] `ElastiCacheClient` class docstring（第 88-95 行）：確認 Layer 4 描述正確
     - [ ] `_get_parameter_group_params()` docstring（第 235-246 行）：確認沒有提到 instance cache
   - [ ] 單元測試：驗證沒有 `_param_cache` attribute

**Task 6: 新增單元測試 - 共享快取**
   - [ ] 新增 `TestSharedCache` 類別在 `tests/test_client.py`
   - [ ] **測試案例 1**：多個 instances 共用同一個 cache
     ```python
     def test_shared_cache_across_instances(self, mock_session):
         """Test that multiple instances share the same parameter cache."""
         # Create two clients
         client1 = ElastiCacheClient(region="us-east-1", profile="default")
         client2 = ElastiCacheClient(region="ap-northeast-1", profile="default")

         # Mock API response for client1
         # ... (mock paginator)

         # Client1 queries parameter group
         params1 = client1._get_parameter_group_params("default.redis7")

         # Client2 should get cached result (verify no API call)
         params2 = client2._get_parameter_group_params("default.redis7")

         assert params1 == params2
         # Verify API was only called once
     ```
   - [ ] **測試案例 2**：Cache hit/miss 邏輯
   - [ ] **測試案例 3**：Lock 正確使用（驗證 API 只被呼叫一次，即使多個 instances 查詢相同 parameter group）
   - [ ] **不測試 race condition timing**：精確的 timing control 太複雜，相信 Python 的 `threading.Lock` 實作

**Task 7: 新增單元測試 - 並行查詢**
   - [ ] 新增 `TestParallelQuery` 類別在 `tests/test_client.py`
   - [ ] **測試案例 1**：並行查詢多個 regions（用真的 ThreadPoolExecutor）
     ```python
     @patch('elasticache_info.aws.client.boto3.Session')
     def test_parallel_query_multiple_regions(self, mock_session):
         """Test parallel querying with real ThreadPoolExecutor."""
         # Mock boto3 responses for 3 regions
         # ... setup mocks ...

         # Use REAL ThreadPoolExecutor (not mocked)
         client = ElastiCacheClient(region="us-east-1", profile="default")
         results = client.get_elasticache_info(engines=["redis"])

         # Verify results from all regions
         regions = {r.region for r in results}
         assert regions == {"us-east-1", "ap-northeast-1", "eu-west-1"}
     ```
   - [ ] **測試案例 2**：單一 region 查詢（向後相容性）
   - [ ] **測試案例 3**：部分 region 失敗（錯誤處理）
   - [ ] **測試案例 4**：結果排序正確
   - [ ] **不 mock ThreadPoolExecutor**：用真的 executor，只 mock boto3

**Task 8: 向後相容性測試**
   - [ ] 執行所有現有單元測試：`pytest tests/`
   - [ ] 驗證所有測試通過（特別是 `TestGetGlobalDatastores` 和 `TestQuerySingleRegion`）
   - [ ] 測試單一 region 查詢（無 Global Datastore）
   - [ ] 測試 Memcached clusters（不受影響）
   - [ ] 測試 cluster filter 功能

**Task 9: 新增手動效能測試**
   - [ ] 在 `tests/` 建立 `test_performance_manual.py`（不自動執行）
   - [ ] **測試案例**：
     ```python
     import pytest
     import time
     from elasticache_info.aws.client import ElastiCacheClient

     @pytest.mark.skip(reason="Manual performance test - run with: pytest tests/test_performance_manual.py::test_parallel_query_performance -v -s")
     def test_parallel_query_performance():
         """Manual test to verify performance improvement.

         Expected: 3 regions should complete in ~2-3 seconds (vs 6-9 seconds in Phase 1)
         """
         client = ElastiCacheClient(region="eu-central-1", profile="default")

         start = time.time()
         results = client.get_elasticache_info(engines=["redis"])
         elapsed = time.time() - start

         regions = sorted(set(r.region for r in results))

         print(f"\n{'='*60}")
         print(f"Performance Test Results:")
         print(f"{'='*60}")
         print(f"Total time: {elapsed:.2f}s")
         print(f"Clusters found: {len(results)}")
         print(f"Regions queried: {len(regions)} - {', '.join(regions)}")
         print(f"{'='*60}")

         # No assertion - just for manual verification
     ```
   - [ ] **執行方式**：`pytest tests/test_performance_manual.py -v -s`
   - [ ] **不加入 CI**：這是手動測試，用於驗證效能改善

**Task 10: 整合測試與文件更新**
   - [ ] 在實際 AWS 環境測試並行查詢
   - [ ] 執行手動效能測試（Task 9），驗證效能改善（目視確認 3 regions 約 2-3 秒）
   - [ ] 驗證進度條正確顯示（多個 tasks 並行更新）
   - [ ] 驗證 thread logging 清楚（可以看出 `[region]` prefix）
   - [ ] 更新 README.md（如需要，說明效能改善）
   - [ ] **Commit 策略**：實作類 Tasks 各一個 commit，測試類 Tasks 合併為 2-3 個 commits
   - [ ] Commit messages 遵循 Conventional Commits：
     - Task 1: `feat(client): 新增 class-level 共享快取和 threading.Lock`
     - Task 2: `refactor(client): 修改 _get_parameter_group_params 使用 lock-protected cache`
     - Task 3: `feat(client): 新增 _query_region_wrapper 輔助方法與 thread logging`
     - Task 4: `feat(client): 實作 ThreadPoolExecutor 並行查詢`
     - Task 5: `refactor(client): 清理 instance-level cache 相關程式碼`
     - Task 6-7: `test: 新增共享快取和並行查詢單元測試`
     - Task 8-9: `test: 新增向後相容性測試和手動效能測試`

### Acceptance Criteria

**AC1: 共享快取正確運作**
- Given: 兩個 `ElastiCacheClient` instances（不同 regions）
- When: 第一個 instance 查詢 `default.redis7` parameter group
- Then: 第二個 instance 查詢相同 parameter group 時，應該從 shared cache 取得（不呼叫 API）
- And: 驗證方式為單元測試中 mock API call，確認只被呼叫一次

**AC2: Lock 保護避免重複 API Call**
- Given: 多個 threads 同時查詢相同的 parameter group
- When: 並行執行查詢
- Then: Lock 確保 cache 讀寫的 thread safety，避免 race condition
- And: 即使多個 threads 同時查詢，API 也只被呼叫一次（第一個 thread 查詢，其他 threads 等待並取得 cache）
- And: 驗證方式為單元測試中確認 API 只被呼叫一次

**AC3: 並行查詢正確執行**
- Given: 需要查詢 3 個 regions（us-east-1, ap-northeast-1, eu-west-1）
- When: 執行 `get_elasticache_info()`
- Then: 所有 3 個 regions 應該並行查詢（使用 ThreadPoolExecutor）
- And: 結果應該包含所有 regions 的 clusters
- And: 驗證方式為單元測試中使用真的 ThreadPoolExecutor（不 mock），mock boto3 responses，確認所有 regions 的結果都被回傳

**AC4: 效能改善**
- Given: 查詢包含 3 個 regions 的 Global Datastore
- When: 執行查詢
- Then: 總時間應該接近最慢 region 的查詢時間（而非所有 regions 時間總和）
- And: 預期 3 regions 約 2-3 秒（vs Phase 1 的 6-9 秒），但實際時間取決於網路延遲
- And: 驗證方式為手動測試（Task 9），目視確認時間明顯縮短（不需要自動化測量）

**AC5: 進度條正確顯示**
- Given: 並行查詢 3 個 regions
- When: 執行查詢
- Then: 進度條應該顯示 3 個獨立的 tasks，並行更新
- And: 每個 task 完成時應該標記為完成
- And: 驗證方式為人工目視檢查終端輸出

**AC9: Thread Logging 清楚顯示**
- Given: 並行查詢 3 個 regions
- When: 執行查詢並查看 log 輸出
- Then: 每個 log message 應該包含 `[region]` prefix
- And: 可以清楚看出哪些 logs 來自同一個 region/thread
- And: 驗證方式為人工目視檢查 log 輸出或單元測試中驗證 log message 格式

**AC6: 錯誤處理維持不變**
- Given: 並行查詢時，其中一個 region 因權限不足而失敗
- When: 執行查詢
- Then: 記錄 warning log，但繼續查詢其他 regions
- And: 進度條顯示失敗狀態：`❌ {region} (查詢失敗)`
- And: 回傳可用的結果（不拋出異常）

**AC7: 向後相容性**
- Given: 查詢不包含 Global Datastore 的 region（單一 region）
- When: 執行查詢
- Then: 行為與 Phase 1 完全相同（只是使用 ThreadPoolExecutor with 1 task）
- And: 所有現有單元測試應該繼續通過

**AC8: 結果排序正確**
- Given: 並行查詢結果以任意順序完成
- When: 所有 futures 完成後
- Then: 結果應該按 region 字母順序排序（ap-northeast-1 → eu-west-1 → us-east-1）
- And: 驗證方式為單元測試中檢查回傳的 `List[ElastiCacheInfo]` 順序

## Additional Context

### Dependencies

- `concurrent.futures`：Python 標準庫，ThreadPoolExecutor（Python 3.8+ 已內建）
- `threading`：Python 標準庫，Lock（Python 3.8+ 已內建）
- `boto3`：AWS SDK（已在專案中，thread-safe for independent sessions）
- `rich`：進度條顯示（已在專案中，thread-safe）
- **無新增外部依賴**

### Testing Strategy

1. **單元測試 - 共享快取**：
   - Mock boto3 API responses
   - 測試多個 instances 共用同一個 cache
   - 測試 lock 保護（模擬並行寫入）
   - 測試 cache hit/miss 邏輯
   - 覆蓋率目標：新增/修改的程式碼 90%+

2. **單元測試 - 並行查詢**：
   - 使用真的 ThreadPoolExecutor（不 mock），只 mock boto3 responses
   - 測試所有 regions 都被查詢
   - 測試結果正確聚合和排序
   - 測試錯誤處理（部分 region 失敗）
   - 測試向後相容性（單一 region）

3. **整合測試**（手動）：
   - 在實際 AWS 環境測試並行查詢
   - 驗證效能改善（目視確認時間從 6-9 秒降到 2-3 秒）
   - 驗證進度條正確顯示（多個 tasks 並行更新）
   - 驗證共享快取減少 API calls（檢查 CloudTrail logs，可選）

4. **Thread Safety 測試**：
   - 使用 `threading.Thread` 模擬多個 threads 同時查詢
   - 驗證 cache 資料一致性
   - 驗證沒有 race conditions 或 deadlocks

### Notes

**實作重點**：

1. **Thread Safety 考量**：
   - boto3 Session 和 Client：每個 thread 建立獨立實例（boto3 官方 best practice）
   - Rich Progress：原生 thread-safe，可以從多個 threads 更新
   - 共享快取：使用 `threading.Lock` 保護所有讀寫操作
   - **不需要 GIL 考量**：I/O-bound 任務，GIL 不是瓶頸

2. **Lock 使用最佳實踐**：
   - Lock 範圍最小化：只在 cache 讀寫時持有，不在 API call 時持有
   - 避免 nested locks：只有一個 lock，不會有 deadlock
   - 使用 `with` statement：確保 lock 一定會被釋放
   - **寫入前再檢查一次**：避免覆蓋其他 thread 剛寫入的值（雖然機率很小）

3. **Thread Logging 策略**：
   - 在所有 log message 中加上 `[region]` prefix
   - 格式：`logger.info(f"[{region}] message")`
   - 不需要改 logging config 或管理 thread name
   - 可以清楚看出哪些 log 來自同一個 region/thread

3. **效能預期**：
   - 3 regions 並行查詢：約 2-3 秒（最慢的 region 決定總時間）
   - 共享快取減少 API calls：約 10-20%（取決於 parameter groups 重複程度）
   - ThreadPoolExecutor overhead：可忽略（< 100ms）
   - **不需要精確測量**：效能目標是預估值，目視確認即可

4. **boto3 Thread Safety**：
   - 官方文件建議：每個 thread 建立獨立的 Session 和 Client
   - 原因：避免 connection pooling 的 contention
   - 我們的實作：在 `_query_region_wrapper()` 中為每個 region 建立新 client
   - **不重用初始 client**：保持程式碼簡單一致

5. **Rich Progress Thread Safety**：
   - Rich Progress 內部使用 `threading.RLock` 保護
   - 可以安全地從多個 threads 調用 `add_task()` 和 `update()`
   - 進度條會自動更新顯示（即使 tasks 並行完成）

6. **錯誤處理策略（維持 Phase 1）**：
   - 個別 region 失敗不影響其他 regions
   - 使用 `future.result()` 會自動 re-raise exceptions
   - 捕捉 exceptions，記錄 log，繼續處理其他 futures
   - 不改變回傳型別（維持 `List[ElastiCacheInfo]`）

7. **向後相容性保證**：
   - 方法簽名完全不變
   - 單一 region 查詢行為相同（只是使用 ThreadPoolExecutor with 1 task）
   - 所有現有測試應該繼續通過
   - CLI 參數和輸出格式完全不變

**Phase 2 vs Phase 1 比較**：

| 面向 | Phase 1 (序列) | Phase 2 (並行) |
|------|---------------|---------------|
| 查詢方式 | `for region in regions` | `ThreadPoolExecutor.submit()` |
| 3 regions 時間 | 6-9 秒 | 2-3 秒 |
| Client 建立 | 每個 region 一個 | 每個 region 一個（相同） |
| Parameter cache | Instance-level | Class-level (shared) |
| Thread safety | N/A | Lock 保護 |
| 進度顯示 | 序列更新 | 並行更新 |
| 錯誤處理 | 即時 log | 即時 log（相同） |
| API 相容性 | 完全相容 | 完全相容 |

**潛在風險與緩解**：

1. **風險：Thread contention on shared cache**
   - 緩解：Lock 範圍最小化，只在 cache 讀寫時持有
   - 影響：可忽略（cache 操作非常快）

2. **風險：ThreadPoolExecutor 建立過多 threads**
   - 緩解：使用預設 pool size（通常 < 10 regions）
   - 影響：可忽略（AWS regions 數量有限）

3. **風險：boto3 connection pool exhaustion**
   - 緩解：每個 thread 建立獨立 session 和 client
   - 影響：已緩解

4. **風險：Rich Progress 顯示混亂**
   - 緩解：Rich Progress 原生支援並行更新
   - 影響：已緩解

5. **風險：向後相容性破壞**
   - 緩解：保持所有方法簽名和回傳型別不變
   - 影響：已緩解

**未來優化方向（Phase 3，可選）**：

1. **Connection Pooling**：重用 boto3 connections（需要仔細處理 thread safety）
2. **Adaptive Thread Pool Size**：根據 regions 數量動態調整
3. **Cache Expiration**：實作 TTL 避免 cache 無限增長
4. **Metrics Collection**：收集效能指標（API calls, cache hit rate, query time）
5. **CLI 參數**：`--max-workers` 允許使用者控制並行度
