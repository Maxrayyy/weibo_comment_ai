import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")

# 通过环境变量区分服务名，用于生成独立日志文件
SERVICE_NAME = os.environ.get("SERVICE_NAME", "app")
LOG_FILE = os.path.join(LOG_DIR, f"{SERVICE_NAME}.log")


def setup_logger(name="weibo_comment_ai", level=logging.INFO):
    """配置并返回logger，同时输出到控制台和日志文件"""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（单文件最大500KB，保留2个备份，共约1.5MB）
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=500 * 1024, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
