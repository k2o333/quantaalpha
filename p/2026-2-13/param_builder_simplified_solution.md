# App4 参数构建重构方案（简化版）

## 一、核心问题（基于代码分析）

### 1. main.py 参数构建逻辑分散
- `run_update_mode()` 约200行代码处理参数构建
- stock_loop 场景判断重复出现3次
- 特殊接口（broker_recommend/disclosure_date）硬编码

### 2. downloader.py 参数处理与下载耦合
- `download_single_stock()` 中混入了参数清理、日期处理逻辑

### 3. 配置能力未充分利用
- 接口配置中已有 `is_date_anchor` 标记，但处理逻辑仍硬编码
- 特殊接口的差异性可以通过配置表达

---

## 二、方案框架：配置驱动 + 函数组合

```
┌─────────────────────────────────────────┐
│           Interface Config              │
│  (已有：is_date_anchor, pagination等)    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         ParamBuilder (单一入口)          │
│                                         │
│   build_params(interface, args, date)   │
│       ├── 读取接口配置                   │
│       ├── 识别场景类型                   │
│       └── 调用对应构建函数               │
└─────────────────┬───────────────────────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
┌─────────┐  ┌─────────┐  ┌──────────┐
│  direct │  │stock_loop│  │ special  │
│  直接构建 │  │ 股票循环 │  │ 特殊处理  │
│         │  │         │  │(配置驱动) │
└─────────┘  └─────────┘  └──────────┘
```

---

## 三、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 抽象层次 | 函数而非类 | App4现有风格，特殊接口只有3个，无需策略模式 |
| 特殊接口处理 | 配置化 | 在yaml中增加 `special_handling` 字段，避免硬编码 |
| 与现有组件关系 | 复用而非替换 | PaginationExecutor已有参数处理逻辑，直接复用 |
| 日期计算 | 保持独立 | DateCalculator不动，ParamBuilder只负责组装 |

---

## 四、核心模块

### 4.1 配置增强（yaml层）

在现有接口配置基础上，可选增加 `special_handling` 字段：

```yaml
# broker_recommend.yaml 示例
api_name: broker_recommend
description: 券商每月荐股

# 原有配置保持不变
parameters:
  month:
    description: 月度 YYYYMM
    required: true
    type: string

# 新增：特殊处理配置
special_handling:
  type: month_loop              # 处理类型：month_loop / date_anchor / full_history
  param_mapping:                # 参数映射规则
    input_start: month          # 将输入的start_date映射为month参数
    date_format: "%Y%m"         # 日期格式转换
    date_range_to_list: true    # 将日期范围转换为列表

pagination:
  enabled: false                # broker_recommend不需要分页
```

```yaml
# disclosure_date.yaml 示例（已有is_date_anchor）
api_name: disclosure_date
parameters:
  end_date:
    description: 报告期
    type: string
    is_date_anchor: true        # 已有标记

# 无需special_handling，通过is_date_anchor自动识别
```

### 4.2 参数构建模块（param_builder.py）

```python
"""
参数构建模块 - 统一构建API请求参数
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class BuildScenario(Enum):
    """参数构建场景"""
    DIRECT = "direct"                    # 直接下载
    STOCK_LOOP_DATE = "stock_loop_date"  # 股票循环 + 日期范围
    STOCK_LOOP_ANCHOR = "stock_loop_anchor"  # 股票循环 + 日期锚点
    STOCK_LOOP_FULL = "stock_loop_full"  # 股票循环 + 全历史
    SPECIAL = "special"                  # 特殊接口处理


@dataclass
class ParamBuildResult:
    """参数构建结果"""
    params: Dict[str, Any]           # 原始参数（含内部标记）
    clean_params: Dict[str, Any]     # 清理后（用于API请求）
    scenario: BuildScenario          # 场景类型
    needs_stock_loop: bool           # 是否需要股票循环


def build_params(
    interface_config: Dict[str, Any],
    args: Any,
    date_range: Optional['DateRange'] = None,
    user_provided_dates: bool = False
) -> ParamBuildResult:
    """
    统一入口：根据接口配置构建请求参数
    
    Args:
        interface_config: 接口配置
        args: 命令行参数
        date_range: 日期范围（可选）
        user_provided_dates: 用户是否提供了日期
        
    Returns:
        ParamBuildResult: 构建结果
    """
    scenario = _detect_scenario(interface_config, user_provided_dates)
    
    if scenario == BuildScenario.DIRECT:
        params = _build_direct_params(interface_config, args, date_range)
    elif scenario in (BuildScenario.STOCK_LOOP_DATE, 
                      BuildScenario.STOCK_LOOP_ANCHOR,
                      BuildScenario.STOCK_LOOP_FULL):
        params = _build_stock_loop_params(
            interface_config, args, date_range, user_provided_dates, scenario
        )
    else:
        params = _build_special_params(interface_config, args, date_range)
    
    return ParamBuildResult(
        params=params,
        clean_params=clean_internal_params(params),
        scenario=scenario,
        needs_stock_loop=scenario != BuildScenario.DIRECT
    )


def _detect_scenario(
    interface_config: Dict[str, Any],
    user_provided_dates: bool
) -> BuildScenario:
    """识别参数构建场景"""
    pagination = interface_config.get('pagination', {})
    
    # 非股票循环模式
    if not pagination.get('enabled') or pagination.get('mode') != 'stock_loop':
        # 检查是否有特殊处理配置
        if interface_config.get('special_handling'):
            return BuildScenario.SPECIAL
        return BuildScenario.DIRECT
    
    # 股票循环模式
    params_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in params_config and 'end_date' in params_config
    has_date_anchor = any(
        cfg.get('is_date_anchor') for cfg in params_config.values()
    )
    
    if has_start_end:
        return BuildScenario.STOCK_LOOP_DATE
    elif has_date_anchor:
        return BuildScenario.STOCK_LOOP_ANCHOR
    else:
        return BuildScenario.STOCK_LOOP_FULL


def _build_direct_params(
    interface_config: Dict[str, Any],
    args: Any,
    date_range: Optional['DateRange']
) -> Dict[str, Any]:
    """构建直接下载参数"""
    params = {}
    
    if date_range:
        params['start_date'] = date_range.start_date
        params['end_date'] = date_range.end_date
    
    if getattr(args, 'ts_code', None):
        params['ts_code'] = args.ts_code
    
    return params


def _build_stock_loop_params(
    interface_config: Dict[str, Any],
    args: Any,
    date_range: Optional['DateRange'],
    user_provided_dates: bool,
    scenario: BuildScenario
) -> Dict[str, Any]:
    """构建股票循环参数"""
    params = {}
    ts_code = getattr(args, 'ts_code', None)
    
    if scenario == BuildScenario.STOCK_LOOP_DATE:
        # 场景1: 支持start_date/end_date
        if date_range:
            params['start_date'] = date_range.start_date
            params['end_date'] = date_range.end_date
    
    elif scenario == BuildScenario.STOCK_LOOP_ANCHOR:
        # 场景2: 日期锚点参数
        if ts_code and not user_provided_dates:
            # 单股票全历史
            params = {'ts_code': ts_code}
        elif not user_provided_dates and not ts_code:
            # 每只股票全历史
            params = {'_stock_full_history': True}
        else:
            # 日期范围 + 锚点
            if date_range:
                params['start_date'] = date_range.start_date
                params['end_date'] = date_range.end_date
            # 获取锚点参数名
            params_config = interface_config.get('parameters', {})
            anchor_param = next(
                (name for name, cfg in params_config.items() 
                 if cfg.get('is_date_anchor')), None
            )
            if anchor_param:
                params['_date_anchor_param'] = anchor_param
    
    else:  # STOCK_LOOP_FULL
        # 场景3: 无日期参数，全历史
        params = {'_stock_full_history': True}
    
    if ts_code:
        params['ts_code'] = ts_code
    
    return params


def _build_special_params(
    interface_config: Dict[str, Any],
    args: Any,
    date_range: Optional['DateRange']
) -> Dict[str, Any]:
    """构建特殊接口参数（配置驱动）"""
    special = interface_config.get('special_handling', {})
    handler_type = special.get('type')
    params = {}
    
    if handler_type == 'month_loop':
        # 月份循环接口（如broker_recommend）
        if date_range:
            months = _generate_months(
                date_range.start_date, 
                date_range.end_date,
                special.get('date_format', '%Y%m')
            )
            params['_month_list'] = months  # 内部标记，供下游使用
        
        if getattr(args, 'ts_code', None):
            params['ts_code'] = args.ts_code
    
    # 其他特殊类型可扩展...
    
    return params


def clean_internal_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """清理内部标记参数，返回可用于API请求的参数"""
    return {k: v for k, v in params.items() if not k.startswith('_')}


def _generate_months(start_date: str, end_date: str, fmt: str = '%Y%m') -> list:
    """将日期范围转换为月份列表"""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    start = datetime.strptime(start_date[:6], '%Y%m')
    end = datetime.strptime(end_date[:6], '%Y%m')
    
    months = []
    current = start
    while current <= end:
        months.append(current.strftime(fmt))
        current += relativedelta(months=1)
    
    return months
```

### 4.3 使用示例（main.py 改造后）

```python
def run_update_mode(args):
    # ... 初始化代码 ...
    
    from core.param_builder import build_params
    
    for interface_name in interfaces_to_update:
        interface_config = config_loader.get_interface_config(interface_name)
        
        # 计算日期范围（保持现有逻辑）
        if user_provided_dates:
            start_date, end_date = validate_and_adjust_date(args.start_date, args.end_date)
            date_range = DateRange(start_date, end_date)
        else:
            date_range = date_calculator.calculate_update_range(interface_name)
        
        # 使用统一的参数构建（替代原有的复杂if-else）
        result = build_params(interface_config, args, date_range, user_provided_dates)
        
        # 根据场景执行
        if result.needs_stock_loop:
            # 股票循环模式
            stock_list = _prepare_stock_list(downloader, args, result.params, ...)
            downloaded_count = run_concurrent_stock_download(
                downloader, scheduler, interface_name, interface_config,
                result.params, stock_list, ...
            )
        else:
            # 直接下载模式
            data = downloader.download(interface_name, result.clean_params)
            ...
```

---

## 五、重构范围

### 修改文件

| 文件 | 修改内容 | 预估行数变化 |
|------|----------|-------------|
| `main.py` | 替换`run_update_mode()`中的参数构建逻辑 | -150行 |
| `downloader.py` | 移除参数清理逻辑，复用`clean_internal_params()` | -20行 |
| 新增`core/param_builder.py` | 实现参数构建模块 | +120行 |
| `broker_recommend.yaml` | 增加`special_handling`配置 | +5行 |

### 不修改

- `DateCalculator` - 保持独立，负责日期范围计算
- `PaginationExecutor` - 复用其参数处理逻辑
- 接口核心配置结构

---

## 六、渐进实施步骤

```
Step 1: 提取工具函数
        └── 将clean_internal_params()等提取到param_utils.py
        └── 风险：低，纯重构
        
Step 2: 新增param_builder.py
        └── 实现build_params()入口和场景检测
        └── 添加单元测试
        └── 风险：低，新增代码不影响现有逻辑
        
Step 3: 修改main.py
        └── 在run_update_mode()中使用build_params()
        └── 保留原有逻辑作为fallback
        └── 风险：中，需充分测试
        
Step 4: 迁移特殊接口配置
        └── broker_recommend.yaml增加special_handling
        └── 验证特殊接口行为一致
        └── 风险：中，需验证
        
Step 5: 清理downloader.py
        └── 复用param_builder的工具函数
        └── 移除重复逻辑
        └── 风险：低，纯清理
```

---

## 七、与原有方案对比

| 维度 | 原方案 | 本简化方案 |
|------|--------|-----------|
| 抽象层次 | 3个策略类 + 协议定义 | 5个函数 |
| 代码量 | 约400行 | 约120行 |
| 特殊接口处理 | 硬编码字典 | 配置驱动（yaml） |
| 与现有组件关系 | 部分重复实现 | 复用PaginationExecutor等 |
| 学习成本 | 高（需理解策略模式） | 低（函数调用链） |
| 扩展性 | 新增策略类 | 新增配置项或函数 |

---

## 八、风险评估

| 风险点 | 等级 | 缓解措施 |
|--------|------|----------|
| 场景识别错误 | 中 | 增加场景检测的单元测试覆盖所有接口类型 |
| 特殊接口行为变化 | 中 | broker_recommend等接口单独验证 |
| 与PaginationExecutor逻辑冲突 | 低 | 复用其clean逻辑，保持一致 |
| 日期边界处理 | 低 | 复用DateCalculator，不改动日期逻辑 |

---

**核心原则**：配置表达差异，函数处理逻辑，保持与现有架构一致，避免过度抽象。
