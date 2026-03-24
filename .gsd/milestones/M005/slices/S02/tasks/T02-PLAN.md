# T02: 建立 vendored proposal.py 并同步文件

**Slice:** S02 — 强化 normalize_corrected_expression
**Milestone:** M005

## Description

After T01 hardened the main `proposal.py`, create the missing vendored copy at `third_party/quantaalpha/quantaalpha/factors/proposal.py` and establish the dual-file synchronization invariant (both files must be byte-identical for the function body).

## Steps

1. **Verify the main file is updated** — confirm `normalize_corrected_expression` in `quantaalpha/factors/proposal.py` is the hardened version:
   ```bash
   grep -A 3 "def normalize_corrected_expression" quantaalpha/factors/proposal.py
   ```
   You should see the multi-line implementation (not the old 3-line version).

2. **Create the vendored directory structure:**
   ```bash
   mkdir -p third_party/quantaalpha/quantaalpha/factors
   ```
   The `third_party/quantaalpha/quantaalpha/` parent directory already exists (created by S01). We only need to add the `factors/` subdirectory.

3. **Copy the main file to the vendored location:**
   ```bash
   cp quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py
   ```

4. **Verify the vendored copy is readable and syntactically valid:**
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py && echo "SYNTAX OK"
   ```

5. **Confirm byte-identical** between the two copies:
   ```bash
   diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py
   ```
   Expected output: nothing (no differences).

6. **Create a vendored `__init__.py`** in the `factors/` directory to make it a Python package:
   ```bash
   echo "" > third_party/quantaalpha/quantaalpha/factors/__init__.py
   ```

## Must-Haves

- [ ] `third_party/quantaalpha/quantaalpha/factors/proposal.py` 存在并与主文件 byte-identical
- [ ] `third_party/quantaalpha/quantaalpha/factors/__init__.py` 存在
- [ ] `python -m py_compile` 两份文件均无语法错误
- [ ] `diff` 确认两份文件无差异

## Verification

```bash
python -m py_compile quantaalpha/factors/proposal.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py
diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py && echo "IDENTICAL"
```

Expected: both py_compile succeed with no output, and `diff` prints nothing (IDENTICAL).

## Inputs

- `quantaalpha/factors/proposal.py` — 已更新的主文件（T01 输出）

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — vendored 副本，与主文件一致
- `third_party/quantaalpha/quantaalpha/factors/__init__.py` — Python 包标识文件
