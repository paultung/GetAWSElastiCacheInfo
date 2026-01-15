---
title: 'AWS ElastiCache Info CLI Tool'
slug: 'aws-elasticache-info-cli'
created: '2026-01-12'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.8+', 'Typer', 'boto3', 'Rich', 'uv', 'pytest', 'moto']
files_to_modify: ['elasticache_info/cli.py', 'elasticache_info/aws/client.py', 'elasticache_info/aws/models.py', 'elasticache_info/aws/exceptions.py', 'elasticache_info/field_formatter.py', 'elasticache_info/formatters/csv_formatter.py', 'elasticache_info/formatters/markdown_formatter.py', 'elasticache_info/formatters/base.py', 'elasticache_info/utils.py', 'pyproject.toml', 'README.md', '.gitignore']
code_patterns: ['Dataclass models', 'Layered AWS API queries', 'Formatter pattern', 'boto3 Paginator', 'Rich Progress/Table', 'Error handling with graceful degradation']
test_patterns: ['pytest', 'Mock boto3 with moto', 'Unit tests for formatters', 'Integration tests for AWS client', 'E2E tests with CliRunner']
---

# Tech-Spec: AWS ElastiCache Info CLI Tool

**Created:** 2026-01-12

## Overview

### Problem Statement

需要一個方便的 CLI 工具來快速查詢和匯出 AWS ElastiCache 的詳細資訊，支援不同的引擎類型（Redis OSS、Valkey、Memcached），可靈活選擇要顯示的欄位，並以結構化的格式（CSV 或 Markdown）輸出到檔案，方便後續分析和文件化。

### Solution

使用 Python + Typer 建立 CLI 工具，透過 boto3 查詢 AWS ElastiCache API（包含 Global Datastore、Replication Groups、Cache Clusters、Parameter Groups），使用 Rich 進行終端機表格顯示，支援匯出為 CSV 或 Markdown 格式。

### Scope

**In Scope:**

1. **引擎支援**：Redis OSS、Valkey、Memcached

2. **18 個可選資訊欄位**（預設全選）：
   - Region - AWS Region 名稱
   - Type - Cache 類型（Redis/Memcached/Valkey）
   - Global Datastore/Cluster Name - 全球資料存放區或叢集名稱
   - Role - 角色（Primary/Secondary，僅 Global Datastore）
   - Node Type - 節點類型
   - Engine Version - 引擎版本
   - Cluster Mode - 叢集模式（Enabled/Disabled）
   - Shards - 分片數量
   - Number of nodes - 節點數量
   - Multi-AZ - 多可用區（Enabled/Disabled）
   - Auto-failover - 自動故障轉移（Enabled/Disabled）
   - Encryption in transit - 傳輸加密（Enabled/Disabled）
   - Encryption at rest - 靜態加密（Enabled/Disabled）
   - Slow logs/SlowerThan/MaxLen - Slow logs 狀態及參數
   - Engine logs - 引擎日誌（Enabled/Disabled）
   - Maintenance window - 維護窗口時間
   - Auto upgrade minor versions - 自動升級小版本（Enabled/Disabled）
   - Backup window/Retention - 備份窗口及保留期

3. **CLI 參數**：
   - `--region` / `-r`：AWS Region（必填）
   - `--profile` / `-p`：AWS Profile（選填，預設 `default`）
   - `--engine` / `-e`：引擎類型篩選（選填，預設所有：`redis,valkey,memcached`）
   - `--cluster` / `-c`：叢集名稱篩選，支援萬用字元（選填，預設所有叢集）
   - `--info-type` / `-i`：欄位選擇（選填，預設 `all`）
   - `--output-format` / `-f`：輸出格式（csv/markdown，選填，預設 `csv`）
   - `--output-file` / `-o`：輸出檔案路徑（選填，預設 `./output/`，自動建立目錄）
   - `--verbose` / `-v`：啟用詳細日誌輸出（選填，預設關閉）

4. **特殊邏輯**：
   - Global Datastore 偵測和名稱格式化（`global-name/cluster-name`）
   - Parameter Group 查詢（slow logs 參數：`slowlog-log-slower-than`、`slowlog-max-len`）
   - 備份設定查詢
   - 萬用字元叢集名稱篩選
   - 多引擎查詢和篩選
   - 自動建立輸出目錄

**Out of Scope:**

- 修改或建立 ElastiCache 資源（唯讀工具）
- CloudWatch Metrics 即時查詢
- 即時監控或持續輪詢
- GUI 介面
- 其他 AWS 服務的整合
- 歷史資料分析

## Context for Development

### Codebase Patterns

這是一個全新的專案（Greenfield），採用模組化結構：

**專案結構：**
```
GetAWSElastiCacheInfo/
├── elasticache_info/
│   ├── __init__.py
│   ├── cli.py                    # Typer CLI 入口點
│   ├── aws/
│   │   ├── __init__.py
│   │   ├── client.py             # boto3 ElastiCache 客戶端封裝
│   │   ├── models.py             # 資料模型（ElastiCacheInfo dataclass）
│   │   └── exceptions.py         # 自訂異常類別
│   ├── formatters/
│   │   ├── __init__.py
│   │   ├── base.py               # 基礎 Formatter 介面
│   │   ├── csv_formatter.py     # CSV 輸出
│   │   └── markdown_formatter.py # Markdown 表格輸出
│   ├── field_formatter.py        # 複合欄位格式化
│   └── utils.py                  # 工具函數
├── tests/
│   ├── test_cli.py
│   ├── test_aws_client.py
│   ├── test_formatters.py
│   └── test_field_formatter.py
├── output/                        # 預設輸出目錄
├── pyproject.toml                 # uv 專案配置
├── README.md
└── LICENSE
```

**設計模式：**

1. **分層查詢架構**（Winston 建議）：
   - Layer 1: Global Datastore Discovery
   - Layer 2: Replication Group Enumeration
   - Layer 3: Cache Cluster Details
   - Layer 4: Parameter Group Queries

2. **Dataclass 資料模型**：使用 `@dataclass` 定義 `ElastiCacheInfo`，包含所有 18 個欄位

3. **Formatter 模式**：基礎 Formatter 介面，CSV 和 Markdown 實作繼承

4. **複合欄位格式化器**（Barry 建議）：
   - `format_slow_logs()` → `Enabled/10000/128` 或 `Disabled`
   - `format_backup()` → `00:00-01:00 UTC/35 days` 或 `Disabled`
   - `format_cluster_name()` → `global-ds-name/cluster-name` 或 `cluster-name`

5. **錯誤處理**：
   - 清楚的中文錯誤訊息
   - 優雅降級（欄位查詢失敗顯示 `N/A`）
   - 處理權限不足、Region 不存在等情況

6. **使用者體驗**：
   - Rich Progress 進度指示器
   - Rich Table 終端顯示

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `elasticache_info/cli.py` | Typer CLI 主程式，定義所有 CLI 參數 |
| `elasticache_info/aws/client.py` | boto3 封裝，處理所有 AWS API 呼叫和分頁 |
| `elasticache_info/aws/models.py` | ElastiCacheInfo dataclass 定義 |
| `elasticache_info/field_formatter.py` | 複合欄位格式化邏輯 |
| `elasticache_info/formatters/csv_formatter.py` | CSV 輸出實作 |
| `elasticache_info/formatters/markdown_formatter.py` | Markdown 表格輸出實作 |
| `elasticache_info/utils.py` | 萬用字元匹配、目錄建立等工具函數 |
| `pyproject.toml` | uv 專案配置，定義依賴和 CLI 入口點 |
| `tests/test_*.py` | pytest 測試檔案 |

### Technical Decisions

- **CLI 框架**：使用 Typer 提供現代化的 CLI 介面和自動文件生成
- **AWS SDK**：使用 boto3 作為 AWS API 的標準 Python SDK，使用內建 Paginator 處理分頁
- **表格顯示**：使用 Rich 提供美觀的終端機表格輸出和進度指示器
- **輸出格式**：支援 CSV（機器可讀）和 Markdown（人類可讀）
- **Python 版本**：Python 3.8+
- **套件管理**：使用 `uv` 提供快速的依賴解析和執行
- **CLI 入口點**：`get-aws-ec-info`，透過 pyproject.toml 的 `[project.scripts]` 定義
- **測試框架**：pytest + moto（AWS mock library）
- **專案結構**：採用模組化設計，分離 CLI、AWS 查詢邏輯、格式化輸出等功能

## Implementation Plan

### Tasks

#### Phase 1: 專案基礎設定

- [ ] Task 1: 建立專案結構和 pyproject.toml
  - File: `pyproject.toml`
  - Action: 建立 uv 專案配置檔，定義專案名稱、版本、依賴套件（typer, boto3, rich, pytest, moto）
  - Action: 設定初始版本號為 `0.1.0`（遵循 Semantic Versioning 2.0.0）
  - Action: 版本號管理策略：
    - `0.x.y`：開發階段，API 可能變動
    - `1.0.0`：第一個穩定版本，所有功能完成且測試通過
    - `x.y.z`：
      - `x`（Major）：不相容的 API 變更
      - `y`（Minor）：向後相容的功能新增
      - `z`（Patch）：向後相容的錯誤修正
  - Action: 設定 CLI 入口點 `[project.scripts]` 為 `get-aws-ec-info = "elasticache_info.cli:app"`
  - Notes: 確保 Python 版本要求為 3.8+，版本號也需在 `elasticache_info/__init__.py` 中定義 `__version__` 變數

- [ ] Task 2: 建立目錄結構
  - Files: `elasticache_info/__init__.py`, `elasticache_info/aws/__init__.py`, `elasticache_info/formatters/__init__.py`, `tests/__init__.py`, `output/.gitkeep`
  - Action: 建立所有必要的目錄和 `__init__.py` 檔案
  - Action: 建立預設輸出目錄 `output/` 並加入 `.gitkeep` 檔案（保留空目錄結構）
  - Notes: 確保套件可正確匯入，`.gitkeep` 確保 output 目錄被 git 追蹤但內容被忽略

#### Phase 2: 資料模型與格式化器

- [ ] Task 3: 實作 ElastiCacheInfo 資料模型
  - File: `elasticache_info/aws/models.py`
  - Action: 使用 `@dataclass` 定義 `ElastiCacheInfo` 類別，包含 18 個欄位，型別定義如下：
    - `region: str` - AWS Region 名稱
    - `type: str` - Cache 類型（Redis/Memcached/Valkey）
    - `name: str` - Global Datastore/Cluster Name（複合欄位）
    - `role: str` - 角色（Primary/Secondary 或空字串）
    - `node_type: str` - 節點類型
    - `engine_version: str` - 引擎版本
    - `cluster_mode: str` - 叢集模式（Enabled/Disabled）
    - `shards: int` - 分片數量
    - `nodes: int` - 節點數量
    - `multi_az: str` - 多可用區（Enabled/Disabled）
    - `auto_failover: str` - 自動故障轉移（Enabled/Disabled）
    - `encryption_transit: str` - 傳輸加密（Enabled/Disabled）
    - `encryption_rest: str` - 靜態加密（Enabled/Disabled）
    - `slow_logs: str` - Slow logs（複合欄位，格式：Enabled/10000/128 或 Disabled）
    - `engine_logs: str` - 引擎日誌（Enabled/Disabled）
    - `maintenance_window: str` - 維護窗口時間
    - `auto_upgrade: str` - 自動升級小版本（Enabled/Disabled）
    - `backup: str` - 備份（複合欄位，格式：00:00-01:00 UTC/35 days 或 Disabled）
  - Action: 所有欄位設定預設值為空字串或 0（針對 int 欄位）
  - Notes: 欄位順序應與輸出順序一致

- [ ] Task 4: 實作複合欄位格式化器
  - File: `elasticache_info/field_formatter.py`
  - Action: 實作 `FieldFormatter` 類別，包含以下靜態方法：
    - `format_slow_logs(slower_than: Optional[int], max_len: Optional[int]) -> str`
      - 判斷邏輯：如果 `slower_than` 和 `max_len` 都不是 None 且 `slower_than > 0`，則視為 Enabled
      - Enabled 格式：`f"Enabled/{slower_than}/{max_len}"`
      - Disabled 格式：`"Disabled"`
      - 如果參數為 None 或查詢失敗：返回 `"N/A"`
    - `format_backup(window: Optional[str], retention_days: Optional[int]) -> str`
      - 判斷邏輯：如果 `retention_days` 不是 None 且 > 0，且 `window` 不是 None，則視為 Enabled
      - Enabled 格式：`f"{window}/{retention_days} days"`
      - Disabled 格式：`"Disabled"`
      - 如果 `retention_days > 0` 但 `window` 為 None：返回 `f"Enabled/{retention_days} days"（無窗口資訊）`
      - 如果參數為 None：返回 `"N/A"`
    - `format_cluster_name(global_ds_id: Optional[str], cluster_id: str) -> str`
      - 有 Global DS：`f"{global_ds_id}/{cluster_id}"`
      - 無 Global DS：`cluster_id`
    - `format_enabled_disabled(value: Optional[bool]) -> str`
      - True → "Enabled"
      - False → "Disabled"
      - None → "N/A"
  - Notes: 所有方法都需處理 None 值並返回適當的預設值

- [ ] Task 5: 實作基礎 Formatter 介面
  - File: `elasticache_info/formatters/base.py`
  - Action: 定義抽象基礎類別 `BaseFormatter`，包含 `format(data: List[ElastiCacheInfo], fields: List[str]) -> str` 方法
  - Notes: 使用 ABC (Abstract Base Class)

- [ ] Task 6: 實作 CSV Formatter
  - File: `elasticache_info/formatters/csv_formatter.py`
  - Action: 繼承 `BaseFormatter`，實作 `format()` 方法
  - Action: 使用 Python 內建 `csv` 模組生成 CSV 格式
  - Notes: 確保正確處理逗號和換行符號

- [ ] Task 7: 實作 Markdown Formatter
  - File: `elasticache_info/formatters/markdown_formatter.py`
  - Action: 繼承 `BaseFormatter`，實作 `format()` 方法
  - Action: 生成 Markdown 表格格式（使用 `|` 分隔）
  - Action: 表格對齊方式：
    - 標題列：使用 `|` 分隔欄位名稱
    - 分隔列：使用 `|---|---|---|` 格式（左對齊）
    - 數值欄位（shards, nodes）：右對齊 `|---:|`
    - 其他欄位：左對齊 `|---|`
  - Notes: 標準 Markdown 表格格式，相容於 GitHub、GitLab 等平台

#### Phase 3: AWS 客戶端實作

- [ ] Task 8: 實作 ElastiCache 客戶端 - 基礎架構
  - File: `elasticache_info/aws/client.py`
  - Action: 建立 `ElastiCacheClient` 類別，初始化 boto3 客戶端
  - Action: 實作建構子，接受 `region`, `profile` 參數，使用 boto3 session 支援 profile
  - Action: 實作錯誤處理裝飾器 `@handle_aws_errors`，行為定義：
    - 捕捉 `ClientError`：
      - 權限錯誤（AccessDenied, UnauthorizedOperation）→ 拋出自訂 `AWSPermissionError` 異常，包含清楚的中文錯誤訊息
      - 無效參數（InvalidParameterValue）→ 拋出自訂 `AWSInvalidParameterError` 異常
      - 其他 ClientError → 拋出自訂 `AWSAPIError` 異常，包含原始錯誤訊息
    - 捕捉 `NoCredentialsError`：拋出自訂 `AWSCredentialsError` 異常
    - 捕捉 `BotoCoreError`：拋出自訂 `AWSConnectionError` 異常
    - 實作 exponential backoff 重試機制（最多 3 次，針對 throttling 錯誤）
  - Notes: 所有自訂異常應包含清楚的中文錯誤訊息和建議的解決方案

- [ ] Task 8.5: 定義自訂異常類別
  - File: `elasticache_info/aws/exceptions.py`
  - Action: 定義以下自訂異常類別（繼承自 `Exception`）：
    - `AWSPermissionError` - 權限不足錯誤
    - `AWSInvalidParameterError` - 無效參數錯誤
    - `AWSAPIError` - 一般 AWS API 錯誤
    - `AWSCredentialsError` - AWS 認證錯誤
    - `AWSConnectionError` - AWS 連線錯誤
  - Action: 每個異常類別都應包含：
    - `message: str` - 中文錯誤訊息
    - `suggestion: Optional[str]` - 建議的解決方案
    - `original_error: Optional[Exception]` - 原始異常（用於除錯）
  - Notes: 在 `client.py` 中 import 這些異常類別使用

- [ ] Task 9: 實作 Layer 1 - Global Datastore Discovery
  - File: `elasticache_info/aws/client.py`
  - Action: 實作 `_get_global_datastores() -> Dict[str, Dict[str, str]]` 方法
  - Action: 使用 `describe_global_replication_groups()` API 和 Paginator
  - Action: 建立 Global Datastore 映射字典，結構為：
    ```python
    {
      "replication_group_id": {
        "global_datastore_id": "global-ds-name",
        "role": "Primary" or "Secondary"
      }
    }
    ```
  - Action: 映射字典邏輯：
    - **只包含**屬於 Global Datastore 的 Replication Group
    - 不屬於 Global Datastore 的 Replication Group **不會出現**在字典中
    - 在 Task 13 中，透過 `replication_group_id in global_ds_map` 判斷是否屬於 Global Datastore
    - 如果 `replication_group_id` 不在字典中，表示該叢集不屬於任何 Global Datastore
  - Action: 返回空字典 `{}` 如果沒有任何 Global Datastore
  - Notes: 此映射字典將在 Task 13 中用於判斷叢集是否屬於 Global Datastore

- [ ] Task 10: 實作 Layer 2 - Replication Group Enumeration
  - File: `elasticache_info/aws/client.py`
  - Action: 實作 `_get_replication_groups(engine_filter: List[str])` 方法
  - Action: 使用 `describe_replication_groups()` API 和 Paginator
  - Action: 根據 engine 參數篩選，引擎判斷邏輯：
    - 從 ReplicationGroup 的 `CacheNodeType` 和 `Engine` 欄位判斷
    - AWS API 中 Valkey 會被標記為 `Engine: "valkey"`（AWS 7.x 版本後支援）
    - Redis OSS 標記為 `Engine: "redis"`
    - 如果 engine_filter 包含 "redis" 或 "valkey"，則篩選對應的引擎
  - Notes: Memcached 不使用 Replication Groups，在 Task 11 中處理

- [ ] Task 11: 實作 Layer 3 - Cache Cluster Details
  - File: `elasticache_info/aws/client.py`
  - Action: 實作 `_get_cache_clusters(engine_filter: List[str])` 方法
  - Action: 使用 `describe_cache_clusters()` API 和 Paginator
  - Action: 根據 engine 參數篩選（memcached）
  - Notes: 取得 `show_cache_node_info=True` 以獲取節點詳細資訊

- [ ] Task 12: 實作 Layer 4 - Parameter Group Queries
  - File: `elasticache_info/aws/client.py`
  - Action: 實作 `_get_parameter_group_params(parameter_group_name: str) -> Dict[str, str]` 方法
  - Action: 使用 `describe_cache_parameters()` API 和 Paginator
  - Action: 提取 `slowlog-log-slower-than` 和 `slowlog-max-len` 參數
  - Action: 實作快取機制：
    - 在 `ElastiCacheClient` 類別中建立實例變數 `self._param_cache: Dict[str, Dict[str, str]] = {}`
    - 快取結構：`{"parameter_group_name": {"slowlog-log-slower-than": "10000", "slowlog-max-len": "128"}}`
    - 在查詢前檢查快取，如果存在則直接返回
    - 查詢後將結果存入快取
    - 快取生命週期：整個 CLI 執行期間（單次查詢）
  - Notes: 相同 Parameter Group 只查詢一次，大幅提升效能

- [ ] Task 13: 實作資料轉換邏輯
  - File: `elasticache_info/aws/client.py`
  - Action: 實作 `_convert_to_model(rg_or_cluster, global_ds_map, region)` 方法
  - Action: 將 AWS API 回應轉換為 `ElastiCacheInfo` 物件
  - Action: 欄位資料來源映射：
    - **Engine logs**：從 `LogDeliveryConfigurations` 欄位判斷
      - 檢查是否有 `LogType: "engine-log"` 且 `LogFormat: "json"` 或 `"text"`
      - 如果存在且 `DestinationDetails` 不為空，則為 "Enabled"
      - 否則為 "Disabled"
    - **其他欄位**：從 ReplicationGroup 或 CacheCluster 的對應欄位提取
  - Action: None 值處理職責分工：
    - **此方法負責**：從 AWS API 回應中提取原始值，如果欄位不存在則傳遞 None 給 FieldFormatter
    - **FieldFormatter 負責**：將 None 值轉換為使用者友善的字串（"N/A", "Disabled" 等）
    - 範例：如果 API 回應中沒有 `SnapshotWindow`，傳遞 `None` 給 `format_backup(None, retention_days)`，由 FieldFormatter 決定顯示 "Disabled" 或 "N/A"
  - Action: 呼叫 `FieldFormatter` 處理所有複合欄位（slow_logs, backup, cluster_name）
  - Action: 使用 try-except 包裝 Parameter Group 查詢，失敗時傳遞 None 給 FieldFormatter
  - Notes: 保持資料轉換邏輯簡單，將格式化邏輯集中在 FieldFormatter

- [ ] Task 14: 實作主查詢方法
  - File: `elasticache_info/aws/client.py`
  - Action: 實作 `get_elasticache_info(engines: List[str], cluster_filter: Optional[str]) -> List[ElastiCacheInfo]` 方法
  - Action: 協調所有 4 層查詢
  - Action: 整合 Rich Progress 進度指示器
  - Action: 實作叢集名稱萬用字元篩選
  - Action: 從建構子中的 `self.region` 取得 region 資訊，傳遞給 `_convert_to_model()` 方法
  - Notes: 這是對外的主要 API，region 資訊來自 ElastiCacheClient 建構子的參數

#### Phase 4: 工具函數與日誌

- [ ] Task 15: 實作工具函數
  - File: `elasticache_info/utils.py`
  - Action: 實作 `match_wildcard(pattern: str, text: str) -> bool` - 萬用字元匹配
  - Action: 實作 `ensure_output_dir(path: str) -> str` - 確保輸出目錄存在
  - Action: 實作 `parse_engines(engine_str: str) -> List[str]` - 解析引擎參數
  - Action: 實作 `parse_info_types(info_type_str: str) -> List[str]` - 解析欄位參數
    - 定義有效欄位清單（CLI 參數格式，使用連字號）：`VALID_FIELDS = ["region", "type", "name", "role", "node-type", "engine-version", "cluster-mode", "shards", "nodes", "multi-az", "auto-failover", "encryption-transit", "encryption-rest", "slow-logs", "engine-logs", "maintenance-window", "auto-upgrade", "backup"]`
    - 定義欄位名稱映射（CLI 參數 → dataclass 欄位）：`FIELD_MAPPING = {"node-type": "node_type", "engine-version": "engine_version", ...}`
    - 如果 info_type_str 是 "all"，返回所有有效欄位（dataclass 格式，使用底線）
    - 否則以逗號分隔，驗證每個欄位名稱，並轉換為 dataclass 格式
    - 如果發現無效欄位，拋出 `ValueError` 異常，訊息包含無效欄位名稱和有效欄位清單
    - 範例錯誤訊息：「無效的欄位名稱：'invalid-field'。有效欄位：region, type, name, node-type, ...」
    - 返回的欄位清單使用 dataclass 格式（底線），以便直接從 ElastiCacheInfo 物件中提取
  - Action: 實作 `setup_logger(verbose: bool = False) -> logging.Logger` - 設定日誌記錄器
  - Notes: 使用 `fnmatch` 模組處理萬用字元

- [ ] Task 15.5: 實作日誌策略
  - File: `elasticache_info/aws/client.py` 和 `elasticache_info/cli.py`
  - Action: 使用 Python 標準 `logging` 模組
  - Action: 日誌層級：
    - INFO：記錄主要操作（開始查詢、完成查詢、檔案輸出）
    - DEBUG：記錄 API 呼叫詳細資訊（API 名稱、參數、回應時間）
    - WARNING：記錄非致命錯誤（Parameter Group 查詢失敗、部分欄位缺失）
    - ERROR：記錄致命錯誤（權限不足、Region 不存在）
  - Action: 日誌輸出：
    - 預設輸出到 stderr（不影響 stdout 的表格顯示）
    - 可選：透過 `--verbose` 或 `-v` 參數啟用 DEBUG 層級
  - Action: 日誌格式：`%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  - Notes: 在所有 AWS API 呼叫前後記錄日誌，方便除錯和效能分析

#### Phase 5: CLI 實作

- [ ] Task 16: 實作 Typer CLI 主程式
  - File: `elasticache_info/cli.py`
  - Action: 建立 Typer app 實例
  - Action: 定義主命令函數，包含所有 CLI 參數：
    - `--region / -r` (必填)
    - `--profile / -p` (選填，預設 "default")
    - `--engine / -e` (選填，預設 "redis,valkey,memcached")
    - `--cluster / -c` (選填)
    - `--info-type / -i` (選填，預設 "all")
    - `--output-format / -f` (選填，預設 "csv")
    - `--output-file / -o` (選填，預設 "./output/")
    - `--verbose / -v` (選填，flag，預設 False)
  - Action: 實作參數驗證邏輯
  - Action: 根據 `--verbose` 參數設定日誌層級（呼叫 `setup_logger(verbose)`）
  - Notes: 使用 Typer 的型別提示和預設值

- [ ] Task 17: 整合所有元件
  - File: `elasticache_info/cli.py`
  - Action: 在主命令函數中整合：
    1. 解析和驗證參數（包含欄位選擇）
    2. 建立 `ElastiCacheClient` 實例
    3. 呼叫 `get_elasticache_info()` 查詢資料
    4. 使用 Rich Table 在終端顯示結果（**根據 `--info-type` 參數篩選顯示的欄位**）
    5. 選擇適當的 Formatter 並輸出到檔案（**同樣根據 `--info-type` 參數篩選欄位**）
  - Action: 欄位選擇邏輯：
    - 如果 `--info-type` 指定了特定欄位，則終端顯示和檔案輸出都只包含這些欄位
    - Rich Table 和 Formatter 都接收相同的欄位清單參數
    - 確保終端顯示和檔案輸出的欄位一致
  - Action: 實作輸出檔案路徑處理邏輯：
    - 如果 `--output-file` 是目錄（以 `/` 結尾或是現有目錄），自動生成檔名
    - 檔名格式：`elasticache-{region}-{timestamp}.{extension}`
      - `{region}`：AWS Region（例如 us-east-1）
      - `{timestamp}`：格式為 `YYYYMMDD-HHMMSS`，使用本地時間（例如 20260112-143025）
      - `{extension}`：根據 output_format（csv 或 md）
    - 使用 `datetime.now().strftime("%Y%m%d-%H%M%S")` 生成時間戳記
    - 範例：`./output/elasticache-us-east-1-20260112-143025.csv`
  - Action: 實作錯誤處理和使用者友善的中文錯誤訊息
  - Notes: 確保輸出檔案路徑正確且不會覆蓋現有檔案（加入時間戳記避免衝突）

#### Phase 6: 測試

- [ ] Task 18: 實作 FieldFormatter 單元測試
  - File: `tests/test_field_formatter.py`
  - Action: 測試 `format_slow_logs()` - Enabled 和 Disabled 情況
  - Action: 測試 `format_backup()` - Enabled 和 Disabled 情況
  - Action: 測試 `format_cluster_name()` - Global DS 和一般叢集情況
  - Notes: 使用 pytest 參數化測試

- [ ] Task 19: 實作 Formatter 單元測試
  - File: `tests/test_formatters.py`
  - Action: 測試 CSV Formatter 輸出格式
  - Action: 測試 Markdown Formatter 輸出格式
  - Action: 測試欄位選擇功能
  - Notes: 使用 mock 資料

- [ ] Task 20: 實作 AWS Client 單元測試
  - File: `tests/test_aws_client.py`
  - Action: 使用 moto mock AWS API
  - Action: 測試 Global Datastore 偵測
  - Action: 測試 Replication Group 查詢
  - Action: 測試 Parameter Group 查詢
  - Action: 測試資料轉換邏輯
  - Notes: 建立 fixture 提供 mock 資料

- [ ] Task 21: 實作 CLI 整合測試
  - File: `tests/test_cli.py`
  - Action: 測試 CLI 參數解析
  - Action: 測試完整的執行流程（使用 mock AWS client）
  - Action: 測試錯誤處理（權限不足、Region 不存在等）
  - Action: 測試 `--profile` 參數：
    - 測試未指定 profile 時使用 default profile
    - 測試指定 profile 時使用該 profile
    - 測試 default profile 權限不足但指定 profile 有權限的情況
  - Notes: 使用 Typer 的 CliRunner 和 mock boto3 session

#### Phase 7: 文件與收尾

- [ ] Task 22: 撰寫 README.md
  - File: `README.md`
  - Action: 採用雙語並列格式（英文在前，中文在後，用分隔線區分）
  - Action: 內容結構範例：
    ```markdown
    # AWS ElastiCache Info CLI Tool

    A CLI tool to query and export AWS ElastiCache information...

    ## Features
    - Support for Redis OSS, Valkey, and Memcached
    - 18 configurable information fields
    - ...

    ## Installation
    ...

    ## Usage
    ...

    ## CLI Parameters
    | Parameter | Description |
    |-----------|-------------|
    | --region  | AWS Region  |
    ...

    ## License
    MIT

    ---

    # AWS ElastiCache 資訊查詢 CLI 工具

    一個用於查詢和匯出 AWS ElastiCache 資訊的命令列工具...

    ## 功能特色
    - 支援 Redis OSS、Valkey 和 Memcached
    - 18 個可配置的資訊欄位
    - ...

    ## 安裝
    ...

    ## 使用方式
    ...

    ## CLI 參數
    | 參數 | 說明 |
    |------|------|
    | --region | AWS Region |
    ...

    ## 授權
    MIT
    ```
  - Action: 使用 Markdown 格式，確保在 GitHub 上顯示美觀
  - Notes: 英文完整章節在前，中文完整章節在後，用 `---` 分隔

- [ ] Task 23: 建立 .gitignore
  - File: `.gitignore`
  - Action: 加入 Python 標準忽略項目（`__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`, `*.egg-info/`）
  - Action: 加入 `output/` 目錄但排除 `.gitkeep`：
    ```
    output/*
    !output/.gitkeep
    ```
  - Notes: 使用標準 Python .gitignore 模板，保留 output 目錄結構但忽略所有輸出檔案

### Acceptance Criteria

#### 功能性驗收標準

- [ ] AC1: Given 使用者執行 `get-aws-ec-info -r us-east-1`，When 查詢成功，Then 應顯示該 Region 所有 ElastiCache 叢集的資訊，並輸出 CSV 檔案到 `./output/` 目錄

- [ ] AC2: Given 使用者執行 `get-aws-ec-info -r us-east-1 -e redis`，When 查詢成功，Then 應只顯示 Redis 類型的叢集

- [ ] AC3: Given 使用者執行 `get-aws-ec-info -r us-east-1 -e redis,valkey`，When 查詢成功，Then 應顯示 Redis 和 Valkey 類型的叢集

- [ ] AC4: Given 使用者執行 `get-aws-ec-info -r us-east-1 -c "prod-*"`，When 查詢成功，Then 應只顯示名稱符合 "prod-*" 萬用字元的叢集

- [ ] AC5: Given 使用者執行 `get-aws-ec-info -r us-east-1 -i region,type,name,node-type`，When 查詢成功，Then 輸出應只包含指定的 4 個欄位

- [ ] AC6: Given 使用者執行 `get-aws-ec-info -r us-east-1 -f markdown -o output.md`，When 查詢成功，Then 應生成 Markdown 格式的表格並儲存到 `output.md`

- [ ] AC7: Given 使用者執行 `get-aws-ec-info -r us-east-1 -p prod-profile`，When 查詢成功，Then 應使用 AWS CLI 的 "prod-profile" 設定檔

- [ ] AC8: Given 叢集有 Global Datastore，When 查詢該叢集，Then "Global Datastore/Cluster Name" 欄位應顯示為 "global-ds-name/cluster-name" 格式，且 "Role" 欄位應顯示 "Primary" 或 "Secondary"

- [ ] AC9: Given 叢集沒有 Global Datastore，When 查詢該叢集，Then "Global Datastore/Cluster Name" 欄位應只顯示叢集名稱，且 "Role" 欄位應為空白

- [ ] AC10: Given 叢集啟用 Slow logs，When 查詢該叢集，Then "Slow logs/SlowerThan/MaxLen" 欄位應顯示為 "Enabled/10000/128" 格式（數值來自 Parameter Group）

- [ ] AC11: Given 叢集停用 Slow logs，When 查詢該叢集，Then "Slow logs/SlowerThan/MaxLen" 欄位應顯示為 "Disabled"

- [ ] AC12: Given 叢集啟用自動備份，When 查詢該叢集，Then "Backup window/Retention" 欄位應顯示為 "00:00-01:00 UTC/35 days" 格式

- [ ] AC13: Given 叢集停用自動備份，When 查詢該叢集，Then "Backup window/Retention" 欄位應顯示為 "Disabled"

#### 錯誤處理驗收標準

- [ ] AC14: Given 使用者沒有 ElastiCache 讀取權限，When 執行查詢，Then 應顯示清楚的中文錯誤訊息："權限不足：您的 AWS Profile 沒有 elasticache:DescribeReplicationGroups 權限"

- [ ] AC15: Given 使用者指定不存在的 Region，When 執行查詢，Then 應顯示錯誤訊息："無效的 Region：'invalid-region' 不存在"

- [ ] AC16: Given Parameter Group 查詢失敗（權限不足或 API 錯誤），When 查詢叢集資訊，Then "Slow logs/SlowerThan/MaxLen" 欄位應顯示 "N/A"（整個欄位），且不應中斷整個查詢流程，其他欄位應正常顯示

- [ ] AC17: Given 輸出目錄不存在，When 執行查詢，Then 應自動建立目錄並成功輸出檔案

- [ ] AC18: Given AWS API 回應分頁資料，When 查詢大量叢集，Then 應正確處理所有分頁並返回完整結果

#### 使用者體驗驗收標準

- [ ] AC19: Given 使用者執行查詢，When 正在查詢 AWS API，Then 應顯示 Rich Progress 進度指示器，顯示當前進度（例如："正在查詢叢集... (5/15)"）

- [ ] AC20: Given 使用者執行查詢，When 查詢完成，Then 應在終端使用 Rich Table 顯示結果表格（美觀格式）

- [ ] AC21: Given 使用者執行 `get-aws-ec-info --help`，When 顯示說明，Then 應顯示所有 CLI 參數的說明（Typer 自動生成）

- [ ] AC22: Given default profile 權限不足，When 使用者執行 `get-aws-ec-info -r us-east-1 -p prod-profile`（prod-profile 有足夠權限），Then 應成功使用 prod-profile 查詢並返回結果

- [ ] AC23: Given 使用者執行 `get-aws-ec-info -r us-east-1` 且未指定 profile，When default profile 存在且有權限，Then 應自動使用 default profile 查詢

- [ ] AC24: Given 使用者執行 `get-aws-ec-info -r us-east-1 -i region,invalid-field,type`，When 解析欄位參數，Then 應拋出錯誤並顯示：「無效的欄位名稱：'invalid-field'。有效欄位：region, type, name, ...」

- [ ] AC25: Given 使用者執行 `get-aws-ec-info -r us-east-1 -o ./output/`（目錄路徑），When 輸出檔案，Then 應自動生成檔名格式為 `elasticache-{region}-{timestamp}.csv`（例如：`elasticache-us-east-1-20260112-143025.csv`）

- [ ] AC26: Given 執行查詢過程中發生 AWS API 錯誤，When 記錄日誌，Then 應在 stderr 輸出適當層級的日誌訊息（INFO/DEBUG/WARNING/ERROR），且不影響 stdout 的表格顯示

- [ ] AC27: Given 使用者執行 `get-aws-ec-info -r us-east-1 --verbose`，When 啟用詳細模式，Then 應輸出 DEBUG 層級的日誌，包含所有 AWS API 呼叫詳細資訊

- [ ] AC28: Given 使用者執行 `get-aws-ec-info -r us-east-1 -i region,type,node-type`（使用連字號格式），When 解析欄位參數，Then 應正確轉換為 dataclass 欄位名稱（region, type, node_type），並在終端和檔案輸出中只顯示這 3 個欄位

- [ ] AC29: Given 叢集有備份設定但 SnapshotWindow 為 None，When 查詢該叢集，Then "Backup window/Retention" 欄位應顯示為 "Enabled/35 days（無窗口資訊）"

- [ ] AC30: Given 使用者執行 `get-aws-ec-info -r us-east-1 -o ./output/`（目錄路徑），When 生成輸出檔案，Then 檔名應包含本地時間戳記，格式為 `elasticache-us-east-1-20260112-143025.csv`

## Additional Context

### Dependencies

**核心依賴：**
- `typer[all]` >= 0.9.0 - CLI 框架（包含 rich 整合）
- `boto3` >= 1.28.0 - AWS SDK
- `rich` >= 13.0.0 - 終端機表格顯示和進度指示器

**開發依賴：**
- `pytest` >= 7.4.0 - 測試框架
- `pytest-cov` >= 4.1.0 - 測試覆蓋率
- `moto[elasticache]` >= 4.2.0 - AWS mock library
- `black` - 程式碼格式化（選用）
- `ruff` - Linter（選用）

**系統需求：**
- Python 3.8+
- 有效的 AWS 認證（透過 AWS CLI 或環境變數）
- 適當的 IAM 權限（`elasticache:Describe*`）

### Testing Strategy

**測試層級：**

1. **單元測試（Unit Tests）**
   - **目標**：測試個別函數和類別的邏輯
   - **工具**：pytest + mock
   - **涵蓋範圍**：
     - `FieldFormatter` 的所有格式化方法
     - `BaseFormatter`, `CSVFormatter`, `MarkdownFormatter`
     - `utils.py` 中的工具函數
     - CLI 參數解析邏輯
   - **Mock 策略**：Mock boto3 API 回應

2. **整合測試（Integration Tests）**
   - **目標**：測試元件之間的互動
   - **工具**：pytest + moto
   - **涵蓋範圍**：
     - `ElastiCacheClient` 的完整查詢流程
     - 4 層查詢架構的協調
     - 資料轉換邏輯
   - **Mock 策略**：使用 moto 模擬 AWS ElastiCache 服務

3. **端對端測試（E2E Tests）**
   - **目標**：測試完整的 CLI 執行流程
   - **工具**：pytest + Typer CliRunner + moto
   - **涵蓋範圍**：
     - 完整的命令執行（從 CLI 輸入到檔案輸出）
     - 錯誤處理流程
     - 進度顯示和終端輸出
   - **Mock 策略**：Mock AWS client 或使用 moto

**moto 支援程度說明：**

- moto 支援基本的 ElastiCache API（`describe_cache_clusters`, `describe_replication_groups`, `describe_cache_parameters`）
- **限制**：moto 可能不完整支援 Global Datastore API（`describe_global_replication_groups`）
- **測試策略調整**：
  - 對於 Global Datastore 相關測試，使用 mock 而非 moto
  - 對於基本 Replication Group 和 Cache Cluster 測試，使用 moto
  - 對於 Parameter Group 測試，使用 moto
  - 建議在 CI/CD 中加入真實 AWS 測試環境（使用測試帳號）

**測試案例優先級（基於 Murat 的風險評估）：**

- 🔴 **高優先級**（必須測試）：
  - Global Datastore 偵測和名稱格式化（使用 mock，因 moto 可能不支援）
  - 複合欄位格式化（Slow logs, Backup）
  - 萬用字元叢集名稱篩選
  - 錯誤處理（權限不足、Region 不存在）
  - API 分頁處理
  - Profile 切換（default profile 權限不足時使用指定 profile）

- 🟡 **中優先級**（應該測試）：
  - 引擎類型篩選
  - 欄位選擇功能
  - 輸出格式轉換（CSV, Markdown）
  - Parameter Group 查詢快取

- 🟢 **低優先級**（可以測試）：
  - CLI 參數驗證
  - 輸出目錄自動建立
  - 進度顯示

**測試覆蓋率目標：**
- 整體覆蓋率：> 80%
- 核心邏輯（AWS client, formatters）：> 90%

**手動測試：**
- 使用真實 AWS 帳號測試（在開發環境）
- 驗證所有 18 個欄位的資料正確性
- 測試不同 Region 和 Profile 組合
- 驗證輸出檔案格式

### Notes

**高風險項目（需特別注意）：**

1. **Global Datastore 偵測邏輯**
   - 風險：API 回應結構可能因 AWS 版本而異
   - 緩解：充分的單元測試和錯誤處理

2. **Parameter Group 查詢效能**
   - 風險：每個叢集都查詢 Parameter Group 可能很慢
   - 緩解：實作快取機制，相同 Parameter Group 只查詢一次

3. **API 限流（Rate Limiting）**
   - 風險：大量叢集可能觸發 AWS API 限流
   - 緩解：實作 exponential backoff 重試機制

4. **權限問題**
   - 風險：使用者可能沒有完整的 ElastiCache 讀取權限
   - 緩解：優雅降級，缺少權限的欄位顯示 "N/A"

**已知限制：**

- 目前只支援單一 Region 查詢（多 Region 為未來功能）
- 不支援 CloudWatch Metrics 查詢
- 輸出格式僅支援 CSV 和 Markdown（未來可擴充 JSON, YAML）

**未來考慮（Out of Scope）：**

- 多 Region 並行查詢
- 快取機制（避免重複查詢相同資料）
- 輸出格式擴充（JSON, YAML, Excel）
- 互動式模式（TUI）
- 定期排程查詢和報告生成
- 與其他 AWS 服務整合（CloudWatch, Cost Explorer）
