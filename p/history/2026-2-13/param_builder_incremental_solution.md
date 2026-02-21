# App4 参数构建渐进式重构方案

## 一、背景

基于对原简化方案的反馈分析和源代码验证，本方案提出更适合 app4 当前代码状态的渐进式重构路径。

**核心观点**：现有代码结构不是错误的——只是需要清理和提取，不需要大规模重构。

---

## 二、问题分析

### 2.1 参数构建逻辑分布现状

通过代码分析，参数构建逻辑分散在多个文件：

| 位置 | 职责 | 代码行数 |
|------|------|---------|
| [main.py#L333-383](app4/main.py#L333-L383) | `run_update_mode()` 中的场景判断 | ~50行 |
| [main.py#L967-1007](app4/main.py#L967-L1007) | `main()` 中的场景判断（几乎相同逻辑） | ~40行 |
| [main.py#L1046-1068](app4/main.py#L1046-L1068) | broker_recommend 特殊处理 | ~22行 |
| [downloader.py#L416-540](app4/core/downloader.py#L416-L540) | 单股票参数处理（gap detection、日期默认值） | ~125行 |
| [pagination_executor.py#L73-95](app4/core/pagination_executor.py#L73-L95) | 参数生成器（_date_anchor_param、_stock_full_history） | ~22行 |

### 2.2 原简化方案的问题

| 问题 | 说明 |
|------|------|
| 试图统一所有逻辑 | 会与 PaginationExecutor 现有逻辑冲突 |
| 新增 special_handling 配置 | 收益不大，只有 2-3 个特殊接口 |
| 步子太大 | 风险高，改动面广 |

---

## 三、方案：渐进式重构

### 3.1 策略

**最小改动原则**：只提取重复代码为独立函数，不改变现有逻辑和组件边界。

```
阶段1：提取场景判断函数（低风险）
阶段2：提取工具函数（中风险）
阶段3：统一调用入口（可选，低优先级）
```

### 3.2 阶段1：提取场景判断函数

#### 目标

将 main.py 中两处几乎相同的场景判断逻辑提取为独立函数，消除重复代码。

#### 新增文件

创建 `app4/core/param_utils.py`：

```python
"""
参数工具函数 - 场景检测和参数处理
"""
from typing import Dict, Any, Tuple, Optional
from enum import Enum


class DownloadScenario(Enum):
    """下载场景类型"""
    DIRECT = "direct"                      # 直接下载，无股票循环
    STOCK_LOOP_DATE = "stock_loop_date"   # 股票循环 + 日期范围
    STOCK_LOOP_ANCHOR = "stock_loop_anchor"  # 股票循环 + 日期锚点
    STOCK_LOOP_FULL = "stock_loop_full"   # 股票循环 + 全历史


def detect_download_scenario(
    interface_config: Dict[str, Any],
    interface_name: str,
    user_provided_dates: bool = False,
    has_ts_code: bool = False,
    is_update_mode: bool = False
) -> Tuple[DownloadScenario, Dict[str, Any]]:
    """
    根据接口配置检测下载场景
    
    Args:
        interface_config: 接口配置
        interface_name: 接口名称（用于特殊处理）
        user_provided_dates: 用户是否提供了日期范围
        has_ts_code: 是否指定了股票代码
        is_update_mode: 是否为增量更新模式
        
    Returns:
        (场景类型, 内部参数标记字典)
    """
    pagination = interface_config.get('pagination', {})
    
    # 非股票循环模式
    if not pagination.get('enabled') or pagination.get('mode') != 'stock_loop':
        return DownloadScenario.DIRECT, {}
    
    # 股票循环模式：判断子场景
    params_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in params_config and 'end_date' in params_config
    
    # 检查日期锚点参数
    date_anchor_param = None
    for param_name, param_def in params_config.items():
        if param_def.get('is_date_anchor', False):
            date_anchor_param = param_name
            break
    
    # 场景1：支持 start_date/end_date
    if has_start_end:
        return DownloadScenario.STOCK_LOOP_DATE, {}
    
    # 场景2：日期锚点参数
    elif date_anchor_param:
        internal_params = {'_date_anchor_param': date_anchor_param}
        
        # 特殊处理：单股票全历史
        if has_ts_code and not user_provided_dates:
            return DownloadScenario.STOCK_LOOP_FULL, {}
        
        # 特殊处理：disclosure_date 在更新模式下无日期时全历史
        if is_update_mode and interface_name == 'disclosure_date' and not user_provided_dates and not has_ts_code:
            return DownloadScenario.STOCK_LOOP_FULL, {}
        
        return DownloadScenario.STOCK_LOOP_ANCHOR, internal_params
    
    # 场景3：无日期参数，全历史
    else:
        return DownloadScenario.STOCK_LOOP_FULL, {'_stock_full_history': True}


def clean_internal_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """清理内部标记参数，返回可用于API请求的参数"""
    return {k: v for k, v in params.items() if not k.startswith('_')}
```

#### 改动 main.py

在 `run_update_mode()` 中使用新函数：

```python
# 原来 ~50 行代码替换为：
from core.param_utils import detect_download_scenario, clean_internal_params

scenario, internal_params = detect_download_scenario(
    interface_config=interface_config,
    interface_name=interface_name,
    user_provided_dates=user_provided_dates,
    has_ts_code=bool(args.ts_code),
    is_update_mode=True
)

if scenario == DownloadScenario.DIRECT:
    # 直接下载模式
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    if args.ts_code:
        params['ts_code'] = args.ts_code

elif scenario == DownloadScenario.STOCK_LOOP_DATE:
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    if args.ts_code:
        params['ts_code'] = args.ts_code

elif scenario == DownloadScenario.STOCK_LOOP_ANCHOR:
    params = {
        'start_date': start_date,
        'end_date': end_date,
        **internal_params
    }
    if args.ts_code:
        params['ts_code'] = args.ts_code

else:  # STOCK_LOOP_FULL
    params = internal_params.copy()
    if args.ts_code:
        params['ts_code'] = args.ts_code
```

在 `main()` 中做类似修改（复用同一函数）。

### 3.3 阶段2：提取 broker_recommend 处理

#### 目标

将 main.py 中的 broker_recommend 特殊处理提取为独立函数。

#### 扩展 param_utils.py

```python
def build_special_interface_params(
    interface_name: str,
    params: Dict[str, Any],
    downloader: Any
) -> Optional[list]:
    """
    构建特殊接口参数并执行下载
    
    Args:
        interface_name: 接口名称
        params: 基础参数
        downloader: 下载器实例
        
    Returns:
        下载的数据列表，如果不需要特殊处理返回 None
    """
    if interface_name == 'broker_recommend':
        import polars as pl
        from datetime import datetime
        
        start = datetime.strptime(params['start_date'], '%Y%m%d')
        end = datetime.strptime(params['end_date'], '%Y%m%d')
        months = pl.date_range(start, end, '1mo', eager=True).dt.strftime('%Y%m').to_list()
        
        all_data = []
        for month in months:
            month_params = {'month': month}
            if 'ts_code' in params:
                month_params['ts_code'] = params['ts_code']
            data = downloader.download(interface_name, month_params)
            if data:
                all_data.extend(data)
        
        return all_data
    
    # 其他特殊接口...
    return None
```

#### 改动 main.py

```python
# 在循环中调用
special_data = build_special_interface_params(
    interface_name, params, downloader
)
if special_data is not None:
    # 已处理，直接继续下一个接口
    process_and_save_data(special_data, ...)
    continue
```

### 3.4 阶段3（可选）：统一参数构建入口

在阶段1和2稳定后，可选地创建一个薄封装函数：

```python
def build_params(
    interface_config: Dict[str, Any],
    interface_name: str,
    args: Any,
    date_range: Dict[str, str],
    user_provided_dates: bool,
    downloader: Any = None
) -> Tuple[Dict[str, Any], Optional[list]]:
    """
    统一参数构建入口
    
    Returns:
        (params, special_data): 常规参数和特殊接口数据
    """
    # 检测场景
    scenario, internal_params = detect_download_scenario(
        interface_config, interface_name, user_provided_dates,
        bool(getattr(args, 'ts_code', None)), is_update_mode=True
    )
    
    # 构建参数...
    
    # 特殊接口处理
    special_data = None
    if downloader:
        special_data = build_special_interface_params(interface_name, params, downloader)
    
    return params, special_data
```

---

## 四、实施计划

### 4.1 阶段划分

| 阶段 | 内容 | 风险 | 预估改动量 |
|------|------|------|-----------|
| Phase 1 | 创建 param_utils.py，提取 detect_download_scenario() | 低 | +80行 |
| Phase 1 | 修改 main.py 两处调用 | 中 | -30行 |
| Phase 2 | 提取 build_special_interface_params() | 低 | +30行 |
| Phase 2 | 修改 main.py 调用 | 低 | -20行 |
| Phase 3 | 可选：统一入口 | 低 | +20行 |

### 4.2 实施顺序

```
Step 1: 创建 core/param_utils.py
        └── 实现 detect_download_scenario() 和 clean_internal_params()
        └── 添加单元测试
        
Step 2: 修改 run_update_mode()
        └── 使用新函数替换原有场景判断
        └── 验证功能一致
        
Step 3: 修改 main() 中的场景判断
        └── 复用同一函数
        └── 验证功能一致
        
Step 4: 提取特殊接口处理
        └── 实现 build_special_interface_params()
        └── 验证 broker_recommend 行为不变
```

---

## 五、不做的事情

| 原方案建议 | 本方案决策 | 理由 |
|-----------|-----------|------|
| 创建完整 param_builder.py | 不做 | 与 PaginationExecutor 逻辑冲突 |
| 新增 special_handling 配置 | 不做 | 收益不大，只有 2-3 个接口 |
| 修改 downloader.py 参数逻辑 | 不做 | 现有逻辑正常工作 |
| 修改 PaginationExecutor | 不做 | 已有完善的参数生成逻辑 |

---

## 六、预期收益

| 维度 | 改善 |
|------|------|
| 代码重复 | 消除 main.py 中两处 ~90 行重复代码 |
| 可读性 | 场景判断逻辑封装为清晰函数 |
| 可维护性 | 新增接口时只需修改配置，无需添加 if-else |
| 可测试性 | 独立函数可单独单元测试 |
| 风险 | 最小化改动，现有逻辑完全保持 |

---

## 七、风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 场景判断逻辑遗漏 | 低 | 仔细对比两处现有逻辑的差异 |
| disclosure_date 特殊行为变化 | 低 | 本方案保留了特殊处理逻辑 |
| 单元测试覆盖不足 | 中 | 第一阶段同步编写测试用例 |

---

## 八、总结

本方案采用**渐进式重构**策略，核心原则：

1. **不复制组件**：不创建新的 param_builder 模块，避免与现有 PaginationExecutor 冲突
2. **不增加配置**：现有 is_date_anchor 机制足够，不引入 special_handling
3. **只做提取**：将重复代码提取为函数，不改变行为
4. **小步快跑**：分阶段实施，每阶段可独立回滚

相比原简化方案，本方案更贴近 app4 实际代码状态，改动更小，风险更低。
