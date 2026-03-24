# QuantaAlpha + vnpy 第一阶段 MVP 集成实施方案

## 1. MVP 核心目标

本文档描述如何最快速地验证 `/home/quan/testdata/aspipe_v4/p/factormining/architecture_design2.md` 中**“基于 LLM 的因子挖掘系统”**的核心逻辑。

**方案核心思想：** 不造轮子。直接本地安装部署开源的 `quantaalpha` (或者你本地的仿制实现) 和 `vnpy`，只编写最核心的**胶水代码**（Glue Code）将二者串联起来。

MVP 验证闭环：
1. **输入**：研究方向提示词
2. **生成**：QuantaAlpha 调用 LLM 生成因子表达式
3. **转换**：胶水代码将 QuantaAlpha 表达式转为 vnpy 可理解的格式
4. **回测**：vnpy 加载测试数据计算因子值，并产出 IC 或基础回测结果

---

## 2. MVP 架构级裁剪对比

对照完整的 `architecture_design2.md`，MVP 将做极其粗暴的裁剪，只保留业务主干：

| 架构设计模块 | 完整版设计 | MVP 原型实现 (胶水化) |
| :--- | :--- | :--- |
| **模块一：LLM 因子生成** | 多模型路由、向量库检索、动态负例反哺 | 直接运行 `quantaalpha` 单次生成脚本，输出因子表达式 (如 JSON) |
| **模块二：质量门控层** | 量纲检查、AST对齐检查、复杂互信息分析 | 胶水代码里硬写 `try...except` 拦截语法报错和运行时除零错误 |
| **模块三：数据层** | 海量 Parquet、Polars 高性能处理 | 准备少量测试数据（如全市场 50 只股票 2 年日线）直接送入 vnpy |
| **模块四：事件驱动** | 进程池、GIL 优化、多队列分布式系统 | **全放弃**。一个写死的 `while` 循环串行单线程执行一遍流程 |
| **模块五：回测引擎** | IC/DSR防过拟合、完整滑点撮合成交 | vnpy 的 `vnpy.alpha` 数据集直接算一组基础因子值和下一期收益相关性 |
| **模块六：资源调度** | LinUCB 动态资源分配及探索 | **全放弃**。人为指定挖掘主题，按顺序穷举测试 |

---

## 3. 极速实施步骤 (手把手路线图)

### 步骤 1: 环境准备与仓库部署
创建一个新的虚拟环境，直接安装依赖：
```bash
pip install quantaalpha vnpy polars pandas
```
*(注：如果官方 `quantaalpha` 暂未发布 pip 版，可拉取源码通过 `pip install -e .` 安装)*

### 步骤 2: 准备一小份测试数据
不要用庞大的本地历史库，切出一小段干净的数据（例如 1年，20只股票的 OCLHV 数据），制作成 `bar_data.parquet`，放在工作目录下，供 vnpy 的 `AlphaLab` 或自定义胶水脚本快速读取。

### 步骤 3: 运行 QuantaAlpha 产出第一批“裸因子”
直接调用 QuantaAlpha 的命令行或最上层 API，让其生成因子并输出到一个简单的 `factors.json` 文件中。
*(如果 QuantaAlpha 自身包含简单的回测，在这一步先关掉或跳过，让它只做 “LLM Generator” 的角色)*
```json
// factors.json 示例
[
    {"id": "F001", "expression": "TS_RANK(TS_DELTA(CLOSE, 1), 10)"},
    {"id": "F002", "expression": "TS_MEAN(VOLUME, 20) / VOLUME"}
]
```

### 步骤 4: 编写核心“胶水代码” (Glue Code)
实现一个 `glue_runner.py`，核心逻辑：
1. **读取** `factors.json`
2. **转换语法**：把 QuantaAlpha 独特的表达式转为 vnpy 兼容代码（字符串替换）
3. **计算回测**：调用 vnpy 产生结果。

```python
# glue_runner.py 伪代码
import json
import polars as pl
from vnpy.alpha.dataset import AlphaDataset # 假设使用 vnpy 的 Alpha 原生库

# 1. 定义简单的语法转换胶水 (Expression Mapper)
def translate_to_vnpy(quanta_expr: str) -> str:
    # 粗暴的字符串替换，将 QAlpha 算子转换为 vnpy 算子
    mapping = {
        'TS_RANK': 'ts_rank',
        'TS_DELTA': 'ts_delta',
        'TS_MEAN': 'ts_mean',
        'CLOSE': 'close',
        'VOLUME': 'volume'
    }
    expr = quanta_expr.upper()
    for k, v in mapping.items():
        expr = expr.replace(k, v)
    return expr

# 2. 从 QuantaAlpha 输出读取因子
with open('factors.json', 'r') as f:
    factors = json.load(f)

# 3. 准备一小份测试数据给 vnpy 算子用
df_data = pl.read_parquet("small_test_data.parquet")

# 4. 执行循环回测
for factor in factors:
    vnpy_expr = translate_to_vnpy(factor['expression'])
    print(f"Testing {factor['id']}: {vnpy_expr}")
    
    try:
        # 使用 vnpy 数据集和对应算子执行计算 (示例伪代码)
        # df_result = dataset.add_feature(vnpy_expr)
        # ic = calc_ic(df_result['factor'], df_result['forward_return'])
        
        # 简化演示:
        ic = 0.05 # 假设这是胶水引擎底层调 vnpy 算出的结果
        print(f"Success! {factor['id']} IC: {ic}")
        
    except Exception as e:
        print(f"Skipped {factor['id']} due to parsing/eval error: {e}")
```

### 步骤 5: 验证跑通并沉淀经验库
运行 `glue_runner.py`。
- 如果代码抛出 `KeyError` 或是除零错误等异常，就用 `try` 捕获拦截它；
- 如果跑出了有效 IC，就将其写入到本地的一个 `success_mvp_factors.csv` 中。

这就完成了从“LLM出公式”到“回测出结果”的完整通路。

---

## 4. 结论与建议
通过上述“胶水拼装法”，您可以在**极短时间（几个小时到1天内）**就把 `/factormining/architecture_design2.md` 的主要业务主干拉通。一旦跑通，系统就有了“生命力”。

后续如果您想实现更复杂的功能（如引入 LinUCB 调度、并发多进程解 GIL 锁等），只需在完全跑通的 `glue_runner.py` 的基础上，将这几个简化掉的功能点（如简单的 `try..except` 门控）逐个替换为您自行研制的**独立模块**(Quality Gate Layer, Event-Driven Layer) 即可，步步为营，不会乱阵脚。
