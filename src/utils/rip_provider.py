"""
rip_provider.py

多源获取并缓存公网IP（rip），自动兜底
"""

import re
import requests
from src.utils.logger import logger

_RIP_CACHE = None


IP_SOURCES = [
    # 国内稳定
    "https://myip.ipip.net",
    "https://ip.sb",
    "https://api.ip.sb/ip",
    # 国外备用
    "https://ifconfig.me/ip",
]


def _extract_ip(text):
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    return match.group(0) if match else None


def _fetch_public_ip():
    for url in IP_SOURCES:
        try:
            logger.info(f"尝试获取公网IP: {url}")
            resp = requests.get(
                url,
                timeout=5,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )
            ip = _extract_ip(resp.text)
            if ip:
                logger.info(f"公网IP获取成功: {ip}")
                return ip
        except Exception as e:
            logger.warning(f"从 {url} 获取IP失败: {e}")

    logger.error("所有公网IP源均不可用")
    return None


def get_rip(force_refresh=False):
    global _RIP_CACHE
    if force_refresh or not _RIP_CACHE:
        _RIP_CACHE = _fetch_public_ip()
    return _RIP_CACHE
