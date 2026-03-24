# T03: Integrate ResourceManager with loop.py

**Slice:** S08 — ResourceManager 资源管理 (S7/D018)
**Milestone:** M003

## Description

Integrate ResourceManager into the `AlphaAgentLoop.run()` method to enforce resource budget checks before each loop iteration. This follows the D017 Checkpoint pattern established in S06.

## Steps

1. **Add import at top of loop.py** (after existing imports):
   ```python
   from quantaalpha.pipeline.resource_manager import ResourceManager
   ```

2. **Add `_get_resource_manager()` method to `AlphaAgentLoop`**:
   - Following the `_get_checkpoint()` pattern from S06
   - Lazy import to avoid circular dependency
   ```python
   def _get_resource_manager(self) -> "ResourceManager | None":
       try:
           from quantaalpha.pipeline.resource_manager import resource_manager
           return resource_manager
       except ImportError:
           return None
   ```

3. **Modify `run()` method to add resource checks**:
   - At the START of the while loop, before step execution
   - Call `check_and_enforce()` before each iteration
   - If resources exceeded, log WARNING and break from loop
   ```python
   def run(self, step_n: int | None = None, stop_event: threading.Event = None):
       # Initialize resource manager (lazy)
       resource_mgr = self._get_resource_manager()
       
       with tqdm(total=len(self.steps), desc="Workflow Progress", unit="step") as pbar:
           while True:
               # Resource budget check before each iteration
               if resource_mgr:
                   allowed, reason = resource_mgr.check_and_enforce()
                   if not allowed:
                       logger.warning(f"Resource budget exceeded: {reason}")
                       logger.warning("Consider increasing budget or clearing old results.")
                       break  # Stop loop gracefully
               
               if step_n is not None:
                   if step_n <= 0:
                       break
                   step_n -= 1
               
               # ... rest of loop body unchanged ...
   ```

4. **Validate syntax**:
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py
   ```

## Must-Haves

- [ ] Import `ResourceManager` or lazy import in `_get_resource_manager()`
- [ ] `_get_resource_manager()` method follows S06 checkpoint pattern
- [ ] `run()` calls `check_and_enforce()` at iteration start
- [ ] When budget exceeded: WARNING log + graceful break (not crash)
- [ ] Syntax validates with py_compile

## Verification

- Syntax validation:
  ```bash
  python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py
  ```
- Import check:
  ```bash
  python -c "from quantaalpha.pipeline.loop import AlphaAgentLoop; print('OK: AlphaAgentLoop imports')"
  ```

## Observability Impact

- **Signals added/changed:**
  - WARNING log when resource budget exceeded (loop breaks)
  - INFO log when resource manager initializes
- **How a future agent inspects this:**
  - Check `loop.py` for `_get_resource_manager()` and `check_and_enforce()` call
  - Check logs for "Resource budget exceeded" messages
- **Failure state exposed:**
  - When budget exceeded: loop exits gracefully with WARNING
  - When ResourceManager unavailable: graceful None handling, loop continues

## Inputs

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — Modify here
- `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` — Reference for API
- `third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py` — Reference for lazy import pattern

## Expected Output

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — Modified with resource_mgr integration
