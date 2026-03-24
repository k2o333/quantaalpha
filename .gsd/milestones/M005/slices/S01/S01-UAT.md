# S01: UAT — 移除 rdagent.log 硬依赖

**Milestone:** M005
**Slice:** S01
**Date:** 2026-03-24
**Preconditions:** rdagent.log 不可用（不在 sys.modules 中）

---

## Test Cases

### TC01: 基本导入成功

**Precondition:** rdagent.log 模块不可用（干净 Python 环境）

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M005
python -c "from quantaalpha.log import logger, LogColors; print(type(logger).__name__)"
```

**Expected:**
- Exit code 0
- Output: `FallbackLoggerWrapper`
- `LogColors` is an Enum with RED, GREEN, etc.

**Fail signal:** `ImportError: cannot import name 'logger' from 'quantaalpha.log'`

---

### TC02: 主包路径导入成功

**Precondition:** 同 TC01

**Steps:**
```bash
python -c "import quantaalpha.log; print('OK')"
```

**Expected:** Exit code 0, 输出 `OK`

---

### TC03: Vendored 路径导入成功

**Precondition:** 同 TC01

**Steps:**
```bash
python -c "import sys; sys.path.insert(0, 'third_party/quantaalpha'); from quantaalpha.log import logger, LogColors; print(type(logger).__name__)"
```

**Expected:** Exit code 0, 输出 `FallbackLoggerWrapper`

**Fail signal:** `ImportError` on the vendored path

---

### TC04: 所有必需方法存在

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import logger

for method in ['info', 'warning', 'error', 'exception']:
    assert hasattr(logger, method), f"Missing: {method}"
print("All methods exist")
```

**Expected:** Exit code 0, 输出 `All methods exist`

---

### TC05: log_trace_path 返回 Path 类型

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import logger
from pathlib import Path
assert isinstance(logger.log_trace_path, Path)
print(f"trace_path={logger.log_trace_path}")
```

**Expected:** Exit code 0, `trace_path` 是 `pathlib.Path` 对象，默认值在 `/tmp/quantaalpha_logs/` 或 `$LOG_TRACE_PATH`

---

### TC06: set_trace_path 修改 log_trace_path

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import logger
import tempfile
tmp = tempfile.mkdtemp()
logger.set_trace_path(tmp)
assert str(logger.log_trace_path) == tmp
print(f"Changed to: {logger.log_trace_path}")
```

**Expected:** Exit code 0, 新 path 等于 `tmp`

**Fail signal:** `log_trace_path` 未更新

---

### TC07: storage 接口存在

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import logger
assert hasattr(logger, 'storage')
assert hasattr(logger.storage, 'path')
assert hasattr(logger.storage, 'truncate')
print("storage OK")
```

**Expected:** Exit code 0

---

### TC08: LogColors Enum 完整

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import LogColors
required = ['RESET', 'RED', 'GREEN', 'YELLOW', 'BLUE', 'MAGENTA', 'CYAN', 'WHITE', 'GRAY', 'BOLD', 'UNDERLINE']
for name in required:
    assert hasattr(LogColors, name), f"Missing LogColors.{name}"
print(f"LogColors OK: {[e.name for e in LogColors]}")
```

**Expected:** Exit code 0, 11 种颜色

---

### TC09: rdagent 不在 sys.modules 中（隔离验证）

**Precondition:** 同 TC01

**Steps:**
```python
import sys
rdagent_mods = [m for m in sys.modules if 'rdagent' in m.lower()]
assert len(rdagent_mods) == 0, f"Unexpected rdagent modules: {rdagent_mods}"
from quantaalpha.log import logger  # noqa
print("rdagent-free import: PASS")
```

**Expected:** Exit code 0, 输出 `rdagent-free import: PASS`

---

### TC10: 两份 log/__init__.py 完全一致

**Precondition:** 无

**Steps:**
```bash
diff -q quantaalpha/log/__init__.py third_party/quantaalpha/quantaalpha/log/__init__.py && echo "IDENTICAL"
md5sum quantaalpha/log/__init__.py third_party/quantaalpha/quantaalpha/log/__init__.py
```

**Expected:** 无 diff 输出，两份 MD5 相同

**Fail signal:** `Files differ`

---

### TC11: 日志方法实际输出（非 no-op）

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import logger
import sys
from io import StringIO

# Capture stderr
old_stderr = sys.stderr
sys.stderr = StringIO()

logger.info("test_info")
logger.warning("test_warning")
logger.error("test_error")

output = sys.stderr.getvalue()
sys.stderr = old_stderr

assert "test_info" in output
assert "test_warning" in output
assert "test_error" in output
print("Log output verified")
```

**Expected:** Exit code 0, 输出 `Log output verified`

---

### TC12: LogColors ANSI 转义码格式正确

**Precondition:** 同 TC01

**Steps:**
```python
from quantaalpha.log import LogColors
assert LogColors.RED.value == "\033[91m"
assert LogColors.RESET.value == "\033[0m"
print(f"RED={repr(LogColors.RED.value)}, RESET={repr(LogColors.RESET.value)}")
```

**Expected:** Exit code 0, ANSI 转义码格式

---

## Edge Cases

### EC01: 环境变量 LOG_TRACE_PATH 控制默认路径

**Steps:**
```bash
LOG_TRACE_PATH=/custom/path python -c "from quantaalpha.log import logger; print(logger.log_trace_path)"
```

**Expected:** 输出 `/custom/path`

### EC02: set_trace_path 接受 str 和 Path

**Steps:**
```python
from quantaalpha.log import logger
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp()
logger.set_trace_path(tmp)         # str
assert str(logger.log_trace_path) == tmp

tmp2 = tempfile.mkdtemp()
logger.set_trace_path(Path(tmp2))  # Path
assert str(logger.log_trace_path) == tmp2
print("str/Path OK")
```

**Expected:** Exit code 0

### EC03: exception 方法可调用

**Steps:**
```python
from quantaalpha.log import logger
import sys
from io import StringIO

sys.stderr = StringIO()
try:
    raise ValueError("test")
except:
    logger.exception("caught error")
output = sys.stderr.getvalue()
sys.stderr = sys.__stderr__
assert "ValueError" in output
assert "test" in output
print("exception() OK")
```

**Expected:** Exit code 0, ValueError traceback 出现在输出中

---

## Success Criteria

All 12 test cases pass + 3 edge cases pass → **Slice ready to ship**

Run all with:
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M005
python -m pytest --collect-only -q 2>/dev/null && echo "pytest check: none found (manual tests needed)"
# Run TC01-TC12 manually as shown above
```

Manual verification commands (run each independently):
```bash
# TC01
python -c "from quantaalpha.log import logger, LogColors; print(type(logger).__name__, type(LogColors).__name__)"

# TC10
diff -q quantaalpha/log/__init__.py third_party/quantaalpha/quantaalpha/log/__init__.py

# TC11
python -c "
from quantaalpha.log import logger
import sys, io
old = sys.stderr; sys.stderr = io.StringIO()
logger.info('info'); logger.warning('warn'); logger.error('err')
out = sys.stderr.getvalue(); sys.stderr = old
assert 'info' in out and 'warn' in out and 'err' in out
print('Log output: OK')
"
```
