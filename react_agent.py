import json
from typing import List, Dict
from rag_tool import RAGTool
from openai import AsyncOpenAI
import config
from logger import get_logger

logger = get_logger(__name__)


class ReactAgent:
    """
    ReAct Agent 用于搜索资料和生成文章
    """
    
    def __init__(self, max_iterations: int = None, api_key: str = None, base_url: str = None, model: str = None, 
                 project_id: str = None, top_k: int = None, use_refine: bool = None):
        self.max_iterations = max_iterations or config.MAX_ITERATIONS
        self.rag_tool = RAGTool(
            project_id=project_id or config.RAG_PROJECT_ID,
            top_k=top_k or config.RAG_TOP_K,
            use_refine=use_refine if use_refine is not None else config.RAG_USE_REFINE
        )
        self.search_history = []
        self.thinking_process = []  # 记录思考过程
        self.model = model or config.MODEL_NAME
        
        # 初始化 OpenRouter 客户端
        self.client = AsyncOpenAI(
            api_key=api_key or config.OPENROUTER_API_KEY,
            base_url=base_url or config.OPENROUTER_BASE_URL
        )
    
    async def run(self, user_request: str) -> Dict:
        """
        运行 ReAct Agent - 生成模式
        
        Args:
            user_request: 用户请求的主题
            
        Returns:
            生成的文章内容和搜索历史
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"ReAct Agent 启动 - 生成模式")
        logger.info(f"用户请求: {user_request}")
        logger.info(f"{'='*60}\n")
        
        article_parts = []
        context = ""
        first_search_done = False
        
        for iteration in range(self.max_iterations):
            logger.info(f"\n--- 第 {iteration + 1} 轮迭代 ---")
            
            # 思考下一步行动
            action = await self._think(user_request, context, article_parts)
            
            logger.info(f"决策结果: {json.dumps(action, ensure_ascii=False, indent=2)}")
            
            # 记录思考过程
            self.thinking_process.append({
                "iteration": iteration + 1,
                "action": action
            })
            
            if action["type"] == "search":
                # 执行搜索
                logger.info(f"执行搜索: {action['query']}")
                search_result = await self.rag_tool.search(action["query"])
                
                # 检查是否真的有内容（bundles不为空）
                has_content = False
                if search_result["success"] and search_result["data"]:
                    bundles = search_result["data"].get("bundles", [])
                    total_bundles = search_result["data"].get("total_bundles", 0)
                    has_content = len(bundles) > 0 or total_bundles > 0
                
                self.search_history.append({
                    "iteration": iteration + 1,
                    "query": action["query"],
                    "success": search_result["success"],
                    "has_content": has_content
                })
                
                if has_content:
                    context += f"\n\n搜索结果 ({action['query']}):\n{json.dumps(search_result['data'], ensure_ascii=False)}\n"
                    logger.info(f"搜索成功，已更新上下文（bundles: {len(bundles)}）")
                else:
                    logger.warning(f"搜索返回为空（bundles: 0）")
                
                # 第一次搜索后检查是否获得资料
                if not first_search_done:
                    first_search_done = True
                    if not has_content:
                        logger.info("第一次搜索无结果，知识库为空，直接使用大模型知识生成文章")
                        article_part = await self._generate_content_without_rag(user_request)
                        article_parts.append(article_part)
                        logger.info(f"文章已生成（无RAG），长度: {len(article_part)} 字符")
                        break
            
            elif action["type"] == "generate":
                # 生成文章片段
                logger.info(f"生成文章片段...")
                article_part = await self._generate_content(user_request, context, action.get("instruction", ""))
                article_parts.append(article_part)
                logger.info(f"文章片段已生成，长度: {len(article_part)} 字符")
            
            elif action["type"] == "finish":
                # 完成生成
                logger.info("任务完成，结束迭代")
                break
        
        # 合并所有文章片段
        final_content = "\n\n".join(article_parts)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"ReAct Agent 完成")
        logger.info(f"最终文章长度: {len(final_content)} 字符")
        logger.info(f"搜索次数: {len(self.search_history)}")
        logger.info(f"{'='*60}\n")
        
        return {
            "content": final_content,
            "search_history": self.search_history,
            "thinking_process": self.thinking_process
        }
    
    async def run_edit(self, user_request: str, original_content: str) -> Dict:
        """
        运行 ReAct Agent - 编辑模式
        
        Args:
            user_request: 用户的修改要求
            original_content: 原始文章内容
            
        Returns:
            修改后的文章内容和搜索历史
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"ReAct Agent 启动 - 编辑模式")
        logger.info(f"修改要求: {user_request}")
        logger.info(f"原文长度: {len(original_content)} 字符")
        logger.info(f"{'='*60}\n")
        
        context = ""
        has_rag_data = False
        
        # 搜索相关资料来辅助修改
        for iteration in range(min(2, self.max_iterations)):
            logger.info(f"搜索辅助资料 (第 {iteration + 1} 次)...")
            
            # 记录思考过程：搜索
            self.thinking_process.append({
                "iteration": iteration + 1,
                "action": {
                    "type": "search",
                    "query": user_request,
                    "reason": "搜索相关资料以辅助文章修改"
                }
            })
            
            search_result = await self.rag_tool.search(user_request)
            
            # 检查是否真的有内容
            if search_result["success"] and search_result["data"]:
                bundles = search_result["data"].get("bundles", [])
                total_bundles = search_result["data"].get("total_bundles", 0)
                has_content = len(bundles) > 0 or total_bundles > 0
                
                self.search_history.append({
                    "iteration": iteration + 1,
                    "query": user_request,
                    "success": search_result["success"],
                    "has_content": has_content
                })
                
                if has_content:
                    context += f"\n\n搜索结果:\n{json.dumps(search_result['data'], ensure_ascii=False)}\n"
                    logger.info("搜索成功，已获取辅助资料")
                    has_rag_data = True
                    break
                else:
                    logger.info("搜索返回为空，知识库无相关资料")
            else:
                self.search_history.append({
                    "iteration": iteration + 1,
                    "query": user_request,
                    "success": False,
                    "has_content": False
                })
                logger.warning("搜索失败")
        
        # 记录思考过程：编辑
        self.thinking_process.append({
            "iteration": len(self.thinking_process) + 1,
            "action": {
                "type": "generate",
                "instruction": "根据用户要求编辑文章" + ("（使用RAG资料）" if has_rag_data else "（仅使用LLM知识）"),
                "reason": f"开始编辑，{'已获取' if has_rag_data else '未获取'}到辅助资料"
            }
        })
        
        # 基于原文和搜索结果进行编辑
        logger.info(f"开始编辑文章...（{'使用RAG资料' if has_rag_data else '仅使用LLM知识'}）")
        edited_content = await self._edit_content(user_request, original_content, context)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"编辑完成")
        logger.info(f"修改后长度: {len(edited_content)} 字符")
        logger.info(f"{'='*60}\n")
        
        return {
            "content": edited_content,
            "search_history": self.search_history,
            "thinking_process": self.thinking_process
        }
    
    async def _think(self, user_request: str, context: str, article_parts: List[str]) -> Dict:
        """
        思考下一步行动
        
        Returns:
            行动字典，包含 type 和相关参数
            type 可以是: "search", "generate", "finish"
        """
        prompt = f"""你是一个智能写作助手。你需要根据用户请求和已有的信息，决定下一步行动。

用户请求: {user_request}

已搜集的资料:
{context if context else "暂无资料"}

已生成的文章部分:
{chr(10).join(article_parts) if article_parts else "暂无"}

你可以选择以下行动之一:
1. search: 搜索更多资料 (如果资料不足)
2. generate: 生成文章片段 (如果有足够资料)
3. finish: 完成任务 (如果文章已经完整)

请以 JSON 格式返回你的决定:
- 如果选择 search: {{"type": "search", "query": "搜索关键词", "reason": "为什么要搜索"}}
- 如果选择 generate: {{"type": "generate", "instruction": "生成指导", "reason": "为什么现在生成"}}
- 如果选择 finish: {{"type": "finish", "reason": "为什么结束"}}

只返回 JSON，不要其他内容。"""

        try:
            logger.info("调用 LLM 进行思考...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的写作助手，擅长规划和决策。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"LLM 原始响应:\n{content}")
            
            # 尝试提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            action = json.loads(content)
            logger.info(f"解析后的决策: {json.dumps(action, ensure_ascii=False)}")
            return action
            
        except Exception as e:
            logger.error(f"LLM 调用失败: {str(e)}")
            logger.info("使用简单策略作为后备")
            # 如果 LLM 调用失败，使用简单策略
            if not context:
                return {"type": "search", "query": user_request, "reason": "初始搜索"}
            elif len(article_parts) == 0:
                return {"type": "generate", "instruction": "根据已有资料生成文章", "reason": "开始写作"}
            else:
                return {"type": "finish", "reason": "已完成"}
    
    async def _generate_content(self, user_request: str, context: str, instruction: str) -> str:
        """
        根据上下文生成文章内容
        """
        prompt = f"""基于以下资料，生成关于"{user_request}"的文章内容。

资料:
{context}

生成指导: {instruction if instruction else "请生成高质量、有深度的文章内容"}

要求:
1. 内容准确、有深度
2. 逻辑清晰、结构合理
3. 引用资料中的关键信息
4. 使用中文撰写

直接返回文章内容，不要其他说明。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的内容创作者，擅长撰写高质量文章。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"生成内容时出错: {str(e)}"
    
    async def _edit_content(self, user_request: str, original_content: str, context: str) -> str:
        """
        根据用户要求编辑文章内容 - 全文一致性修改
        """
        # 第一步：分析需要修改的地方
        analysis_prompt = f"""请仔细分析以下文章，找出所有需要根据用户要求进行修改的地方。

原始文章:
{original_content}

用户修改要求:
{user_request}

参考资料:
{context if context else "无"}

请以JSON格式输出分析结果：
{{
  "modification_type": "修改类型（如：术语替换、观点转变、数据更新、立场调整等）",
  "affected_sections": [
    {{"section": "段落/章节描述", "reason": "需要修改的原因"}},
    ...
  ],
  "consistency_requirements": "全文一致性要求说明"
}}

只返回JSON，不要其他内容。"""

        try:
            logger.info("第一步：分析全文需要修改的位置...")
            analysis_response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文章分析师，擅长识别文章中需要修改的所有相关位置。"},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            analysis_content = analysis_response.choices[0].message.content.strip()
            
            # 提取JSON
            if "```json" in analysis_content:
                analysis_content = analysis_content.split("```json")[1].split("```")[0].strip()
            elif "```" in analysis_content:
                analysis_content = analysis_content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(analysis_content)
            logger.info(f"分析完成: {json.dumps(analysis, ensure_ascii=False, indent=2)}")
            
        except Exception as e:
            logger.warning(f"分析阶段出错，使用基础模式: {str(e)}")
            analysis = None
        
        # 第二步：执行全文一致性修改
        edit_prompt = f"""你需要对以下文章进行全文一致性修改。

原始文章:
{original_content}

用户修改要求:
{user_request}

参考资料:
{context if context else "无"}

"""
        if analysis:
            edit_prompt += f"""
分析结果:
- 修改类型: {analysis.get('modification_type', '')}
- 受影响的部分: {len(analysis.get('affected_sections', []))} 处
- 一致性要求: {analysis.get('consistency_requirements', '')}

"""
        
        edit_prompt += """关键要求：
1. **全文一致性**：确保所有相关的段落、观点、数据、引用都保持一致地修改
2. **逻辑连贯**：修改后的内容在全文中逻辑自洽，不能出现矛盾
3. **完整性**：不要遗漏任何需要修改的地方
4. **风格保持**：保持原文的写作风格和结构
5. **使用中文**：所有内容使用中文

请仔细检查全文，确保没有遗漏任何需要修改的地方，直接返回修改后的完整文章，不要其他说明。"""

        try:
            logger.info("第二步：执行全文一致性修改...")
            
            # 根据原文长度动态调整 max_tokens
            estimated_tokens = len(original_content) // 2  # 粗略估计
            max_tokens = min(8000, max(4000, estimated_tokens + 1000))
            logger.info(f"原文长度: {len(original_content)} 字符，设置 max_tokens: {max_tokens}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文章编辑，擅长全文一致性修改，确保所有相关位置都被正确修改且逻辑连贯。"},
                    {"role": "user", "content": edit_prompt}
                ],
                temperature=0.7,
                max_tokens=max_tokens
            )
            
            edited_content = response.choices[0].message.content.strip()
            logger.info(f"修改完成，修改后长度: {len(edited_content)} 字符")
            return edited_content
            
        except Exception as e:
            logger.error(f"编辑内容时出错: {str(e)}")
            return f"编辑内容时出错: {str(e)}"
    
    async def _generate_content_without_rag(self, user_request: str) -> str:
        """
        不使用 RAG 资料，直接用大模型知识生成文章
        """
        prompt = f"""请根据以下主题，使用你自身的知识撰写一篇高质量的文章。

主题: {user_request}

要求:
1. 内容准确、有深度
2. 逻辑清晰、结构合理
3. 使用中文撰写
4. 包含引言、主体和结论

直接返回文章内容，不要其他说明。"""

        try:
            logger.info("使用大模型自身知识生成文章（无RAG资料）")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的内容创作者，擅长撰写高质量文章。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=3000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"生成内容时出错: {str(e)}")
            return f"生成内容时出错: {str(e)}"

