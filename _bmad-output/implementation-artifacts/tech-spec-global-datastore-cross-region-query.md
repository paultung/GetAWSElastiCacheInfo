---
title: '實作 Global Datastore 跨 Region 查詢與 Role 欄位修正'
slug: 'global-datastore-cross-region-query'
created: '2026-01-14'
status: 'completed'
completed: '2026-01-14'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.8+', 'boto3>=1.28.0', 'typer>=0.9.0', 'rich>=13.0.0', 'pytest>=7.4.0', 'moto[elasticache]>=4.2.0']
files_to_modify: ['elasticache_info/aws/client.py', 'elasticache_info/cli.py', 'tests/test_client.py (new)']
code_patterns: ['4-Layer Query Architecture', 'Decorator Pattern (@handle_aws_errors)', 'Custom Exception Hierarchy', 'Formatter Pattern', 'Dataclass Model']
test_patterns: ['pytest with parametrize', 'Class-based test organization', 'moto for AWS mocking', 'Unit tests for each layer']
---

# Tech-Spec: 實作 Global Datastore 跨 Region 查詢與 Role 欄位修正

**Created:** 2026-01-14

## Overview

### Problem Statement

AWS ElastiCache Info CLI 工具在查詢 Global Datastore 成員時存在兩個問題：

1. **Role 欄位空白問題**：
   - 當在 secondary region（例如 `ap-northeast-1`）執行查詢時，Role 欄位顯示空白
   - 根本原因：`describe_global_replication_groups` API 是 region-specific，在 secondary region 查詢時無法取得完整的 Global Datastore 資訊
   - 導致 `global_ds_map` 為空或不完整，無法正確填入 Primary/Secondary 角色

2. **缺少跨 Region 成員資訊**：
   - 目前只查詢指定的單一 region
   - 無法顯示 Global Datastore 在其他 regions 的 members
   - 使用者無法看到完整的 Global Datastore 拓撲結構

### Solution

改善現有查詢邏輯，實作跨 region 自動探索與查詢：

1. **修正 Global Datastore 資訊擷取**：
   - 改善 `_get_global_datastores()` 方法，從 API 回應的 `Members` 陣列正確解析所有 region 的 member 資訊
   - 建立完整的 `global_ds_map`，包含每個 member 的 region, role, 和 global_datastore_id

2. **實作跨 Region 查詢**：
   - 從 Global Datastore members 中識別所有相關的 regions
   - 為每個 region 建立獨立的 `ElastiCacheClient` 實例
   - 查詢每個 region 的 cluster 詳細資訊
   - 聚合所有結果並按 region 排序

3. **加上進度顯示**：
   - 使用 Rich Progress 顯示多 region 查詢進度
   - 清楚標示當前正在查詢的 region

### Scope

**In Scope:**
- 修正 `_get_global_datastores()` 方法，正確解析 `Members` 陣列並建立完整的 mapping
- 實作跨 region 查詢邏輯，自動探索並查詢 Global Datastore 的所有 members
- 修正 Role 欄位顯示（Primary/Secondary）
- 按 region 字母順序排序輸出結果
- 加上進度條顯示跨 region 查詢進度
- 保持向後相容性，不改變 CLI 參數和使用方式

**Out of Scope (Phase 1):**
- 新增 CLI 參數或選項
- 改變輸出格式（CSV/Markdown）的結構
- 修改其他欄位的邏輯
- 處理非 Global Datastore clusters 的邏輯變更
- 並行查詢優化（Phase 2）
- 跨 region 快取共享機制（Phase 2）
- 允許使用者選擇性關閉跨 region 查詢（未來功能）
- 回傳 QueryResult metadata（簡化為 log 記錄即可）

## Context for Development

### Codebase Patterns

1. **4-Layer Query Architecture**（`client.py` 第 87-91 行）：
   - Layer 1: Global Datastore Discovery (`_get_global_datastores()`)
   - Layer 2: Replication Group Enumeration (`_get_replication_groups()`)
   - Layer 3: Cache Cluster Details (`_get_cache_clusters()`)
   - Layer 4: Parameter Group Queries (`_get_parameter_group_params()` with caching)

2. **Decorator Pattern for Error Handling**（`client.py` 第 24-81 行）：
   - `@handle_aws_errors` decorator 統一處理 AWS API 錯誤
   - 實作 exponential backoff retry（最多 3 次）
   - 自動轉換為自定義 Exception（`AWSPermissionError`, `AWSConnectionError` 等）

3. **Custom Exception Hierarchy**（`exceptions.py`）：
   - `AWSBaseError` 基礎類別，提供中文錯誤訊息和建議
   - 子類別：`AWSPermissionError`, `AWSConnectionError`, `AWSAPIError`, `AWSCredentialsError`
   - 所有錯誤訊息都是中文，符合使用者需求

4. **Formatter Pattern**（`field_formatter.py`）：
   - `FieldFormatter` 類別提供靜態方法格式化複雜欄位
   - 方法：`format_slow_logs()`, `format_backup()`, `format_cluster_name()`, `format_maintenance_window()`, `format_enabled_disabled()`
   - 已有完整的單元測試覆蓋（`test_field_formatter.py`）

5. **Dataclass Model**（`models.py`）：
   - `ElastiCacheInfo` 使用 `@dataclass` 定義
   - 18 個欄位對應 CLI 的 18 個可選欄位
   - 欄位名稱使用 underscore（`node_type`），CLI 參數使用 hyphen（`node-type`）

6. **Progress Indicator Pattern**（`cli.py` 第 131-145 行）：
   - 使用 `rich.progress.Progress` with `SpinnerColumn` 和 `TextColumn`
   - 目前只有單一 task，需要擴展為多 task 支援跨 region 查詢

7. **Multi-Region Client Management**（需實作）：
   - 為每個 region 建立獨立的 `ElastiCacheClient` 實例
   - 每個實例有自己的 boto3 session 和 client
   - 每個實例有獨立的 `_param_cache`（Phase 1 不共享快取）

8. **Result Aggregation and Sorting**（需實作）：
   - 聚合多個 region 的查詢結果
   - 使用 `sorted(results, key=lambda x: x.region)` 按 region 排序

### Files to Reference

| File | Purpose | Lines of Interest |
| ---- | ------- | ----------------- |
| `elasticache_info/aws/client.py` | ElastiCache 查詢邏輯 | 84-515 (ElastiCacheClient class) |
| - `__init__()` | 初始化 client 和 param cache | 94-109 |
| - `_get_global_datastores()` | **需修改**：解析 Members 陣列 | 112-160 |
| - `_get_replication_groups()` | 查詢 Replication Groups | 162-193 |
| - `_get_cache_clusters()` | 查詢 Cache Clusters | 195-220 |
| - `_convert_to_model()` | **需修改**：加上 current_region 參數 | 278-458 |
| - `get_elasticache_info()` | **需大幅修改**：實作跨 region 查詢 | 460-514 |
| `elasticache_info/cli.py` | CLI 入口點 | 24-216 (main function) |
| - Progress 使用範例 | 參考現有進度條實作 | 131-145 |
| `elasticache_info/aws/models.py` | ElastiCacheInfo 資料模型 | 6-30 (dataclass definition) |
| `elasticache_info/field_formatter.py` | 欄位格式化邏輯（無需修改） | 6-106 (FieldFormatter class) |
| `elasticache_info/aws/exceptions.py` | 自定義 Exception 類別 | 6-131 (exception hierarchy) |
| `elasticache_info/utils.py` | 工具函數（match_wildcard 等） | 55-65 (match_wildcard) |
| `tests/test_field_formatter.py` | FieldFormatter 單元測試（參考） | 1-178 (完整測試覆蓋) |
| **`tests/test_client.py`** | **需新增**：ElastiCacheClient 單元測試 | N/A (新檔案) |
| `pyproject.toml` | 專案配置與依賴 | 1-47 (dependencies & dev tools) |

### Technical Decisions

1. **Global Datastore Members 解析策略**：
   - 從 `describe_global_replication_groups` API 回應中解析 `Members` 陣列
   - 每個 member 包含：`ReplicationGroupId`, `ReplicationGroupRegion`, `Role`, `Status`
   - 建立 mapping: `{region: {replication_group_id: {global_datastore_id, role}}}`
   - **Role 格式標準化**：AWS API 文件顯示回傳 "PRIMARY" / "SECONDARY"（全大寫），但為防禦性處理不同大小寫情況，儲存時統一轉為大寫，顯示時使用 `.capitalize()` 轉換為 "Primary" / "Secondary"（首字母大寫，其餘小寫）以符合使用者友善的輸出格式
   - 移除舊的 `GlobalNodeGroups` 解析邏輯，完全依賴 `Members` 陣列

2. **跨 Region 查詢觸發條件**：
   - 當 `_get_global_datastores()` 發現任何 Global Datastore 時
   - 自動識別所有相關的 regions（從 `global_ds_map.keys()`）
   - 初始 region 始終包含在查詢範圍內
   - 只查詢有 Global Datastore members 的 regions，不查詢所有 AWS regions

3. **Multi-Region Client 管理**（Phase 1）：
   - 在 `get_elasticache_info()` 方法中為每個 region 建立獨立的 `ElastiCacheClient` 實例
   - 每個實例使用相同的 `profile` 但不同的 `region`
   - 每個實例有獨立的 `_param_cache`（不共享快取）
   - 序列查詢，不使用並行（Phase 2 再優化）

4. **`_convert_to_model()` 方法簽名變更**：
   - 新增 `current_region: str` 參數（必填）
   - `info.region` 使用傳入的 `current_region` 而非 `self.region`
   - `global_ds_map` 查詢改為：`global_ds_map.get(current_region, {}).get(rg_id, {})`
   - 這是 **breaking change**，需要更新所有調用處

5. **結果排序邏輯**：
   - 使用 `sorted(all_results, key=lambda x: x.region)` 按 region 字母順序排序
   - 同一個 region 內，Global Datastore members 和 standalone clusters 混合顯示
   - 不特別分組 Global Datastore members（保持簡單）

6. **進度顯示設計**：
   - `get_elasticache_info()` 接受 `progress: Optional[Progress]` 參數
   - 在 `cli.py` 中建立 Progress 物件並傳入
   - 為每個 region 建立獨立的 task：`progress.add_task(f"查詢 {region}...", total=None)`
   - 成功：`progress.update(task, completed=True)`
   - 失敗：`progress.update(task, completed=True, description=f"❌ {region} (權限不足)")`

7. **錯誤處理策略**（三層 Graceful Degradation）：
   - **Layer 1**：`_get_global_datastores()` 失敗 → 回傳空 dict，Role 欄位為空但其他功能正常
   - **Layer 2**：單一 region 查詢失敗 → 捕捉 `AWSPermissionError` 和 `AWSConnectionError`，記錄警告，繼續查詢其他 regions
   - **Layer 3**：單一 cluster 查詢失敗 → 由 `@handle_aws_errors` decorator 處理，retry 3 次後拋出異常
   - 最終回傳所有成功查詢的結果，不因部分失敗而中斷

8. **向後相容性保證**：
   - `get_elasticache_info()` 回傳型別維持 `List[ElastiCacheInfo]`（不改為 QueryResult）
   - CLI 參數完全不變
   - 單一 region 查詢（無 Global Datastore）行為完全相同
   - 輸出格式（CSV/Markdown）完全不變

9. **測試策略決策**：
   - 使用 `moto[elasticache]` mock AWS ElastiCache API
   - 為 `_get_global_datastores()` 建立專門的測試，mock `describe_global_replication_groups` response
   - 為跨 region 查詢建立整合測試，mock 多個 region 的 responses
   - 測試覆蓋率目標：新增/修改的程式碼 90%+，關鍵路徑 100%

## Implementation Plan

### Tasks (Phase 1 - Sequential Query)

**Task 1: 重構 `_get_global_datastores()` 方法**
   - [ ] 修改回傳型別：`Dict[str, Dict[str, Dict[str, str]]]`
   - [ ] 新結構：`{region: {replication_group_id: {global_datastore_id, role}}}`
   - [ ] 解析 `Members` 陣列，提取 `ReplicationGroupId`, `ReplicationGroupRegion`, `Role`
   - [ ] Role 儲存為大寫 "PRIMARY" / "SECONDARY"（使用 `.upper()` 統一轉換）
   - [ ] 移除舊的 `GlobalNodeGroups` 解析邏輯（第 136-143 行）
   - [ ] 回傳包含所有 regions 的完整 mapping
   - [ ] 單元測試：mock API response with 3 regions（參考下方 Mock Response 範例）

   **Mock Response 範例（完整結構）**：
   ```python
   {
       "GlobalReplicationGroups": [{
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
       }],
       "ResponseMetadata": {
           "RequestId": "mock-request-id",
           "HTTPStatusCode": 200
       }
   }
   ```

**Task 2: 抽取 `_query_single_region()` 輔助方法**
   - [ ] 從 `get_elasticache_info()` 抽取單一 region 查詢邏輯
   - [ ] **方法簽名**：`def _query_single_region(self, region: str, engines: List[str], cluster_filter: Optional[str], global_ds_map: Dict[str, Dict[str, Dict[str, str]]]) -> List[ElastiCacheInfo]`
   - [ ] **新增 import**：確認 `from typing import List, Optional, Dict` 已存在
   - [ ] **實作為 instance method**，使用 `self._get_replication_groups()` 和 `self._get_cache_clusters()`
   - [ ] 包含 Replication Groups 和 Cache Clusters 的查詢邏輯
   - [ ] 調用 `self._convert_to_model(rg, global_ds_map, region, is_replication_group=True/False)`
   - [ ] **錯誤處理**：不在此方法內捕捉異常，讓異常往上拋給 `get_elasticache_info()` 處理
   - [ ] 單元測試：驗證單一 region 查詢正確

**Task 3: 修改 `_convert_to_model()` 方法**
   - [ ] 新增 `current_region: str` 參數（在 `is_replication_group` 之前）
   - [ ] 修改 `global_ds_map` 查詢邏輯：`global_ds_map.get(current_region, {}).get(rg_id, {})`
   - [ ] `info.region` 使用傳入的 `current_region` 參數（約在第 295 行，實際行號可能因前面修改而變動）
   - [ ] **Role 欄位格式化**：從 global_ds_map 取得的 role 是 "PRIMARY"/"SECONDARY"，使用 `.capitalize()` 轉換為 "Primary"/"Secondary"（首字母大寫，其餘小寫）再賦值給 `info.role`
   - [ ] **更新所有調用處**（共 2 處，在 `get_elasticache_info()` 方法中）：
     - Replication Group 處理：`info = self._convert_to_model(rg, global_ds_map, self.region, is_replication_group=True)`
     - Cache Cluster 處理：`info = self._convert_to_model(cluster, global_ds_map, self.region, is_replication_group=False)`
   - [ ] 單元測試：驗證 role 欄位正確填入為 "Primary"/"Secondary"（首字母大寫）

**Task 4: 重構 `get_elasticache_info()` 實作跨 region 查詢**
   - [ ] **修改方法簽名**：`def get_elasticache_info(self, engines: List[str], cluster_filter: Optional[str] = None, progress: Optional['Progress'] = None) -> List[ElastiCacheInfo]`
   - [ ] **新增 import**：`from rich.progress import Progress`（在檔案頂部）
   - [ ] Step 1: 調用 `self._get_global_datastores()` 取得 global_ds_map
   - [ ] Step 2: 識別所有需要查詢的 regions
     - [ ] 建立 set：`regions_to_query = set([self.region])`
     - [ ] 加入 Global Datastore regions：`regions_to_query.update(global_ds_map.keys())`
   - [ ] Step 3: 序列查詢每個 region（`for region in sorted(regions_to_query)`）：
     - [ ] **錯誤捕捉範圍**：整個 region 查詢流程（包含建立 client 和調用 _query_single_region）
     - [ ] 在 try 區塊中：
       - [ ] 為每個 region 建立獨立的 `ElastiCacheClient` 實例：`region_client = ElastiCacheClient(region, self.profile)`
       - [ ] 調用 **region_client** 的 `_query_single_region()` 方法：`results = region_client._query_single_region(region, engines, cluster_filter, global_ds_map)`
       - [ ] 將成功的 results extend 到 `all_results`
     - [ ] 在 except 區塊中捕捉 `(AWSPermissionError, AWSConnectionError, Exception)` as e
     - [ ] 記錄警告：`logger.warning(f"{region} 查詢失敗: {e}")`，但繼續查詢其他 regions
     - [ ] **Progress 處理**：暫時不處理，留給 Task 5 整合
   - [ ] Step 4: 聚合所有結果並按 region 排序：`all_results.sort(key=lambda x: x.region)`
   - [ ] 整合測試：模擬 3 regions 查詢

**Task 5: 整合 Progress 進度顯示**
   - [ ] **前置條件**：Task 4 已完成 `get_elasticache_info()` 的方法簽名修改（包含 `progress` 參數）
   - [ ] **Progress 為 None 時的處理**：完全跳過進度顯示相關程式碼（使用 `if progress:` 條件判斷）
   - [ ] 在 `cli.py` 的 `main()` 函數中：
     - [ ] 將現有的 Progress context manager（約第 131-145 行）擴展為傳入 `client.get_elasticache_info()`
     - [ ] 將 Progress 物件作為參數傳入：`results = client.get_elasticache_info(engines=engines, cluster_filter=cluster, progress=progress)`
   - [ ] 在 `client.py` 的 `get_elasticache_info()` 中，於 Task 4 Step 3 的 region 查詢迴圈內加上：
     - [ ] 迴圈開始時：`if progress: task = progress.add_task(f"正在查詢 {region} 的 ElastiCache 叢集...", total=None)`
     - [ ] try 區塊成功後：`if progress: progress.update(task, completed=True)`
     - [ ] except 區塊失敗時：`if progress: progress.update(task, completed=True, description=f"❌ {region} (權限不足)")`
   - [ ] 手動測試：驗證進度條正確顯示

**Task 6: 錯誤處理增強**
   - [ ] 在 `_get_global_datastores()` 中捕捉 `Exception`（不包含 `BaseException` 如 `KeyboardInterrupt`），gracefully degrade 回傳空 dict
   - [ ] 在跨 region 查詢迴圈中捕捉個別 region 的錯誤（已在 Task 4 中實作）
   - [ ] 記錄 warning log：`logger.warning(f"{region} 查詢失敗: {e}")`
   - [ ] **不收集 failed_regions 列表**：直接記錄 log 即可，不改變回傳型別以保持向後相容性
   - [ ] 單元測試：模擬 region 查詢失敗情境（權限不足、連線失敗、無效 region 名稱）

**Task 7: 向後相容性測試**
   - [ ] **測試案例設計**：每個類別至少 2 個測試案例（正常情況 + 邊界情況）
   - [ ] 測試單一 region 查詢（無 Global Datastore）：
     - [ ] 案例 1：查詢只有 standalone clusters 的 region
     - [ ] 案例 2：查詢空 region（無任何 clusters）
   - [ ] 測試 Memcached clusters（不受影響）：
     - [ ] 案例 1：查詢只有 Memcached 的 region
     - [ ] 案例 2：混合 Redis 和 Memcached 的 region
   - [ ] 測試 cluster filter 功能：
     - [ ] 案例 1：使用萬用字元 filter（例如 "prod-*"）
     - [ ] 案例 2：精確 filter（例如 "my-cluster-001"）
   - [ ] 測試所有 18 個欄位的輸出（至少 1 個完整案例）
   - [ ] 驗證 CSV 和 Markdown 輸出格式（各 1 個案例）

**Task 8: 整合測試與文件更新**
   - [ ] 在實際 AWS 環境測試跨 region 查詢
   - [ ] 驗證 Role 欄位正確顯示
   - [ ] 驗證結果按 region 排序
   - [ ] 更新 README.md（如需要）
   - [ ] **Commit 策略**：每個 Task 一個 commit（Task 內的子任務不單獨 commit），方便 rollback
   - [ ] Commit message 遵循 Conventional Commits 格式：
     - Task 1: `refactor(client): 重構 _get_global_datastores 解析 Members 陣列`
     - Task 2: `refactor(client): 抽取 _query_single_region 輔助方法`
     - Task 3: `refactor(client): 修改 _convert_to_model 支援 current_region 參數`
     - Task 4: `feat(client): 實作跨 region 序列查詢`
     - Task 5: `feat(cli): 整合 Progress 進度顯示`
     - Task 6: `feat(client): 增強錯誤處理與 graceful degradation`
     - Task 7: `test: 新增向後相容性測試`
   - [ ] 建立 PR 前的最終檢查清單

### Acceptance Criteria

**AC1: Global Datastore Members 正確解析**
- Given: 一個 Global Datastore 有 primary 在 us-east-1，secondary 在 ap-northeast-1 和 eu-west-1
- When: 在任一 region 執行查詢
- Then: `global_ds_map` 應包含所有 3 個 regions 的 mapping
- And: 驗證方式為單元測試中 assert `set(global_ds_map.keys()) == {"us-east-1", "ap-northeast-1", "eu-west-1"}`

**AC2: Role 欄位正確顯示**
- Given: 查詢包含 Global Datastore members 的 region
- When: 輸出結果
- Then: Primary member 的 Role 欄位顯示 "Primary"，Secondary members 顯示 "Secondary"（首字母大寫）
- And: 非 Global Datastore 的 clusters，Role 欄位顯示空字串

**AC3: 跨 Region 自動查詢**
- Given: 在 ap-northeast-1 查詢，發現一個 Global Datastore 的 secondary member
- When: 執行查詢
- Then: 自動查詢 primary region (us-east-1) 和其他 secondary regions 的詳細資訊

**AC4: 結果按 Region 排序**
- Given: 查詢結果包含 us-east-1, ap-northeast-1, eu-west-1 的 clusters
- When: 輸出結果
- Then: 順序應為 ap-northeast-1 → eu-west-1 → us-east-1（字母順序）

**AC5: 進度條顯示**
- Given: 需要查詢 3 個 regions
- When: 執行查詢
- Then: 進度條應顯示 "正在查詢 {region} 的 ElastiCache 叢集..."，並在每個 region 完成後更新
- And: 驗證方式為人工目視檢查終端輸出（Rich Progress 的自動化測試較困難）

**AC6: 向後相容性**
- Given: 查詢不包含 Global Datastore 的 region
- When: 執行查詢
- Then: 行為與修改前完全相同，只查詢指定的單一 region

**AC7: 錯誤處理**
- Given: 跨 region 查詢時，其中一個 region 因權限不足而失敗
- When: 執行查詢
- Then: 記錄警告訊息，但繼續查詢其他 regions，並回傳可用的結果

**AC8: CLI 參數不變**
- Given: 現有的 CLI 使用方式
- When: 執行 `get-aws-ec-info -r ap-northeast-1`
- Then: 不需要新增任何參數，自動執行跨 region 查詢

## Additional Context

### Dependencies

- `boto3`：AWS SDK，需要支援多 region client 建立
- `rich`：進度條顯示（已在專案中使用）
- Python 3.8+：語言版本要求
- 無新增外部依賴

### Testing Strategy

1. **單元測試**：
   - Mock `describe_global_replication_groups` API 回應，模擬跨 region Global Datastore（參考 Task 1 的 Mock Response 範例）
   - 測試 `_get_global_datastores()` 正確解析 `Members` 陣列
   - 測試 `_query_single_region()` 正確查詢單一 region
   - 測試 `_convert_to_model()` 正確填入 Role 欄位（"Primary"/"Secondary" 首字母大寫）

2. **整合測試**（手動）：
   - 在實際的 AWS 環境中測試，使用真實的 Global Datastore
   - 驗證跨 region 查詢正確執行
   - 驗證輸出結果的正確性和排序
   - 測試進度條顯示

3. **效能測試**：
   - 測量跨 3 個 regions 查詢的總時間
   - 確認進度條能正確反映查詢進度

### Notes

**Phase 1 實作重點：**

1. **API 權限需求**：
   - 使用者需要對所有相關 regions 有 `elasticache:DescribeGlobalReplicationGroups` 和 `elasticache:DescribeReplicationGroups` 權限
   - 如果某個 region 權限不足，會 gracefully degrade，記錄警告但繼續查詢其他 regions

2. **效能考量（Phase 1 - 序列查詢）**：
   - 跨 region 查詢會增加總查詢時間
   - 假設每個 region 查詢需要 2-3 秒，3 個 regions 約需 6-9 秒
   - 使用進度條清楚顯示查詢進度，提升使用者體驗
   - **可接受的效能目標**：3 regions 在 10 秒內完成

3. **Global Datastore API 行為**：
   - `describe_global_replication_groups` 在任何 region 都會回傳所有 Global Datastores
   - **重要**：預設情況下 `Members` 陣列是**空的**，必須加上 `ShowMemberInfo=True` 參數才能取得完整的跨 region 成員資訊
   - `Members` 陣列包含完整的跨 region 資訊（`ReplicationGroupId`, `ReplicationGroupRegion`, `Role`）
   - 這是實作跨 region 查詢的關鍵資料來源

4. **資料結構變更影響**：
   - `global_ds_map` 的結構從二層改為三層：`{region: {rg_id: {global_ds_id, role}}}`
   - 這是內部資料結構變更，不影響外部 API 或 CLI 參數
   - 需要仔細測試所有使用 `global_ds_map` 的地方（主要是 `_convert_to_model()`）

5. **錯誤處理策略**：
   - **Layer 1 失敗**：`_get_global_datastores()` 失敗 → 回傳空 dict，Role 欄位為空但其他功能正常
   - **Layer 2 失敗**：單一 region 查詢失敗 → 記錄警告，繼續查詢其他 regions
   - **Layer 3 失敗**：單一 cluster 查詢失敗 → 由 `@handle_aws_errors` decorator 處理，retry 3 次

6. **向後相容性保證**：
   - 不改變 CLI 參數和使用方式
   - 不改變輸出格式（CSV/Markdown）
   - 單一 region 查詢（無 Global Datastore）行為完全不變
   - 所有現有欄位的邏輯和格式維持不變

**Phase 2 優化方向（可選的未來改進）**：

**注意**：Phase 2 是可選的效能優化，不是承諾的功能。Phase 1 合併後，根據實際使用情況和需求決定是否實作。

1. **並行查詢優化**：
   - 使用 `concurrent.futures.ThreadPoolExecutor` 實作並行查詢
   - 每個 thread 建立獨立的 boto3 session 和 client（thread-safe）
   - 預期效能：3 regions 從 6-9 秒降到 2-3 秒

2. **跨 region 快取共享**：
   - 實作 class-level `_shared_param_cache` with `threading.Lock`
   - 避免重複查詢相同的 parameter group（例如 `default.redis7`）
   - 預期減少 10-20% 的 API calls

3. **進階功能**：
   - 新增 `--no-cross-region` 參數，允許使用者關閉跨 region 查詢
   - 新增 `--global-datastore` 參數，只查詢特定 Global Datastore 的 members
   - 回傳 `QueryResult` metadata，包含 `queried_regions` 和 `failed_regions`

**重要決策記錄**：

- **為何每個 region 都建立新 client？** 避免 instance method 中 `self.client` 的混淆，邏輯更清晰
- **為何不重用初始 region 的 client？** 保持程式碼一致性，避免特殊處理
- **為何不在 Phase 1 實作並行查詢？** boto3 thread safety 需要仔細測試，先求穩再求快
- **為何不回傳 QueryResult metadata？** 簡化 API，log 記錄已足夠，避免 breaking change

## 實作後發現的問題與解決方案

### 問題：Members 陣列為空

**發現時間**：2026-01-14 實際環境測試

**問題描述**：
在實際 AWS 環境測試時，發現 `describe_global_replication_groups` API 回傳的 `Members` 陣列是空的，導致：
1. `global_ds_map` 為空
2. Role 欄位無法正確填入
3. 無法識別其他 regions 的 Global Datastore 成員

**根本原因**：
AWS ElastiCache API 的 `describe_global_replication_groups` 方法預設**不回傳 Members 陣列資訊**。需要明確指定 `ShowMemberInfo=True` 參數才能取得完整的成員列表。

**API 行為對比**：

```python
# 預設行為（Members 為空）
response = client.describe_global_replication_groups()
# 回傳：
# {
#   "GlobalReplicationGroups": [{
#     "GlobalReplicationGroupId": "global-ds-001",
#     "Members": []  # 空陣列
#   }]
# }

# 正確用法（加上 ShowMemberInfo=True）
response = client.describe_global_replication_groups(ShowMemberInfo=True)
# 回傳：
# {
#   "GlobalReplicationGroups": [{
#     "GlobalReplicationGroupId": "global-ds-001",
#     "Members": [
#       {
#         "ReplicationGroupId": "cluster-primary",
#         "ReplicationGroupRegion": "eu-central-1",
#         "Role": "PRIMARY",
#         "Status": "associated"
#       },
#       {
#         "ReplicationGroupId": "cluster-secondary",
#         "ReplicationGroupRegion": "eu-west-3",
#         "Role": "SECONDARY",
#         "Status": "associated"
#       }
#     ]
#   }]
# }
```

**解決方案**：

在 `_get_global_datastores()` 方法中，修改 paginator 呼叫加上 `ShowMemberInfo=True` 參數：

```python
# 修改前
page_iterator = paginator.paginate()

# 修改後
page_iterator = paginator.paginate(ShowMemberInfo=True)
```

**驗證結果**：
- ✅ 成功取得所有 regions 的 Global Datastore 成員資訊
- ✅ Role 欄位正確顯示 "Primary" / "Secondary"
- ✅ 自動探索並查詢所有相關 regions
- ✅ 所有 63 個單元測試通過

**影響範圍**：
- 修改檔案：`elasticache_info/aws/client.py`
- 修改行數：1 行（加上參數）
- 向後相容性：完全相容，不影響現有功能

**經驗教訓**：
1. AWS API 文件中的可選參數可能對功能有關鍵影響
2. 實際環境測試非常重要，mock 測試可能無法發現 API 行為的細節
3. 當 API 回傳空陣列時，需要檢查是否有參數可以控制回傳內容的詳細程度
