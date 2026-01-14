# 修正記錄：ShowMemberInfo 參數缺失問題

**日期**：2026-01-14
**狀態**：已解決
**嚴重程度**：Critical
**影響範圍**：Global Datastore 跨 region 查詢功能

## 問題摘要

在實際環境測試時發現，`describe_global_replication_groups` API 回傳的 `Members` 陣列為空，導致無法正確識別 Global Datastore 的跨 region 成員，Role 欄位顯示空白。

## 問題詳情

### 症狀
1. Role 欄位在 Global Datastore 成員中顯示空白
2. 無法自動探索並查詢其他 regions 的 secondary clusters
3. 日誌顯示：`Found 0 clusters in Global Datastores across 0 regions`

### 測試環境
- Region: `eu-central-1`
- Profile: `sso-polkast-viewonlyaccess`
- Global Datastore: `iudkw-be-redis-master-eu-global`
  - Primary: `be-redis-master-eu` (eu-central-1)
  - Secondary: `be-redis-master-eu-paris` (eu-west-3)

### 根本原因

AWS ElastiCache API 的 `describe_global_replication_groups` 方法有一個隱藏的行為：

**預設情況下，`Members` 陣列是空的**，必須明確指定 `ShowMemberInfo=True` 參數才能取得完整的成員資訊。

這個行為在 AWS 官方文件中有說明，但容易被忽略。

## API 行為對比

### 錯誤的呼叫方式（預設）

```python
response = client.describe_global_replication_groups()
```

**回傳結果**：
```json
{
  "GlobalReplicationGroups": [
    {
      "GlobalReplicationGroupId": "iudkw-be-redis-master-eu-global",
      "Status": "available",
      "Members": []  // 空陣列！
    }
  ]
}
```

### 正確的呼叫方式

```python
response = client.describe_global_replication_groups(ShowMemberInfo=True)
```

**回傳結果**：
```json
{
  "GlobalReplicationGroups": [
    {
      "GlobalReplicationGroupId": "iudkw-be-redis-master-eu-global",
      "Status": "available",
      "Members": [
        {
          "ReplicationGroupId": "be-redis-master-eu",
          "ReplicationGroupRegion": "eu-central-1",
          "Role": "PRIMARY",
          "Status": "associated"
        },
        {
          "ReplicationGroupId": "be-redis-master-eu-paris",
          "ReplicationGroupRegion": "eu-west-3",
          "Role": "SECONDARY",
          "Status": "associated"
        }
      ]
    }
  ]
}
```

## 解決方案

### 程式碼修改

**檔案**：`elasticache_info/aws/client.py`
**方法**：`_get_global_datastores()`
**修改行數**：1 行

```python
# 修改前
page_iterator = paginator.paginate()

# 修改後
page_iterator = paginator.paginate(ShowMemberInfo=True)
```

### 完整修改內容

```python
def _get_global_datastores(self) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Layer 1: Discover Global Datastores."""
    logger.info("Layer 1: Discovering Global Datastores")
    global_ds_map = {}
    global_ds_ids = set()

    try:
        # Get all Global Datastores with ShowMemberInfo=True to get complete Members array
        # IMPORTANT: Without ShowMemberInfo=True, the API returns empty Members array by default
        # This parameter is critical for cross-region Global Datastore discovery
        paginator = self.client.get_paginator("describe_global_replication_groups")
        page_iterator = paginator.paginate(ShowMemberInfo=True)  # 關鍵修改

        # ... 其餘程式碼
```

## 驗證結果

### 測試執行

```bash
uv run get-aws-ec-info --region eu-central-1 --profile sso-polkast-viewonlyaccess --verbose
```

### 日誌輸出

```
2026-01-14 15:46:57 - INFO - Found Global Datastore: iudkw-be-redis-master-eu-global
2026-01-14 15:46:57 - DEBUG - Found Global Datastore member: be-redis-master-eu (PRIMARY) in eu-central-1
2026-01-14 15:46:57 - DEBUG - Found Global Datastore member: be-redis-master-eu-paris (SECONDARY) in eu-west-3
2026-01-14 15:46:57 - INFO - Found 4 clusters in Global Datastores across 2 regions
2026-01-14 15:46:57 - INFO - Regions to query: ['eu-central-1', 'eu-west-3']
```

### 輸出結果

| Region | Type | Name | Role | Node Type | Engine Version |
|--------|------|------|------|-----------|----------------|
| eu-central-1 | Redis | iudkw-be-redis-master-eu-global/be-redis-master-eu | **Primary** | cache.m5.large | 6.2.5 |
| eu-west-3 | Redis | iudkw-be-redis-master-eu-global/be-redis-master-eu-paris | **Secondary** | cache.m5.large | 6.2.5 |

✅ Role 欄位正確顯示
✅ 自動探索並查詢 eu-west-3
✅ 顯示完整的 Global Datastore 拓撲

## 測試覆蓋

### 單元測試
- ✅ 63 個測試全部通過
- ✅ 新增 11 個測試案例覆蓋 Global Datastore 功能
- ✅ 測試 Role 欄位格式化（Primary/Secondary）
- ✅ 測試跨 region 查詢邏輯

### 整合測試
- ✅ 實際 AWS 環境驗證
- ✅ 多 region Global Datastore 查詢
- ✅ 進度條顯示正常
- ✅ 錯誤處理正常（graceful degradation）

## 影響評估

### 功能影響
- ✅ **修正前**：Role 欄位空白，無法識別 Global Datastore 成員
- ✅ **修正後**：完整顯示 Global Datastore 拓撲，自動跨 region 查詢

### 向後相容性
- ✅ 完全相容，不影響現有功能
- ✅ 不改變 CLI 參數
- ✅ 不改變輸出格式
- ✅ 單一 region 查詢行為不變

### 效能影響
- 無負面影響
- 跨 region 查詢時間符合預期（2 regions 約 12 秒）

## 文件更新

### 已更新文件
1. ✅ `README.md` - 加上技術說明
2. ✅ `CHANGELOG.md` - 記錄修正內容
3. ✅ `tech-spec-global-datastore-cross-region-query.md` - 更新實作後發現的問題章節
4. ✅ 程式碼註解 - 在關鍵位置加上警告註解

### 文件內容
- API 行為說明
- ShowMemberInfo 參數的重要性
- 問題發現與解決過程
- 驗證結果

## 經驗教訓

### 技術層面
1. **AWS API 可選參數的重要性**：某些「可選」參數實際上對功能有關鍵影響
2. **實際環境測試的必要性**：Mock 測試無法發現 API 預設行為的細節
3. **API 文件閱讀**：需要仔細閱讀所有參數說明，特別是影響回傳資料結構的參數

### 開發流程
1. **除錯工具的價值**：建立除錯腳本直接檢查 API 回應非常有效
2. **日誌的重要性**：詳細的日誌幫助快速定位問題
3. **文件化的必要性**：記錄問題和解決方案幫助未來維護

### 最佳實踐
1. 對於 AWS API，始終檢查是否有參數可以控制回傳資料的詳細程度
2. 當遇到空陣列時，不要假設是正常行為，檢查 API 文件
3. 在程式碼中加上清楚的註解說明關鍵參數的用途

## 參考資料

### AWS 官方文件
- [DescribeGlobalReplicationGroups API Reference](https://docs.aws.amazon.com/AmazonElastiCache/latest/APIReference/API_DescribeGlobalReplicationGroups.html)
- ShowMemberInfo 參數說明：
  > "An optional parameter that returns the list of members in the Global Datastore. If ShowMemberInfo is not provided or is set to false, member information is not returned."

### 相關 Issue
- 無（內部發現並修正）

### Commit 記錄
- 待建立 commit

## 後續行動

### 立即行動
- [x] 修正程式碼
- [x] 更新測試
- [x] 更新文件
- [x] 實際環境驗證

### 建議改進
- [ ] 考慮在其他 AWS API 呼叫中檢查類似的參數
- [ ] 建立 API 呼叫的最佳實踐文件
- [ ] 加強實際環境測試的自動化

## 結論

這是一個典型的「API 預設行為與預期不符」的問題。透過仔細檢查 API 文件和實際測試，成功找到解決方案。這次經驗強調了：

1. **實際環境測試的重要性**
2. **API 文件閱讀的必要性**
3. **清楚的文件記錄的價值**

修正後的功能完全符合需求，並且保持了向後相容性。
