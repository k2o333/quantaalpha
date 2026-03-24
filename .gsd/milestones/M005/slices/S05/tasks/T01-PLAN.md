# T01: 删除死赋值并归档 proposal.yaml

**Slice:** S05 — 移除 proposal.yaml prompt 配置歧义
**Milestone:** M005

## Description

移除 `quantaalpha/factors/proposal.py` 第 159 行的死赋值 `qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "proposal.yaml")`，并将 `quantaalpha/factors/prompts/proposal.yaml` 归档为 `.archived`。第 305 行的实际赋值（指向 `prompts.yaml`）保持不变。`proposal.yaml` 从不被运行时使用，但其存在造成维护混淆。

## Steps

1. **删除 line 159 死赋值**
   在 `quantaalpha/factors/proposal.py` 中，定位并删除这一行（及前导空行）：
   ```
   qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "proposal.yaml")
   ```
   方法：用 `sed -i '159d'` 删除该行。由于该行上方是空行，删除后结构保持完整（`Hypothesis` 类定义后空一行，逻辑不变）。

2. **归档 proposal.yaml**
   ```
   mv quantaalpha/factors/prompts/proposal.yaml quantaalpha/factors/prompts/proposal.yaml.archived
   ```
   保留原文件内容供历史参考，但不加载到运行时。

3. **验证 Python 语法**
   ```
   python -m py_compile quantaalpha/factors/proposal.py
   ```

## Must-Haves

- [ ] `rg -c "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py` returns `1`
- [ ] `test -f quantaalpha/factors/prompts/proposal.yaml.archived` (file exists)
- [ ] `python -m py_compile quantaalpha/factors/proposal.py` exits 0

## Verification

- `rg -c "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py` — 必须返回 1（只有 line 305 的赋值）
- `ls quantaalpha/factors/prompts/proposal.yaml` — 必须返回 "No such file"
- `ls quantaalpha/factors/prompts/proposal.yaml.archived` — 必须存在
- `python -m py_compile quantaalpha/factors/proposal.py` — 无输出，退出码 0

## Inputs

- `quantaalpha/factors/proposal.py` — 读取并修改（删除 line 159）
- `quantaalpha/factors/prompts/proposal.yaml` — 读取（归档操作）

## Expected Output

- `quantaalpha/factors/proposal.py` — 已修改（删除死赋值行）
- `quantaalpha/factors/prompts/proposal.yaml.archived` — 新增（归档文件）
