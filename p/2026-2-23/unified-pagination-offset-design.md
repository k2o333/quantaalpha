# 方案3：统一分页流程 - 让所有模式走通用逻辑路径

## 背景

当前 `compose()` 方法中存在多个特殊处理的分支，导致 offset 功能不能统一支持：

| 模式 | offset 支持 | 代码位置 |
|------|-------------|----------|
| `period_range` | ✅ 有独立支持 | 第85-91行 early return |
| `reverse_date_range + is_date_anchor` | ❌ 没有支持 | 第95-98行 early return |
| `reverse_date_range`（非 is_date_anchor） | ✅ 有支持 | 走通用逻辑 |
| `stock_loop` | ✅ 有支持 | 走通用逻辑 |
| `type_split` | ✅ 有支持 | 走通用逻辑 |

## 问题

1. **特殊分支过多**：`period_range` 和 `reverse_date_range + is_date_anchor` 都有独立的 early return 逻辑
2. **offset 不统一**：只有 `period_range` 分支检查了 offset，`reverse_date_range + is_date_anchor` 没有
3. **维护困难**：新增维度需要修改多个分支

## 方案3设计目标

**重构 compose() 方法，统一所有分页模式的处理流程，让 offset 功能自动应用于所有模式。**

## 核心思路

### 1. 统一 time_range 配置

在 `migrate_legacy_config` 中，所有分页模式都应生成统一的 `time_range` 配置：

```python
# reverse_date_range 模式
elif mode == "reverse_date_range":
    new_config["mode"] = "reverse_date_range"
    new_config["time_range"] = {
        "enabled": True,
        "window": window_str,
        "reverse": True,  # 关键：标记为反向
    }

# period_range 模式  
elif mode == "period_range":
    new_config["mode"] = "period_range"
    # period_range 不使用 time_range，使用独立的 period 处理
```

### 2. 统一 compose() 流程

重构后的 compose() 方法结构：

```python
def compose(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """组合多个分页维度"""
    params_stream = [base_params]
    
    # 检查是否是日期锚定接口
    is_date_anchor_interface = self._is_date_anchor_interface()
    
    # 检查是否是特殊模式
    pagination_mode = self.config.get("mode", "")
    
    # 1. 基础维度转换（所有模式都执行）
    #    - period_range: 转换为 period 参数
    #    - reverse_date_range + is_date_anchor: 转换为日期锚点
    #    - reverse_date_range: 转换为 start_date/end_date 窗口
    params_stream = self._apply_primary_dimension(params_stream, pagination_mode, is_date_anchor_interface)
    
    # 2. 股票维度（可选）
    if self._is_enabled("stock_loop"):
        params_stream = list(self._apply_stock_loop(params_stream))
    
    # 3. 分类维度（可选）
    if self._is_enabled("type_split"):
        params_stream = list(self._apply_type_split(params_stream))
    
    # 4. 偏移量维度（统一应用于所有模式）
    if self._is_enabled("offset"):
        params_stream = list(self._apply_offset(params_stream))
    
    yield from params_stream
```

### 3. 新增统一维度处理方法

```python
def _apply_primary_dimension(
    self, 
    params_stream: List[Dict[str, Any]],
    pagination_mode: str,
    is_date_anchor_interface: bool
) -> Iterator[Dict[str, Any]]:
    """
    应用主要分页维度
    
    统一处理：period_range、reverse_date_range、date_anchor 等模式
    """
    if pagination_mode == "period_range":
        # period 维度处理
        yield from self._apply_period_range(params_stream)
        
    elif pagination_mode == "reverse_date_range":
        if is_date_anchor_interface:
            # 日期锚点维度处理（转换为单个日期值）
            yield from self._apply_date_anchor_range(params_stream)
        else:
            # 时间窗口维度处理（保持 start_date/end_date）
            yield from self._apply_time_range(params_stream)
            
    elif self._is_enabled("time_range"):
        # 通用时间窗口处理
        yield from self._apply_time_range(params_stream)
    else:
        yield from params_stream
```

### 4. 修改 migrate_legacy_config

统一生成配置，消除特殊分支：

```python
def migrate_legacy_config(interface_config: Dict) -> Dict:
    """迁移旧版配置格式"""
    old_pagination = interface_config.get("pagination", {})
    mode = old_pagination.get("mode", "")
    window_str = f"{old_pagination.get('window_size_days', 365)}d"
    
    new_config = {}
    
    # 统一设置 time_range
    if mode == "reverse_date_range":
        new_config["mode"] = "reverse_date_range"
        new_config["time_range"] = {
            "enabled": True,
            "window": window_str,
            "reverse": True,  # 关键：标记为反向
            "stop_on_empty": old_pagination.get("empty_threshold_days", 90),
        }
    elif mode == "period_range":
        new_config["mode"] = "period_range"
        # period_range 不需要 time_range
        if "periods_per_batch" in old_pagination:
            new_config["periods_per_batch"] = old_pagination["periods_per_batch"]
    elif mode == "stock_loop":
        new_config["stock_loop"] = {"enabled": True, "skip_existing": True}
        new_config["time_range"] = {
            "enabled": True,
            "window": window_str,
            "reverse": False,
        }
    elif mode == "type_split":
        new_config["type_split"] = {...}
    elif mode == "quarterly_range":
        new_config["time_range"] = {"enabled": True, "window": "1q", "reverse": False}
    elif mode == "periodic_range":
        new_config["time_range"] = {...}
    else:
        # 默认启用 offset
        new_config["offset"] = {"enabled": True, "limit": 5000}
    
    # 统一处理 offset 配置（所有模式都可能启用）
    if "offset" in old_pagination:
        new_config["offset"] = old_pagination["offset"]
    
    return new_config
```

## 改动清单

### 1. app4/core/pagination.py

| 改动 | 说明 |
|------|------|
| `compose()` 方法 | 移除 early return，统一流程 |
| `_apply_primary_dimension()` | 新增方法，统一处理主要分页维度 |
| `migrate_legacy_config()` | 统一生成配置，确保 time_range 正确设置 |

### 2. 测试用例更新

需要更新以下测试文件：
- `test/test_date_anchor_pagination.py`
- `test/test_app4_pagination.py`

## 优点

1. **统一流程**：所有分页模式都经过相同的处理流程
2. **自动支持 offset**：新增维度时无需手动添加 offset 检查
3. **易于维护**：新增分页模式只需实现对应的 `_apply_xxx` 方法
4. **代码简洁**：消除重复的 early return 逻辑

## 风险

1. **重构范围较大**：需要修改 compose() 方法的核心逻辑
2. **回归测试**：需要全面测试现有功能确保无回归
3. **行为变化**：可能改变某些边界情况的处理顺序

## 实施步骤

1. **第一阶段**：重构 `migrate_legacy_config`，确保所有模式都正确生成配置
2. **第二阶段**：新增 `_apply_primary_dimension()` 方法
3. **第三阶段**：重构 `compose()` 方法，移除 early return
4. **第四阶段**：更新测试用例并验证
5. **第五阶段**：灰度发布，观察线上效果
