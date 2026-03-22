# S08: ResourceManager 资源管理

**触发决策**: D018

**问题**: 持续运行会导致 API 成本、磁盘空间、内存使用不可控。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.7 节
- D018: 24H 资源管理约束

---

## 目标

实现 ResourceManager，强制约束：
1. 每日 Token 预算硬上限（默认 5M tokens）
2. 磁盘空间监控与告警（<5GB 触发）
3. result.h5 自动清理（默认保留 30 天）
4. 因子库条目上限与 SQLite 迁移阈值

---

## 成功标准

- [ ] `resource_manager.py:ResourceManager` 实现
- [ ] 每日 Token 预算硬上限
- [ ] 磁盘空间监控与告警
- [ ] result.h5 自动清理
- [ ] 因子库条目上限
- [ ] 资源超限拦截并告警

---

## 任务拆分

### T01: 实现 ResourceManager 类
**文件**: `quantaalpha/continuous/resource_manager.py` (新建)
**估算**: 4h

```python
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ResourceManager:
    """24 小时运行的资源管理"""

    def __init__(self, config: dict):
        self.max_disk_gb = config.get("max_disk_gb", 50)
        self.daily_token_budget = config.get("daily_token_budget", 5_000_000)
        self.max_trace_history = config.get("max_trace_history", 50)
        self.max_library_factors = config.get("max_library_factors", 10000)
        self.h5_retention_days = config.get("h5_retention_days", 30)

        self._daily_tokens_used = 0
        self._daily_reset_date = datetime.now().date()

    def check_disk_space(self, data_dir: str) -> bool:
        """检查磁盘空间是否充足"""
        total, used, free = shutil.disk_usage(data_dir)
        free_gb = free / (1024**3)
        if free_gb < 5:
            logger.warning(f"Low disk space: {free_gb:.1f} GB free")
            return False
        return True

    def cleanup_old_h5_files(self, workspace_root: str):
        """清理过期的 result.h5 文件"""
        cutoff = datetime.now() - timedelta(days=self.h5_retention_days)
        cleaned = 0
        for h5 in Path(workspace_root).rglob("result.h5"):
            mtime = datetime.fromtimestamp(h5.stat().st_mtime)
            if mtime < cutoff:
                h5.unlink()
                cleaned += 1
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} expired result.h5 files")

    def check_token_budget(self, tokens_to_use: int) -> bool:
        """检查日 token 预算"""
        today = datetime.now().date()
        if today != self._daily_reset_date:
            self._daily_tokens_used = 0
            self._daily_reset_date = today

        if self._daily_tokens_used + tokens_to_use > self.daily_token_budget:
            logger.warning(f"Token budget exceeded: {self._daily_tokens_used}/{self.daily_token_budget}")
            return False
        return True

    def record_tokens(self, tokens_used: int):
        self._daily_tokens_used += tokens_used

    def should_archive_trace(self, trace_len: int) -> bool:
        return trace_len > self.max_trace_history
```

**验收**:
- [ ] 磁盘空间检查正确
- [ ] result.h5 清理正确
- [ ] Token 预算检查正确
- [ ] 每日自动重置

### T02: 设计 experiment.yaml 配置
**文件**: `configs/experiment.yaml` (新增 resource_management 段)
**估算**: 1h

```yaml
resource_management:
  max_disk_gb: 50
  daily_token_budget: 5000000
  max_trace_history: 50
  max_library_factors: 10000
  h5_retention_days: 30
  cleanup_interval_hours: 6
  sqlite_migration_threshold: 5000
```

**验收**:
- [ ] 配置格式正确
- [ ] 默认值合理

### T03: 集成到 pipeline/loop.py
**文件**: `quantaalpha/pipeline/loop.py`
**估算**: 2h

在 `AlphaAgentLoop` 中调用 ResourceManager。

**验收**:
- [ ] Token 预算超限拦截
- [ ] 磁盘空间告警
- [ ] 定期清理 result.h5

---

## 依赖

- **D018**: 资源管理约束决策
- **S04**: ProviderPool Token 追踪
