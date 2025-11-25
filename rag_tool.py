import httpx
import json
from typing import List, Dict
from logger import get_logger

logger = get_logger(__name__)


class RAGTool:
    """RAG 搜索工具"""
    
    def __init__(self, project_id: str = "default", top_k: int = 5, use_refine: bool = True):
        self.search_url = "http://localhost:1234/search"
        self.project_id = project_id
        self.top_k = top_k
        self.use_refine = use_refine
    
    async def search(self, query: str, project_id: str = None, top_k: int = None, 
                    use_refine: bool = None, metadata_filter: Dict = None) -> Dict:
        """
        调用 RAG 搜索接口
        
        Args:
            query: 搜索查询字符串
            project_id: 项目ID（可选，使用初始化时的默认值）
            top_k: 返回结果数量（可选，使用初始化时的默认值）
            use_refine: 是否使用精炼（可选，使用初始化时的默认值）
            metadata_filter: 元数据过滤条件（如 {"content_type": "file_chunk"}）
            
        Returns:
            搜索结果字典
        """
        try:
            payload = {
                "query": query,
                "project_id": project_id or self.project_id,
                "top_k": top_k or self.top_k,
                "use_refine": use_refine if use_refine is not None else self.use_refine
            }
            
            # 添加 metadata_filter（如果提供）
            if metadata_filter:
                payload["metadata_filter"] = metadata_filter
            
            logger.info(f"=== RAG 搜索请求 ===")
            logger.info(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.search_url,
                    json=payload
                )
                response.raise_for_status()
                result_data = response.json()
                
                logger.info(f"=== RAG 搜索成功 ===")
                logger.info(f"返回结果: {json.dumps(result_data, ensure_ascii=False, indent=2)}")
                
                return {
                    "success": True,
                    "query": query,
                    "data": result_data
                }
        except httpx.HTTPError as e:
            logger.error(f"=== RAG 搜索失败 (HTTP错误) ===")
            logger.error(f"错误信息: {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "data": None
            }
        except Exception as e:
            logger.error(f"=== RAG 搜索失败 (未知错误) ===")
            logger.error(f"错误信息: {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": f"Unexpected error: {str(e)}",
                "data": None
            }

