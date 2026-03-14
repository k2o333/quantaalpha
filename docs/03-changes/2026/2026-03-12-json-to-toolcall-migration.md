# 从正文解析 JSON 改为 Tool Call 方案

## 1. 背景

当前系统通过 `robust_json_parse()` 函数从 LLM 返回的正文文本中解析 JSON 数据。这种方式存在以下问题：

1. **解析脆弱**：LLM 可能返回格式不规范的 JSON（截断、转义、多余文本等）
2. **需要修复逻辑**：需要复杂的 `robust_json_parse()` 多策略修复机制
3. **不可靠**：解析失败率高，需要 JSON 修复链作为兜底
4. **语义不明确**：正文中的 JSON 可能是随意插入的，模型可能输出其他解释性文本

## 2. 目标

改用 LLM 的 **Tool Call（Function Calling）** 功能，让模型直接返回结构化的函数调用结果，避免正文解析。

## 3. 方案设计

### 3.1 核心思路

1. 定义结构化的 Tool（函数）schema
2. 在 LLM 调用时传入 `tools` 参数
3. LLM 直接返回符合 schema 的函数调用
4. 直接解析函数调用结果，无需正文解析

### 3.2 实现步骤

#### Step 1: 定义 Tool Schema

根据当前业务需求，定义对应的 function schema。例如：

```python
from typing import List, Optional
from pydantic import BaseModel

class HypothesisOutput(BaseModel):
    hypothesis: str
    reason: str
    concise_reason: str
    concise_observation: str
    concise_justification: str
    concise_knowledge: str

class FactorExperimentOutput(BaseModel):
    factors: dict  # factor_name -> factor_code mapping

# Tool 定义
HYPOTHESIS_TOOL = {
    "type": "function",
    "function": {
        "name": "output_hypothesis",
        "description": "输出因子假设和推理",
        "parameters": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string", "description": "因子假设"},
                "reason": {"type": "string", "description": "推理过程"},
                "concise_reason": {"type": "string", "description": "简洁推理"},
                "concise_observation": {"type": "string", "description": "简洁观察"},
                "concise_justification": {"type": "string", "description": "简洁论证"},
                "concise_knowledge": {"type": "string", "description": "简洁知识"},
            },
            "required": ["hypothesis", "reason"]
        }
    }
}

EXPERIMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "output_experiment",
        "description": "输出因子实验配置",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "object",
                    "description": "因子名称到因子代码的映射",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["factors"]
        }
    }
}
```

#### Step 2: 修改 LLM 客户端

在 `quantaalpha/llm/client.py` 中添加 tool call 支持：

```python
def chat_with_tools(
    self,
    messages: List[dict],
    tools: List[dict],
    model: Optional[str] = None,
    **kwargs
) -> dict:
    """使用 tool call 调用 LLM"""
    params = {
        "model": model or self.cfg.model,
        "messages": messages,
        "tools": tools,
        **kwargs
    }
    
    response = self._create_chat_completion_inner_function(**params)
    
    # 解析 tool call
    if response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        return {
            "function_name": tool_call.function.name,
            "function_args": json.loads(tool_call.function.arguments)
        }
    
    # 如果没有 tool call，回退到正文解析
    return {"content": response.choices[0].message.content}
```

#### Step 3: 修改业务代码

将 `proposal.py` 等文件中的调用方式改为：

**Before（当前方式）**:
```python
response = llm.chat(messages)
response_dict = robust_json_parse(response)
hypothesis = QlibFactorHypothesis(
    hypothesis=response_dict.get("hypothesis", ""),
    ...
)
```

**After（使用 tool call）**:
```python
# 构造 messages
messages = [...]

# 调用 LLM with tools
result = llm.chat_with_tools(
    messages=messages,
    tools=[HYPOTHESIS_TOOL]
)

# 直接获取结构化结果
if "function_args" in result:
    args = result["function_args"]
    hypothesis = QlibFactorHypothesis(
        hypothesis=args.get("hypothesis", ""),
        ...
    )
else:
    # 回退机制
    response_dict = robust_json_parse(result["content"])
    ...
```

### 3.3 兼容方案

考虑到不是所有模型都支持 tool call，建议：

1. **渐进式迁移**：先在部分场景使用 tool call，其他场景保留正文解析
2. **回退机制**：如果模型不支持 tool call 或调用失败，自动回退到正文解析
3. **模型选择**：确保使用的模型支持 function calling（如 OpenAI GPT-4, Claude 3.5 等）

```python
def chat_with_fallback(
    self,
    messages: List[dict],
    tools: Optional[List[dict]] = None,
    **kwargs
) -> dict:
    """带回退的 tool call 调用"""
    if tools is None:
        # 不使用 tools，直接正文解析
        return {"content": self.chat(messages, **kwargs)}
    
    try:
        return self.chat_with_tools(messages, tools, **kwargs)
    except Exception as e:
        logger.warning(f"Tool call failed: {e}, falling back to text parsing")
        return {"content": self.chat(messages, **kwargs)}
```

### 3.4 需要改造的文件

| 文件 | 改造内容 |
|------|----------|
| `quantaalpha/llm/client.py` | 添加 `chat_with_tools` 方法 |
| `quantaalpha/factors/proposal.py` | 将 `robust_json_parse` 调用改为 tool call |
| 其他调用 `robust_json_parse` 的文件 | 逐步迁移 |

## 4. 优势

| 方面 | 当前方案（正文解析） | 方案（Tool Call） |
|------|---------------------|-------------------|
| 可靠性 | 需要复杂修复逻辑 | 直接结构化输出 |
| 解析失败率 | 高（需修复链） | 极低 |
| 实现复杂度 | 中（多策略解析） | 低（直接解析） |
| 语义明确性 | 低（可能混入文本） | 高（强制结构化） |
| 模型要求 | 无特殊要求 | 需要支持 function calling |

## 5. 风险与注意事项

1. **模型兼容性**：确保使用的 LLM 支持 tool call
2. **schema 设计**：需要精确设计 function schema，包含完整的参数说明
3. **错误处理**：保留回退机制以应对特殊情况
4 **测试验证**：改造后需要充分测试确保功能等价

## 6. 实施计划

1. **第一阶段**：在 `llm/client.py` 中实现 `chat_with_tools` 方法
2. **第二阶段**：改造 `proposal.py` 中的 Hypothesis 输出
3. **第三阶段**：改造 FactorExperiment 输出
4. **第四阶段**：逐步迁移其他使用 `robust_json_parse` 的场景
5. **第五阶段**：验证并监控效果，移除冗余的 JSON 修复代码
