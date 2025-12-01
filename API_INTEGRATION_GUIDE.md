# AI一致性助手 API集成指南

## 概述

AI一致性助手提供了一个基于RAG的文档一致性检查和修改服务，可以作为工具挂载到其他Agent系统上。

## 核心API接口

### 1. 一致性检查API

**端点**: `POST /api/check-consistency`

**功能**: 检查并修改多个文档中与某个主题相关的内容，确保一致性。

---

## 请求格式

### HTTP请求

```http
POST http://your-server:8007/api/check-consistency
Content-Type: application/json
```

### 请求体（Request Body）

```json
{
  "modification_point": "早季分类",
  "modification_request": "将所有提到'早季分类'的地方统一改为'早期作物分类'，并补充说明其在粮食安全中的重要性",
  "project_id": "project_123",
  "top_k": 15
}
```

### 参数说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `modification_point` | string | ✅ | - | 要修改的主题/概念，用于RAG检索相关文档 |
| `modification_request` | string | ✅ | - | 具体的修改要求，AI会根据这个生成修改建议 |
| `project_id` | string | ✅ | - | 项目ID，用于在知识库中定位文档 |
| `top_k` | integer | ❌ | 15 | RAG检索返回的相关文档数量 |

---

## 响应格式

### 成功响应示例

```json
{
  "success": true,
  "modification_point": "早季分类",
  "consistency_analysis": {
    "summary": "分析了3个文档，发现术语使用不一致",
    "issues_found": [
      "文档A使用'早季分类'",
      "文档B使用'早期分类'"
    ],
    "recommendation": "统一使用'早期作物分类'"
  },
  "related_files": {
    "minio://bucket/doc1.md": [
      {
        "content": "...文档片段...",
        "score": 0.95,
        "metadata": {
          "chunk_id": "chunk_123",
          "file_name": "doc1.md"
        }
      }
    ],
    "minio://bucket/doc2.md": [...]
  },
  "total_files": 3,
  "total_chunks": 12,
  "modifications": [
    {
      "file_path": "minio://bucket/doc1.md",
      "original_content": "...原始内容...",
      "modified_content": "...修改后内容...",
      "diff_summary": "将'早季分类'改为'早期作物分类'，新增粮食安全相关说明",
      "original_length": 5420,
      "modified_length": 6150,
      "evaluation": {
        "modification_points": [
          {
            "location": "第2章第3节",
            "original_text": "早季分类是...",
            "reason": "术语不统一",
            "suggestion": "改为'早期作物分类'"
          }
        ]
      },
      "react_thinking_process": [
        {
          "iteration": 1,
          "thought": "需要搜索早期作物分类的学术定义",
          "action": {"type": "search", "query": "早期作物分类 粮食安全"}
        },
        {
          "iteration": 2,
          "thought": "已找到足够信息，开始生成修改内容",
          "action": {"type": "finish"}
        }
      ],
      "react_search_history": [
        {
          "query": "早期作物分类 粮食安全",
          "results": ["文献1", "文献2"],
          "timestamp": "2025-11-27T10:30:00"
        }
      ],
      "truncated": false
    }
  ],
  "message": "成功分析 3 个文档，生成 3 个修改建议"
}
```

### 响应字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `success` | boolean | 请求是否成功 |
| `modification_point` | string | 原始修改点 |
| `consistency_analysis` | object | AI的一致性分析结果 |
| `related_files` | object | RAG检索到的相关文档及其片段 |
| `total_files` | integer | 找到的相关文档总数 |
| `total_chunks` | integer | 找到的相关文档片段总数 |
| `modifications` | array | 每个文档的修改建议详情 |

#### modifications数组元素说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `file_path` | string | 文档路径（MinIO URL） |
| `original_content` | string | 原始文档完整内容 |
| `modified_content` | string | 修改后的文档内容 |
| `diff_summary` | string | 修改摘要（人类可读） |
| `original_length` | integer | 原始文档字符数 |
| `modified_length` | integer | 修改后文档字符数 |
| `evaluation` | object | AI评估结果，包含具体修改点 |
| `react_thinking_process` | array | ReactAgent的思考过程 |
| `react_search_history` | array | ReactAgent的搜索历史 |
| `truncated` | boolean | 是否因内容过长被截断 |

---

## Python调用示例

### 同步调用（requests库）

```python
import requests

# 一致性检查请求
def check_consistency(modification_point: str, 
                     modification_request: str,
                     project_id: str,
                     top_k: int = 15):
    """
    调用一致性检查API
    
    Args:
        modification_point: 修改主题
        modification_request: 具体修改要求
        project_id: 项目ID
        top_k: RAG检索数量
    
    Returns:
        API响应结果
    """
    url = "http://localhost:8000/api/check-consistency"
    
    payload = {
        "modification_point": modification_point,
        "modification_request": modification_request,
        "project_id": project_id,
        "top_k": top_k
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API调用失败: {response.status_code} - {response.text}")

# 使用示例
result = check_consistency(
    modification_point="早季分类",
    modification_request="将所有'早季分类'改为'早期作物分类'，并补充粮食安全说明",
    project_id="my_project",
    top_k=20
)

print(f"成功: {result['success']}")
print(f"找到文档: {result['total_files']} 个")
print(f"修改建议: {len(result['modifications'])} 个")

# 处理修改结果
for mod in result["modifications"]:
    print(f"\n文件: {mod['file_path']}")
    print(f"修改摘要: {mod['diff_summary']}")
    print(f"原始长度: {mod['original_length']} → 修改后: {mod['modified_length']}")
```

### 异步调用（aiohttp库）

```python
import aiohttp
import asyncio

async def check_consistency_async(modification_point: str,
                                  modification_request: str,
                                  project_id: str,
                                  top_k: int = 15):
    """异步调用一致性检查API"""
    url = "http://localhost:8000/api/check-consistency"
    
    payload = {
        "modification_point": modification_point,
        "modification_request": modification_request,
        "project_id": project_id,
        "top_k": top_k
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                text = await response.text()
                raise Exception(f"API调用失败: {response.status} - {text}")

# 使用示例
async def main():
    result = await check_consistency_async(
        modification_point="损失函数",
        modification_request="统一损失函数的数学表达式格式",
        project_id="ml_project",
        top_k=10
    )
    print(f"修改了 {len(result['modifications'])} 个文档")

asyncio.run(main())
```

---

## 作为Agent工具集成

### LangChain工具示例

```python
from langchain.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import requests

class ConsistencyCheckInput(BaseModel):
    """一致性检查工具的输入模型"""
    modification_point: str = Field(description="要修改的主题或概念")
    modification_request: str = Field(description="具体的修改要求")
    project_id: str = Field(description="项目ID")
    top_k: int = Field(default=15, description="RAG检索数量")

class ConsistencyCheckTool(BaseTool):
    """LangChain工具：文档一致性检查"""
    
    name = "consistency_checker"
    description = """
    用于检查和修改多个文档中的内容一致性。
    输入：
    - modification_point: 要修改的主题（如"早季分类"）
    - modification_request: 具体修改要求（如"改为'早期作物分类'"）
    - project_id: 项目ID
    - top_k: 检索相关文档数量（默认15）
    
    输出：包含所有相关文档的修改建议和diff
    """
    args_schema: Type[BaseModel] = ConsistencyCheckInput
    api_url: str = "http://localhost:8000/api/check-consistency"
    
    def _run(self, 
             modification_point: str,
             modification_request: str,
             project_id: str,
             top_k: int = 15) -> str:
        """执行一致性检查"""
        payload = {
            "modification_point": modification_point,
            "modification_request": modification_request,
            "project_id": project_id,
            "top_k": top_k
        }
        
        response = requests.post(self.api_url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            
            # 格式化返回给Agent的结果
            summary = f"一致性检查完成！\n"
            summary += f"- 找到相关文档: {result['total_files']} 个\n"
            summary += f"- 生成修改建议: {len(result['modifications'])} 个\n\n"
            
            for i, mod in enumerate(result['modifications'], 1):
                summary += f"{i}. {mod['file_path'].split('/')[-1]}\n"
                summary += f"   修改摘要: {mod['diff_summary']}\n"
                summary += f"   字符变化: {mod['original_length']} → {mod['modified_length']}\n\n"
            
            return summary
        else:
            return f"API调用失败: {response.status_code} - {response.text}"
    
    async def _arun(self, *args, **kwargs):
        """异步执行（可选）"""
        raise NotImplementedError("暂不支持异步调用")

# 使用示例
from langchain.agents import initialize_agent, AgentType
from langchain.llms import OpenAI

# 创建工具
consistency_tool = ConsistencyCheckTool()

# 集成到Agent
agent = initialize_agent(
    tools=[consistency_tool],
    llm=OpenAI(temperature=0),
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Agent使用工具
result = agent.run(
    "请检查项目中所有关于'早季分类'的文档，将术语统一为'早期作物分类'"
)
print(result)
```

### OpenAI Function Calling示例

```python
import openai
import json
import requests

# 定义Function Schema
consistency_check_function = {
    "name": "check_consistency",
    "description": "检查和修改多个文档中的内容一致性，确保术语、概念、格式等的统一",
    "parameters": {
        "type": "object",
        "properties": {
            "modification_point": {
                "type": "string",
                "description": "要修改的主题或概念，例如：'早季分类'、'损失函数'"
            },
            "modification_request": {
                "type": "string",
                "description": "具体的修改要求，例如：'将所有早季分类改为早期作物分类'"
            },
            "project_id": {
                "type": "string",
                "description": "项目ID，用于定位知识库中的文档"
            },
            "top_k": {
                "type": "integer",
                "description": "RAG检索相关文档的数量",
                "default": 15
            }
        },
        "required": ["modification_point", "modification_request", "project_id"]
    }
}

def execute_consistency_check(modification_point, modification_request, project_id, top_k=15):
    """执行一致性检查的实际函数"""
    url = "http://localhost:8000/api/check-consistency"
    payload = {
        "modification_point": modification_point,
        "modification_request": modification_request,
        "project_id": project_id,
        "top_k": top_k
    }
    response = requests.post(url, json=payload)
    return response.json()

# GPT调用示例
messages = [
    {"role": "system", "content": "你是一个文档管理助手，可以使用工具检查和修改文档一致性。"},
    {"role": "user", "content": "请检查我的机器学习项目中所有关于'损失函数'的文档，确保数学公式格式一致"}
]

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=messages,
    functions=[consistency_check_function],
    function_call="auto"
)

# 处理Function Call
if response.choices[0].message.get("function_call"):
    function_call = response.choices[0].message["function_call"]
    function_args = json.loads(function_call["arguments"])
    
    # 执行工具调用
    result = execute_consistency_check(**function_args)
    
    # 将结果返回给GPT
    messages.append(response.choices[0].message)
    messages.append({
        "role": "function",
        "name": "check_consistency",
        "content": json.dumps(result)
    })
    
    # 获取最终响应
    final_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    
    print(final_response.choices[0].message["content"])
```

---

## 工作流程详解

```
用户请求
   ↓
1. RAG检索相关文档
   - 根据modification_point检索
   - 使用project_id定位知识库
   - 返回top_k个相关文档片段
   ↓
2. 从MinIO读取完整文档
   - 根据检索结果的file_path
   - 下载并读取完整文档内容
   ↓
3. AI评估修改点
   - 分析每个文档中需要修改的位置
   - 提取原文片段
   - 生成修改建议
   ↓
4. ReactAgent生成修改内容
   - 并行处理多个修改点
   - 搜索补充资料（如需要）
   - 生成精确的修改内容
   ↓
5. 应用Diff修改
   - 使用模糊匹配定位原文
   - 替换为修改后内容
   - 去重处理
   ↓
6. 返回结果
   - 包含原文、修改后内容、diff摘要
   - 附带AI思考过程和搜索历史
```

---

## 注意事项

### 1. 前置条件

✅ **必须先上传文档到知识库**

在调用一致性检查前，需要先将文档上传到知识库：

```python
# 上传单个文件
requests.post("http://localhost:8000/api/upload-to-kb", json={
    "minio_url": "minio://bucket/doc.md",
    "project_id": "my_project",
    "enable_vlm": False
})

# 批量上传
requests.post("http://localhost:8000/api/batch-upload-to-kb", json={
    "minio_urls": ["minio://bucket/doc1.md", "minio://bucket/doc2.md"],
    "project_id": "my_project",
    "enable_vlm": False
})
```

### 2. 性能考虑

- **top_k设置**: 建议10-20之间，过大会影响性能
- **并行处理**: 系统会自动并行处理多个文档和修改点
- **超时时间**: 复杂请求可能需要1-3分钟，建议设置合适的HTTP超时

### 3. 错误处理

```python
try:
    result = check_consistency(...)
    if not result['success']:
        print(f"检查失败: {result['message']}")
except requests.exceptions.Timeout:
    print("请求超时，请稍后重试")
except requests.exceptions.RequestException as e:
    print(f"网络错误: {e}")
```

### 4. modification_point的选择

- ✅ **好的例子**: "早季分类"、"损失函数"、"LSTM模型"
- ❌ **不好的例子**: "修改第三章"、"优化内容"、"修复错误"

`modification_point`应该是**语义明确的主题/概念**，而不是操作指令。

### 5. modification_request的编写

```python
# ✅ 好的例子
modification_request = """
1. 将所有'早季分类'统一改为'早期作物分类'
2. 补充说明其在粮食安全中的重要性
3. 更新相关引用格式为APA第7版
"""

# ❌ 不好的例子
modification_request = "改一下"  # 太模糊
```

---

## 其他API接口

### 健康检查

```http
GET /api/health
```

返回：
```json
{"status": "ok"}
```

### 文章生成（可选）

```http
POST /api/generate
```

详见API文档中的ArticleRequest/ArticleResponse模型。

---

## 环境变量配置

使用此API前，需要配置以下环境变量：

```bash
# OpenAI/OpenRouter配置
OPENROUTER_API_KEY=your_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=anthropic/claude-3.5-sonnet

# RAG系统配置
RAG_API_URL=http://your-rag-service/api
RAG_API_KEY=your_rag_key

# MinIO配置
MINIO_ENDPOINT=your-minio-endpoint
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
```

---

## 联系与支持

如有问题，请查看日志或联系开发团队。

API版本: v1.0  
最后更新: 2025-11-27

