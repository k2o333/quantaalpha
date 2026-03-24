# T01: 实现 LoopCheckpoint 类与单元测试

**Slice:** S06 — Checkpoint 与幂等性恢复
**Milestone:** M003

## Description

实现 D017 核心组件 `LoopCheckpoint` 类，提供中断保存机制。该类在每个 pipeline 步骤后持久化状态，支持 pickle 序列化（含换行符验证，符合 D019 约束），并通过原子写（tmp+rename）确保 JSON 元数据不因崩溃而损坏。

## Steps

1. **Create `quantaalpha/pipeline/checkpoint.py`** — new file with `LoopCheckpoint` class:
   - `__init__(checkpoint_dir: str | Path)` — create dir, store path
   - `save(loop_state: dict, step_name: str)` — atomic JSON meta write (tmp+rename) + pickle state write
   - `load() -> dict | None` — load pickled state, return None if no checkpoint
   - `restore(loop_instance: AlphaAgentLoop) -> bool` — patch loop_instance.loop_idx, loop_instance.step_idx, loop_instance.loop_prev_out from pickled state
   - `clear()` — remove checkpoint_meta.json and checkpoint_state.pkl
   - `exists -> bool` — property checking checkpoint_meta.json existence
   - D019 constraint: before pickle.dumps(), validate no raw control chars (0x00-0x08) in string fields of loop_state; if found, log warning and skip those fields

2. **Create `quantaalpha/tests/test_checkpoint.py`** — unit tests:
   - `test_save_creates_files` — verify checkpoint_meta.json and checkpoint_state.pkl created
   - `test_load_returns_state` — verify load() returns correct loop_state dict
   - `test_load_returns_none_when_no_checkpoint` — verify load() returns None on clean start
   - `test_clear_removes_files` — verify clear() deletes both files
   - `test_exists_property` — True after save, False after clear, False when no file
   - `test_atomic_json_write` — verify tmp file + rename pattern (no partial writes visible)
   - `test_newline_in_state` — D019: save state with newlines/tabs in hypothesis text, load back correctly
   - `test_restore_patches_loop` — create mock AlphaAgentLoop, restore state, verify attrs patched

3. **Verify syntax and run tests**:
   - `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py`
   - `python -m pytest third_party/quantaalpha/tests/test_checkpoint.py -v`

## Must-Haves

- [ ] `LoopCheckpoint.save()` writes both checkpoint_meta.json (atomic) and checkpoint_state.pkl
- [ ] `LoopCheckpoint.load()` returns dict or None; restores loop_idx, step_idx, loop_prev_out
- [ ] `LoopCheckpoint.clear()` removes checkpoint files
- [ ] `LoopCheckpoint.restore()` patches AlphaAgentLoop instance attributes
- [ ] D019 constraint: newline-containing fields serialize safely without corruption
- [ ] Atomic write: JSON meta uses tmp+rename, no partial-write file visible
- [ ] 8 unit tests pass covering all methods and edge cases

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py

# Run all unit tests
python -m pytest third_party/quantaalpha/tests/test_checkpoint.py -v

# D019 newline constraint — inline verification
python -c "
import pickle, json, tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    state = {
        'loop_idx': 0,
        'step_idx': 1,
        'loop_prev_out': {
            'factor_propose': {
                'hypothesis': 'line1\nline2\nline3\twith\ttabs',
            }
        },
        'round_idx': 0,
        'direction_id': 0,
        'trace_len': 2,
    }
    ckpt.save(state, 'factor_propose')
    loaded = ckpt.load()
    assert loaded is not None
    assert loaded['loop_idx'] == 0
    assert loaded['step_idx'] == 1
    with open(Path(tmp)/'checkpoint_meta.json') as f:
        meta = json.load(f)
    assert meta['step_name'] == 'factor_propose'
    ckpt.clear()
    assert not ckpt.exists
    print('D019 checkpoint serialization: PASS')
"
```

## Observability Impact

- Signals added: `checkpoint.save()` emits structured JSON meta (step_name, round_idx, timestamp); `checkpoint.restore()` emits INFO log "Restored from checkpoint: round={n} step={n}"; control-char warning emits WARNING log
- How a future agent inspects: `cat {session_folder}/checkpoint/checkpoint_meta.json` — human-readable checkpoint state
- Failure state exposed: Missing checkpoint → load() returns None (INFO log "No checkpoint found, starting clean"); Corrupt pickle → "checkpoint load failed" logged as ERROR with exception

## Inputs

- `third_party/quantaalpha/quantaalpha/utils/workflow.py` — reference LoopBase.dump() pattern (lines 147-153), LoopTrace dataclass definition
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — reference AlphaAgentLoop attributes (loop_idx, step_idx, loop_prev_out, round_idx, direction_id, trace)

## Expected Output

- `third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py` — LoopCheckpoint class with save/load/clear/restore/exists methods
- `third_party/quantaalpha/tests/test_checkpoint.py` — 8+ unit tests covering all methods and D019 newline constraint
