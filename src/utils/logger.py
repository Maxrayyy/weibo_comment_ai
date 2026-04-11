import logging
from logging.handlers import RotatingFileHandler
import os

import yaml

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

# 通过环境变量区分服务名，用于生成独立日志文件
SERVICE_NAME = os.environ.get("SERVICE_NAME", "app")
LOG_FILE = os.path.join(LOG_DIR, f"{SERVICE_NAME}.log")


def _load_log_config():
    """直接从yaml读取日志配置（避免与config_loader循环依赖）"""
    config_dir = os.path.join(_PROJECT_ROOT, "config")
    prod_path = os.path.join(config_dir, "config.prod.yaml")
    config_file = prod_path if os.path.exists(prod_path) else os.path.join(config_dir, "config.yaml")
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("logging", {})
    except Exception:
        return {}


def setup_logger(name="weibo_comment_ai", level=logging.INFO):
    """配置并返回logger，同时输出到控制台和日志文件"""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_cfg = _load_log_config()
    max_bytes = log_cfg.get("max_bytes", 524288)
    backup_count = log_cfg.get("backup_count", 2)

    logger.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（大小和备份数从config读取）
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
