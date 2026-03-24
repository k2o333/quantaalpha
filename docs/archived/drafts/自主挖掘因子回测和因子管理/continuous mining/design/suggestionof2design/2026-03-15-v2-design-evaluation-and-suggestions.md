# QuantaAlpha V2 持续挖掘设计评估与建议

**文档状态**: Draft  
**评估日期**: 2026-03-15  
**评估对象**: `/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/continuous mining/design/2026-03-15-quantaalpha-continuous-mining-design-v2.md`  
**评估者**: AI Assistant

---

## 一、执行摘要

### 1.1 总体结论

**V2 设计合理且可执行**。相比 V1 的"四层大平台"构想，V2 做出了正确的战略收缩：

| 评估维度 | 评分 | 说明 |
|----------|------|------|
| 设计定位 | ✅ 优秀 | 从"平台思维"转向"闭环思维" |
| 与代码现状一致性 | ✅ 优秀 | 核心能力已完整实现 |
| 可执行性 | ✅ 良好 | 下一阶段任务清晰 |
| 风险控制 | ✅ 优秀 | 明确不做事项，避免过度工程 |
| 完整性 | ⚠️ 良好 | 部分模块需补充细节 |

### 1.2 核心优势

1. **准确反映已验证能力** — 多周期验证、状态流转、质量门控等已在代码中落地
2. **稳定性优先** — 把运行期约束写进主线设计，而非事后补救
3. **外部调度策略务实** — 不做常驻 daemon，用 cron/scheduler 触发 CLI
4. **JSON 因子库保持轻量** — 避免过早引入复杂检索和向量层

### 1.3 主要风险

1. **数据能力注册表缺失** — 当前仅靠硬编码 forbidden terms 约束数据边界
2. **revalidate CLI 功能简化** — 仅更新状态，不实际执行回测
3. **外部调度脚本空白** — 无标准 cron 配置或调度器示例
4. **回归测试覆盖不足** — V2 强调测试但当前覆盖有限

---

## 二、V2 设计与代码现状映射

### 2.1 已完整实现的能力

| V2 设计模块 | 代码位置 | 实现状态 |
|-------------|----------|----------|
| **研究主链路** | | |
| └─ direction 生成 | `pipeline/planning.py:generate_parallel_directions()` | ✅ |
| └─ hypothesis 生成 | `core/proposal.py:HypothesisGen` | ✅ |
| └─ factor construct | `core/proposal.py:Hypothesis2Experiment` | ✅ |
| └─ 一致性检查 | `core/proposal.py` + `quality_gate_config` | ✅ |
| └─ debug 失败项优先重试 | `pipeline/loop.py` | ✅ |
| └─ backtest | `factors/runner.py:QlibFactorRunner` | ✅ |
| └─ feedback | `core/proposal.py:HypothesisExperiment2Feedback` | ✅ |
| **验证与治理层** | | |
| └─ 统一股票池 | `configs/backtest.yaml:data.stock_filter` | ✅ |
| └─ 多周期验证 | `backtest/runner.py` + `validation.py` | ✅ |
| └─ 稳定性评分 | `validation.py:compute_stability_score()` | ✅ |
| └─ 结果质量门控 | `runner.py:_validate_factor_frame()` | ✅ |
| └─ 状态更新规则 | `factors/status_rules.py:update_factor_status()` | ✅ |
| **因子事实层** | | |
| └─ JSON 因子库 | `factors/library.py:FactorLibraryManager` | ✅ |
| └─ evaluation 字段 | `library.py` + `status_rules.py` | ✅ |
| └─ data_requirements | `library.py:_infer_dimensions/fields()` | ✅ |
| └─ 状态流转 | `status_rules.py` (5 状态) | ✅ |
| **外部调度层** | | |
| └─ CLI mine 命令 | `cli.py:mine` | ✅ |
| └─ CLI backtest 命令 | `cli.py:backtest` | ✅ |
| └─ CLI revalidate 命令 | `cli.py:revalidate` | ✅ |
| **演化追踪** | | |
| └─ StrategyTrajectory | `pipeline/evolution/trajectory.py` | ✅ |
| └─ 状态驱动路由 | `trajectory.py:route_factor_by_status()` | ✅ |
| └─ Parent 选择 | `trajectory.py:select_parent_factors()` | ✅ |
| **LLM 稳定性** | | |
| └─ 任务级路由 | `llm/config.py:routing_tasks` | ✅ |
| └─ Tokenizer fallback | `llm/client.py` (qwen 托底) | ✅ |
| └─ JSON 鲁棒解析 | `llm/client.py:robust_json_parse()` | ✅ |

### 2.2 部分实现/待完善的能力

| V2 设计模块 | 代码现状 | 差距描述 |
|-------------|----------|----------|
| **数据能力注册表** | 无独立模块 | 仅 `planning.py` 硬编码 `FORBIDDEN_DIRECTION_TERMS` |
| **revalidate 实际执行** | CLI 仅更新状态 | 不实际调用 backtest 流程 |
| **外部调度脚本** | 无 | 无 cron 配置或调度器示例 |
| **因子库检索方法** | 基础 CRUD | 缺少 `get_reference_factors()` 等 |
| **回归测试** | 部分测试 | `tests/test_continuous_factor_features.py` 覆盖有限 |

---

## 三、设计合理性评估

### 3.1 战略收缩决策评估

V2 相比 V1 的关键收缩决策：

| 收缩点 | V1 设计 | V2 设计 | 评估 |
|--------|---------|---------|------|
| 多模型层 | TaskPolicy + ModelProfiles + ProviderPool + RepairChain + fanout=2 | 任务级路由 + 必要兜底 | ✅ 正确：fanout 和轮询过早 |
| 数据注册表 | 主 prompt 默认注入 | 默认不注入，特定任务受控 | ✅ 正确：避免上下文膨胀 |
| 24h 运行 | 常驻 orchestrator/daemon | 外部 cron/scheduler 触发 | ✅ 正确：降低系统复杂度 |
| 因子库 | 知识库 + 检索 + embedding | JSON 主事实源，核心字段优先 | ✅ 正确：避免过早优化 |

**评估结论**：所有收缩决策均合理，符合"最小闭环"原则。

### 3.2 三层主链路设计评估

```
外部调度 / 人工触发
        ↓
研究主链路
  direction -> hypothesis -> factor construct -> debug -> backtest -> feedback
        ↓
验证与治理层
  stock universe -> multi-period validation -> quality gate -> status update
        ↓
因子事实层
  factor library JSON
```

**优势**：
1. 链路清晰，职责分离
2. 每层可独立测试和验证
3. 外部调度解耦，避免系统膨胀

**潜在问题**：
1. 链路中缺少"数据能力注册表"注入点
2. feedback 到下一轮 direction 的闭环不够明确

### 3.3 模块设计评估

#### 3.3.1 研究主链路 (Section 5.1)

**优点**：
- planning 数据边界约束已实现 (`FORBIDDEN_DIRECTION_TERMS`)
- construct 阶段一致性检查已接入
- debug 成功项早退、失败项优先重试已实现

**建议**：
- 增加"方向质量评估"环节，避免低质量 direction 进入主链路
- 明确 feedback 如何影响下一轮 hypothesis 生成

#### 3.3.2 验证与治理层 (Section 5.2)

**优点**：
- 统一股票池配置已实现
- 多周期验证完整实现，稳定性评分合理
- 质量门控检查 NaN/inf/唯一值

**建议**：
- 质量门控可增加"因子间相关性检查"，避免冗余因子
- 多周期验证可增加"跨周期一致性"指标

#### 3.3.3 因子事实层 (Section 5.3)

**优点**：
- JSON 因子库 schema 完整 (evaluation/data_requirements)
- 状态流转规则清晰 (5 状态)
- 支持因子演化追踪

**建议**：
- 增加因子库检索方法 (见第 4 节)
- 增加"因子去重"工具方法

#### 3.3.4 外部调度层 (Section 5.4)

**优点**：
- CLI 命令完整 (mine/backtest/revalidate)
- 不做常驻 daemon，降低复杂度

**建议**：
- 提供标准 cron 配置示例
- revalidate 增加 `--actual-run` 选项真正执行回测

---

## 四、具体建议

### 4.1 Phase A：稳定主链路（1-2 周）

#### A1. 补齐回归测试

**优先级**: 🔴 高

**测试清单**：

| 测试项 | 测试文件 | 覆盖点 |
|--------|----------|--------|
| planning 边界约束 | `tests/test_planning_constraints.py` | forbidden terms 拦截 |
| debug 失败项优先重试 | `tests/test_debug_retry.py` | 成功项早退逻辑 |
| 质量门控拦截 | `tests/test_quality_gate.py` | NaN/inf/唯一值检查 |
| 状态流转端到端 | `tests/test_status_flow.py` | validation → status 更新 |
| 多周期验证聚合 | `tests/test_multi_period_aggregation.py` | 稳定性评分计算 |

**验收标准**：
- 核心链路测试覆盖率 > 80%
- 所有测试可 CI 自动运行

#### A2. 完善 revalidate 命令

**优先级**: 🔴 高

**当前问题**：
```python
# cli.py 当前实现 - 仅更新状态，不实际回测
def revalidate(...):
    validation_result = {
        "status": "success",
        "period_results": evaluation.get("period_results", []),
        "summary": summary,
    }
```

**建议修改**：
```python
def revalidate(
    library_path: str,
    days: int | None = None,
    status: str | None = None,
    factor_ids: str | None = None,
    dry_run: bool = False,
    actual_run: bool = False,  # 新增
    parallel: int = 1,         # 新增
):
    """
    Revalidate factors from library.
    
    Args:
        actual_run: If True, actually run backtest for each factor.
        parallel: Number of parallel backtests when actual_run=True.
    """
    manager = FactorLibraryManager(library_path)
    candidates = manager.select_revalidation_candidates(...)
    
    if actual_run:
        # 实际执行回测
        return _run_actual_revalidation(candidates, manager, parallel)
    elif dry_run:
        # 仅输出待复验清单
        return {"total_candidates": len(candidates), "details": [...]}
    else:
        # 仅更新状态 (当前行为)
        return _update_status_only(candidates, manager)
```

**新增 CLI 选项**：
```bash
quantaalpha revalidate factors.json --days=30 --status=stale --actual-run --parallel=4
```

#### A3. 增加外部调度脚本

**优先级**: 🟡 中

**建议文件**：`scripts/scheduler/cron_example.conf`

```bash
# QuantaAlpha 持续挖掘 cron 配置示例
# 编辑：crontab -e

# 每日 02:00 执行因子挖掘 (日志输出到文件)
0 2 * * * cd /home/quan/testdata/aspipe_v4 && /usr/bin/python3 -m quantaalpha.cli mine >> log/mine_$(date +\%Y\%m\%d).log 2>&1

# 每周日 03:00 执行 stale 因子复验 (dry-run 模式)
0 3 * * 0 cd /home/quan/testdata/aspipe_v4 && /usr/bin/python3 -m quantaalpha.cli revalidate data/factor_library.json --days=21 --status=stale --dry-run >> log/revalidate_dryrun_$(date +\%Y\%m\%d).log 2>&1

# 每月 1 号 04:00 执行全量复验 (actual-run 模式，并行 4)
0 4 1 * * cd /home/quan/testdata/aspipe_v4 && /usr/bin/python3 -m quantaalpha.cli revalidate data/factor_library.json --status=active --actual-run --parallel=4 >> log/revalidate_full_$(date +\%Y\%m\%d).log 2>&1
```

**建议文件**：`scripts/scheduler/simple_scheduler.py`

```python
#!/usr/bin/env python3
"""
简单调度器：按固定间隔执行 mine 和 revalidate 任务。
适用于无 cron 环境（如 Docker 容器内）。
"""

import subprocess
import time
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

MINE_INTERVAL_HOURS = 24      # 挖掘间隔
REVALIDATE_INTERVAL_DAYS = 7  # 复验间隔

def run_command(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False

def main():
    last_mine = datetime.now()
    last_revalidate = datetime.now()
    
    logger.info("Scheduler started")
    
    while True:
        now = datetime.now()
        
        # Check mine
        if now - last_mine >= timedelta(hours=MINE_INTERVAL_HOURS):
            logger.info("Starting mine job...")
            success = run_command(["python", "-m", "quantaalpha.cli", "mine"])
            logger.info(f"Mine job {'completed' if success else 'failed'}")
            last_mine = now
        
        # Check revalidate
        if now - last_revalidate >= timedelta(days=REVALIDATE_INTERVAL_DAYS):
            logger.info("Starting revalidate job (dry-run)...")
            success = run_command([
                "python", "-m", "quantaalpha.cli", "revalidate",
                "data/factor_library.json", "--days=21", "--status=stale", "--dry-run"
            ])
            logger.info(f"Revalidate job {'completed' if success else 'failed'}")
            last_revalidate = now
        
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
```

### 4.2 Phase B：最小持续维护（2-4 周）

#### B1. 实现数据能力注册表

**优先级**: 🟡 中

**建议文件**：`quantaalpha/data/registry.py`

```python
"""
数据能力注册表：结构化描述当前可用数据维度。
"""

import json
from pathlib import Path
from typing import Any

from quantaalpha.log import logger


class DataCapabilityRegistry:
    """Manage data capability registry."""
    
    DEFAULT_REGISTRY = {
        "dimensions": {
            "price_volume": {
                "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
                "freq": "daily",
                "join_mode": "native",
                "lag_days": 0,
                "availability_status": "active",
                "description": "标准日频价量数据",
                "suitable_for": ["momentum", "volatility", "liquidity", "mean_reversion"]
            },
        },
        "forbidden_terms": [
            "news", "sentiment", "supply chain", "order flow",
            "order book", "level-2", "tick", "intraday",
            "alternative data", "fundamental"
        ]
    }
    
    def __init__(self, registry_path: str | None = None):
        self.registry_path = Path(registry_path) if registry_path else None
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.registry_path and self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load registry, using default: {e}")
        return self.DEFAULT_REGISTRY.copy()
    
    def get_available_dimensions(self) -> list[str]:
        """Get list of available dimension names."""
        return list(self.data.get("dimensions", {}).keys())
    
    def get_dimension_info(self, dimension: str) -> dict | None:
        """Get detailed info for a dimension."""
        return self.data.get("dimensions", {}).get(dimension)
    
    def get_available_fields(self, dimensions: list[str] | None = None) -> list[str]:
        """Get all available fields, optionally filtered by dimensions."""
        fields = []
        dims = dimensions or self.get_available_dimensions()
        for dim in dims:
            dim_info = self.get_dimension_info(dim)
            if dim_info:
                fields.extend(dim_info.get("fields", []))
        return fields
    
    def get_forbidden_terms(self) -> list[str]:
        """Get list of forbidden terms for planning constraints."""
        return self.data.get("forbidden_terms", self.DEFAULT_REGISTRY["forbidden_terms"])
    
    def to_prompt_injection(self, dimensions: list[str] | None = None) -> str:
        """
        Generate prompt injection text for LLM.
        Use sparingly - only for specific tasks that need data awareness.
        """
        dims = dimensions or self.get_available_dimensions()
        parts = ["当前系统可用数据维度："]
        
        for dim_name in dims:
            dim_info = self.get_dimension_info(dim_name)
            if dim_info:
                parts.append(f"\n- {dim_name}:")
                parts.append(f"  字段：{', '.join(dim_info.get('fields', []))}")
                parts.append(f"  频率：{dim_info.get('freq', 'unknown')}")
                parts.append(f"  说明：{dim_info.get('description', '')}")
        
        parts.append(f"\n禁止使用的数据类型：{', '.join(self.get_forbidden_terms())}")
        
        return "\n".join(parts)
```

**建议文件**：`configs/data_registry.json`

```json
{
  "dimensions": {
    "price_volume": {
      "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
      "freq": "daily",
      "join_mode": "native",
      "lag_days": 0,
      "availability_status": "active",
      "description": "标准日频价量数据",
      "suitable_for": ["momentum", "volatility", "liquidity", "mean_reversion"]
    }
  },
  "forbidden_terms": [
    "news", "sentiment", "supply chain", "order flow",
    "order book", "level-2", "tick", "intraday",
    "alternative data", "fundamental"
  ]
}
```

**集成点**：
1. `planning.py` 使用 `registry.get_forbidden_terms()` 替代硬编码
2. 特定任务（如新数据维度挖掘）使用 `registry.to_prompt_injection()` 注入

#### B2. 增强因子库检索

**优先级**: 🟡 中

**建议修改**：`factors/library.py` 新增方法

```python
class FactorLibraryManager:
    # ... 现有方法 ...
    
    def get_reference_factors(
        self,
        direction: str | None = None,
        data_fields: list[str] | None = None,
        status: str = "active",
        top_k: int = 5,
    ) -> list[dict]:
        """
        Get reference factors for guiding new factor generation.
        
        Args:
            direction: Optional direction keyword for filtering.
            data_fields: Optional data fields to match.
            status: Filter by status (default: active).
            top_k: Number of factors to return.
        
        Returns:
            List of factor entries sorted by stability_score.
        """
        candidates = []
        for fid, entry in self.data.get("factors", {}).items():
            evaluation = entry.get("evaluation", {})
            if evaluation.get("status") != status:
                continue
            
            # Match data fields
            if data_fields:
                req_fields = entry.get("data_requirements", {}).get("fields", [])
                if not any(f in req_fields for f in data_fields):
                    continue
            
            # Match direction keywords
            if direction:
                desc = entry.get("factor_description", "").lower()
                form = entry.get("factor_formulation", "").lower()
                if direction.lower() not in desc and direction.lower() not in form:
                    continue
            
            candidates.append(entry)
        
        # Sort by stability_score descending
        candidates.sort(
            key=lambda x: x.get("evaluation", {}).get("stability_score") or 0.0,
            reverse=True
        )
        
        return candidates[:top_k]
    
    def get_stale_factors(self, days_threshold: int = 21) -> list[dict]:
        """Get factors that haven't been validated for specified days."""
        from datetime import datetime, timedelta
        
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        stale = []
        
        for fid, entry in self.data.get("factors", {}).items():
            evaluation = entry.get("evaluation", {})
            if evaluation.get("status") != "stale":
                continue
            
            last_validated = evaluation.get("last_validated")
            if last_validated:
                try:
                    validated_at = datetime.fromisoformat(str(last_validated))
                    if validated_at >= threshold_date:
                        continue
                except ValueError:
                    pass
            
            stale.append(entry)
        
        return stale
    
    def get_mutation_candidates(
        self,
        status: str = "active",
        min_stability_score: float = 0.5,
        top_k: int = 10,
    ) -> list[dict]:
        """Get factors suitable for mutation."""
        candidates = []
        
        for fid, entry in self.data.get("factors", {}).items():
            evaluation = entry.get("evaluation", {})
            if evaluation.get("status") != status:
                continue
            
            stability = evaluation.get("stability_score")
            if stability is None or stability < min_stability_score:
                continue
            
            candidates.append(entry)
        
        # Sort by stability_score descending
        candidates.sort(
            key=lambda x: x.get("evaluation", {}).get("stability_score") or 0.0,
            reverse=True
        )
        
        return candidates[:top_k]
    
    def get_underexplored_field_combinations(
        self,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Analyze factor library to find underexplored field combinations.
        
        Returns:
            List of {fields: [...], count: int} sorted by count ascending.
        """
        from collections import defaultdict
        
        field_combos = defaultdict(int)
        
        for entry in self.data.get("factors", {}).values():
            fields = tuple(sorted(entry.get("data_requirements", {}).get("fields", [])))
            if fields:
                field_combos[fields] += 1
        
        # Sort by count ascending (least explored first)
        sorted_combos = sorted(field_combos.items(), key=lambda x: x[1])
        
        return [
            {"fields": list(fields), "count": count}
            for fields, count in sorted_combos[:top_k]
        ]
    
    def deduplicate_factors(
        self,
        similarity_threshold: float = 0.95,
    ) -> dict:
        """
        Detect and mark duplicate factors based on expression similarity.
        
        Returns:
            {
                "total": int,
                "duplicates_found": int,
                "duplicate_groups": [[factor_id1, factor_id2, ...], ...]
            }
        """
        import hashlib
        
        # Group by normalized expression
        expr_groups = defaultdict(list)
        
        for fid, entry in self.data.get("factors", {}).items():
            expr = entry.get("factor_expression", "").strip()
            if not expr:
                continue
            
            # Normalize: remove whitespace, lowercase
            normalized = " ".join(expr.lower().split())
            expr_hash = hashlib.md5(normalized.encode()).hexdigest()
            expr_groups[expr_hash].append(fid)
        
        # Find duplicates
        duplicate_groups = [
            group for group in expr_groups.values()
            if len(group) > 1
        ]
        
        return {
            "total": len(self.data.get("factors", {})),
            "duplicates_found": sum(len(g) - 1 for g in duplicate_groups),
            "duplicate_groups": duplicate_groups,
        }
```

#### B3. 运行日志可观测

**优先级**: 🟢 低

**建议文件**：`scripts/reporting/generate_summary.py`

```python
#!/usr/bin/env python3
"""
生成因子挖掘和复验摘要报告。
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from quantaalpha.factors.library import FactorLibraryManager


def generate_library_summary(library_path: str) -> dict:
    """Generate factor library summary."""
    manager = FactorLibraryManager(library_path)
    
    status_counts = defaultdict(int)
    stability_scores = []
    
    for entry in manager.data.get("factors", {}).values():
        status = entry.get("evaluation", {}).get("status", "unknown")
        status_counts[status] += 1
        
        score = entry.get("evaluation", {}).get("stability_score")
        if score is not None:
            stability_scores.append(score)
    
    return {
        "total_factors": len(manager.data.get("factors", {})),
        "status_distribution": dict(status_counts),
        "stability_score_stats": {
            "mean": sum(stability_scores) / len(stability_scores) if stability_scores else None,
            "max": max(stability_scores) if stability_scores else None,
            "min": min(stability_scores) if stability_scores else None,
        },
        "last_updated": manager.data.get("metadata", {}).get("last_updated"),
    }


def generate_mining_summary(log_path: str, days: int = 7) -> dict:
    """Generate mining summary from logs."""
    # 解析日志文件，统计挖掘结果
    # 简化版本：返回占位符
    return {
        "period_days": days,
        "factors_generated": 0,
        "factors_passed": 0,
        "average_stability": None,
    }


def main():
    library_path = "data/factor_library.json"
    log_path = "log/"
    
    summary = generate_library_summary(library_path)
    
    print("=" * 60)
    print("QuantaAlpha 因子库摘要报告")
    print("=" * 60)
    print(f"总因子数：{summary['total_factors']}")
    print(f"状态分布：{summary['status_distribution']}")
    print(f"稳定性评分均值：{summary['stability_score_stats']['mean']}")
    print(f"最后更新：{summary['last_updated']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

### 4.3 Phase C：受控增强（4-8 周）

#### C1. 受控恢复数据注册表注入

**优先级**: 🟢 低

**建议**：
- 仅在特定任务（如新数据维度挖掘）启用注入
- 使用 `registry.to_prompt_injection()` 生成精简版注入
- 默认任务不注入，避免上下文膨胀

#### C2. 增加 fallback 模型

**优先级**: 🟢 低

**建议配置**：`configs/llm_routing.yaml`

```yaml
llm_routing:
  tasks:
    hypothesis_generation:
      primary_model: reasoning_large
      fallback_model: reasoning_medium
    
    factor_construction:
      primary_model: reasoning_large
      fallback_model: reasoning_medium
    
    evaluation_screening:
      primary_model: cheap_small
      fallback_model: reasoning_medium
    
    json_repair:
      primary_model: coding_model
      fallback_model: reasoning_medium

model_profiles:
  reasoning_large: "gpt-4o"
  reasoning_medium: "deepseek-v3"
  cheap_small: "qwen2.5-7b"
  coding_model: "codestral-latest"
```

#### C3. Provider Pool（可选）

**评估**：仅当单 provider 限流频繁时考虑引入

---

## 五、验收标准

V2 设计的验收标准应围绕以下问题：

| 问题 | 验收方式 | 当前状态 |
|------|----------|----------|
| 方向是否被限制在当前数据边界内 | 测试 forbidden terms 拦截 | ✅ 已实现 |
| 坏因子是否在回测前被挡掉 | 测试质量门控拦截率 | ✅ 已实现 |
| 成功因子是否不再被重复 debug | 日志分析成功项早退 | ✅ 已实现 |
| 因子库是否反映当前有效状态 | 检查 evaluation 字段更新 | ✅ 已实现 |
| 多周期结果是否参与后续选择 | 检查 evolution 使用 stability_score | ✅ 已实现 |
| 系统能否在外部调度下持续运行 | 提供 cron 配置并验证 | ⚠️ 待补充 |

**新增验收标准**（建议）：

| 问题 | 验收方式 |
|------|----------|
| revalidate 能否实际执行回测 | CLI 增加 `--actual-run` 选项 |
| 数据注册表能否被查询 | `registry.get_available_fields()` 可用 |
| 因子库能否检索参考因子 | `get_reference_factors()` 返回合理结果 |
| 回归测试覆盖核心链路 | 测试覆盖率 > 80% |

---

## 六、风险与缓解

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| LLM 服务不稳定 | 挖掘中断 | 中 | fallback 模型 + 重试机制 |
| 因子库规模膨胀 | JSON 读写变慢 | 低 | 定期归档旧因子 |
| 多周期验证成本高 | 验证时间过长 | 中 | fail_fast + 并行执行 |

### 6.2 工程风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 外部调度配置错误 | 任务未执行 | 中 | 提供标准配置示例 |
| 回归测试不足 | 变更引入 bug | 高 | Phase A 优先补齐测试 |
| revalidate 误用 | 因子状态错误更新 | 中 | 默认 dry-run，需显式启用 actual-run |

---

## 七、结论

### 7.1 总体评价

V2 设计是**合理且可执行**的持续挖掘方案：

1. **战略收缩正确** — 从"平台思维"转向"闭环思维"
2. **与代码现状一致** — 核心能力已完整实现
3. **风险控制得当** — 明确不做事项，避免过度工程
4. **演进路径清晰** — Phase A/B/C 分阶段实施

### 7.2 关键建议

**立即执行（Phase A）**：
1. 补齐回归测试（优先级最高）
2. 完善 revalidate 命令（增加 `--actual-run`）
3. 提供外部调度脚本（cron 示例 + 简单调度器）

**中期执行（Phase B）**：
1. 实现数据能力注册表
2. 增强因子库检索方法
3. 增加运行日志可观测

**长期考虑（Phase C）**：
1. 受控恢复数据注册表注入
2. 增加 fallback 模型配置
3. 根据实际需求决定是否引入 provider pool

### 7.3 下一步行动

1. 评审本建议文档，确认优先级
2. 创建 Phase A 任务清单（todo list）
3. 开始实施回归测试

---

**文档版本**: 1.0  
**创建日期**: 2026-03-15  
**审阅建议**: 建议 QuantaAlpha 团队审阅后更新 Phase A 任务优先级
