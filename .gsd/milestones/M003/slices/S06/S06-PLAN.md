# S06: Checkpoint 与幂等性恢复

**触发决策**: D017

**问题**: 24 小时运行中进程崩溃会丢失整轮进度，需要中断恢复机制。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 3.5 节

---

## 目标

实现：
1. LoopCheckpoint 在每个 pipeline 步骤后持久化状态
2. 因子库支持版本历史（versions 字段）
3. 文件锁超时机制（M001 教训）

---

## 成功标准

- [ ] `checkpoint.py:LoopCheckpoint` 实现
- [ ] 支持 save/load/clear 操作
- [ ] 使用 pickle 序列化（处理换行符，D019 约束）
- [ ] library.py 增加 versions 字段
- [ ] 锁超时 30 秒（M001 教训）
- [ ] 进程崩溃后能从检查点恢复

---

## 设计约束（来自 D017/D019）

1. **持久化格式**: JSON 元数据 + pickle 状态
2. **锁超时**: 30 秒超时后强制获取（M001 教训）
3. **换行符处理**: pickle 序列化需验证含换行符字段的兼容性（D019 约束）

---

## 任务拆分

### T01: 实现 LoopCheckpoint 类
**文件**: `quantaalpha/pipeline/checkpoint.py` (新建)
**估算**: 4h

```python
import json
import pickle
from pathlib import Path
from datetime import datetime

class LoopCheckpoint:
    """为 AlphaAgentLoop 提供中断恢复能力"""

    def __init__(self, checkpoint_dir: str):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, loop_state: dict, step_name: str):
        """在每个 pipeline 步骤完成后保存检查点"""
        ckpt = {
            "step_name": step_name,
            "timestamp": datetime.now().isoformat(),
            "round_idx": loop_state.get("round_idx", 0),
            "direction_id": loop_state.get("direction_id", 0),
            "trace_len": loop_state.get("trace_len", 0),
        }

        # JSON 元数据
        meta_path = self.checkpoint_dir / "checkpoint_meta.json"
        with open(meta_path, "w") as f:
            json.dump(ckpt, f, indent=2)

        # pickle 序列化状态（D019: 需验证换行符兼容性）
        state_path = self.checkpoint_dir / "checkpoint_state.pkl"
        with open(state_path, "wb") as f:
            pickle.dump(loop_state, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self) -> dict | None:
        """尝试加载最近的检查点"""
        state_path = self.checkpoint_dir / "checkpoint_state.pkl"
        if not state_path.exists():
            return None

        with open(state_path, "rb") as f:
            return pickle.load(f)

    def clear(self):
        """清除检查点（正常完成时调用）"""
        for f in self.checkpoint_dir.glob("checkpoint_*"):
            f.unlink(missing_ok=True)
```

**验收**:
- [ ] save 生成 json 和 pkl 文件
- [ ] load 正确恢复状态
- [ ] clear 删除检查点

### T02: 修改 library.py 增加版本历史
**文件**: `quantaalpha/factors/library.py`
**估算**: 2h

```python
def _normalize_factor_entry(self, factor_entry):
    entry = dict(factor_entry or {})
    entry.setdefault("versions", [])  # 新增
    return entry

def add_factors_from_experiment(self, ...):
    # ... 现有逻辑 ...
    existing = self.data["factors"].get(factor_id)
    if existing and existing.get("backtest_results"):
        versions = existing.get("versions", [])
        versions.append({
            "backtest_results": existing["backtest_results"],
            "timestamp": existing.get("metadata", {}).get("created_at"),
            "experiment_id": existing.get("metadata", {}).get("experiment_id"),
        })
        versions = versions[-10:]  # 只保留最近 10 个
        factor_entry["versions"] = versions

    self.data["factors"][factor_id] = factor_entry
```

**验收**:
- [ ] versions 字段存在
- [ ] 最多保留 10 个历史版本

### T03: 修改 _acquire_lock() 添加超时
**文件**: `quantaalpha/factors/library.py`
**估算**: 1h

```python
import time

def _acquire_lock(self, timeout: int = 30):  # D019 约束：30 秒超时
    self._ensure_lock_dir()
    lock_file = self._lock_dir / f"{self.library_path.name}.lock"
    lock_fd = open(lock_file, "w")
    start = time.time()

    while True:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except BlockingIOError:
            if time.time() - start > timeout:
                lock_fd.close()
                logger.warning(f"Lock timeout after {timeout}s, forcing lock")
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                return lock_fd
            time.sleep(0.5)
```

**验收**:
- [ ] 30 秒超时后强制获取锁
- [ ] 日志记录超时事件

### T04: 集成到 pipeline/loop.py
**文件**: `quantaalpha/pipeline/loop.py`
**估算**: 2h

```python
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

class AlphaAgentLoop:
    def __init__(self, ...):
        # ... 现有代码 ...
        self.checkpoint = LoopCheckpoint(
            checkpoint_dir=workspace / "checkpoints"
        )

    def run(self):
        # 尝试恢复
        restored = self.checkpoint.load()
        if restored:
            self._restore_state(restored)
            logger.info(f"Restored from checkpoint: round {restored.get('round_idx')}")

        try:
            for round_idx in range(self.max_rounds):
                self._run_round(round_idx)
                self.checkpoint.save(self._get_state(), f"round_{round_idx}")
        finally:
            self.checkpoint.clear()

    def _get_state(self) -> dict:
        return {
            "round_idx": self.current_round,
            "direction_id": self.current_direction_id,
            "trace_len": len(self.trace),
            "trace": self.trace,
            "library_state": self.library.data if self.library else None,
        }

    def _restore_state(self, state: dict):
        self.current_round = state.get("round_idx", 0)
        self.current_direction_id = state.get("direction_id", 0)
        self.trace = state.get("trace", [])
```

**验收**:
- [ ] 启动时尝试恢复检查点
- [ ] 每轮后保存检查点
- [ ] 正常完成时清除检查点

### T05: 添加 D019 约束测试
**文件**: `tests/pipeline/test_checkpoint.py` (新建)
**估算**: 1h

测试：
1. pickle 序列化含换行符字段（D019 约束）
2. 锁超时机制（M001 教训）

**验收**:
- [ ] 含换行符状态正常序列化/反序列化
- [ ] 锁超时后强制获取成功

---

## 依赖

- **D017**: Checkpoint 决策要求
- **D019**: M001 教训转化为代码约束
