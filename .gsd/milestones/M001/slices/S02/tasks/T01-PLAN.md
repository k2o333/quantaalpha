# T01: 在 client.py 添加空响应检测
**Slice:** S02  **Milestone:** M001
## Goal
在流式/非流式路径添加空响应检测逻辑。
## Must-Haves
### Truths
- `grep -c "Empty LLM response" client.py` 返回 2
### Artifacts
- `third_party/quantaalpha/quantaalpha/llm/client.py` line 1022-1038 已修改
## Steps
1. 流式路径后检查 `if not resp or not resp.strip()`
2. 非流式路径后检查 `if resp is None`
