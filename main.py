from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict
from react_agent import ReactAgent
from logger import get_logger
from consistency_checker import ConsistencyChecker
from knowledge_base import KnowledgeBaseManager

logger = get_logger(__name__)

app = FastAPI(title="ReAct Article Generator")

# 创建API路由器（所有API都挂载在 /api 下）
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")

# 初始化一致性检查器和知识库管理器
consistency_checker = ConsistencyChecker()
kb_manager = KnowledgeBaseManager()

# CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ArticleRequest(BaseModel):
    query: str
    original_content: Optional[str] = None
    max_iterations: int = 5
    mode: str = "generate"  # "generate" 或 "edit"
    project_id: Optional[str] = None
    top_k: Optional[int] = None
    use_refine: Optional[bool] = None


class ArticleResponse(BaseModel):
    content: str
    search_history: list
    thinking_process: list
    mode: str


@api_router.post("/generate", response_model=ArticleResponse)
async def generate_article(request: ArticleRequest):
    """
    生成或编辑文章
    - mode="generate": 纯生成模式，根据 query 生成新文章
    - mode="edit": 编辑模式，基于 original_content 和 query 修改文章
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"收到新请求")
    logger.info(f"模式: {request.mode}")
    logger.info(f"Query: {request.query}")
    logger.info(f"Project ID: {request.project_id}")
    logger.info(f"Top K: {request.top_k}")
    logger.info(f"Use Refine: {request.use_refine}")
    logger.info(f"{'#'*80}\n")
    
    agent = ReactAgent(
        max_iterations=request.max_iterations,
        project_id=request.project_id,
        top_k=request.top_k,
        use_refine=request.use_refine
    )
    
    if request.mode == "edit" and request.original_content:
        # 编辑模式：基于原文修改
        result = await agent.run_edit(request.query, request.original_content)
    else:
        # 生成模式：纯生成
        result = await agent.run(request.query)
    
    logger.info(f"\n{'#'*80}")
    logger.info(f"请求处理完成")
    logger.info(f"{'#'*80}\n")
    
    return ArticleResponse(
        content=result["content"],
        search_history=result["search_history"],
        thinking_process=result.get("thinking_process", []),
        mode=request.mode
    )


@api_router.get("/health")
async def health_check():
    return {"status": "ok"}


# ============ 知识库上传API ============

class UploadRequest(BaseModel):
    minio_url: str
    project_id: str
    enable_vlm: bool = False


class BatchUploadRequest(BaseModel):
    minio_urls: List[str]
    project_id: str
    enable_vlm: bool = False


class UploadResponse(BaseModel):
    success: bool
    message: str
    success_count: int = 0
    total: int = 0
    results: List[Dict] = []


@api_router.post("/upload-to-kb")
async def upload_to_knowledge_base(request: UploadRequest):
    """
    上传单个文件到知识库
    """
    logger.info(f"上传文件到知识库: {request.minio_url}")
    
    try:
        result = await kb_manager.upload_to_knowledge_base(
            minio_url=request.minio_url,
            project_id=request.project_id,
            enable_vlm=request.enable_vlm
        )
        
        if result.get("success"):
            return UploadResponse(
                success=True,
                message="上传成功",
                success_count=1,
                total=1,
                results=[result]
            )
        else:
            return UploadResponse(
                success=False,
                message=result.get("error", "上传失败"),
                success_count=0,
                total=1,
                results=[result]
            )
    except Exception as e:
        logger.error(f"上传失败: {str(e)}")
        return UploadResponse(
            success=False,
            message=str(e),
            success_count=0,
            total=1,
            results=[]
        )


@api_router.post("/batch-upload-to-kb")
async def batch_upload_files_to_knowledge_base(request: BatchUploadRequest):
    """
    批量上传文件到知识库
    """
    logger.info(f"=" * 80)
    logger.info(f"批量上传 {len(request.minio_urls)} 个文件到知识库")
    logger.info(f"Project ID: {request.project_id}")
    logger.info(f"=" * 80)
    
    try:
        results = await kb_manager.batch_upload_files_to_kb(
            minio_urls=request.minio_urls,
            project_id=request.project_id,
            enable_vlm=request.enable_vlm
        )
        
        success_count = sum(1 for r in results if r.get("success"))
        
        logger.info(f"批量上传完成: {success_count}/{len(request.minio_urls)} 成功")
        
        return UploadResponse(
            success=success_count > 0,
            message=f"上传完成: {success_count}/{len(request.minio_urls)} 成功",
            success_count=success_count,
            total=len(request.minio_urls),
            results=results
        )
        
    except Exception as e:
        logger.error(f"批量上传失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return UploadResponse(
            success=False,
            message=f"批量上传失败: {str(e)}",
            success_count=0,
            total=len(request.minio_urls),
            results=[]
        )


# ============ RAG模式一致性检查API ============

class ConsistencyCheckRequest(BaseModel):
    modification_point: str
    modification_request: str
    project_id: str
    top_k: int = 15
    # 🆕 可选：直接指定要修改的文档（如刚生成的文档）
    target_file: Optional[str] = None  # MinIO URL
    # 🆕 可选：是否同时检索并修改相关文档
    include_related: bool = True


class FileModification(BaseModel):
    file_path: str
    original_content: str
    modified_content: str
    diff_summary: str
    original_length: int
    modified_length: int
    evaluation: Optional[Dict] = None  # AI评估结果
    react_thinking_process: Optional[List] = None  # ReactAgent思考过程
    react_search_history: Optional[List] = None  # ReactAgent搜索历史
    truncated: bool = False


class ConsistencyCheckResponse(BaseModel):
    success: bool
    modification_point: str
    consistency_analysis: dict
    related_files: Dict[str, List] = {}
    total_files: int = 0
    total_chunks: int = 0
    modifications: List[FileModification]
    message: str


@api_router.post("/check-consistency", response_model=ConsistencyCheckResponse)
async def check_consistency(request: ConsistencyCheckRequest):
    """
    RAG模式一致性检查
    
    工作流程：
    1. （可选）如果指定了target_file，优先加载该文档
    2. （可选）如果include_related=True，通过RAG检索相关文档
    3. AI分析一致性
    4. 为所有加载的文档生成修改建议并返回Diff结果
    
    参数：
    - target_file: 指定要修改的文档（优先级最高）
    - include_related: 是否同时检索相关文档（默认True）
    - modification_point: 修改点关键词，用于RAG检索
    - modification_request: 具体修改要求
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"RAG模式一致性检查")
    logger.info(f"修改点: {request.modification_point}")
    logger.info(f"Project ID: {request.project_id}")
    logger.info(f"Top K: {request.top_k}")
    logger.info(f"🎯 指定文件: {request.target_file or '无'}")
    logger.info(f"🔍 检索相关文档: {'是' if request.include_related else '否'}")
    logger.info(f"{'='*80}\n")
    
    try:
        files_content = {}
        related_docs_result = {"related_files": {}, "total_files": 0, "total_chunks": 0}
        
        # 🆕 步骤1: 如果指定了target_file，优先加载
        if request.target_file:
            logger.info(f"步骤1: 加载指定文档: {request.target_file}")
            content = await consistency_checker.read_file_content(request.target_file)
            if content:
                files_content[request.target_file] = content
                logger.info(f"✅ 加载成功: {len(content)} 字符")
            else:
                logger.warning(f"⚠️ 无法读取指定文档: {request.target_file}")
        
        # 🆕 步骤2: 如果需要相关文档，通过RAG检索
        if request.include_related:
            logger.info("步骤2: RAG检索相关文档...")
            related_docs_result = await consistency_checker.find_related_documents(
                modification_point=request.modification_point,
                project_id=request.project_id,
                top_k=request.top_k,
                current_file=request.target_file  # 排除已加载的target_file
            )
            
            logger.info(f"找到 {related_docs_result['total_files']} 个相关文档")
            
            # 读取RAG检索到的文档
            for minio_url in related_docs_result["related_files"].keys():
                if minio_url not in files_content:  # 避免重复加载
                    content = await consistency_checker.read_file_content(minio_url)
                    if content:
                        files_content[minio_url] = content
                        logger.info(f"读取成功: {minio_url.split('/')[-1]} ({len(content)} 字符)")
        
        # 检查是否有文档需要处理
        if not files_content:
            return ConsistencyCheckResponse(
                success=True,
                modification_point=request.modification_point,
                consistency_analysis={},
                related_files=related_docs_result["related_files"],
                total_files=related_docs_result["total_files"],
                total_chunks=related_docs_result["total_chunks"],
                modifications=[],
                message="未找到需要修改的文档"
            )
        
        logger.info(f"📊 总共加载 {len(files_content)} 个文档")
        
        # 步骤3: AI分析一致性
        logger.info("步骤3: AI分析一致性...")
        
        analysis = await consistency_checker.analyze_consistency(
            modification_request=request.modification_request,
            current_file_content=None,  # 不需要当前文件，直接分析所有找到的文档
            related_files_content=files_content  # 所有找到的文档
        )
        
        # 步骤4: 为所有找到的文档生成修改建议
        logger.info("步骤4: 生成修改建议...")
        modifications = []
        
        if files_content:
            logger.info(f"为 {len(files_content)} 个相关文档生成修改建议...")
            modifications = await consistency_checker.generate_modifications(
                modification_request=request.modification_request,
                current_modification=None,  # 没有参考修改，直接根据用户请求修改
                files_to_modify=files_content,  # 所有找到的文档
                project_id=request.project_id  # 传递项目ID给ReactAgent
            )
        else:
            logger.info("没有文档需要修改")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"一致性检查完成")
        logger.info(f"相关文档: {len(files_content)} 个")
        logger.info(f"修改建议: {len(modifications)} 个")
        logger.info(f"{'='*80}\n")
        
        return ConsistencyCheckResponse(
            success=True,
            modification_point=request.modification_point,
            consistency_analysis=analysis,
            related_files=related_docs_result["related_files"],
            total_files=related_docs_result["total_files"],
            total_chunks=related_docs_result["total_chunks"],
            modifications=[FileModification(**m) for m in modifications],
            message=f"成功分析 {len(files_content)} 个文档，生成 {len(modifications)} 个修改建议"
        )
        
    except Exception as e:
        logger.error(f"一致性检查失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return ConsistencyCheckResponse(
            success=False,
            modification_point=request.modification_point,
            consistency_analysis={},
            related_files={},
            total_files=0,
            total_chunks=0,
            modifications=[],
            message=f"检查失败: {str(e)}"
        )


# 挂载API路由器
app.include_router(api_router)

# 静态文件服务（前端）
try:
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
except:
    pass
