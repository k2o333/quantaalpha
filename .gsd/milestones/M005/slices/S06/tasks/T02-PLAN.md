# T02: 同步 vendored 副本并验证

**Slice:** S06 — 集中 JSON 转义修复
**Milestone:** M005

## Description

将 T01 修改后的 `quantaalpha/llm/client.py` 同步到 vendored 路径 `third_party/quantaalpha/quantaalpha/llm/client.py`，确保两份文件 byte-identical，并用 diff 和语法检查验证。

## Steps

1. 将修改后的主文件复制到 vendored 路径：

   ```bash
   cp quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py
   ```

2. 验证两份文件一致：

   ```bash
   diff -q quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py
   ```

   应无输出（表示完全一致）。

3. 验证 MD5 一致：

   ```bash
   md5sum quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py
   ```

4. 运行 vendored 文件语法检查：

   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
   ```

## Must-Haves

- [ ] vendored `client.py` 与主 `client.py` byte-identical（diff 无输出）
- [ ] MD5 校验值一致
- [ ] vendored 文件语法检查通过

## Verification

- `diff -q quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py` — 无输出
- `md5sum` 两文件一致
- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` — 无输出

## Inputs

- `quantaalpha/llm/client.py` — T01 修改后的主文件
- `third_party/quantaalpha/quantaalpha/llm/client.py` — 待同步的 vendored 文件

## Expected Output

- `third_party/quantaalpha/quantaalpha/llm/client.py` — 与主文件同步的 vendored 副本
