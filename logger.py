"""日志配置"""
import logging
import sys
import os
from datetime import datetime

# 创建日志目录
os.makedirs("logs", exist_ok=True)

# 创建日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 配置根日志器
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/app_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8')
    ]
)

def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)

