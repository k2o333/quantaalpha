# T03: 将 Checkpoint 集成到 AlphaAgentLoop 并添加实验配置

**Slice:** S06 — Checkpoint 与幂等性恢复
**Milestone:** M003

## Description

将 T01 的 `LoopCheckpoint` 集成到 `AlphaAgentLoop` 的 pipeline 流程中，并在 `experiment.yaml` 中添加 checkpoint 配置段。Checkpoint 在 `__init__` 中尝试从上一个崩溃实例恢复，每步完成后保存，正常退出时清除。

## Steps

1. **Modify `quantaalpha/pipeline/loop.py`** — add checkpoint integration:

   a. **Add import** at top of file (after existing imports):
      ```python
      from quantaalpha.pipeline.checkpoint import LoopCheckpoint
      ```

   b. **In `__init__()`** (after `self._last_feedback = None` line ~100), add checkpoint initialization and restore:
      ```python
      # Checkpoint recovery from previous crash
      self._checkpoint = LoopCheckpoint(str(self.session_folder / "checkpoint"))
      restored = self._checkpoint.restore(self)
      if restored:
          logger.info(
              f"Restored from checkpoint: loop_idx={self.loop_idx} step_idx={self.step_idx} "
              f"round={getattr(self, 'round_idx', 0)}"
          )
      else:
          logger.info("No checkpoint found, starting clean")
      ```

   c. **In `feedback()`** (after `self.trace.hist.append(...)` ~line 255), add checkpoint save:
      ```python
      # Save checkpoint after successful step (crash recovery support)
      try:
          self._checkpoint.save(
              {
                  "loop_idx": self.loop_idx,
                  "step_idx": self.step_idx,
                  "loop_prev_out": self.loop_prev_out,
                  "round_idx": getattr(self, "round_idx", 0),
                  "direction_id": getattr(self, "direction_id", 0),
                  "trace_len": len(self.trace.hist) if hasattr(self, "trace") else 0,
              },
              step_name="feedback",
          )
      except Exception as e:
          logger.warning(f"Failed to save checkpoint: {e}")

      # Clear checkpoint on clean round completion (step_idx reset means new round)
      if self.step_idx == 0:
          self._checkpoint.clear()
      ```

   d. **After `LoopBase.dump()` call in `run()`** (line ~134), add checkpoint save after every step:
      (Note: The existing `self.dump()` call is at line ~134 of workflow.py. In loop.py, the `run()` method is inherited from `LoopBase`. The `AlphaAgentLoop` does not override `run()`. We need to either override `run()` or add checkpoint save in each step method. The cleanest approach is to override `run()` in `AlphaAgentLoop`.)

      Add `run()` override after `__init__`:
      ```python
      def run(self, step_n: int | None = None, stop_event: threading.Event = None):
          """Override LoopBase.run() to add checkpoint save after each step."""
          from tqdm.auto import tqdm

          steps = self.steps
          with tqdm(total=len(steps), desc="Workflow Progress", unit="step") as pbar:
              while True:
                  if step_n is not None:
                      if step_n <= 0:
                          break
                      step_n -= 1

                  li, si = self.loop_idx, self.step_idx
                  start = datetime.datetime.now(datetime.timezone.utc)
                  name = steps[si]
                  func = getattr(self, name)
                  try:
                      self.loop_prev_out[name] = func(self.loop_prev_out)
                  except self.skip_loop_error as e:
                      logger.warning(f"Skip loop {li} due to {e}")
                      self.loop_idx += 1
                      self.step_idx = 0
                      self._checkpoint.clear()  # clear on skip
                      continue
                  except Exception as e:
                      logger.warning(f"Traceback loop {li} due to {e}")
                      self.step_idx = 0
                      continue
                  end = datetime.datetime.now(datetime.timezone.utc)
                  self.loop_trace[li].append(
                      LoopTrace(start, end)
                  )
                  pbar.set_postfix(loop_index=li, step_index=si, step_name=name)
                  pbar.update(1)

                  # Index increase and save session
                  self.step_idx = (self.step_idx + 1) % len(steps)
                  if self.step_idx == 0:
                      self.loop_idx += 1
                      self.loop_prev_out = {}
                      pbar.reset()
                      self._checkpoint.clear()  # clear on clean round exit

                  # Checkpoint save after every step (D017 requirement)
                  try:
                      self._checkpoint.save(
                          {
                              "loop_idx": li,
                              "step_idx": si,
                              "loop_prev_out": self.loop_prev_out,
                              "round_idx": getattr(self, "round_idx", 0),
                              "direction_id": getattr(self, "direction_id", 0),
                              "trace_len": len(self.trace.hist) if hasattr(self, "trace") else 0,
                          },
                          step_name=name,
                      )
                  except Exception as e:
                      logger.warning(f"Failed to save checkpoint: {e}")

                  self.dump(self.session_folder / f"{li}" / f"{si}_{name}")

                  if stop_event is not None and stop_event.is_set():
                      raise Exception("Mining stopped by user")
      ```

2. **Modify `configs/experiment.yaml`** — add checkpoint section at the end:
   ```yaml
   # ============================================================
   # CHECKPOINT CONFIGURATION (D017)
   # Controls crash recovery and factor version history
   # ============================================================
   checkpoint:
     # Enable checkpoint save/load (required for 24H autonomous operation)
     enabled: true
     # Checkpoint directory (null = auto from session_folder/checkpoint)
     checkpoint_dir: null
     # Lock acquisition timeout in seconds (D019 constraint: prevents deadlock)
     lock_timeout_seconds: 30
     # Maximum historical versions per factor in library
     max_versions_per_factor: 10
   ```

3. **Create `quantaalpha/tests/test_checkpoint_integration.py`** — integration tests:
   - `test_loop_init_restores_checkpoint` — mock LoopCheckpoint, verify restore() called in __init__
   - `test_feedback_calls_checkpoint_save` — mock checkpoint, call feedback(), verify save() called with correct args
   - `test_checkpoint_config_parsed` — parse experiment.yaml, verify checkpoint.enabled=true, timeout=30, max_versions=10
   - `test_run_clears_on_clean_exit` — verify clear() called when step_idx resets to 0

4. **Verify syntax and run tests**:
   - `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py`
   - `python -m pytest third_party/quantaalpha/tests/test_checkpoint_integration.py -v`

## Must-Haves

- [ ] `AlphaAgentLoop.__init__()` instantiates `LoopCheckpoint` and calls `restore()`
- [ ] `AlphaAgentLoop.run()` override saves checkpoint after each step
- [ ] `AlphaAgentLoop.run()` clears checkpoint on clean round exit (step_idx == 0)
- [ ] `feedback()` calls checkpoint.save() (backup after each step)
- [ ] `experiment.yaml` contains `checkpoint:` section with enabled/timeout/max_versions
- [ ] All integration tests pass

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py

# Run integration tests
python -m pytest third_party/quantaalpha/tests/test_checkpoint_integration.py -v

# Config parse verification
python -c "
import yaml
from pathlib import Path
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))
ckpt = cfg.get('checkpoint', {})
assert ckpt.get('enabled') == True, f'checkpoint.enabled should be True, got {ckpt}'
assert ckpt.get('lock_timeout_seconds') == 30, f'timeout should be 30'
assert ckpt.get('max_versions_per_factor') == 10, f'max_versions should be 10'
print('experiment.yaml checkpoint config: PASS')
"
```

## Observability Impact

- Signals added: `restore()` logs INFO "Restored from checkpoint" or "No checkpoint found"; `save()` emits no log (called frequently, would spam); `clear()` emits no log; lock timeout emits WARNING
- How a future agent inspects: `cat {session_folder}/checkpoint/checkpoint_meta.json` to see crash state; grep logs for "Restored from checkpoint" to detect recovery events
- Failure state exposed: checkpoint save failure → WARNING log, operation continues (checkpoint is best-effort, not critical path)

## Inputs

- `third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py` — T01 output: LoopCheckpoint class
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — source file to modify (AlphaAgentLoop class)
- `third_party/quantaalpha/configs/experiment.yaml` — config file to modify

## Expected Output

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — MODIFY: add checkpoint import, __init__ restore, run() override with checkpoint save/clear
- `third_party/quantaalpha/configs/experiment.yaml` — MODIFY: add checkpoint: section
- `third_party/quantaalpha/tests/test_checkpoint_integration.py` — NEW: 4 integration tests
