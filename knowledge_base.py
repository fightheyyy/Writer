"""知识库管理模块 - 文件上传和内容读取"""
import httpx
import json
from typing import Dict, List, Optional, Optional
from pathlib import Path
import config
from logger import get_logger

logger = get_logger(__name__)


class KnowledgeBaseManager:
    """知识库管理器"""
    
    def __init__(self):
        self.process_url = config.KB_PROCESS_URL
        self.search_url = "http://localhost:1234/search"
        self.cache_dir = Path(config.KB_CACHE_DIR)
    
    async def upload_to_knowledge_base(self, 
                                      minio_url: str,
                                      project_id: str,
                                      enable_vlm: bool = False) -> Dict:
        """
        上传文件到知识库
        
        Args:
            minio_url: MinIO文件URL
            project_id: 项目ID
            enable_vlm: 是否启用VLM
            
        Returns:
            上传结果
        """
        try:
            payload = {
                "minio_url": minio_url,
                "project_id": project_id,
                "enable_vlm": enable_vlm
            }
            
            logger.info(f"=== 上传文件到知识库 ===")
            logger.info(f"目标地址: {self.process_url}")
            logger.info(f"MinIO URL: {minio_url}")
            logger.info(f"Project ID: {project_id}")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.process_url,
                    json=payload
                )
                
                # 记录响应信息
                logger.info(f"响应状态码: {response.status_code}")
                logger.info(f"响应内容长度: {len(response.content)} 字节")
                
                # 检查HTTP状态
                if response.status_code != 200:
                    logger.error(f"HTTP错误: {response.status_code}")
                    logger.error(f"响应内容: {response.text[:500]}")
                    return {
                        "success": False,
                        "minio_url": minio_url,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                
                # 尝试解析JSON
                try:
                    result = response.json()
                except json.JSONDecodeError as je:
                    logger.error(f"JSON解析失败: {str(je)}")
                    logger.error(f"响应内容: {response.text[:500]}")
                    return {
                        "success": False,
                        "minio_url": minio_url,
                        "error": f"知识库返回非JSON响应: {response.text[:200]}"
                    }
                
                logger.info(f"=== 上传成功 ===")
                logger.info(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 提取本地缓存路径（如果返回了）
                file_path = result.get("file_path") or result.get("local_path")
                if file_path:
                    logger.info(f"文件已缓存到: {file_path}")
                
                return {
                    "success": True,
                    "minio_url": minio_url,
                    "file_path": file_path,
                    "result": result
                }
                
        except httpx.ConnectError as e:
            logger.error(f"=== 连接知识库服务失败 ===")
            logger.error(f"目标地址: {self.process_url}")
            logger.error(f"错误: {str(e)}")
            return {
                "success": False,
                "minio_url": minio_url,
                "error": f"无法连接到知识库服务 ({self.process_url}): {str(e)}"
            }
        except httpx.TimeoutException as e:
            logger.error(f"=== 上传超时 ===")
            logger.error(f"错误: {str(e)}")
            return {
                "success": False,
                "minio_url": minio_url,
                "error": f"上传超时（120秒）: {str(e)}"
            }
        except httpx.HTTPError as e:
            logger.error(f"=== 上传失败 (HTTP错误) ===")
            logger.error(f"错误: {str(e)}")
            return {
                "success": False,
                "minio_url": minio_url,
                "error": f"HTTP错误: {str(e)}"
            }
        except Exception as e:
            logger.error(f"=== 上传失败 (未知错误) ===")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误: {str(e)}")
            import traceback
            logger.error(f"堆栈: {traceback.format_exc()}")
            return {
                "success": False,
                "minio_url": minio_url,
                "error": f"未知错误 ({type(e).__name__}): {str(e)}"
            }
    
    async def batch_upload_files_to_kb(self,
                                       minio_urls: List[str],
                                       project_id: str,
                                       enable_vlm: bool = False) -> List[Dict]:
        """
        批量上传文件到知识库
        
        Args:
            minio_urls: MinIO文件URL列表
            project_id: 项目ID
            enable_vlm: 是否启用VLM
            
        Returns:
            上传结果列表
        """
        logger.info(f"=== 批量上传 {len(minio_urls)} 个文件到知识库 ===")
        
        results = []
        for i, minio_url in enumerate(minio_urls, 1):
            logger.info(f"上传进度: {i}/{len(minio_urls)}")
            result = await self.upload_to_knowledge_base(
                minio_url=minio_url,
                project_id=project_id,
                enable_vlm=enable_vlm
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"=== 批量上传完成: {success_count}/{len(minio_urls)} 成功 ===")
        
        return results
    
    async def read_file_from_minio(self, minio_url: str) -> Optional[str]:
        """
        从MinIO读取文件内容
        
        Args:
            minio_url: MinIO文件URL
            
        Returns:
            文件内容（文本）或 None
        """
        try:
            logger.info(f"从MinIO读取文件: {minio_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(minio_url)
                response.raise_for_status()
                
                # 假设是文本文件（MD）
                content = response.text
                
                logger.info(f"文件读取成功，长度: {len(content)} 字符")
                return content
                
        except httpx.HTTPError as e:
            logger.error(f"从MinIO读取文件失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"读取文件时发生错误: {str(e)}")
            return None
    
    async def batch_upload_files(self, 
                                 minio_urls: list,
                                 project_id: str,
                                 enable_vlm: bool = False) -> Dict:
        """
        批量上传文件到知识库
        
        Args:
            minio_urls: MinIO文件URL列表
            project_id: 项目ID
            enable_vlm: 是否启用VLM
            
        Returns:
            批量上传结果
        """
        results = []
        success_count = 0
        
        logger.info(f"=== 批量上传 {len(minio_urls)} 个文件 ===")
        
        for i, minio_url in enumerate(minio_urls, 1):
            logger.info(f"上传进度: {i}/{len(minio_urls)}")
            
            result = await self.upload_to_knowledge_base(
                minio_url=minio_url,
                project_id=project_id,
                enable_vlm=enable_vlm
            )
            
            results.append(result)
            if result["success"]:
                success_count += 1
        
        logger.info(f"=== 批量上传完成: {success_count}/{len(minio_urls)} 成功 ===")
        
        return {
            "success": success_count == len(minio_urls),
            "total": len(minio_urls),
            "success_count": success_count,
            "failed_count": len(minio_urls) - success_count,
            "results": results
        }

