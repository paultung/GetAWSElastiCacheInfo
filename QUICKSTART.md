# Quick Start Guide

## 安裝 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 快速開始

```bash
# 1. 複製專案
git clone <repository-url>
cd GetAWSElastiCacheInfo

# 2. 直接執行（uv 會自動處理依賴）
uv run get-aws-ec-info -r us-east-1

# 3. 查看說明
uv run get-aws-ec-info --help
```

## 常用指令

### 查詢所有叢集

```bash
uv run get-aws-ec-info -r us-east-1
```

### 只查詢 Redis 叢集

```bash
uv run get-aws-ec-info -r us-east-1 -e redis
```

### 篩選特定叢集

```bash
uv run get-aws-ec-info -r us-east-1 -c "prod-*"
```

### 選擇特定欄位

```bash
uv run get-aws-ec-info -r us-east-1 -i region,type,name,node-type,shards,nodes
```

### 輸出為 Markdown

```bash
uv run get-aws-ec-info -r us-east-1 -f markdown -o report.md
```

### 使用特定 AWS Profile

```bash
uv run get-aws-ec-info -r us-east-1 -p prod-profile
```

### 詳細模式（除錯用）

```bash
uv run get-aws-ec-info -r us-east-1 -v
```

## 執行測試

```bash
# 執行所有測試
uv run pytest

# 執行特定測試
uv run pytest tests/test_field_formatter.py -v
```

## 為什麼使用 uv run？

- **自動管理依賴**：不需要手動建立虛擬環境或安裝套件
- **快速執行**：uv 使用 Rust 實作，速度極快
- **隔離環境**：每個專案自動隔離，不會互相干擾
- **簡化流程**：一個指令就能執行，不需要 `source .venv/bin/activate`

## 傳統方式（可選）

如果你偏好傳統的 pip 方式：

```bash
# 建立虛擬環境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安裝套件
pip install -e .

# 執行
get-aws-ec-info -r us-east-1
```

---

# Quick Start Guide (English)

## Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd GetAWSElastiCacheInfo

# 2. Run directly (uv handles dependencies automatically)
uv run get-aws-ec-info -r us-east-1

# 3. View help
uv run get-aws-ec-info --help
```

## Common Commands

### Query all clusters

```bash
uv run get-aws-ec-info -r us-east-1
```

### Query only Redis clusters

```bash
uv run get-aws-ec-info -r us-east-1 -e redis
```

### Filter specific clusters

```bash
uv run get-aws-ec-info -r us-east-1 -c "prod-*"
```

### Select specific fields

```bash
uv run get-aws-ec-info -r us-east-1 -i region,type,name,node-type,shards,nodes
```

### Output as Markdown

```bash
uv run get-aws-ec-info -r us-east-1 -f markdown -o report.md
```

### Use specific AWS Profile

```bash
uv run get-aws-ec-info -r us-east-1 -p prod-profile
```

### Verbose mode (for debugging)

```bash
uv run get-aws-ec-info -r us-east-1 -v
```

## Run Tests

```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_field_formatter.py -v
```

## Why use uv run?

- **Automatic dependency management**: No need to manually create virtual environments or install packages
- **Fast execution**: uv is implemented in Rust and is extremely fast
- **Isolated environments**: Each project is automatically isolated
- **Simplified workflow**: One command to run, no need for `source .venv/bin/activate`

## Traditional Way (Optional)

If you prefer the traditional pip approach:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install packages
pip install -e .

# Run
get-aws-ec-info -r us-east-1
```
