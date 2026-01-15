# AWS ElastiCache Info CLI Tool

A CLI tool to query and export AWS ElastiCache cluster information with support for Redis OSS, Valkey, and Memcached engines.

## Features

- **Multi-Engine Support**: Query Redis OSS, Valkey, and Memcached clusters
- **18 Configurable Fields**: Select specific information fields to display and export
- **Global Datastore Detection**: Automatically detect and display Global Datastore relationships
- **Cross-Region Query**: Automatically query all regions in a Global Datastore topology
- **Multiple Output Formats**: Export to CSV or Markdown table format
- **Flexible Filtering**: Filter clusters by name with wildcard support
- **Rich Terminal Display**: Beautiful table output in terminal using Rich library
- **AWS Profile Support**: Use different AWS CLI profiles for authentication
- **Detailed Logging**: Optional verbose mode for debugging

## Installation

### Prerequisites

- Python 3.8 or higher
- Valid AWS credentials (via AWS CLI or environment variables)
- Appropriate IAM permissions: `elasticache:Describe*`

### Install with uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repository-url>
cd GetAWSElastiCacheInfo

# uv will automatically manage dependencies when you run commands
# No manual installation needed!
```

### Install with pip (Alternative)

```bash
pip install -e .

# For development
pip install -e ".[dev]"
```

## Usage

### Basic Usage

```bash
# Query all clusters in us-east-1
uv run get-aws-ec-info -r us-east-1

# Query with specific AWS profile
uv run get-aws-ec-info -r us-east-1 -p prod-profile

# Query only Redis clusters
uv run get-aws-ec-info -r us-east-1 -e redis

# Query Redis and Valkey clusters
uv run get-aws-ec-info -r us-east-1 -e redis,valkey
```

### Filtering

```bash
# Filter by cluster name with wildcard
uv run get-aws-ec-info -r us-east-1 -c "prod-*"

# Filter by specific cluster name
uv run get-aws-ec-info -r us-east-1 -c "my-cluster-001"
```

### Field Selection

```bash
# Select specific fields
uv run get-aws-ec-info -r us-east-1 -i region,type,name,node-type,engine-version

# Show all fields (default)
uv run get-aws-ec-info -r us-east-1 -i all
```

### Output Formats

```bash
# Output as CSV (default)
uv run get-aws-ec-info -r us-east-1 -f csv -o output.csv

# Output as Markdown table
uv run get-aws-ec-info -r us-east-1 -f markdown -o output.md

# Auto-generate filename with timestamp
uv run get-aws-ec-info -r us-east-1 -o ./output/
# Creates: ./output/elasticache-us-east-1-20260112-143025.csv
```

### Verbose Mode

```bash
# Enable detailed logging
uv run get-aws-ec-info -r us-east-1 -v
```

## CLI Parameters

| Parameter | Short | Description | Default |
|-----------|-------|-------------|---------|
| `--region` | `-r` | AWS Region (required) | - |
| `--profile` | `-p` | AWS Profile | `default` |
| `--engine` | `-e` | Engine types (comma-separated) | `redis,valkey,memcached` |
| `--cluster` | `-c` | Cluster name filter (supports wildcards) | All clusters |
| `--info-type` | `-i` | Fields to display (comma-separated or `all`) | `all` |
| `--output-format` | `-f` | Output format: `csv` or `markdown` | `csv` |
| `--output-file` | `-o` | Output file path | `./output/` |
| `--verbose` | `-v` | Enable verbose logging | `False` |

## Available Fields

The following 18 fields are available for selection:

1. `region` - AWS Region name
2. `type` - Cache type (Redis/Memcached/Valkey)
3. `name` - Global Datastore/Cluster Name
4. `role` - Role (Primary/Secondary for Global Datastore)
5. `node-type` - Node type (e.g., cache.r6g.large)
6. `engine-version` - Engine version
7. `cluster-mode` - Cluster mode (Enabled/Disabled)
8. `shards` - Number of shards
9. `nodes` - Number of nodes
10. `multi-az` - Multi-AZ (Enabled/Disabled)
11. `auto-failover` - Auto-failover (Enabled/Disabled)
12. `encryption-transit` - Encryption in transit (Enabled/Disabled)
13. `encryption-rest` - Encryption at rest (Enabled/Disabled)
14. `slow-logs` - Slow logs status and parameters (Enabled/threshold/length or Disabled)
15. `engine-logs` - Engine logs (Enabled/Disabled)
16. `maintenance-window` - Maintenance window time
17. `auto-upgrade` - Auto upgrade minor versions (Enabled/Disabled)
18. `backup` - Backup window and retention period

## Field Details

### Slow Logs

The `slow-logs` field displays the slow log configuration status for Redis clusters:

- **Disabled**: Cluster does not have slow log delivery configured in `LogDeliveryConfigurations`
- **Enabled/threshold/length**: Cluster has slow log delivery enabled, showing the threshold (microseconds) and max length from parameter group

**Note**: The tool checks cluster-level slow log delivery configuration first, then retrieves parameter values only for enabled clusters. This ensures accurate status reporting.

## Examples

### Example 1: Query Production Redis Clusters

```bash
uv run get-aws-ec-info \
  -r us-east-1 \
  -e redis \
  -c "prod-*" \
  -i region,name,node-type,engine-version,shards,nodes \
  -o prod-redis-clusters.csv
```

### Example 2: Export All Cluster Information as Markdown

```bash
uv run get-aws-ec-info \
  -r ap-northeast-1 \
  -f markdown \
  -o elasticache-report.md
```

### Example 3: Debug with Verbose Logging

```bash
uv run get-aws-ec-info \
  -r us-west-2 \
  -p staging-profile \
  -v
```

## Output Format Examples

### CSV Output

```csv
Region,Type,Name,Node Type,Engine Version,Shards,Nodes
us-east-1,Redis,global-ds-001/cluster-001,cache.r6g.large,7.0,3,6
us-east-1,Memcached,memcached-001,cache.t3.medium,1.6.17,0,3
```

### Markdown Output

```markdown
| Region | Type | Name | Node Type | Engine Version | Shards | Nodes |
| --- | --- | --- | --- | --- | ---: | ---: |
| us-east-1 | Redis | global-ds-001/cluster-001 | cache.r6g.large | 7.0 | 3 | 6 |
| us-east-1 | Memcached | memcached-001 | cache.t3.medium | 1.6.17 | 0 | 3 |
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage (requires pytest-cov)
uv run pytest --cov=elasticache_info --cov-report=html

# Run specific test file
uv run pytest tests/test_field_formatter.py
```

### Code Formatting

```bash
# Format code with black
black elasticache_info tests

# Lint with ruff
ruff check elasticache_info tests
```

## Architecture

The tool implements a 4-layer query architecture:

1. **Layer 1: Global Datastore Discovery** - Detect Global Datastore relationships and identify all regions
2. **Layer 2: Replication Group Enumeration** - Query Redis/Valkey replication groups
3. **Layer 3: Cache Cluster Details** - Query Memcached and standalone clusters
4. **Layer 4: Parameter Group Queries** - Retrieve parameter group settings (with caching)

### Cross-Region Query

When a Global Datastore is detected, the tool automatically:
- Identifies all regions participating in the Global Datastore
- Queries each region sequentially with progress indication
- Displays the role (Primary/Secondary) for each member
- Sorts results by region alphabetically
- Handles permission errors gracefully (continues querying other regions)

**Technical Note**: The tool uses `describe_global_replication_groups` API with `ShowMemberInfo=True` parameter to retrieve complete member information across all regions. Without this parameter, the API returns an empty Members array by default.

## Error Handling

The tool provides clear error messages in Chinese for common issues:

- **Permission Errors**: Missing IAM permissions
- **Invalid Parameters**: Invalid region or parameter values
- **Connection Errors**: Network or AWS service issues
- **Credentials Errors**: Missing or invalid AWS credentials

## License

MIT

---

# AWS ElastiCache 資訊查詢 CLI 工具

一個用於查詢和匯出 AWS ElastiCache 叢集資訊的命令列工具，支援 Redis OSS、Valkey 和 Memcached 引擎。

## 功能特色

- **多引擎支援**：查詢 Redis OSS、Valkey 和 Memcached 叢集
- **18 個可配置欄位**：選擇特定資訊欄位進行顯示和匯出
- **Global Datastore 偵測**：自動偵測並顯示 Global Datastore 關係
- **跨 Region 查詢**：自動查詢 Global Datastore 拓撲中的所有 regions
- **多種輸出格式**：匯出為 CSV 或 Markdown 表格格式
- **靈活篩選**：支援萬用字元的叢集名稱篩選
- **豐富的終端顯示**：使用 Rich 函式庫在終端顯示美觀的表格
- **AWS Profile 支援**：使用不同的 AWS CLI profile 進行認證
- **詳細日誌**：可選的詳細模式用於除錯

## 安裝

### 前置需求

- Python 3.8 或更高版本
- 有效的 AWS 認證（透過 AWS CLI 或環境變數）
- 適當的 IAM 權限：`elasticache:Describe*`

### 使用 uv 安裝（推薦）

```bash
# 如果尚未安裝 uv，先安裝
curl -LsSf https://astral.sh/uv/install.sh | sh

# 複製專案
git clone <repository-url>
cd GetAWSElastiCacheInfo

# uv 會在執行指令時自動管理依賴
# 不需要手動安裝！
```

### 使用 pip 安裝（替代方案）

```bash
pip install -e .

# 開發模式
pip install -e ".[dev]"
```

## 使用方式

### 基本用法

```bash
# 查詢 us-east-1 的所有叢集
uv run get-aws-ec-info -r us-east-1

# 使用特定 AWS profile 查詢
uv run get-aws-ec-info -r us-east-1 -p prod-profile

# 只查詢 Redis 叢集
uv run get-aws-ec-info -r us-east-1 -e redis

# 查詢 Redis 和 Valkey 叢集
uv run get-aws-ec-info -r us-east-1 -e redis,valkey
```

### 篩選

```bash
# 使用萬用字元篩選叢集名稱
uv run get-aws-ec-info -r us-east-1 -c "prod-*"

# 篩選特定叢集名稱
uv run get-aws-ec-info -r us-east-1 -c "my-cluster-001"
```

### 欄位選擇

```bash
# 選擇特定欄位
uv run get-aws-ec-info -r us-east-1 -i region,type,name,node-type,engine-version

# 顯示所有欄位（預設）
uv run get-aws-ec-info -r us-east-1 -i all
```

### 輸出格式

```bash
# 輸出為 CSV（預設）
uv run get-aws-ec-info -r us-east-1 -f csv -o output.csv

# 輸出為 Markdown 表格
uv run get-aws-ec-info -r us-east-1 -f markdown -o output.md

# 自動生成帶時間戳記的檔名
uv run get-aws-ec-info -r us-east-1 -o ./output/
# 建立：./output/elasticache-us-east-1-20260112-143025.csv
```

### 詳細模式

```bash
# 啟用詳細日誌
uv run get-aws-ec-info -r us-east-1 -v
```

## CLI 參數

| 參數 | 簡寫 | 說明 | 預設值 |
|------|------|------|--------|
| `--region` | `-r` | AWS Region（必填） | - |
| `--profile` | `-p` | AWS Profile | `default` |
| `--engine` | `-e` | 引擎類型（逗號分隔） | `redis,valkey,memcached` |
| `--cluster` | `-c` | 叢集名稱篩選（支援萬用字元） | 所有叢集 |
| `--info-type` | `-i` | 顯示欄位（逗號分隔或 `all`） | `all` |
| `--output-format` | `-f` | 輸出格式：`csv` 或 `markdown` | `csv` |
| `--output-file` | `-o` | 輸出檔案路徑 | `./output/` |
| `--verbose` | `-v` | 啟用詳細日誌 | `False` |

## 可用欄位

以下 18 個欄位可供選擇：

1. `region` - AWS Region 名稱
2. `type` - Cache 類型（Redis/Memcached/Valkey）
3. `name` - Global Datastore/叢集名稱
4. `role` - 角色（Global Datastore 的 Primary/Secondary）
5. `node-type` - 節點類型（例如：cache.r6g.large）
6. `engine-version` - 引擎版本
7. `cluster-mode` - 叢集模式（Enabled/Disabled）
8. `shards` - 分片數量
9. `nodes` - 節點數量
10. `multi-az` - 多可用區（Enabled/Disabled）
11. `auto-failover` - 自動故障轉移（Enabled/Disabled）
12. `encryption-transit` - 傳輸加密（Enabled/Disabled）
13. `encryption-rest` - 靜態加密（Enabled/Disabled）
14. `slow-logs` - Slow logs 狀態及參數（Enabled/閾值/長度 或 Disabled）
15. `engine-logs` - 引擎日誌（Enabled/Disabled）
16. `maintenance-window` - 維護窗口時間
17. `auto-upgrade` - 自動升級小版本（Enabled/Disabled）
18. `backup` - 備份窗口及保留期

## 欄位詳細說明

### Slow Logs

`slow-logs` 欄位顯示 Redis 叢集的 slow log 配置狀態：

- **Disabled**：叢集在 `LogDeliveryConfigurations` 中沒有配置 slow log delivery
- **Enabled/閾值/長度**：叢集已啟用 slow log delivery，顯示參數組中的閾值（微秒）和最大長度

**注意**：工具會先檢查叢集層級的 slow log delivery 配置，然後只對啟用的叢集擷取參數值。這確保了狀態報告的準確性。

## 範例

### 範例 1：查詢生產環境 Redis 叢集

```bash
uv run get-aws-ec-info \
  -r us-east-1 \
  -e redis \
  -c "prod-*" \
  -i region,name,node-type,engine-version,shards,nodes \
  -o prod-redis-clusters.csv
```

### 範例 2：匯出所有叢集資訊為 Markdown

```bash
uv run get-aws-ec-info \
  -r ap-northeast-1 \
  -f markdown \
  -o elasticache-report.md
```

### 範例 3：使用詳細日誌除錯

```bash
uv run get-aws-ec-info \
  -r us-west-2 \
  -p staging-profile \
  -v
```

## 輸出格式範例

### CSV 輸出

```csv
Region,Type,Name,Node Type,Engine Version,Shards,Nodes
us-east-1,Redis,global-ds-001/cluster-001,cache.r6g.large,7.0,3,6
us-east-1,Memcached,memcached-001,cache.t3.medium,1.6.17,0,3
```

### Markdown 輸出

```markdown
| Region | Type | Name | Node Type | Engine Version | Shards | Nodes |
| --- | --- | --- | --- | --- | ---: | ---: |
| us-east-1 | Redis | global-ds-001/cluster-001 | cache.r6g.large | 7.0 | 3 | 6 |
| us-east-1 | Memcached | memcached-001 | cache.t3.medium | 1.6.17 | 0 | 3 |
```

## 開發

### 執行測試

```bash
# 執行所有測試
uv run pytest

# 執行測試並產生覆蓋率報告（需要 pytest-cov）
uv run pytest --cov=elasticache_info --cov-report=html

# 執行特定測試檔案
uv run pytest tests/test_field_formatter.py
```

### 程式碼格式化

```bash
# 使用 black 格式化程式碼
black elasticache_info tests

# 使用 ruff 檢查程式碼
ruff check elasticache_info tests
```

## 架構

工具實作了 4 層查詢架構：

1. **Layer 1: Global Datastore Discovery** - 偵測 Global Datastore 關係並識別所有 regions
2. **Layer 2: Replication Group Enumeration** - 查詢 Redis/Valkey replication groups
3. **Layer 3: Cache Cluster Details** - 查詢 Memcached 和獨立叢集
4. **Layer 4: Parameter Group Queries** - 取得 parameter group 設定（含快取機制）

### 跨 Region 查詢

當偵測到 Global Datastore 時，工具會自動：
- 識別所有參與 Global Datastore 的 regions
- 序列查詢每個 region 並顯示進度
- 顯示每個成員的角色（Primary/Secondary）
- 按 region 字母順序排序結果
- 優雅處理權限錯誤（繼續查詢其他 regions）

**技術說明**：工具使用 `describe_global_replication_groups` API 並加上 `ShowMemberInfo=True` 參數來取得所有 regions 的完整成員資訊。若不加此參數，API 預設會回傳空的 Members 陣列。

## 錯誤處理

工具提供清楚的中文錯誤訊息，涵蓋常見問題：

- **權限錯誤**：缺少 IAM 權限
- **無效參數**：無效的 region 或參數值
- **連線錯誤**：網路或 AWS 服務問題
- **認證錯誤**：缺少或無效的 AWS 認證

## 授權

MIT
