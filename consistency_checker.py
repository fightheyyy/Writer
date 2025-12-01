"""文档一致性检查与修改模块 - 基于外部RAG系统"""
import json
import asyncio
from typing import List, Dict, Set
from pathlib import Path
from openai import AsyncOpenAI
import config
from rag_tool import RAGTool
from knowledge_base import KnowledgeBaseManager
from logger import get_logger

logger = get_logger(__name__)


class ConsistencyChecker:
    """文档一致性检查器 - 利用外部RAG系统"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None, project_id: str = None):
        self.model = model or config.MODEL_NAME
        self.client = AsyncOpenAI(
            api_key=api_key or config.OPENROUTER_API_KEY,
            base_url=base_url or config.OPENROUTER_BASE_URL
        )
        self.rag_tool = RAGTool()
        self.kb_manager = KnowledgeBaseManager()
        self.project_id = project_id  # 保存项目ID，用于ReactAgent
    
    async def find_related_documents(self, 
                                     modification_point: str,
                                     project_id: str,
                                     current_file: str = None,
                                     top_k: int = 10) -> Dict:
        """
        查找与修改点相关的所有文档
        
        Args:
            modification_point: 修改的内容点（如"早季分类"）
            project_id: 项目ID
            current_file: 当前正在修改的文件（可选，用于排除）
            top_k: RAG召回数量
            
        Returns:
            {
                "related_files": {
                    "file_path1": [chunk1, chunk2, ...],
                    "file_path2": [chunk3, ...]
                },
                "total_files": int,
                "total_chunks": int
            }
        """
        logger.info(f"查找与 '{modification_point}' 相关的文档...")
        
        # 调用RAG检索，使用metadata_filter筛选file_chunk
        search_result = await self.rag_tool.search(
            query=modification_point,
            project_id=project_id,
            top_k=top_k,
            use_refine=False,
            metadata_filter={"content_type": "file_chunk"}
        )
        
        if not search_result["success"] or not search_result["data"]:
            logger.warning("RAG检索未返回结果")
            return {
                "related_files": {},
                "total_files": 0,
                "total_chunks": 0
            }
        
        data = search_result["data"]
        
        # RAG返回的数据可能有多种结构，需要灵活处理
        all_chunks = []
        
        # 方式1: 直接的bundles数组（每个bundle包含conversations/facts）
        if data.get("bundles"):
            for bundle in data["bundles"]:
                # 从conversations中提取
                for conv in bundle.get("conversations", []):
                    all_chunks.append({
                        "content": conv.get("text", ""),
                        "score": conv.get("score", 1.0),
                        "metadata": conv.get("metadata", {})
                    })
                
                # 从facts中提取（也可能包含相关信息）
                for fact in bundle.get("facts", []):
                    all_chunks.append({
                        "content": fact.get("content", ""),
                        "score": fact.get("score", 1.0),
                        "metadata": fact.get("metadata", {})
                    })
            
            if all_chunks:
                logger.info(f"从bundles中提取到 {len(all_chunks)} 个chunks")
        
        # 方式2: short_term_memory格式（旧版RAG）
        elif data.get("short_term_memory"):
            short_term_memory = data["short_term_memory"]
            
            # 从conversations提取
            for conv in short_term_memory.get("conversations", []):
                all_chunks.append({
                    "content": conv.get("text", ""),
                    "score": 1.0,
                    "metadata": conv.get("metadata", {})
                })
            
            # 从facts提取
            for fact in short_term_memory.get("facts", []):
                all_chunks.append({
                    "content": fact.get("content", ""),
                    "score": 1.0,
                    "metadata": fact.get("metadata", {})
                })
            
            if all_chunks:
                logger.info(f"从short_term_memory中提取到 {len(all_chunks)} 个chunks")
        
        # 使用提取到的chunks
        bundles = all_chunks
        
        # 按文件路径分组chunks
        related_files = {}
        for i, bundle in enumerate(bundles):
            # 从bundle中提取文件路径和内容
            metadata = bundle.get("metadata", {})
            
            # 尝试多个可能的字段名（不同RAG版本可能使用不同字段）
            file_identifier = (
                metadata.get("file_path") or          # 优先使用file_path
                metadata.get("source_identifier") or  # 其次source_identifier
                metadata.get("minio_url") or          # 然后minio_url
                metadata.get("source") or             # 最后source
                "unknown"
            )
            
            # 调试：输出前2个chunk的metadata
            if i < 2:
                logger.info(f"Chunk {i} - 可用字段: {list(metadata.keys())}")
                logger.info(f"Chunk {i} - 提取的file_identifier: {file_identifier}")
            
            # 跳过无效URL
            if file_identifier == "unknown" or not file_identifier.startswith("http"):
                logger.warning(f"跳过无效的file_identifier: {file_identifier} (metadata keys: {list(metadata.keys())})")
                continue
            
            # 跳过当前正在修改的文件（可选）
            if current_file and file_identifier == current_file:
                continue
            
            if file_identifier not in related_files:
                related_files[file_identifier] = []
            
            related_files[file_identifier].append({
                "content": bundle.get("content", ""),
                "score": bundle.get("score", 0),
                "metadata": metadata
            })
        
        if related_files:
            logger.info(f"文件标识符示例: {list(related_files.keys())[:2]}")
        
        logger.info(f"找到 {len(related_files)} 个相关文档，共 {len(bundles)} 个chunks")
        
        return {
            "related_files": related_files,
            "total_files": len(related_files),
            "total_chunks": len(bundles)
        }
    
    async def analyze_consistency(self,
                                  modification_request: str,
                                  current_file_content: str,
                                  related_files_content: Dict[str, str]) -> Dict:
        """
        分析文档间的一致性，判断哪些文档需要同步修改
        
        Args:
            modification_request: 用户的修改要求
            current_file_content: 当前文件内容（可选，可能为None）
            related_files_content: {file_path: file_content}
            
        Returns:
            {
                "needs_modification": [file_path1, file_path2, ...],
                "modification_type": str,
                "consistency_analysis": str,
                "global_consistency_required": bool
            }
        """
        # 如果没有其他文件，直接返回需要修改
        if not related_files_content:
            return {
                "needs_modification": [],
                "modification_type": "文档修改",
                "consistency_analysis": "未找到相关文档",
                "global_consistency_required": False
            }
        
        # 构建分析prompt
        files_summary = []
        for file_path, content in list(related_files_content.items())[:5]:  # 最多分析5个文件
            # 从路径提取文件名
            file_name = file_path.split('/')[-1] if '/' in file_path else file_path.split('\\')[-1]
            files_summary.append(
                f"文件: {file_name}\n"
                f"内容预览: {content[:300]}...\n"
            )
        
        # 如果提供了当前文件内容，包含在分析中
        current_file_section = ""
        if current_file_content:
            current_file_section = f"""
当前文件内容预览:
{current_file_content[:500]}...
"""
        
        analysis_prompt = f"""你需要分析以下修改需求对文档的影响。

修改要求:
{modification_request}
{current_file_section}
相关文档:
{chr(10).join(files_summary)}

请分析:
1. 根据修改要求，哪些文档需要修改？
2. 修改类型是什么（术语统一/数据更新/方法改进等）？
3. 为什么这些文档需要修改？

以JSON格式返回:
{{
  "needs_modification": ["file1.md", "file2.md"],  // 需要修改的文件列表
  "modification_type": "术语统一/观点调整/数据更新等",
  "consistency_analysis": "详细说明为什么这些文档需要修改",
  "global_consistency_required": true/false
}}

只返回JSON，不要其他内容。"""

        try:
            logger.info("分析文档一致性...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文档一致性分析师。"},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            logger.info(f"一致性分析完成: {json.dumps(analysis, ensure_ascii=False)}")
            return analysis
            
        except Exception as e:
            logger.error(f"分析失败: {str(e)}")
            # 默认所有相关文件都需要修改
            return {
                "needs_modification": list(related_files_content.keys()),
                "modification_type": "一致性修改",
                "consistency_analysis": "默认全部同步修改",
                "global_consistency_required": True
            }
    
    async def generate_modifications(self,
                                    modification_request: str,
                                    current_modification: str,
                                    files_to_modify: Dict[str, str],
                                    project_id: str = None) -> List[Dict]:
        """
        为需要修改的文档生成修改版本
        
        Args:
            modification_request: 修改要求
            current_modification: 当前文件的修改示例
            files_to_modify: {file_path: file_content}
            
        Returns:
            [
                {
                    "file_path": str,
                    "original_content": str,
                    "modified_content": str,
                    "diff_summary": str
                }
            ]
        """
        logger.info(f"🚀 并行处理 {len(files_to_modify)} 个文档的修改...")
        
        # 并行处理所有文档
        tasks = [
            self._modify_single_file(
                modification_request,
                current_modification,
                file_path,
                original_content,
                project_id=project_id or self.project_id
            )
            for file_path, original_content in files_to_modify.items()
        ]
        
        modifications = await asyncio.gather(*tasks)
        
        logger.info(f"✅ {len(modifications)} 个文档处理完成")
        return list(modifications)
    
    async def _modify_single_file(self,
                                  modification_request: str,
                                  current_modification: str,
                                  minio_url: str,
                                  original_content: str,
                                  project_id: str = None) -> Dict:
        """
        修改单个文件 - 新流程：AI评估 → ReactAgent生成 → Diff
        
        流程：
        1. AI评估需要修改的点（不生成具体修改内容）
        2. 将评估结果和原文传给ReactAgent生成修改后的内容
        3. 生成diff
        """
        # 从URL提取文件名
        file_name = minio_url.split('/')[-1] if '/' in minio_url else minio_url
        
        try:
            # ========== 第1步：AI评估需要修改的点 ==========
            logger.info(f"🔍 第1步：AI评估文档修改点: {file_name}")
            evaluation = await self._evaluate_modification_points(
                modification_request,
                current_modification,
                file_name,
                original_content
            )
            
            if not evaluation.get("needs_modification", True):
                logger.info(f"ℹ️ AI认为文档 {file_name} 无需修改")
                return {
                    "file_path": minio_url,
                    "original_content": original_content,
                    "modified_content": original_content,
                    "diff_summary": "无需修改",
                    "original_length": len(original_content),
                    "modified_length": len(original_content),
                    "evaluation": evaluation,
                    "react_thinking_process": [],
                    "react_search_history": [],
                    "truncated": False
                }
            
            # ========== 第2步：调用ReactAgent生成修改后的内容 ==========
            logger.info(f"🤖 第2步：调用ReactAgent生成修改后的内容")
            react_result = await self._generate_with_react_agent(
                modification_request,
                original_content,
                evaluation,
                project_id=project_id or self.project_id
            )
            
            modified_content = react_result.get("content", original_content)
            thinking_process = react_result.get("thinking_process", [])
            search_history = react_result.get("search_history", [])
            
            # ========== 第3步：生成Diff ==========
            logger.info(f"📊 第3步：生成diff")
            diff_summary = f"✅ ReactAgent已生成修改内容"
            
            return {
                "file_path": minio_url,
                "original_content": original_content,
                "modified_content": modified_content,
                "diff_summary": diff_summary,
                "original_length": len(original_content),
                "modified_length": len(modified_content),
                "evaluation": evaluation,
                "react_thinking_process": thinking_process,  # ReactAgent思考过程
                "react_search_history": search_history,  # ReactAgent搜索历史
                "truncated": False
            }
            
        except Exception as e:
            logger.error(f"修改文件失败 {minio_url}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "file_path": minio_url,
                "original_content": original_content,
                "modified_content": original_content,
                "diff_summary": f"修改失败: {str(e)}",
                "original_length": len(original_content),
                "modified_length": len(original_content),
                "evaluation": {},
                "react_thinking_process": [],
                "react_search_history": [],
                "truncated": False
            }
    
    async def _evaluate_modification_points(self,
                                           modification_request: str,
                                           current_modification: str,
                                           file_name: str,
                                           original_content: str) -> Dict:
        """
        AI评估阶段：只评估需要修改的点，不生成具体修改内容
        
        Returns:
            {
                "needs_modification": True/False,
                "modification_points": [
                    {
                        "location": "章节名称或位置",
                        "original_text": "需要修改的原始文本片段",
                        "modification_reason": "为什么需要修改",
                        "modification_type": "修改类型（如术语统一、内容补充等）"
                    }
                ],
                "overall_guidance": "整体修改指导"
            }
        """
        # 构建评估prompt
        reference_section = ""
        if current_modification:
            reference_section = f"""
参考修改示例（保持一致的修改风格）:
{current_modification[:500]}...
"""
        
        evaluation_prompt = f"""你是一个专业的文档评估专家。请**深入分析**以下文档，评估需要修改的点。

修改要求:
{modification_request}
{reference_section}
待评估文件: {file_name}
文件内容:
{original_content}

你的任务是**深度评估并提取**需要修改的位置：

**第一步：深度分析文档**
- 仔细阅读文档，理解其结构、内容和逻辑
- 根据修改要求，识别哪些部分**真正需要修改**
- 不要只看关键词，要理解**修改的目的和意义**

**第二步：评估修改点**
1. **识别修改点**: 找出文档中哪些章节/段落需要修改
   - 对于"术语替换"：不是简单地找包含术语的章节，而是分析替换后对内容的影响
   - 对于"内容补充"：分析哪些部分内容不足，需要补充什么
   - 对于"观点调整"：分析哪些观点与要求不符，如何调整

2. **精确提取原文**: 从文档中提取需要修改的原文片段（用于定位）
   
3. **深度说明原因**: 不要只说"包含XX术语"，而要说明：
   - 这部分为什么需要修改？
   - 修改后会有什么效果？
   - 这个修改对整体文档的价值是什么？
   
4. **分类修改**: 说明修改类型（如术语统一、内容补充、观点调整、逻辑优化等）

**输出格式**: 使用以下JSON格式：
```json
{{
  "needs_modification": true/false,
  "modification_points": [
    {{
      "location": "清晰的位置描述（如'第1章 Introduction 第一段'）",
      "original_text": "从文档中逐字精确复制的原文片段（完整的段落或句子，用于精确定位）",
      "modification_reason": "为什么需要修改这部分",
      "modification_type": "修改类型",
      "is_full_chapter": true/false
    }}
  ],
  "overall_guidance": "整体修改指导说明"
}}
```

**CRITICAL RULES - 按章节提取，严禁重复**:

**核心策略：只提取Markdown标题，系统会自动扩展到完整章节**

1. **original_text提取规则**：
   - ✅ **只提取Markdown标题行**（如 "# 4 Memory Modeling in MemOS"）
   - ✅ 系统会自动扩展到该标题对应的完整章节内容
   - ✅ 支持所有级别的标题：#, ##, ###, ####等
   - ❌ 不要提取完整内容（太长，容易超token限制）
   - ❌ 不要使用省略号

2. **层级互斥原则（重要！防止重复）**：
   - ❌ **禁止同时提取父章节和子章节**
   - 例如：如果提取了 `# 3 Design Philosophy`（父章节），就**不要**再提取 `## 3.1 Vision`、`## 3.2 From OS`（子章节）
   - 原因：父章节包含了所有子章节的内容，重复提取会导致内容重复
   
3. **优先级选择**：
   - 优先选择**顶层章节**（#）：如果整章都需要修改，只提取顶层标题
   - 仅在**部分子章节**需要修改时，才提取子章节（##）
   - 示例：
     * 如果第3章的3.1、3.2都需要修改 → 只提取 `# 3 章节名`
     * 如果只有3.2需要修改，3.1不需要 → 只提取 `## 3.2 小节名`

4. **修改粒度建议**：
   - 对于"术语统一"等全文修改：按**顶层章节**（#）提取，一章一个修改点
   - 对于"局部修改"：按需要修改的**最小章节单位**提取

5. **深度分析要求（重要！）**：
   - ❌ **禁止**简单地说"包含XX术语"、"需要替换XX"这种浅层原因
   - ✅ **必须**深入分析：
     * 这个章节的核心内容是什么？
     * 为什么这部分需要修改？（不是"因为有关键词"，而是"这部分讲了什么，修改后有什么意义"）
     * 修改后对读者理解有什么帮助？
     * 这个修改在整个文档中的价值是什么？
   - ✅ **modification_reason至少要包含**：
     * 章节的主要内容概述
     * 修改的具体原因和目的
     * 修改后的预期效果
   - 示例对比：
     * ❌ 差："章节包含'MemOS'术语，需要替换"
     * ✅ 好："本章介绍了系统架构的三层设计，包括接口层、操作层和基础设施层。标题和正文多处使用'MemOS'术语，需要统一替换为'mem0'以保持品牌一致性。这种替换不仅是文字变更，更体现了系统从概念到产品的演进，ReactAgent需要在保持技术深度的同时，确保新术语自然融入架构说明中。"

**正确示例** ✅（深度分析）:
```json
{{
  "modification_points": [
    {{
      "location": "第3章 Design Philosophy",
      "original_text": "# 3 MemOS Design Philosophy",
      "modification_reason": "本章详细阐述了MemOS的设计理念，包括将记忆视为系统资源、演化作为核心能力等核心思想。章节标题和正文多处使用'MemOS'术语，需要统一替换为'mem0'以保持品牌一致性。同时，这种替换不仅是简单的文字变更，更体现了从'Memory OS'到'mem0'的品牌升级，ReactAgent需要在保持原有技术深度的基础上，确保新术语的自然融入。",
      "modification_type": "术语统一与品牌升级",
      "is_full_chapter": true
    }},
    {{
      "location": "第5.2节 Execution Path",
      "original_text": "## 5.2 Execution Path and Interaction Flow of MemOS",
      "modification_reason": "本节通过具体的执行流程案例（'查询去年的医疗记录'）展示了MemOS各模块的协同工作机制。这是一个关键的技术说明章节，不仅标题包含术语，正文中的架构描述、模块交互说明也大量使用了'MemOS'。需要ReactAgent在替换术语的同时，确保技术描述的准确性和完整性，特别是要保持示例的连贯性和可理解性。",
      "modification_type": "术语统一 + 技术描述优化",
      "is_full_chapter": true
    }}
  ]
}}
```

**错误示例** ❌（重复提取父子章节）:
```json
{{
  "modification_points": [
    {{
      "original_text": "# 3 MemOS Design Philosophy",  // ❌ 提取了父章节
      "is_full_chapter": true
    }},
    {{
      "original_text": "## 3.1 Vision of MemOS",  // ❌ 又提取了子章节，会导致重复！
      "is_full_chapter": true
    }},
    {{
      "original_text": "## 3.2 From Computer OS",  // ❌ 又提取了另一个子章节，会导致重复！
      "is_full_chapter": true
    }}
  ]
}}
```

**正确做法**：上面的情况只需要提取 `# 3 MemOS Design Philosophy` 即可，系统会自动包含3.1、3.2等所有子章节。

**部分修改示例** ✅（只修改某个子章节）:
```json
{{
  "modification_points": [
    {{
      "location": "4.2 Memory Cube",
      "original_text": "## 4.2 Memory Cube as Core Resource",
      "modification_reason": "只有4.2需要修改，4.1不需要",
      "modification_type": "内容补充",
      "is_full_chapter": true
    }}
  ]
}}
```

**段落级修改** ✅（如果确实只需要改一段）:
```json
{{
  "location": "Introduction 第2段",
  "original_text": "MemOS is a revolutionary memory management system designed for large language models.",
  "modification_reason": "该段落包含'MemOS'术语",
  "modification_type": "术语统一",
  "is_full_chapter": false
}}
```

**工作原理**：
1. 你只需提取标题：`"# 4 Memory Modeling in MemOS"`
2. 系统自动检测这是标题（以#开头）
3. 系统自动扩展到完整章节（从这个标题到下一个同级标题之间的所有内容）
4. ReactAgent基于完整章节生成修改后的完整章节
5. 完整替换，不会丢失内容

**建议**：
- 优先使用标题提取方式（最简单、最可靠）
- 一个章节一个modification_point
- 让系统自动处理章节边界

只返回JSON，不要其他说明。如果无法返回JSON，请返回：{{"needs_modification": false, "modification_points": [], "overall_guidance": "无法分析"}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文档评估专家。你需要深入分析文档内容，理解修改的深层目的，而不是简单地搜索关键词。对于章节修改，提取Markdown标题即可（如'# 4 章节名'），但modification_reason必须体现你的深度思考和分析。"},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.3,  # 提高温度，让AI更有创造性分析
                max_tokens=8000
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            # 提取JSON
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_response
            
            evaluation = json.loads(json_str)
            
            modification_points = evaluation.get("modification_points", [])
            logger.info(f"📋 评估结果: 需要修改 {len(modification_points)} 处")
            
            # 🔧 第1步：去除重复的父子章节（防止AI违反规则）
            modification_points = self._deduplicate_hierarchical_chapters(modification_points, original_content)
            logger.info(f"🔄 去重后: {len(modification_points)} 处")
            
            # 🔧 第2步：立即扩展所有修改点的original_text
            for idx, point in enumerate(modification_points, 1):
                location = point.get('location', '未知位置')
                mod_type = point.get('modification_type', '未知类型')
                original_text = point.get('original_text', '')
                is_full_chapter = point.get('is_full_chapter', False)
                
                logger.info(f"  {idx}. [{location}] {mod_type} (原文: {len(original_text)}字符)")
                
                # 如果是标题（is_full_chapter=true），自动扩展到完整章节
                if is_full_chapter and original_text.strip().startswith('#'):
                    logger.info(f"     🔍 检测到章节标题，扩展到完整章节...")
                    expanded = self._expand_original_text(original_content, original_text)
                    if len(expanded) > len(original_text):
                        point['original_text'] = expanded
                        logger.info(f"     ✅ 扩展: {len(original_text)} → {len(expanded)} 字符")
                    else:
                        logger.warning(f"     ⚠️ 扩展失败，保持原样")
            
            # 更新evaluation中的modification_points
            evaluation['modification_points'] = modification_points
            
            return evaluation
            
        except Exception as e:
            logger.error(f"❌ 评估失败: {str(e)}")
            logger.error(f"AI原始响应: {raw_response[:500] if 'raw_response' in locals() else 'N/A'}")
            return {
                "needs_modification": False,
                "modification_points": [],
                "overall_guidance": f"评估失败: {str(e)}"
            }
    
    async def _generate_with_react_agent(self,
                                        modification_request: str,
                                        original_content: str,
                                        evaluation: Dict,
                                        project_id: str = None) -> Dict:
        """
        智能选择修改策略：
        - 简单术语替换 → 直接字符串替换
        - 复杂修改 → ReactAgent搜索+生成
        
        Args:
            modification_request: 修改要求
            original_content: 原始文档内容
            evaluation: AI评估结果（包含modification_points）
            project_id: 项目ID
            
        Returns:
            {
                "content": 修改后的文档内容,
                "thinking_process": ReactAgent思考过程,
                "search_history": ReactAgent搜索历史
            }
        """
        # 导入ReactAgent（延迟导入避免循环依赖）
        from react_agent import ReactAgent
        
        modification_points = evaluation.get("modification_points", [])
        
        # 如果没有具体的修改点，直接返回原文
        if not modification_points:
            logger.warning("评估结果中没有具体修改点，返回原文")
            return {
                "content": original_content,
                "thinking_process": [],
                "search_history": []
            }
        
        # 创建ReactAgent实例
        # max_iterations=5: 允许多次search搜集资料，但generate只能1次
        agent = ReactAgent(
            max_iterations=5,  # ✅ 允许多次搜索资料
            project_id=project_id or self.project_id,
            top_k=10,
            use_refine=False
        )
        
        # 🚀 并行处理所有修改点
        logger.info(f"🚀 并行处理 {len(modification_points)} 个修改点...")
        
        async def process_single_point(idx, point):
            """处理单个修改点"""
            try:
                location = point.get("location", "未知位置")
                original_text_ref = point.get("original_text", "")  # 评估阶段的参考原文
                modification_reason = point.get("modification_reason", "")
                modification_type = point.get("modification_type", "")
                is_full_chapter = point.get("is_full_chapter", False)
                
                # 检查original_text长度
                original_length = len(original_text_ref)
                
                logger.info(f"🔄 修改点 {idx}/{len(modification_points)}: [{location}] - {modification_type}")
                logger.info(f"   原文长度: {original_length} 字符, 完整章节: {is_full_chapter}")
                
                # 根据is_full_chapter和original_length决定生成策略
                if is_full_chapter or original_length > 1000:
                    task_type = "章节重写"
                    length_requirement = f"必须生成与原文等长的完整章节（{original_length}字符左右，允许±10%）"
                    structure_requirement = "保持原章节的所有子章节结构（##、###等）"
                else:
                    task_type = "段落修改"
                    length_requirement = f"保持段落长度（约{original_length}字符）"
                    structure_requirement = "保持段落格式"
                
                # 构建ReactAgent的任务
                react_task = f"""你是一个专业的文档修改助手。请按以下步骤完成任务：

【修改要求】
{modification_request}

【修改位置】{location}

【修改原因与深度分析】
{modification_reason}

【修改类型】{modification_type}

【原文内容】（{original_length}字符）
```
{original_text_ref}
```

【工作流程】

**阶段1：理解修改的深层目的**
- 仔细阅读【修改原因与深度分析】，理解为什么要修改这部分内容
- 这不是简单的文字替换，而是要根据分析中提到的目的和意义进行修改
- 思考：修改后应该达到什么效果？对读者有什么帮助？

**阶段2：搜索资料（如果需要）**
- 如果修改要求是简单的术语替换（如"将MemOS改为mem0"），**不需要搜索**，直接进入阶段3
- 如果修改要求涉及内容补充、扩展、优化，**可以多次搜索**相关资料
- 根据【修改原因与深度分析】中提到的需求，有针对性地搜索
- 搜索策略：
  * 第1次搜索：核心概念和定义
  * 第2次搜索（如需要）：相关技术细节
  * 第3次搜索（如需要）：应用案例或最新研究
- 搜索够了就停止，不要过度搜索

**阶段3：生成修改后的内容（只能1次）**
- 基于原文、【修改原因与深度分析】和搜索到的资料，**一次性**生成完整的修改后内容
- **禁止**生成后再继续迭代或继续生成
- 生成完立即finish

【生成要求】

1. **完整性**：
   - 必须覆盖原文的所有内容（{original_length}字符）
   - {structure_requirement}
   - 不要截断，不要只生成开头部分
   - 一次性生成完整内容

2. **修改准确性**：
   - 根据【修改原因与深度分析】中的深层目的进行修改，而不是简单的文字替换
   - 严格按照修改要求执行（如"MemOS"→"mem0"）
   - 保持原文的结构、逻辑、学术风格
   - 如果【修改原因与深度分析】中提到了特定的修改意义或预期效果，要在生成内容中体现出来
   - 只修改需要改的部分，不要大幅改写

3. **格式规范**：
   - 保留所有Markdown格式
   - 不要添加```代码块标记
   - 直接输出纯文本

4. **长度控制**：
   - 目标长度：{length_requirement}
   - 如果明显偏短，说明内容不完整

【重要】
- 生成时一次性输出完整内容，不要分段生成
- 生成后立即返回finish，不要继续迭代
"""
                
                # 使用ReactAgent生成内容
                result = await agent.run(react_task)
                
                content = result.get("content", "").strip()
                thinking = result.get("thinking_process", [])
                search_history = result.get("search_history", [])
                
                # 直接使用ReactAgent返回的内容作为修改后的文本
                # 使用评估阶段的original_text_ref来定位
                final_modified = content
                final_original = original_text_ref
                
                logger.info(f"✅ 修改点 {idx} 完成")
                logger.info(f"   生成内容长度: {len(final_modified)} 字符")
            
                logger.info(f"✅ 修改点 {idx} 处理完成: 将用于定位的原文长度 {len(final_original)} → 修改后 {len(final_modified)} 字符")
                
                return {
                    "modification": {
                        "location": location,
                        "original_text": final_original,  # 使用评估阶段的original_text_ref
                        "modified_text": final_modified,   # 使用ReactAgent生成的修改后内容
                        "reason": modification_reason,
                        "modification_type": modification_type
                    },
                    "thinking": {
                        "modification_point": idx,
                        "location": location,
                        "thinking_steps": thinking,
                        "generated_length": len(final_modified),
                        "used_react_original": False
                    },
                    "search_history": search_history
                }
            except Exception as e:
                logger.error(f"❌ 修改点 {idx} [{location}] 处理失败: {str(e)}")
                import traceback
                traceback.print_exc()
                # 返回一个默认的结果，保持原文不变
                return {
                    "modification": {
                        "location": location,
                        "original_text": original_text_ref,
                        "modified_text": original_text_ref,  # 保持原样
                        "reason": f"处理失败: {str(e)}",
                        "modification_type": modification_type
                    },
                    "thinking": {
                        "modification_point": idx,
                        "location": location,
                        "thinking_steps": [],
                        "generated_length": len(original_text_ref),
                        "used_react_original": False
                    },
                    "search_history": []
                }
        
        # 并行处理所有修改点
        tasks = [
            process_single_point(idx, point) 
            for idx, point in enumerate(modification_points, 1)
        ]
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        modifications_list = [r["modification"] for r in results]
        all_thinking_process = [r["thinking"] for r in results]
        all_search_history = []
        for r in results:
            all_search_history.extend(r["search_history"])
        
        # 应用所有修改到原文
        logger.info(f"\n📝 应用 {len(modifications_list)} 处修改到原文...")
        modified_content = self._apply_diff_modifications(original_content, modifications_list)
        
        logger.info(f"✅ 所有修改完成")
        logger.info(f"   原文: {len(original_content)} → 修改后: {len(modified_content)} 字符")
        logger.info(f"   变化: {len(modified_content) - len(original_content):+d} 字符")
        
        return {
            "content": modified_content,
            "thinking_process": all_thinking_process,
            "search_history": all_search_history
        }
    
    async def _generate_modifications_with_rag(self,
                                              modification_request: str,
                                              original_content: str,
                                              modification_points: List[Dict],
                                              reference_materials: str) -> List[Dict]:
        """
        基于RAG搜索资料和评估结果，生成具体的修改建议（JSON diff格式）
        
        Args:
            modification_request: 修改要求
            original_content: 原始文档内容
            modification_points: 评估出的修改点列表
            reference_materials: RAG搜索到的参考资料
            
        Returns:
            modifications列表: [{"location": "...", "original_text": "...", "modified_text": "...", "reason": "..."}]
        """
        # 构建修改点摘要
        points_summary = "\n".join([
            f"{idx}. 位置：{point.get('location', '未知')}\n"
            f"   原文片段：{point.get('original_text', '')[:200]}...\n"
            f"   修改原因：{point.get('modification_reason', '')}\n"
            f"   修改类型：{point.get('modification_type', '')}"
            for idx, point in enumerate(modification_points, 1)
        ])
        
        prompt = f"""你需要根据评估结果和参考资料，为文档生成具体的修改建议。

修改要求：
{modification_request}

评估出的修改点：
{points_summary}

参考资料：
{reference_materials if reference_materials else "无"}

原始文档（部分）：
{original_content[:2000]}...

请基于以上信息，为每个修改点生成具体的修改内容。使用JSON格式输出：
```json
{{
  "modifications": [
    {{
      "location": "章节名称或位置描述",
      "original_text": "需要替换的原始文本（从文档中精确复制）",
      "modified_text": "修改后的文本（可以参考RAG资料完善内容）",
      "reason": "修改原因"
    }}
  ]
}}
```

**重要要求**：
1. original_text必须从文档中精确复制，用于定位
2. modified_text应该参考RAG搜索到的资料（如果有）来完善
3. 保持原文的格式和风格
4. 只修改必要的部分，不要大幅改写

只返回JSON，不要其他说明。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文档编辑，擅长基于参考资料生成精确的修改建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )
            
            raw_response = response.choices[0].message.content.strip()
            
            # 提取JSON
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_response
            
            modifications_data = json.loads(json_str)
            modifications_list = modifications_data.get("modifications", [])
            
            logger.info(f"📝 生成了 {len(modifications_list)} 个修改建议")
            for idx, mod in enumerate(modifications_list, 1):
                logger.info(f"  {idx}. [{mod.get('location', '未知')}] {mod.get('reason', '')}")
            
            return modifications_list
            
        except Exception as e:
            logger.error(f"❌ 生成修改建议失败: {str(e)}")
            # 降级方案：直接使用评估点作为修改建议
            return [{
                "location": point.get("location", "未知"),
                "original_text": point.get("original_text", ""),
                "modified_text": point.get("original_text", ""),  # 保持原样
                "reason": f"生成失败，保持原样: {str(e)}"
            } for point in modification_points]
    
    async def read_file_content(self, minio_url: str) -> str:
        """
        读取文件内容（从MinIO）
        
        Args:
            minio_url: MinIO文件URL（来自RAG metadata）
            
        Returns:
            文件内容
        """
        try:
            # 从MinIO读取文件
            content = await self.kb_manager.read_file_from_minio(minio_url)
            
            if content:
                logger.info(f"成功从MinIO读取文件, 长度: {len(content)} 字符")
                return content
            else:
                logger.error(f"从MinIO读取文件失败: {minio_url}")
                return ""
                
        except Exception as e:
            logger.error(f"读取MinIO文件异常 {minio_url}: {str(e)}")
            return ""
    
    def _apply_diff_modifications(self, original_content: str, modifications: list) -> str:
        """
        将JSON格式的修改应用到原文档（智能模糊匹配版本）
        
        Args:
            original_content: 原始文档内容
            modifications: [{"location": "...", "original_text": "...", "modified_text": "...", "reason": "..."}]
            
        Returns:
            修改后的文档内容
        """
        result = original_content
        applied_count = 0
        failed_mods = []
        skipped_duplicates = []
        
        # 标准化文本用于比较
        def normalize_text(text):
            """标准化文本：去除多余空格、统一换行、去除省略号"""
            # 去除省略号
            text = text.replace('...', ' ')
            text = text.replace('…', ' ')
            # 统一空白字符
            text = ' '.join(text.split())
            return text.strip()
        
        def fuzzy_find_in_content(search_text, content, threshold=0.8):
            """
            在内容中模糊查找文本
            
            Args:
                search_text: 要查找的文本（可能不精确）
                content: 内容
                threshold: 相似度阈值
                
            Returns:
                (找到的文本, 起始位置) 或 (None, -1)
            """
            search_normalized = normalize_text(search_text)
            search_words = search_normalized.split()
            
            # 如果search_text太短，直接精确查找
            if len(search_normalized) < 20:
                if search_text in content:
                    return search_text, content.find(search_text)
                return None, -1
            
            # 按段落分割
            paragraphs = content.split('\n\n')
            
            for p_idx, paragraph in enumerate(paragraphs):
                para_normalized = normalize_text(paragraph)
                para_words = para_normalized.split()
                
                # 检查关键词匹配度
                if len(search_words) > 0:
                    # 计算有多少个关键词出现在段落中
                    matched_words = sum(1 for word in search_words if word in para_words)
                    similarity = matched_words / len(search_words)
                    
                    if similarity >= threshold:
                        # 找到匹配的段落
                        return paragraph, content.find(paragraph)
            
            # 尝试按句子查找（处理跨段落的情况）
            sentences = content.replace('\n\n', '\n').split('\n')
            for sent in sentences:
                sent_normalized = normalize_text(sent)
                sent_words = sent_normalized.split()
                
                if len(search_words) > 0:
                    matched_words = sum(1 for word in search_words if word in sent_words)
                    similarity = matched_words / len(search_words)
                    
                    if similarity >= threshold:
                        return sent, content.find(sent)
            
            return None, -1
        
        # 去重 + 智能扩展原文提取
        seen_originals = set()
        deduplicated_mods = []
        for mod in modifications:
            original_text = mod.get("original_text", "").strip()
            modified_text = mod.get("modified_text", "").strip()
            location = mod.get("location", "未知")
            
            # 注意：original_text的扩展已经在评估阶段完成
            # 这里不再需要二次扩展
            
            original_normalized = normalize_text(original_text)
            
            if original_text and original_normalized not in seen_originals:
                seen_originals.add(original_normalized)
                deduplicated_mods.append(mod)
            elif original_text:
                logger.info(f"⚠️ 跳过重复的修改点: {location}")
                logger.info(f"   内容: {original_text[:60]}...")
                skipped_duplicates.append(location)
        
        if skipped_duplicates:
            logger.info(f"🔄 去重: 跳过了 {len(skipped_duplicates)} 个重复的修改点")
        
        # 按顺序应用每个修改
        for idx, mod in enumerate(deduplicated_mods, 1):
            original_text = mod.get("original_text", "").strip()
            modified_text = mod.get("modified_text", "").strip()
            location = mod.get("location", "未指定位置")
            reason = mod.get("reason", "")
            
            if not original_text:
                logger.warning(f"⚠️ 修改 #{idx} [{location}]: 缺少original_text")
                failed_mods.append(f"{location} (缺少原文)")
                continue
            
            # 标准化比较
            original_normalized = normalize_text(original_text)
            modified_normalized = normalize_text(modified_text)
            
            # 检测是否真的有修改
            if original_normalized == modified_normalized:
                logger.info(f"⏭️  修改 #{idx} [{location}]: 内容实质未变化，跳过")
                logger.info(f"   原文: {original_text[:60]}...")
                continue
            
            # 方法1: 精确匹配
            if original_text in result:
                # 直接替换，不需要额外的重复检查
                # 因为我们找到了原文，就应该替换它，不管替换后的内容是什么
                result = result.replace(original_text, modified_text, 1)
                applied_count += 1
                logger.info(f"✅ 修改 #{idx} [{location}] (精确匹配)")
                logger.info(f"   {len(original_text)} 字符 → {len(modified_text)} 字符")
                if reason:
                    logger.info(f"   原因: {reason}")
            else:
                # 方法2: 模糊匹配
                logger.info(f"🔍 尝试模糊匹配修改点 #{idx} [{location}]...")
                found_text, pos = fuzzy_find_in_content(original_text, result, threshold=0.7)
                
                if found_text and pos != -1:
                    # 找到了匹配的文本
                    logger.info(f"✅ 修改 #{idx} [{location}] (模糊匹配，相似度>=70%)")
                    logger.info(f"   找到的文本: {found_text[:80]}...")
                    
                    # 替换找到的文本
                    result = result.replace(found_text, modified_text, 1)
                    applied_count += 1
                    if reason:
                        logger.info(f"   原因: {reason}")
                else:
                    # 方法3: 降低阈值再试一次
                    found_text, pos = fuzzy_find_in_content(original_text, result, threshold=0.5)
                    
                    if found_text and pos != -1:
                        logger.info(f"✅ 修改 #{idx} [{location}] (低相似度匹配，相似度>=50%)")
                        logger.info(f"   找到的文本: {found_text[:80]}...")
                        logger.warning(f"   ⚠️ 注意：此匹配相似度较低，请检查结果")
                        
                        # 替换找到的文本
                        result = result.replace(found_text, modified_text, 1)
                        applied_count += 1
                    else:
                        # 完全无法定位
                        logger.warning(f"❌ 修改 #{idx} [{location}]: 无法定位（即使使用模糊匹配）")
                        logger.warning(f"   查找文本: {original_text[:100]}...")
                        logger.warning(f"   提示：AI提取的原文可能不准确，包含省略号或格式问题")
                        failed_mods.append(location)
        
        logger.info(f"\n📊 修改统计:")
        logger.info(f"   总修改点: {len(modifications)}")
        logger.info(f"   去重后: {len(deduplicated_mods)}")
        logger.info(f"   成功应用: {applied_count}")
        logger.info(f"   失败: {len(failed_mods)}")
        
        if failed_mods:
            logger.warning(f"⚠️ 未应用的修改: {', '.join(failed_mods)}")
        
        return result
    
    def _deduplicate_hierarchical_chapters(self, modification_points: List[Dict], document: str) -> List[Dict]:
        """
        去除重复的父子章节
        
        例如：如果同时有 "# 3 章节" 和 "## 3.1 小节"，只保留父章节
        
        Args:
            modification_points: 修改点列表
            document: 完整文档
            
        Returns:
            去重后的修改点列表
        """
        if not modification_points:
            return modification_points
        
        # 提取每个修改点的标题级别和章节编号
        points_with_meta = []
        for point in modification_points:
            original_text = point.get('original_text', '').strip()
            if not original_text.startswith('#'):
                # 不是标题，保留
                points_with_meta.append({
                    'point': point,
                    'is_title': False,
                    'level': 999,  # 非标题，级别最低
                    'chapter_num': None
                })
                continue
            
            # 提取标题级别（#的数量）
            title_line = original_text.split('\n')[0]
            level = 0
            for char in title_line:
                if char == '#':
                    level += 1
                else:
                    break
            
            # 提取章节编号（如 "3", "3.1", "4.2"）
            # 假设格式为 "# 3 章节名" 或 "## 3.1 小节名"
            import re
            chapter_match = re.search(r'#\s+(\d+(?:\.\d+)*)', title_line)
            chapter_num = chapter_match.group(1) if chapter_match else None
            
            points_with_meta.append({
                'point': point,
                'is_title': True,
                'level': level,
                'chapter_num': chapter_num,
                'title': title_line
            })
        
        # 检测并移除子章节（如果父章节存在）
        to_remove = set()
        for i, meta_i in enumerate(points_with_meta):
            if not meta_i['is_title'] or meta_i['chapter_num'] is None:
                continue
            
            for j, meta_j in enumerate(points_with_meta):
                if i == j or not meta_j['is_title'] or meta_j['chapter_num'] is None:
                    continue
                
                # 检查是否为父子关系
                # 例如：chapter_i="3", chapter_j="3.1" → j是i的子章节
                if (meta_j['level'] > meta_i['level'] and 
                    meta_j['chapter_num'].startswith(meta_i['chapter_num'] + '.')):
                    # meta_j是meta_i的子章节，标记删除
                    to_remove.add(j)
                    logger.warning(f"🔄 检测到父子章节重复:")
                    logger.warning(f"   父章节: {meta_i['title']}")
                    logger.warning(f"   子章节: {meta_j['title']} ← 将被移除（已包含在父章节中）")
        
        # 移除重复的子章节
        deduplicated = [meta['point'] for i, meta in enumerate(points_with_meta) if i not in to_remove]
        
        if to_remove:
            logger.info(f"✅ 移除了 {len(to_remove)} 个重复的子章节")
        
        return deduplicated
    
    def _expand_original_text(self, document: str, partial_text: str) -> str:
        """
        智能扩展原文提取范围
        
        核心功能：将Markdown标题扩展为完整章节内容
        
        Args:
            document: 完整文档
            partial_text: 部分提取的原文（通常是标题）
            
        Returns:
            扩展后的完整章节内容
        """
        if not partial_text:
            return partial_text
        
        partial_text_stripped = partial_text.strip()
        
        # 找到partial_text在文档中的位置（忽略前后空白）
        start_pos = document.find(partial_text_stripped)
        if start_pos == -1:
            # 尝试模糊匹配（去除多余空格）
            import re
            normalized_partial = re.sub(r'\s+', ' ', partial_text_stripped)
            normalized_doc = re.sub(r'\s+', ' ', document)
            start_pos_normalized = normalized_doc.find(normalized_partial)
            if start_pos_normalized != -1:
                # 在原文档中找到对应位置
                # 简化处理：直接使用原始查找
                pass
            else:
                logger.warning(f"⚠️ 无法在文档中找到原文: {partial_text_stripped[:100]}")
                return partial_text
        
        # 检测是否为Markdown标题（以#开头）
        if partial_text_stripped.startswith('#'):
            logger.info(f"🔍 检测到标题，开始扩展到完整章节...")
            
            # 提取标题级别（#的数量）
            title_match = partial_text_stripped.split('\n')[0]  # 只看第一行
            title_level = 0
            for char in title_match:
                if char == '#':
                    title_level += 1
                else:
                    break
            
            logger.info(f"   标题级别: {'#' * title_level} (level {title_level})")
            
            # 从start_pos开始查找这个章节的结束位置
            # 结束位置 = 下一个同级或更高级的标题
            chapter_start = start_pos
            chapter_end = len(document)  # 默认到文档末尾
            
            # 在start_pos之后查找下一个标题
            lines_after = document[start_pos + len(partial_text_stripped):].split('\n')
            chars_accumulated = start_pos + len(partial_text_stripped)
            
            for line in lines_after:
                chars_accumulated += len(line) + 1  # +1 for \n
                
                line_stripped = line.strip()
                if line_stripped.startswith('#'):
                    # 找到一个标题，检查级别
                    current_level = 0
                    for char in line_stripped:
                        if char == '#':
                            current_level += 1
                        else:
                            break
                    
                    # 如果是同级或更高级的标题，这里就是章节结束
                    if current_level <= title_level:
                        chapter_end = chars_accumulated - len(line) - 1  # 回退到这一行之前
                        logger.info(f"   找到下一个同级标题: {'#' * current_level} {line_stripped[:50]}")
                        break
            
            # 提取完整章节
            full_chapter = document[chapter_start:chapter_end].strip()
            
            logger.info(f"   ✅ 扩展成功: {len(partial_text_stripped)} → {len(full_chapter)} 字符")
            logger.info(f"   章节预览: {full_chapter[:100]}...")
            
            return full_chapter
        
        # 如果不是标题，尝试扩展到段落结束
        else:
            end_pos = start_pos + len(partial_text_stripped)
            # 找到下一个双换行（段落结束）
            next_para = document.find('\n\n', end_pos)
            if next_para != -1 and next_para - start_pos < 2000:
                paragraph = document[start_pos:next_para].strip()
                logger.info(f"   扩展段落: {len(partial_text_stripped)} → {len(paragraph)} 字符")
                return paragraph
        
        return partial_text
    
    def _generate_diff_summary(self, original: str, modified: str) -> str:
        """生成简单的diff摘要"""
        orig_lines = original.split('\n')
        mod_lines = modified.split('\n')
        
        added = len(mod_lines) - len(orig_lines)
        
        # 简单统计变化
        return f"行数变化: {added:+d}，原{len(orig_lines)}行 → 新{len(mod_lines)}行"

