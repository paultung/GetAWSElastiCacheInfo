---
title: '修正 ElastiCache Info 輸出欄位格式與資料錯誤'
slug: 'fix-elasticache-output-fields'
created: '2026-01-14'
completed: '2026-01-14'
status: 'completed'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.8+', 'boto3', 'AWS ElastiCache API']
files_to_modify: ['elasticache_info/field_formatter.py', 'elasticache_info/aws/client.py']
code_patterns: ['Formatter pattern', 'AWS API response parsing']
test_patterns: ['Unit tests for formatters']
---

# Tech-Spec: 修正 ElastiCache Info 輸出欄位格式與資料錯誤

**Created:** 2026-01-14

## Overview

### Problem Statement

AWS ElastiCache Info CLI 工具的輸出結果中存在兩個資料錯誤和兩個格式問題：

1. **資料錯誤**：
   - Engine Version 欄位為空，無法顯示 cluster 的引擎版本
   - Maintenance Window 欄位為空，無法顯示 cluster 的維護時間

2. **格式問題**：
   - Slow Logs 未設定時顯示 "N/A"，應改為 "Disabled" 以保持一致性
   - Backup Window 時間缺少時區標示，應加上 "UTC" 字樣

### Solution

修改兩個核心檔案：

1. **`field_formatter.py`**：調整 `format_slow_logs()` 和 `format_backup()` 方法的輸出格式
2. **`client.py`**：修正 `_convert_to_model()` 方法中 Engine Version 和 Maintenance Window 的資料擷取邏輯

### Scope

**In Scope (Phase 1 - Confirmed Fixes):**
- 修改 `FieldFormatter.format_slow_logs()` 方法，將 "N/A" 改為 "Disabled"
- 修改 `FieldFormatter.format_backup()` 方法，在時間後方加上 " UTC" 字樣
- 修正 `ElastiCacheClient._convert_to_model()` 中 Replication Group 的 Engine Version 擷取邏輯
- 更新相關單元測試以符合新的輸出格式

**Deferred (Phase 2 - Requires Investigation):**
- Maintenance Window 欄位空白問題 - 需要先查看實際 API 回應確認正確欄位名稱

**Out of Scope:**
- 其他欄位的邏輯和格式
- CLI 參數和使用者介面
- Cache Cluster (Memcached) 的處理邏輯（已正常運作）
- 輸出檔案格式（CSV/Markdown）
- 錯誤處理機制

## Context for Development

### Codebase Patterns

1. **Formatter Pattern**：使用 `FieldFormatter` 類別的靜態方法處理複雜欄位的格式化
2. **AWS API Response Parsing**：在 `_convert_to_model()` 方法中將 AWS API 回應轉換為 `ElastiCacheInfo` 模型
3. **4-Layer Query Architecture**：工具使用分層查詢架構，從 Global Datastore 到 Parameter Group
4. **Graceful Degradation**：當 API 查詢失敗時，使用預設值而非中斷執行

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `elasticache_info/field_formatter.py` | 包含所有欄位格式化邏輯 |
| `elasticache_info/aws/client.py` | AWS API 查詢和資料轉換邏輯 |
| `elasticache_info/aws/models.py` | ElastiCacheInfo 資料模型定義 |
| `tests/test_field_formatter.py` | FieldFormatter 的單元測試 |
| `output/elasticache-ap-northeast-1-20260114-104834.csv` | 當前輸出範例（顯示問題） |

### Technical Decisions

1. **Slow Logs "Disabled" vs "N/A"**：
   - 當 `slower_than` 或 `max_len` 為 `None` 時（無法取得參數），維持顯示 "Disabled"
   - 這樣可以與其他 Enabled/Disabled 欄位保持一致性
   - 原本的 "N/A" 會讓使用者誤以為功能不適用

2. **Backup Window UTC 標示**：
   - 在時間字串後方加上 " UTC" 以明確標示時區
   - 格式：`20:00-21:00 UTC/5 days`
   - 只在有時間窗口時加上 UTC，"Disabled" 和 "N/A" 不加

3. **Engine Version 擷取**：
   - 優先使用 `CacheClusterEngineVersion` 欄位（如果存在）
   - 其次使用 Replication Group 的 member cluster 的 `EngineVersion`
   - 最後使用 Replication Group 本身的 `EngineVersion` 欄位

4. **Maintenance Window 擷取**：
   - 直接從 Replication Group 的 `PreferredMaintenanceWindow` 欄位取得
   - 該欄位應該始終存在，如果為空則顯示空字串

## Implementation Plan

### Tasks (Phase 1)

1. **修改 `field_formatter.py`**
   - [ ] 修改 `format_slow_logs()` 方法：將回傳值從 "N/A" 改為 "Disabled"
   - [ ] 修改 `format_backup()` 方法：在時間窗口字串後加上 " UTC"

2. **修改 `client.py`**
   - [ ] 修正 `_convert_to_model()` 中 Replication Group 的 Engine Version 邏輯（第 326 行）

3. **更新測試**
   - [ ] 更新 `tests/test_field_formatter.py` 中 `format_slow_logs()` 的測試案例
   - [ ] 更新 `tests/test_field_formatter.py` 中 `format_backup()` 的測試案例

4. **驗證**
   - [ ] 執行單元測試確認無迴歸
   - [ ] 建立備份後執行修改

### Tasks (Phase 2 - Deferred)

5. **調查 Maintenance Window**
   - [ ] 使用 boto3 直接查詢 Replication Group，印出完整 API 回應
   - [ ] 確認 `PreferredMaintenanceWindow` 欄位是否存在及其值
   - [ ] 根據調查結果修正程式碼

### Acceptance Criteria

**AC1: Slow Logs 格式修正**
- Given: Parameter Group 的 slow log 參數為 None
- When: 格式化 slow logs 欄位
- Then: 輸出應為 "Disabled" 而非 "N/A"

**AC2: Backup Window UTC 標示**
- Given: Backup window 為 "20:00-21:00"，retention 為 5 天
- When: 格式化 backup 欄位
- Then: 輸出應為 "20:00-21:00 UTC/5 days"

**AC3: Backup Disabled 不加 UTC**
- Given: Backup retention 為 0
- When: 格式化 backup 欄位
- Then: 輸出應為 "Disabled"（不加 UTC）

**AC4: Engine Version 正確顯示**
- Given: Replication Group 有 engine version 資訊
- When: 查詢 ElastiCache 資訊
- Then: Engine Version 欄位應顯示正確的版本號（例如：7.1）

**AC5: Maintenance Window 正確顯示**
- Given: Replication Group 有 maintenance window 設定
- When: 查詢 ElastiCache 資訊
- Then: Maintenance Window 欄位應顯示正確的時間窗口（例如：sun:17:00-sun:18:00）

**AC6: 其他欄位不受影響**
- Given: 執行完整的 ElastiCache 查詢
- When: 輸出結果
- Then: 所有其他欄位（Region, Type, Name, Node Type 等）應維持原有格式和邏輯

## Additional Context

### Dependencies

- `boto3`：AWS SDK，用於查詢 ElastiCache API
- Python 3.8+：語言版本要求
- 無新增外部依賴

### Testing Strategy

1. **單元測試**：
   - 測試 `format_slow_logs()` 在不同參數組合下的輸出
   - 測試 `format_backup()` 在不同 window 和 retention 組合下的輸出
   - 確保邊界條件處理正確（None, 0, 負數等）

2. **整合測試**（手動）：
   - 執行 CLI 工具查詢實際的 AWS ElastiCache clusters
   - 驗證輸出 CSV 檔案中的欄位格式正確
   - 比對修正前後的輸出差異

### Notes

1. **Engine Version 問題根因**：
   - 目前程式碼在第 326 行使用 `rg_or_cluster.get("CacheClusterCreateTime", "")` 賦值給 `engine_version`
   - 這是錯誤的欄位，應該使用 `EngineVersion` 或從 member cluster 取得

2. **Maintenance Window 問題根因**：
   - 需要實際測試確認 API 回應中該欄位的存在性
   - 可能是 API 回應中該欄位為空字串，而非不存在

3. **向後相容性**：
   - 這些修改只影響輸出格式，不影響 API 查詢邏輯
   - 現有的 CLI 參數和使用方式完全不變
   - 使用者可能需要更新依賴此輸出格式的下游系統（如果有的話）
