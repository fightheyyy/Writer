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
        
        evaluation_prompt = f"""你是一个专业的文档评估专家。请分析以下文档，评估需要修改的点。

修改要求:
{modification_request}
{reference_section}
待评估文件: {file_name}
文件内容:
{original_content}

你的任务是**评估并提取**需要修改的位置：
1. **识别修改点**: 找出文档中哪些章节/段落需要修改
2. **精确提取原文**: 从文档中逐字复制需要修改的原文片段（用于定位）
3. **说明原因**: 解释为什么需要修改这些部分
4. **分类修改**: 说明修改类型（如术语统一、内容补充、观点调整等）

**输出格式**: 使用以下JSON格式：
```json
{{
  "needs_modification": true/false,
  "modification_points": [
    {{
      "location": "清晰的位置描述（如'第1章 Introduction 第一段'）",
      "original_text": "从文档中逐字精确复制的原文片段（完整的段落或句子，用于精确定位）",
      "modification_reason": "为什么需要修改这部分",
      "modification_type": "修改类型"
    }}
  ],
  "overall_guidance": "整体修改指导说明"
}}
```

**关键要求**:
- **original_text必须从文档中逐字精确复制**，包括所有标点符号和空格
- **original_text必须是完整的、连续的内容块**：
  * 如果是一个章节，提取从标题到该章节结束的完整内容
  * 如果是一个段落，提取完整的段落（不能只提取开头或结尾）
  * 如果是多个子章节，提取完整的所有子章节
- **禁止使用省略号（...或…）**，必须提取完整文本
- **禁止只提取标题或开头几句**，必须提取需要修改的完整范围
- 如果某处需要修改的内容太长（超过500行），可以拆分成多个完整的小节
- 不要生成修改后的内容，只提取需要修改的原文
- 如果文档无需修改，设置needs_modification为false

**特别注意**：
- ❌ 错误示例：只提取了标题和开头
  ```
  "original_text": "## 3.3. Loss Function\n\n本节详细阐述..."
  ```
- ✅ 正确示例：提取了完整的章节（包括所有子章节）
  ```
  "original_text": "## 3.3. Loss Function\n\n本节详细阐述...\n\n### 3.3.1. ...\n\n（完整内容）\n\n### 3.3.2. ...\n\n（完整内容）"
  ```

**示例**（正确）:
```json
{{
  "location": "1. Introduction 第一段",
  "original_text": "作物产量预测对保障粮食安全、优化农业生产布局以及制定精准农业政策具有显著的现实意义和应用价值。"
}}
```

**示例**（错误）:
```json
{{
  "location": "1. Introduction 第一段",
  "original_text": "作物产量预测对保障粮食安全...具有显著意义。"  // ❌ 使用了省略号
}}
```

只返回JSON，不要其他说明。如果无法返回JSON，请返回：{{"needs_modification": false, "modification_points": [], "overall_guidance": "无法分析"}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文档评估专家，擅长分析文档并识别需要修改的部分。"},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.3
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
            for idx, point in enumerate(modification_points, 1):
                logger.info(f"  {idx}. [{point.get('location', '未知位置')}] {point.get('modification_type', '未知类型')}")
            
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
        使用ReactAgent为每个修改点搜集资料并生成修改后的片段
        
        流程：
        1. 对每个评估出的修改点
        2. 让ReactAgent搜集相关资料
        3. ReactAgent生成修改后的片段内容
        4. 替换回原文
        
        Args:
            modification_request: 修改要求
            original_content: 原始文档内容
            evaluation: AI评估结果（包含modification_points）
            
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
        agent = ReactAgent(
            max_iterations=3,
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
                
                logger.info(f"🔄 修改点 {idx}/{len(modification_points)}: [{location}] - {modification_type}")
                
                # 构建ReactAgent的搜索和生成任务
                # 简化策略：让ReactAgent只生成修改后的内容，不提取原文
                react_task = f"""根据以下要求，生成修改后的内容片段。

【修改要求】
{modification_request}

【修改位置】
{location}

【修改类型】
{modification_type}

【修改原因】
{modification_reason}

【原文参考】
{original_text_ref}

**任务**：
1. 搜集相关资料来完善修改内容
2. 基于原文和RAG资料，生成修改后的内容

**输出要求**：
- 直接输出修改后的完整内容片段
- 保持原文的格式和结构（如Markdown格式）
- 基于RAG搜索的资料完善修改内容
- 只修改必要的部分，不要大幅改写
- 不要重复输出原文

直接输出修改后的内容片段，不要JSON格式，不要其他说明。"""
                
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
            
            # 🔧 智能检测：如果modified_text比original_text长很多，说明提取不完整
            if len(modified_text) > len(original_text) * 2 and len(modified_text) > 500:
                logger.warning(f"⚠️ 检测到修改点 [{location}] 的original_text可能不完整")
                logger.warning(f"   原文长度: {len(original_text)}, 修改后长度: {len(modified_text)}")
                logger.warning(f"   尝试从文档中扩展提取范围...")
                
                # 尝试智能扩展：找到包含original_text的更大段落
                expanded_text = self._expand_original_text(original_content, original_text)
                if expanded_text and len(expanded_text) > len(original_text):
                    logger.info(f"   ✅ 扩展成功: {len(original_text)} → {len(expanded_text)} 字符")
                    original_text = expanded_text
                    mod["original_text"] = original_text
            
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
            
            # 🚨 防止重复：智能检测重复模式
            
            # 检测1：modified_text 包含 original_text
            if original_text in modified_text and modified_text != original_text:
                if modified_text.startswith(original_text):
                    logger.warning(f"⚠️ 修改 #{idx} [{location}]: 检测到修改内容包含原文（前置）")
                    logger.warning(f"   跳过以防止重复")
                    continue
                elif modified_text.endswith(original_text):
                    logger.warning(f"⚠️ 修改 #{idx} [{location}]: 检测到修改内容包含原文（后置）")
                    logger.warning(f"   跳过以防止重复")
                    continue
            
            # 检测2：检查替换后是否会导致段落重复
            # 提取 modified_text 的前100字符作为特征
            modified_signature = modified_text[:100].strip()
            if modified_signature and modified_signature in result:
                # 检查这个签名是否已经在文档中（不是来自original_text）
                if modified_signature not in original_text:
                    logger.warning(f"⚠️ 修改 #{idx} [{location}]: 修改内容的开头已存在于文档中")
                    logger.warning(f"   特征: {modified_signature[:50]}...")
                    logger.warning(f"   可能导致重复，跳过")
                    continue
            
            # 方法1: 精确匹配
            if original_text in result:
                # 检查替换后是否会导致重复
                temp_result = result.replace(original_text, modified_text, 1)
                
                # 检测是否会产生连续重复的内容
                if modified_text in result and modified_text != original_text:
                    logger.warning(f"⚠️ 修改 #{idx} [{location}]: 修改后的内容已存在于文档中")
                    logger.warning(f"   跳过以防止重复")
                    logger.warning(f"   修改内容: {modified_text[:60]}...")
                    continue
                
                result = temp_result
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
        
        # 🔧 后处理：检测并移除重复的段落
        result = self._remove_duplicate_paragraphs(result)
        
        return result
    
    def _remove_duplicate_paragraphs(self, content: str) -> str:
        """
        检测并移除文档中重复的段落
        
        Args:
            content: 文档内容
            
        Returns:
            去重后的文档内容
        """
        paragraphs = content.split('\n\n')
        seen_paragraphs = {}
        unique_paragraphs = []
        removed_count = 0
        
        for idx, para in enumerate(paragraphs):
            para_normalized = para.strip()
            if not para_normalized:
                unique_paragraphs.append(para)
                continue
            
            # 使用段落的前100字符作为签名
            signature = para_normalized[:100]
            
            if signature in seen_paragraphs:
                # 发现重复段落
                prev_idx = seen_paragraphs[signature]
                logger.warning(f"🔄 检测到重复段落 (位置 {idx} 与 {prev_idx})")
                logger.warning(f"   内容: {signature[:60]}...")
                removed_count += 1
                # 跳过这个重复段落
                continue
            else:
                seen_paragraphs[signature] = idx
                unique_paragraphs.append(para)
        
        if removed_count > 0:
            logger.info(f"✅ 移除了 {removed_count} 个重复段落")
        
        return '\n\n'.join(unique_paragraphs)
    
    def _expand_original_text(self, document: str, partial_text: str) -> str:
        """
        智能扩展原文提取范围
        
        如果AI只提取了章节的开头，尝试提取完整的章节
        
        Args:
            document: 完整文档
            partial_text: 部分提取的原文
            
        Returns:
            扩展后的完整原文
        """
        if not partial_text or partial_text not in document:
            return partial_text
        
        # 找到partial_text在文档中的位置
        start_pos = document.find(partial_text)
        if start_pos == -1:
            return partial_text
        
        # 检测partial_text是否以标题开头（##, ###等）
        if partial_text.startswith('#'):
            # 提取标题级别
            title_level = len(partial_text.split()[0])  # 计算#的数量
            
            # 从start_pos开始，找到下一个同级或更高级的标题
            end_pos = start_pos + len(partial_text)
            remaining_doc = document[end_pos:]
            
            # 查找下一个同级或更高级标题
            lines = remaining_doc.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('#'):
                    # 计算这个标题的级别
                    current_level = len(line.strip().split()[0]) if line.strip().split() else 0
                    if current_level <= title_level:
                        # 找到了同级或更高级标题，在这里截断
                        expanded_text = document[start_pos:end_pos + sum(len(l) + 1 for l in lines[:i])]
                        return expanded_text.strip()
            
            # 如果没找到下一个标题，提取到文档末尾（但限制在5000字符内）
            expanded_text = document[start_pos:start_pos + len(partial_text) + 5000]
            return expanded_text.strip()
        
        # 如果不是标题开头，尝试扩展到段落结束
        end_pos = start_pos + len(partial_text)
        # 找到下一个空行（段落结束）
        next_double_newline = document.find('\n\n', end_pos)
        if next_double_newline != -1 and next_double_newline - start_pos < 3000:
            return document[start_pos:next_double_newline].strip()
        
        return partial_text
    
    def _generate_diff_summary(self, original: str, modified: str) -> str:
        """生成简单的diff摘要"""
        orig_lines = original.split('\n')
        mod_lines = modified.split('\n')
        
        added = len(mod_lines) - len(orig_lines)
        
        # 简单统计变化
        return f"行数变化: {added:+d}，原{len(orig_lines)}行 → 新{len(mod_lines)}行"

