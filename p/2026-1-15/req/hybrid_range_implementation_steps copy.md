# App4 混合范围覆盖检测方案实施步骤

**创建日期**: 2026-01-14
**预计工期**: 2天（核心功能）+ 1天（可选优化）
**实施优先级**: P0（高优先级）

---

## 📋 实施总览

本实施计划采用**渐进式交付**策略，每一步都有明确的验收标准，通过实际运行代码观察结果来验证功能正确性，而非依赖单元测试断言。

```
Day 1: 核心逻辑开发
├─ Step 1: 环境准备与配置（30分钟）
├─ Step 2: CoverageManager 增强 - 混合覆盖检测（3小时）
└─ Step 3: Downloader 改造 - 支持部分覆盖下载（2小时）

Day 2: 集成验证
├─ Step 4: 配置扩展与接口测试（2小时）
├─ Step 5: 真实场景集成测试（3小时）
└─ Step 6: 性能基准测试（1小时）

Day 3: 可选优化（索引管理）
└─ Step 7: StorageManager 索引功能实现（4小时）
```

---

## Step 1: 环境准备与配置（30分钟）

### 目标
- 确认代码库状态
- 创建测试配置
- 准备测试数据

### 实施内容

1. **检查当前代码状态**
   ```bash
   # 确认当前分支
   git status
   
   # 检查核心文件是否存在且最新
   ls -lh app4/core/storage.py
   ls -lh app4/core/coverage_manager.py
   ls -lh app4/core/downloader.py
   ```

2. **创建测试接口配置**
   ```bash
   # 复制一个测试接口配置
   cp app4/config/interfaces/daily.yaml app4/config/interfaces/daily_test.yaml
   ```

3. **修改测试配置**
   编辑 `app4/config/interfaces/daily_test.yaml`：
   ```yaml
   name: daily_test
   api_name: daily
   
   pagination:
     enabled: true
     mode: "date_range"
     window_size_days: 365
   
   duplicate_detection:
     enabled: true
     mode: "hybrid_range"  # 新增混合模式
     date_column: trade_date
     threshold: 0.95
     partial_coverage: "download_missing"  # 部分覆盖策略
   
   # 其他配置保持不变...
   ```

### 验收标准 ✅

**验收命令 1：配置验证**
```bash
cd /home/quan/testdata/aspipe_v4/app4
python -c "
from core.config_loader import ConfigLoader
loader = ConfigLoader()
config = loader.get_interface_config('daily_test')
print('✓ 配置加载成功')
print(f"✓ 混合模式: {config.get('duplicate_detection', {}).get('mode')}")
print(f"✓ 阈值: {config.get('duplicate_detection', {}).get('threshold')}")
print(f"✓ 部分覆盖策略: {config.get('duplicate_detection', {}).get('partial_coverage')}")
"
```

**预期输出**：
```
✓ 配置加载成功
✓ 混合模式: hybrid_range
✓ 阈值: 0.95
✓ 部分覆盖策略: download_missing
```

**验收命令 2：交易日历可用性**
```bash
python -c "
from core.downloader import GenericDownloader
downloader = GenericDownloader()
calendar = downloader.get_trade_calendar('20240101', '20240131')
print(f'✓ 交易日历获取成功: {len(calendar)} 个交易日')
print(f'✓ 示例: {calendar[0] if calendar else \"无\"}')
"
```

**预期输出**：
```
✓ 交易日历获取成功: 22 个交易日
✓ 示例: {'cal_date': '20240102', 'is_open': 1}
```

---

## Step 2: CoverageManager 增强 - 混合覆盖检测（3小时）

### 目标
- 实现 `_check_mixed_coverage` 方法
- 支持部分覆盖场景识别
- 返回详细的覆盖信息

### 实施内容

1. **修改文件**: `app4/core/coverage_manager.py`

2. **添加新方法**（在 `_check_range_coverage` 之后）：
   ```python
   def _check_mixed_coverage(self, interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
       """
       混合范围覆盖检测 - 识别部分覆盖场景
       
       Returns:
           {
               'fully_covered': bool,
               'coverage_ratio': float,
               'missing_ranges': [('20230101', '20230115'), ...],
               'existing_ranges': [('20230116', '20230131'), ...],
               'total_expected_days': int,
               'total_covered_days': int,
               'recommendation': 'skip' | 'download_missing' | 'full_download'
           }
       """
       # 实现逻辑：提取文件名中的日期范围、合并重叠范围、计算差集
   ```

3. **实现步骤**：
   - 读取接口目录下所有文件名
   - 提取文件名中的日期范围（解析 `name_start_end_timestamp_uuid.parquet` 格式）
   - 合并重叠的日期范围
   - 计算目标范围与现有范围的差集（缺失范围）
   - 计算覆盖率
   - 根据阈值给出建议

### 验收标准 ✅

**验收命令 1：完全覆盖场景**
```bash
# 假设 daily 接口已有 20240101-20240131 的数据
python -c "
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

result = manager._check_mixed_coverage('daily', {
    'start_date': '20240101',
    'end_date': '20240131'
})

print('=== 完全覆盖场景验证 ===')
print(f'✓ 完全覆盖: {result[\"fully_covered\"]}')
print(f'✓ 覆盖率: {result[\"coverage_ratio\"]:.2%}')
print(f'✓ 缺失范围数: {len(result[\"missing_ranges\"])}')
print(f'✓ 建议: {result[\"recommendation\"]}')
"
```

**预期输出**：
```
=== 完全覆盖场景验证 ===
✓ 完全覆盖: True
✓ 覆盖率: 1.00 or 0.95+
✓ 缺失范围数: 0
✓ 建议: skip
```

**验收命令 2：部分覆盖场景**
```bash
# 假设 daily 接口只有 20240101-20240115 的数据，请求 20240101-20240131
python -c "
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

result = manager._check_mixed_coverage('daily', {
    'start_date': '20240101',
    'end_date': '20240131'
})

print('=== 部分覆盖场景验证 ===')
print(f'✓ 完全覆盖: {result[\"fully_covered\"]}')
print(f'✓ 覆盖率: {result[\"coverage_ratio\"]:.2%}')
print(f'✓ 缺失范围: {result[\"missing_ranges\"]}')
print(f'✓ 建议: {result[\"recommendation\"]}')
"
```

**预期输出**：
```
=== 部分覆盖场景验证 ===
✓ 完全覆盖: False
✓ 覆盖率: ~0.48 or < 0.95
✓ 缺失范围: [('20240116', '20240131')]
✓ 建议: download_missing
```

**验收命令 3：无覆盖场景**
```bash
# 假设 daily 接口没有数据
python -c "
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

result = manager._check_mixed_coverage('daily', {
    'start_date': '20231201',
    'end_date': '20231231'
})

print('=== 无覆盖场景验证 ===')
print(f'✓ 完全覆盖: {result[\"fully_covered\"]}')
print(f'✓ 覆盖率: {result[\"coverage_ratio\"]:.2%}')
print(f'✓ 缺失范围: {result[\"missing_ranges\"]}')
print(f'✓ 建议: {result[\"recommendation\"]}')
"
```

**预期输出**：
```
=== 无覆盖场景验证 ===
✓ 完全覆盖: False
✓ 覆盖率: 0.00%
✓ 缺失范围: [('20231201', '20231231')]
✓ 建议: full_download
```

### 调试技巧
如果验收不通过：
```bash
# 启用调试日志
export LOG_LEVEL=DEBUG

# 手动检查文件
ls -lh data/daily/*.parquet

# 解析文件名中的日期
python -c "
import os
files = os.listdir('data/daily')
for f in files:
    if f.endswith('.parquet'):
        parts = f.split('_')
        if len(parts) >= 4:
            print(f'文件: {f} -> 范围: {parts[1]} - {parts[2]}')
"
```

---

## Step 3: Downloader 改造 - 支持部分覆盖下载（2小时）

### 目标
- 修改日期范围分页逻辑
- 支持只下载缺失的数据范围
- 避免重复下载已有数据

### 实施内容

1. **修改文件**: `app4/core/downloader.py`

2. **定位代码**：第314-322行（`_execute_date_range_pagination` 方法内）

3. **修改覆盖率检查逻辑**（替换现有 `should_skip` 调用）：
   ```python
   # 旧代码（第314-322行）
   if self.coverage_manager:
       should_skip = self.coverage_manager.should_skip(
           interface_config['api_name'],
           window_params,
           strategy='date_range'
       )
       if should_skip:
           logger.info(f"Skipping window {window_start} - {window_end}")
           continue
   ```

   替换为：
   ```python
   # 新代码
   if self.coverage_manager:
       coverage_info = self.coverage_manager._check_mixed_coverage(
           interface_config['api_name'],
           window_params
       )
       
       if coverage_info['recommendation'] == 'skip':
           logger.info(f"Skipping window {window_start} - {window_end} (fully covered)")
           continue
       
       elif coverage_info['recommendation'] == 'download_missing':
           # 只下载缺失的范围
           logger.info(f"Partial coverage {coverage_info['coverage_ratio']:.2%}, downloading missing ranges: {coverage_info['missing_ranges']}")
           
           for missing_start, missing_end in coverage_info['missing_ranges']:
               adjusted_params = window_params.copy()
               adjusted_params['start_date'] = missing_start
               adjusted_params['end_date'] = missing_end
               
               missing_data = self._make_request(interface_config, adjusted_params)
               if missing_data:
                   all_results.extend(missing_data)
                   logger.info(f"Downloaded missing data for {missing_start} - {missing_end}: {len(missing_data)} records")
           
           continue  # 已处理，继续下一个窗口
   
   # recommendation == 'full_download' 继续执行原逻辑
   ```

### 验收标准 ✅

**验收命令 1：测试部分覆盖下载**

准备测试环境：
```bash
# 1. 清理测试接口数据
rm -rf data/daily_test

# 2. 创建部分数据（模拟已有20240101-20240115的数据）
mkdir -p data/daily_test
cp data/daily/daily_20240101_20240115_*.parquet data/daily_test/ 2>/dev/null || echo "Note: 需要先下载一些数据"

# 3. 查看现有数据
ls -lh data/daily_test/
```

运行测试下载：
```bash
python -c "
import sys
sys.path.insert(0, 'app4')

from core.downloader import GenericDownloader
from core.config_loader import ConfigLoader
from core.storage_manager import StorageManager

# 初始化组件
config_loader = ConfigLoader()
storage = StorageManager()
downloader = GenericDownloader()

# 加载测试接口配置
interface_config = config_loader.get_interface_config('daily_test')
print(f'✓ 接口配置加载: {interface_config[\"name\"]}')

# 请求包含已有数据 + 缺失数据的范围
params = {
    'ts_code': '000001.SZ',
    'start_date': '20240101',
    'end_date': '20240131'
}

print(f'\n=== 开始下载测试 ===')
print(f'请求范围: {params[\"start_date\"]} - {params[\"end_date\"]}')
print(f'预期行为: 跳过 20240101-20240115，只下载 20240116-20240131')

result = downloader.download(interface_config, params)

print(f'✓ 下载完成: {len(result)} 条记录')
print(f'✓ 预期: 只包含 20240116-20240131 的数据')

# 验证结果
dates = sorted(set([r.get('trade_date') for r in result]))
print(f'实际日期范围: {dates[0] if dates else \"无\"} - {dates[-1] if dates else \"无\"}')
print(f'日期数量: {len(dates)}')
"
```

**预期输出**：
```
✓ 接口配置加载: daily_test

=== 开始下载测试 ===
请求范围: 20240101 - 20240131
预期行为: 跳过 20240101-20240115，只下载 20240116-20240131

INFO: Checking coverage for daily_test (20240101-20240131)
INFO: Partial coverage 48.00%, downloading missing ranges: [('20240116', '20240131')]
INFO: Downloading missing data for 20240116-20240131
INFO: Downloaded missing data for 20240116-20240131: 11 records
✓ 下载完成: 11 条记录
✓ 预期: 只包含 20240116-20240131 的数据
实际日期范围: 20240116 - 20240131
日期数量: 11
```

**验收命令 2：验证数据完整性**
```bash
python -c "
import polars as pl
import os

# 读取存储的数据
dir_path = 'data/daily_test'
files = [os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith('.parquet')]

if files:
    df = pl.read_parquet(files)
    df = df.filter(pl.col('ts_code') == '000001.SZ')
    
    print('=== 数据完整性验证 ===')
    print(f'✓ 总记录数: {len(df)}')
    print(f'✓ 日期范围: {df[\"trade_date\"].min()} - {df[\"trade_date\"].max()}')
    print(f'✓ 唯一日期数: {df[\"trade_date\"].n_unique()}')
    
    # 检查是否有重复日期
    dates = df['trade_date'].to_list()
    unique_dates = set(dates)
    print(f'✓ 是否有重复日期: {\"否\" if len(dates) == len(unique_dates) else \"是\"}')
    
    # 检查是否覆盖完整范围
    all_dates_exist = all(d in unique_dates for d in range(20240116, 20240132))
    print(f'✓ 20240116-20240131 是否全部存在: {\"是\" if all_dates_exist else \"否\"}')
else:
    print('⚠ 无数据文件')
"
```

**预期输出**：
```
=== 数据完整性验证 ===
✓ 总记录数: 11
✓ 日期范围: 20240116 - 20240131
✓ 唯一日期数: 11
✓ 是否有重复日期: 否
✓ 20240116-20240131 是否全部存在: 是
```

### 调试技巧
如果验收不通过：
```bash
# 1. 检查日志输出
export LOG_LEVEL=DEBUG
python test_script.py 2>&1 | grep -E "(coverage|missing|skip)"

# 2. 验证覆盖率检测逻辑
python -c "
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

# 手动检查
result = manager._check_mixed_coverage('daily_test', {'start_date': '20240101', 'end_date': '20240131'})
print('覆盖率检查结果:', result)
"

# 3. 检查文件名解析
python -c "
import os
files = os.listdir('data/daily_test')
print('数据文件:')
for f in files:
    if f.endswith('.parquet'):
        parts = f.split('_')
        print(f'  {f} -> 范围: {parts[1]} - {parts[2]}')
"
```

---

## Step 4: 配置扩展与接口测试（2小时）

### 目标
- 验证不同阈值配置的效果
- 测试多个接口的兼容性
- 确保配置热加载正常工作

### 实施内容

1. **创建多个测试配置**
   
   a. **高阈值配置**（严格要求 99%）：
   ```bash
   cp app4/config/interfaces/daily.yaml app4/config/interfaces/daily_strict.yaml
   ```
   
   修改 `daily_strict.yaml`：
   ```yaml
   duplicate_detection:
     enabled: true
     mode: "hybrid_range"
     threshold: 0.99  # 99% 阈值
     partial_coverage: "download_missing"
   ```
   
   b. **低阈值配置**（宽松要求 80%）：
   ```bash
   cp app4/config/interfaces/daily.yaml app4/config/interfaces/daily_loose.yaml
   ```
   
   修改 `daily_loose.yaml`：
   ```yaml
   duplicate_detection:
     enabled: true
     mode: "hybrid_range"
     threshold: 0.80  # 80% 阈值
     partial_coverage: "download_missing"
   ```

2. **创建非日期接口测试配置**
   
   测试 `income_vip`（报告期接口）：
   ```bash
   cp app4/config/interfaces/income_vip.yaml app4/config/interfaces/income_vip_test.yaml
   ```
   
   修改 `income_vip_test.yaml`：
   ```yaml
   duplicate_detection:
     enabled: true
     mode: "hybrid_range"  # 即使不是日期范围接口，也应优雅降级
     date_column: period
     threshold: 0.95
   ```

### 验收标准 ✅

**验收命令 1：阈值效果验证**

准备测试数据（模拟 90% 覆盖）：
```bash
# 创建测试数据：在 20240101-20240131 (23个交易日) 中只有 20 天的数据
# 覆盖率 = 20/23 ≈ 87%
mkdir -p data/daily_strict_test
cp data/daily/daily_20240101_20240120_*.parquet data/daily_strict_test/ 2>/dev/null
```

测试严格阈值（99%）：
```bash
python -c "
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

result = manager._check_mixed_coverage('daily_strict', {
    'start_date': '20240101',
    'end_date': '20240131'
})

print('=== 严格阈值 (99%) 测试 ===')
print(f'覆盖率: {result[\"coverage_ratio\"]:.2%}')
print(f'建议: {result[\"recommendation\"]}')
print(f'✓ 预期: full_download (87% < 99%)')
print(f'✓ 实际结果符合预期: {\"✓\" if result[\"recommendation\"] == \"full_download\" else \"✗\"}')
"
```

**预期输出**：
```
=== 严格阈值 (99%) 测试 ===
覆盖率: 86.96%
建议: full_download
✓ 预期: full_download (87% < 99%)
✓ 实际结果符合预期: ✓
```

测试宽松阈值（80%）：
```bash
python -c "
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

result = manager._check_mixed_coverage('daily_loose', {
    'start_date': '20240101',
    'end_date': '20240131'
})

print('=== 宽松阈值 (80%) 测试 ===')
print(f'覆盖率: {result[\"coverage_ratio\"]:.2%}')
print(f'建议: {result[\"recommendation\"]}')
print(f'✓ 预期: download_missing (87% > 80%)')
print(f'✓ 实际结果符合预期: {\"✓\" if result[\"recommendation\"] == \"download_missing\" else \"✗\"}')
"
```

**预期输出**：
```
=== 宽松阈值 (80%) 测试 ===
覆盖率: 86.96%
建议: download_missing
✓ 预期: download_missing (87% > 80%)
✓ 实际结果符合预期: ✓
```

**验收命令 2：配置热加载验证**
```bash
python -c "
from core.config_loader import ConfigLoader

loader = ConfigLoader()

# 测试不同配置的阈值
configs = ['daily', 'daily_strict', 'daily_loose']

print('=== 配置热加载验证 ===')
for config_name in configs:
    config = loader.get_interface_config(config_name)
    dd = config.get('duplicate_detection', {})
    print(f'✓ {config_name:20s}: mode={dd.get(\"mode\", \"N/A\"):15s} threshold={dd.get(\"threshold\", \"N/A\")}')

print('\n✓ 所有配置加载成功，支持热加载')
"
```

**预期输出**：
```
=== 配置热加载验证 ===
✓ daily               : mode=hybrid_range   threshold=0.95
✓ daily_strict        : mode=hybrid_range   threshold=0.99
✓ daily_loose         : mode=hybrid_range   threshold=0.8

✓ 所有配置加载成功，支持热加载
```

---

## Step 5: 真实场景集成测试（3小时）

### 目标
- 在真实业务场景中验证功能
- 测试边界情况和异常处理
- 验证性能提升效果

### 实施内容

1. **准备真实测试场景**
   
   场景 A：历史数据补全（已有大部分数据，补全小部分）
   ```bash
   # 已有数据：20240101-20240125 (缺失最后几天)
   # 请求范围：20240101-20240131
   ```
   
   场景 B：定期增量更新（已有全部历史数据，只更新最新）
   ```bash
   # 已有数据：20240101-20240131
   # 请求范围：20240101-20240205 (新增2月数据)
   ```
   
   场景 C：大范围首次下载（无历史数据）
   ```bash
   # 已有数据：无
   # 请求范围：20240101-20240331
   ```

2. **创建测试脚本**
   
   创建 `test_hybrid_coverage.py`：
   ```bash
   cat > test_hybrid_coverage.py << 'EOF'
   #!/usr/bin/env python3
   """混合覆盖检测集成测试脚本"""
   
   import sys
   import time
   import os
   sys.path.insert(0, 'app4')
   
   from core.downloader import GenericDownloader
   from core.config_loader import ConfigLoader
   from core.storage_manager import StorageManager
   import polars as pl
   
   def test_scenario(name, ts_code, start_date, end_date, existing_ranges):
       """测试场景"""
       print(f"\n{'='*60}")
       print(f"场景: {name}")
       print(f"{'='*60}")
       
       # 1. 准备数据（模拟已有数据）
       test_dir = f"data/daily_scenario_{name.replace(' ', '_')}"
       os.makedirs(test_dir, exist_ok=True)
       
       # 清理旧数据
       for f in os.listdir(test_dir):
           os.remove(os.path.join(test_dir, f))
       
       # 复制已有数据文件
       if existing_ranges:
           print(f"模拟已有数据范围: {existing_ranges}")
           for start, end in existing_ranges:
               # 查找并复制对应文件
               for f in os.listdir('data/daily'):
                   if f.endswith('.parquet'):
                       parts = f.split('_')
                       if len(parts) >= 4 and parts[1] == start and parts[2] == end:
                           src = os.path.join('data/daily', f)
                           dst = os.path.join(test_dir, f)
                           if os.path.exists(src):
                               import shutil
                               shutil.copy2(src, dst)
                               print(f"  复制: {f}")
       
       # 2. 执行下载
       print(f"\n请求下载: {start_date} - {end_date}")
       print("-" * 60)
       
       start_time = time.time()
       
       downloader = GenericDownloader()
       interface_config = ConfigLoader().get_interface_config('daily')
       
       params = {
           'ts_code': ts_code,
           'start_date': start_date,
           'end_date': end_date
       }
       
       try:
           result = downloader.download(interface_config, params)
           
           elapsed = time.time() - start_time
           
           # 3. 验证结果
           if result:
               df = pl.DataFrame(result)
               actual_dates = sorted(df['trade_date'].unique())
               
               print(f"\n✓ 下载完成: {len(result)} 条记录")
               print(f"✓ 耗时: {elapsed:.2f} 秒")
               print(f"✓ 日期范围: {actual_dates[0]} - {actual_dates[-1]}")
               print(f"✓ 交易日数量: {len(actual_dates)}")
               
               # 检查是否有重复
               if len(actual_dates) != df['trade_date'].n_unique():
                   print(f"⚠ 警告: 存在重复日期")
               
               return True, elapsed, len(result)
           else:
               print(f"✓ 无新数据下载（可能已全部存在）")
               return True, elapsed, 0
               
       except Exception as e:
           print(f"✗ 下载失败: {e}")
           return False, 0, 0
   
   if __name__ == "__main__":
       print("混合覆盖检测集成测试")
       
       scenarios = [
           # (场景名称, 股票代码, 开始日期, 结束日期, 已有数据范围)
           ("历史数据补全", "000001.SZ", "20240101", "20240131", [("20240101", "20240125")]),
           ("增量更新", "000001.SZ", "20240101", "20240205", [("20240101", "20240131")]),
           ("首次下载", "000001.SZ", "20240101", "20240131", []),
       ]
       
       results = []
       for scenario in scenarios:
           success, elapsed, count = test_scenario(*scenario)
           results.append((scenario[0], success, elapsed, count))
       
       # 汇总报告
       print(f"\n{'='*60}")
       print("测试总结")
       print(f"{'='*60}")
       
       for name, success, elapsed, count in results:
           status = "✓ 通过" if success else "✗ 失败"
           print(f"{status} {name:20s}: {count:6d} 条记录, {elapsed:.2f} 秒")
   
   EOF
   
   chmod +x test_hybrid_coverage.py
   ```

### 验收标准 ✅

**验收命令：运行集成测试**
```bash
python test_hybrid_coverage.py
```

**预期输出**：
```
混合覆盖检测集成测试

============================================================
场景: 历史数据补全
============================================================
模拟已有数据范围: [('20240101', '20240125')]

请求下载: 20240101 - 20240131
------------------------------------------------------------
INFO: Checking coverage for daily (20240101-20240131)
INFO: Partial coverage 80.77%, downloading missing ranges: [('20240126', '20240131')]
INFO: Downloaded missing data for 20240126-20240131: 4 records

✓ 下载完成: 4 条记录
✓ 耗时: 2.15 秒
✓ 日期范围: 20240126 - 20240131
✓ 交易日数量: 4

============================================================
场景: 增量更新
============================================================
模拟已有数据范围: [('20240101', '20240131')]

请求下载: 20240101 - 20240205
------------------------------------------------------------
INFO: Checking coverage for daily (20240101-20240205)
INFO: Partial coverage 86.36%, downloading missing ranges: [('20240201', '20240205')]
INFO: Downloaded missing data for 20240201-20240205: 4 records

✓ 下载完成: 4 条记录
✓ 耗时: 2.08 秒
✓ 日期范围: 20240201 - 20240205
✓ 交易日数量: 4

============================================================
场景: 首次下载
============================================================
模拟已有数据范围: []

请求下载: 20240101 - 20240131
------------------------------------------------------------
INFO: Checking coverage for daily (20240101-20240131)
INFO: No existing data found, downloading full range
INFO: Downloaded data for 20240101-20240131: 23 records

✓ 下载完成: 23 条记录
✓ 耗时: 5.32 秒
✓ 日期范围: 20240101 - 20240131
✓ 交易日数量: 23

============================================================
测试总结
============================================================
✓ 通过 历史数据补全      :      4 条记录, 2.15 秒
✓ 通过 增量更新          :      4 条记录, 2.08 秒
✓ 通过 首次下载          :     23 条记录, 5.32 秒
```

### 关键验证点

1. **历史数据补全**：只下载缺失的 4 天，而不是 31 天 ✅
2. **增量更新**：只下载 2 月新增的 4 天，而不是 36 天 ✅
3. **首次下载**：完整下载 23 天 ✅
4. **性能提升**：场景1和2明显快于场景3 ✅

---

## Step 6: 性能基准测试（1小时）

### 目标
- 量化性能提升效果
- 验证覆盖率检查开销
- 确保不引入性能退化

### 实施内容

1. **创建性能测试脚本**
   
   ```bash
   cat > benchmark_coverage.py << 'EOF'
   #!/usr/bin/env python3
   """性能基准测试脚本"""
   
   import sys
   import time
   import os
   import statistics
   sys.path.insert(0, 'app4')
   
   from core.coverage_manager import CoverageManager
   from core.storage_manager import StorageManager
   from core.config_loader import ConfigLoader
   
   def benchmark_coverage_check():
       """基准测试：覆盖率检查性能"""
       print("="*60)
       print("覆盖率检查性能基准测试")
       print("="*60)
       
       storage = StorageManager()
       config_loader = ConfigLoader()
       manager = CoverageManager(storage, config_loader)
       
       # 测试不同数据量场景
       scenarios = [
           ("少量文件", "daily_test", 5),  # 假设有5个文件
           ("中等文件", "daily", 50),      # 假设有50个文件
       ]
       
       for name, interface, expected_files in scenarios:
           print(f"\n{name}: {interface}")
           print("-" * 60)
           
           # 检查实际文件数量
           dir_path = f"data/{interface}"
           if os.path.exists(dir_path):
               actual_files = len([f for f in os.listdir(dir_path) if f.endswith('.parquet')])
               print(f"实际数据文件数: {actual_files}")
           else:
               print(f"⚠ 数据目录不存在: {dir_path}")
               continue
           
           # 多次测量取平均值
           times = []
           for i in range(10):
               start = time.perf_counter()
               result = manager._check_mixed_coverage(interface, {
                   'start_date': '20240101',
                   'end_date': '20240131'
               })
               elapsed = time.perf_counter() - start
               times.append(elapsed * 1000)  # 转换为毫秒
           
           avg_time = statistics.mean(times)
           min_time = min(times)
           max_time = max(times)
           
           print(f"覆盖率检查耗时:")
           print(f"  平均: {avg_time:.2f} ms")
           print(f"  最小: {min_time:.2f} ms")
           print(f"  最大: {max_time:.2f} ms")
           print(f"  标准差: {statistics.stdev(times):.2f} ms")
           
           # 验收标准
           if avg_time < 10:
               print(f"✓ 性能优秀 (< 10ms)")
           elif avg_time < 100:
               print(f"✓ 性能良好 (< 100ms)")
           else:
               print(f"⚠ 性能待优化 (>= 100ms)")
   
   def benchmark_download_with_coverage():
       """基准测试：带覆盖率检查的整体下载性能"""
       print("\n" + "="*60)
       print("整体下载性能基准测试")
       print("="*60)
       
       from core.downloader import GenericDownloader
       
       downloader = GenericDownloader()
       interface_config = ConfigLoader().get_interface_config('daily_test')
       
       # 测试场景：已有大部分数据，只缺一小部分
       print("\n场景: 90% 数据已存在，下载 10% 缺失数据")
       print("-" * 60)
       
       params = {
           'ts_code': '000001.SZ',
           'start_date': '20240101',
           'end_date': '20240131'
       }
       
       # 预热
       print("预热...")
       downloader.download(interface_config, params)
       
       # 正式测试
       times = []
       record_counts = []
       
       for i in range(5):
           start = time.perf_counter()
           result = downloader.download(interface_config, params)
           elapsed = time.perf_counter() - start
           
           times.append(elapsed)
           record_counts.append(len(result) if result else 0)
           
           print(f"第 {i+1} 次: {elapsed:.2f} 秒, {len(result) if result else 0} 条记录")
       
       avg_time = statistics.mean(times)
       total_records = sum(record_counts)
       
       print(f"\n平均耗时: {avg_time:.2f} 秒")
       print(f"总下载记录: {total_records} (应远小于 23 * 5 = 115)")
       print(f"每次平均: {total_records / len(record_counts):.1f} 条")
       
       if avg_time < 3.0:
           print("✓ 性能优秀 (< 3秒)")
       elif avg_time < 5.0:
           print("✓ 性能良好 (< 5秒)")
       else:
           print("⚠ 性能待优化 (>= 5秒)")
   
   if __name__ == "__main__":
       benchmark_coverage_check()
       benchmark_download_with_coverage()
   EOF
   
   chmod +x benchmark_coverage.py
   ```

### 验收标准 ✅

**验收命令：运行性能基准测试**
```bash
python benchmark_coverage.py
```

**预期输出**：

```
============================================================
覆盖率检查性能基准测试
============================================================

少量文件: daily_test
------------------------------------------------------------
实际数据文件数: 3
覆盖率检查耗时:
  平均: 3.45 ms
  最小: 2.12 ms
  最大: 8.91 ms
  标准差: 1.23 ms
✓ 性能优秀 (< 10ms)

中等文件: daily
------------------------------------------------------------
实际数据文件数: 45
覆盖率检查耗时:
  平均: 12.34 ms
  最小: 8.45 ms
  最大: 25.67 ms
  标准差: 3.45 ms
✓ 性能良好 (< 100ms)

============================================================
整体下载性能基准测试
============================================================

场景: 90% 数据已存在，下载 10% 缺失数据
------------------------------------------------------------
预热...
第 1 次: 2.15 秒, 2 条记录
第 2 次: 1.98 秒, 2 条记录
第 3 次: 2.23 秒, 2 条记录
第 4 次: 2.05 秒, 2 条记录
第 5 次: 2.11 秒, 2 条记录

平均耗时: 2.10 秒
总下载记录: 10 (应远小于 23 * 5 = 115)
每次平均: 2.0 条
✓ 性能优秀 (< 3秒)
```

### 性能验收标准

| 指标 | 目标 | 验收结果 |
|------|------|----------|
| 覆盖率检查（少量文件） | < 10ms | ✓ 通过 |
| 覆盖率检查（50个文件） | < 100ms | ✓ 通过 |
| 增量下载（10%数据） | < 3秒 | ✓ 通过 |
| 重复下载跳过 | < 1秒 | ✓ 通过 |

---

## Step 7: 可选优化 - StorageManager 索引管理（4小时）

### 目标
- 实现索引文件管理（_index.parquet）
- 支持更快的索引查询（无需扫描文件名）
- 提供索引缓存机制

### 实施内容

1. **修改文件**: `app4/core/storage.py`

2. **添加索引管理方法**：
   ```python
   class StorageManager:
       def __init__(self, ...):
           # ... 现有代码 ...
           self._index_cache = {}  # 新增：索引缓存
           self._index_lock = threading.RLock()  # 新增：并发控制
       
       def _get_interface_index_path(self, interface_name: str) -> str:
           """获取接口索引文件路径"""
           # ...
       
       def _get_interface_index(self, interface_name: str) -> Optional[pl.DataFrame]:
           """获取接口索引（带缓存）"""
           # ...
       
       def _update_interface_index(self, interface_name: str, file_path: str, df: pl.DataFrame):
           """更新接口索引"""
           # ...
   ```

3. **在写入后更新索引**：修改 `_write_interface_data` 方法
   ```python
   def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
       # ... 现有写入逻辑 ...
       
       # 新增：写入成功后更新索引
       self._update_interface_index(interface_name, file_path, df)
   ```

4. **优化 CoverageManager**：修改 `_check_mixed_coverage` 使用索引
   ```python
   def _check_mixed_coverage(self, interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
       # 优先使用索引查询
       index_df = self.storage_manager._get_interface_index(interface_name)
       if index_df is not None and not index_df.is_empty():
           # 使用索引数据计算覆盖范围
           # ... 更高效的实现 ...
   ```

### 验收标准 ✅

**验收命令 1：索引创建与查询**
```bash
# 1. 确认索引文件生成
python -c "
from core.storage_manager import StorageManager

storage = StorageManager()

# 触发一次数据写入（如果有新数据）
# storage.save_data('daily_test', [{'ts_code': 'test', 'trade_date': 20240101}])

# 检查索引文件是否存在
import os
index_path = 'data/daily_test/_index.parquet'
print(f'索引文件存在: {\"✓\" if os.path.exists(index_path) else \"✗\"}')

if os.path.exists(index_path):
    import polars as pl
    df = pl.read_parquet(index_path)
    print(f'索引记录数: {len(df)}')
    print(f'索引列: {df.columns}')
    print(f'示例数据:')
    print(df.head(3))
"
```

**预期输出**：
```
索引文件存在: ✓
索引记录数: 3
索引列: ['file_path', 'min_date', 'max_date', 'row_count', 'update_time']
示例数据:
shape: (3, 5)
┌────────────────────────────────────────────────┬──────────┬──────────┬───────────┬────────────┐
│ file_path                                      ┆ min_date ┆ max_date ┆ row_count ┆ update_tim │
│ ---                                            ┆ ---      ┆ ---      ┆ ---       ┆ e          │
│ str                                            ┆ i64      ┆ i64      ┆ u32       ┆ ---        │
│                                                ┆          ┆          ┆           ┆ i64        │
╞════════════════════════════════════════════════╪══════════╪══════════╪═══════════╪════════════╡
│ data/daily_test/daily_test_20240101_2024011... ┆ 20240101 ┆ 20240115 ┆ 15        ┆ 1736870400 │
│ data/daily_test/daily_test_20240116_2024013... ┆ 20240116 ┆ 20240131 ┆ 8         ┆ 1736870500 │
│ data/daily_test/daily_test_20240201_2024020... ┆ 20240201 ┆ 20240205 ┆ 4         ┆ 1736870600 │
└────────────────────────────────────────────────┴──────────┴──────────┴───────────┴────────────┘
```

**验收命令 2：索引查询性能对比**
```bash
python -c "
import time
from core.coverage_manager import CoverageManager
from core.storage_manager import StorageManager
from core.config_loader import ConfigLoader

storage = StorageManager()
config_loader = ConfigLoader()
manager = CoverageManager(storage, config_loader)

# 测试带索引的查询性能
times = []
for i in range(20):
    start = time.perf_counter()
    result = manager._check_mixed_coverage('daily_test', {
        'start_date': '20240101',
        'end_date': '20240131'
    })
    elapsed = time.perf_counter() - start
    times.append(elapsed * 1000)

avg_time = sum(times) / len(times)
print(f'索引查询平均耗时: {avg_time:.2f} ms')
print(f'✓ 预期: < 5ms（应有显著提升）')
print(f'✓ 实际: {\"✓ 通过\" if avg_time < 5 else \"✗ 未通过\"}')
"
```

**预期输出**：
```
索引查询平均耗时: 2.34 ms
✓ 预期: < 5ms（应有显著提升）
✓ 实际: ✓ 通过
```

### 性能对比

| 查询方式 | 平均耗时 | 性能提升 |
|----------|----------|----------|
| 文件名扫描 | ~10-15ms | 基准 |
| 索引查询 | ~2-3ms | **5-7倍提升** |

---

## 📊 实施进度跟踪

### 每日进度检查

**Day 1 检查清单**:
- [ ] Step 1 环境准备完成（配置验证通过）
- [ ] Step 2 CoverageManager 增强完成（3个验收命令通过）
- [ ] Step 3 Downloader 改造完成（2个验收命令通过）

**Day 2 检查清单**:
- [ ] Step 4 配置扩展完成（2个验收命令通过）
- [ ] Step 5 集成测试完成（所有场景通过）
- [ ] Step 6 性能基准完成（所有指标达标）

**Day 3 检查清单**（可选）:
- [ ] Step 7 索引优化完成（2个验收命令通过）

### 问题处理

如果在某一步验收失败：

1. **检查日志**
   ```bash
   export LOG_LEVEL=DEBUG
   python test_script.py 2>&1 | tee debug.log
   ```

2. **验证前置条件**
   ```bash
   # 检查数据是否存在
   ls -lh data/daily/*.parquet | head -10
   
   # 检查配置文件
   ls -lh app4/config/interfaces/*.yaml | grep daily
   ```

3. **回滚方案**
   ```bash
   # 如果发现问题，可以快速回滚
   git checkout app4/core/coverage_manager.py
   git checkout app4/core/downloader.py
   ```

---

## 🎯 成功标准

### 功能性标准
- ✓ 完全覆盖场景：正确跳过，不重复下载
- ✓ 部分覆盖场景：只下载缺失部分，不重复下载
- ✓ 无覆盖场景：完整下载全部数据
- ✓ 配置热加载：支持不同阈值和策略
- ✓ 异常处理：优雅降级，不影响主流程

### 性能标准
- ✓ 覆盖率检查 < 100ms（50个文件场景）
- ✓ 增量下载 < 3秒（90%已存在）
- ✓ 重复下载跳过 < 1秒（100%已存在）
- ✓ 无内存泄漏，CPU使用正常

### 稳定性标准
- ✓ 连续运行 100 次无崩溃
- ✓ 并发调用无数据竞争
- ✓ 索引与数据保持一致性
- ✓ 失败时自动回退到传统模式

---

## 📝 实施记录

### 实施人员
- 开发：[填写姓名]
- 测试：[填写姓名]
- 审核：[填写姓名]

### 实施日期
- 开始日期：2026-01-XX
- 预计完成：2026-01-XX
- 实际完成：[待填写]

### 关键决策
1. **索引优化为可选步骤**：基于当前文件名过滤已足够高效（< 15ms），索引优化作为第二阶段
2. **缓存 TTL 默认 1 小时**：平衡内存占用和查询性能
3. **覆盖率阈值默认 95%**：在数据完整性和性能之间取得平衡

---

## 🔗 相关文档

- 方案设计文档：`hybrid_range_coverage_solution.md`
- 接口配置示例：`app4/config/interfaces/daily.yaml`
- 核心代码：`app4/core/coverage_manager.py`, `app4/core/downloader.py`

---

**版本历史**
- v1.0: 2026-01-14 初始版本
- v1.1: 2026-01-14 添加性能基准测试步骤
