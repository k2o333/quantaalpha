# Primary Key 测试方法论

本文档说明如何测试接口的 primary key 配置是否完整，以及如何找出需要添加的字段。

## 测试目标

验证 YAML 配置中的 `primary_key` 是否能唯一标识记录，确保去重时不会误删真正的不同数据。

## 核心原理

```
下载原始数据（不去重）
    ↓
按配置的 primary_key 分组
    ↓
检查组内非主键字段是否一致
    ↓
判断是真重复还是假重复
```

## 测试步骤

### 步骤1: 下载原始数据

使用 `download_data.py` 下载完整数据，**不进行去重处理**：

```python
# 直接保存原始数据，不经过 processor 的去重逻辑
df = pd.DataFrame(all_data)
df.to_parquet(output_file, index=False)
```

### 步骤2: 检测重复组

按配置的 primary key 对数据进行分组：

```python
pk = config['output']['primary_key']  # 如 ['ts_code', 'ann_date', 'end_date']
dup_counts = df.groupby(pk).size().reset_index(name='count')
dup_groups = dup_counts[dup_counts['count'] > 1]
```

**三种情况**：

| 情况 | 重复组数 | 含义 |
|------|---------|------|
| A | 0 | 无重复，primary key 定义正确 |
| B | >0 | 有重复，需要进一步检查是否是真重复 |

### 步骤3: 检查冲突字段

对于有重复组的接口，检查每个重复组内的**所有非主键字段**：

```python
non_key_fields = [f for f in df.columns if f not in primary_key]

for _, group_info in dup_groups.iterrows():
    # 筛选出该 primary key 对应的所有记录
    mask = pd.Series(True, index=df.index)
    for pk_field in primary_key:
        mask = mask & (df[pk_field] == group_info[pk_field])
    group = df[mask]
    
    # 检查所有非主键字段
    conflicts = []
    for field in non_key_fields:
        unique_values = group[field].dropna().unique()
        if len(unique_values) > 1:
            conflicts.append({
                'field': field,
                'values': list(unique_values)
            })
```

### 步骤4: 判定结果

#### 情况A: 无重复组
```
结果: ✅ 通过
含义: primary key 能唯一标识每条记录
示例: disclosure_date, income_vip, stk_factor_pro 等
```

#### 情况B: 有重复但无冲突字段
```
结果: ⚠️ 正常重复
含义: 重复组内所有字段完全相同，是真重复，可以安全去重
示例: pledge_stat
验证方法: 所有非主键字段在组内都相同
```

#### 情况C: 有重复且有冲突字段
```
结果: ❌ 失败（主键不完整）
含义: 相同 primary key 下某些字段值不同，这些记录不应该被去重
示例: balancesheet_vip 的 update_flag 冲突
```

## 实际案例

### 案例1: balancesheet_vip（需要添加字段）

**配置**: `primary_key: [ts_code, ann_date, end_date]`

**发现问题**:
```
Primary Key: ts_code='000002.SZ', ann_date='20140307', end_date='20131231'
记录1: update_flag='0'  → 原始报告
记录2: update_flag='1'  → 更新报告

冲突字段: update_flag 有不同值 ['0', '1']
```

**结论**: 需要添加 `update_flag` 到 primary key

**修复**:
```yaml
output:
  primary_key:
    - ts_code
    - ann_date
    - end_date
    - update_flag  # 新增
```

### 案例2: pledge_stat（正常重复）

**配置**: `primary_key: [ts_code, end_date]`

**检测**:
```
发现 112 个重复组
示例组: ts_code='000002.SZ', end_date='20140620'
该组有 2 条记录
```

**验证**:
```python
for field in non_key_fields:
    unique_values = group[field].dropna().unique()
    print(f"{field}: {unique_values}")

# 输出: 所有字段都相同
```

**结论**: 是真重复，可以安全去重，primary key 配置正确

### 案例3: disclosure_date（无需修改）

**配置**: `primary_key: [ts_code, end_date]`

**检测**:
```
重复组数: 0
总记录数: 104
```

**结论**: 每条记录的 primary key 都唯一，配置正确

## 找出需要添加的字段的方法

### 方法1: 收集冲突字段

遍历所有问题样本，统计哪些字段经常导致冲突：

```python
all_conflict_fields = set()
for sample in samples:
    for conflict in sample['conflict_fields']:
        all_conflict_fields.add(conflict['field'])

print(f"需要考虑的字段: {all_conflict_fields}")
```

### 方法2: 业务逻辑判断

根据字段的业务含义判断是否应纳入 primary key：

| 字段 | 业务含义 | 是否应加入 primary key |
|------|---------|---------------------|
| update_flag | 0=原始报告, 1=更新报告 | ✅ 是，区分报告版本 |
| div_proc | 分红阶段（预案/股东会通过/实施） | ✅ 是，区分同一时期不同进度 |
| report_type | 报表类型 | 视情况而定 |

### 方法3: 验证修复效果

修改配置后，重新运行测试验证：

```bash
./run_test.sh --interface balancesheet_vip
```

预期结果：`失败` → `通过`

## 测试脚本说明

### download_data.py
- 下载原始数据，不进行去重
- 保存为 parquet 格式供测试使用

### test_primary_key.py
- 读取接口配置和数据
- 执行重复组检测
- 分析冲突字段
- 生成测试报告

### run_test.sh
- 一键运行下载+测试
- 支持单个接口或全部接口

## 报告输出

测试报告包含：
1. 汇总统计（通过/失败/正常重复的接口数）
2. 失败接口的详细问题分析
3. 问题样本（primary key 值、冲突字段、不同值）
4. 修复建议（需要添加的字段列表）

报告位置: `test/prim/reports/primary_key_test_report_YYYYMMDD_HHMMSS.md`
