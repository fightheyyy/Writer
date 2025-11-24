from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from react_agent import ReactAgent
from logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="ReAct Article Generator")

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


@app.post("/generate", response_model=ArticleResponse)
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


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# 静态文件服务（前端）
try:
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
except:
    pass

