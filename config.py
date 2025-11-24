"""配置文件"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# OpenRouter API 配置
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# 模型配置
MODEL_NAME = os.getenv("MODEL_NAME", "anthropic/claude-3.5-sonnet")

# RAG 搜索接口
RAG_SEARCH_URL = "http://43.139.19.144:1234/search"
RAG_PROJECT_ID = os.getenv("RAG_PROJECT_ID", "default")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_USE_REFINE = os.getenv("RAG_USE_REFINE", "true").lower() == "true"

# Agent 配置
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))

