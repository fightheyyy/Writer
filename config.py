"""配置文件"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 获取当前文件所在目录
BASE_DIR = Path(__file__).resolve().parent

# 加载 .env 文件（指定路径，优先使用 .env 中的配置）
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# OpenRouter API 配置
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# 调试：打印环境变量读取情况
print(f"[CONFIG DEBUG] OPENROUTER_API_KEY: {OPENROUTER_API_KEY[:20] if OPENROUTER_API_KEY else 'EMPTY'}...")
print(f"[CONFIG DEBUG] MODEL_NAME: {os.getenv('MODEL_NAME', 'NOT SET')}")

# 模型配置
MODEL_NAME = os.getenv("MODEL_NAME", "x-ai/grok-4.1-fast")

# RAG 搜索接口
RAG_SEARCH_URL = "http://43.139.19.144:1234/search"
RAG_PROJECT_ID = os.getenv("RAG_PROJECT_ID", "default")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_USE_REFINE = os.getenv("RAG_USE_REFINE", "true").lower() == "true"

# Agent 配置
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))

# 知识库缓存目录（知识库服务缓存文件的位置）
# 注意: 如果知识库服务在不同容器，需要共享volume
KB_CACHE_DIR = os.getenv("KB_CACHE_DIR", "/data/knowledge_base/documents")

# 知识库处理接口
KB_PROCESS_URL = os.getenv("KB_PROCESS_URL", "http://43.139.19.144:8001/api/v1/process_and_extract")

