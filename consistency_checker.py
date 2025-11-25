"""文档一致性检查与修改模块 - 基于外部RAG系统"""
import json
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
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.model = model or config.MODEL_NAME
        self.client = AsyncOpenAI(
            api_key=api_key or config.OPENROUTER_API_KEY,
            base_url=base_url or config.OPENROUTER_BASE_URL
        )
        self.rag_tool = RAGTool()
        self.kb_manager = KnowledgeBaseManager()
    
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
                                    files_to_modify: Dict[str, str]) -> List[Dict]:
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
        logger.info(f"生成 {len(files_to_modify)} 个文档的修改版本...")
        
        modifications = []
        
        for file_path, original_content in files_to_modify.items():
            modified = await self._modify_single_file(
                modification_request,
                current_modification,
                file_path,
                original_content
            )
            modifications.append(modified)
        
        return modifications
    
    async def _modify_single_file(self,
                                  modification_request: str,
                                  current_modification: str,
                                  minio_url: str,
                                  original_content: str) -> Dict:
        """修改单个文件"""
        
        # 从URL提取文件名
        file_name = minio_url.split('/')[-1] if '/' in minio_url else minio_url
        
        # 构建prompt，如果有参考修改就包含，否则直接根据要求修改
        if current_modification:
            reference_section = f"""
参考修改示例（保持一致的修改风格）:
{current_modification[:500]}...
"""
        else:
            reference_section = ""
        
        # 🚀 统一使用JSON diff格式 - 无token限制，高效精准
        prompt = f"""你需要分析以下文档，找出所有需要修改的地方。

修改要求:
{modification_request}
{reference_section}
待修改文件: {file_name}
文件内容:
{original_content}

要求:
1. **全局分析**: 找出文档中所有与"{modification_request}"相关的内容
2. **精确定位**: 提取需要修改的原始文本片段（必须与文档中的文本完全一致）
3. **完整修改**: 给出修改后的文本
4. **保持格式**: 保留原有的Markdown格式

**输出格式**: 必须使用以下JSON格式：
```json
{{
  "modifications": [
    {{
      "location": "章节名称或位置描述",
      "original_text": "需要替换的原始文本（必须完全匹配）",
      "modified_text": "修改后的文本",
      "reason": "修改原因"
    }}
  ]
}}
```

**重要规则**:
- 只输出需要修改的部分，不要输出整个文档
- original_text必须从文档中精确复制，用于定位和替换
- 如果需要修改多处，列出所有修改项
- 可以提取较长的文本片段以确保唯一性

只返回JSON，不要其他说明。"""

        try:
            logger.info(f"🔍 分析文档修改: {file_name} (原文: {len(original_content)} 字符)")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文档编辑，擅长精确定位和修改文档内容。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # 降低温度，提高精确度
                # 不设置max_tokens，JSON diff格式不会超限
            )
            
            raw_response = response.choices[0].message.content.strip()
            finish_reason = response.choices[0].finish_reason
            
            # 解析JSON diff格式
            try:
                # 提取JSON
                if "```json" in raw_response:
                    json_str = raw_response.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_response:
                    json_str = raw_response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = raw_response
                
                modifications_data = json.loads(json_str)
                modifications_list = modifications_data.get("modifications", [])
                
                if not modifications_list:
                    logger.info(f"ℹ️ AI认为文档 {file_name} 无需修改")
                    modified_content = original_content
                    diff_summary = "无需修改"
                else:
                    # 应用所有修改到原文档
                    modified_content = self._apply_diff_modifications(
                        original_content, 
                        modifications_list
                    )
                    
                    diff_summary = f"✅ 应用了 {len(modifications_list)} 处修改"
                    logger.info(f"✅ 修改完成: {file_name}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON解析失败: {str(e)}")
                logger.error(f"原始响应: {raw_response[:500]}...")
                modified_content = original_content
                diff_summary = f"❌ JSON解析失败，文档未修改"
            except Exception as e:
                logger.error(f"❌ 应用修改失败: {str(e)}")
                modified_content = original_content
                diff_summary = f"❌ 修改应用失败: {str(e)}"
            
            return {
                "file_path": minio_url,
                "original_content": original_content,
                "modified_content": modified_content,
                "diff_summary": diff_summary,
                "original_length": len(original_content),
                "modified_length": len(modified_content),
                "truncated": False  # JSON diff模式不会被截断
            }
            
        except Exception as e:
            logger.error(f"修改文件失败 {minio_url}: {str(e)}")
            return {
                "file_path": minio_url,
                "original_content": original_content,
                "modified_content": original_content,  # 保持原样
                "diff_summary": f"修改失败: {str(e)}",
                "error": str(e)
            }
    
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
        将JSON格式的修改应用到原文档
        
        Args:
            original_content: 原始文档内容
            modifications: [{"location": "...", "original_text": "...", "modified_text": "...", "reason": "..."}]
            
        Returns:
            修改后的文档内容
        """
        result = original_content
        applied_count = 0
        failed_mods = []
        
        # 按顺序应用每个修改
        for idx, mod in enumerate(modifications, 1):
            original_text = mod.get("original_text", "")
            modified_text = mod.get("modified_text", "")
            location = mod.get("location", "未指定位置")
            reason = mod.get("reason", "")
            
            if not original_text:
                logger.warning(f"⚠️ 修改 #{idx} [{location}]: 缺少original_text")
                failed_mods.append(f"{location} (缺少原文)")
                continue
            
            if original_text in result:
                # 替换第一次出现
                result = result.replace(original_text, modified_text, 1)
                applied_count += 1
                logger.info(f"✅ 修改 #{idx} [{location}]: {original_text[:40]}... → {modified_text[:40]}...")
                if reason:
                    logger.info(f"   原因: {reason}")
            else:
                logger.warning(f"❌ 修改 #{idx} [{location}]: 无法定位")
                logger.warning(f"   查找文本: {original_text[:100]}...")
                failed_mods.append(location)
        
        logger.info(f"📊 修改统计: 成功 {applied_count}/{len(modifications)}")
        if failed_mods:
            logger.warning(f"⚠️ 未应用的修改: {', '.join(failed_mods)}")
        
        return result
    
    def _generate_diff_summary(self, original: str, modified: str) -> str:
        """生成简单的diff摘要"""
        orig_lines = original.split('\n')
        mod_lines = modified.split('\n')
        
        added = len(mod_lines) - len(orig_lines)
        
        # 简单统计变化
        return f"行数变化: {added:+d}，原{len(orig_lines)}行 → 新{len(mod_lines)}行"

