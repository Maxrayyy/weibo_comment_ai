"""
OAuth2 access_token管理

流程：
1. 检查本地是否有有效的access_token
2. 无效则通过Selenium引导用户授权获取新token
3. 持久化token到本地文件
"""

import json
import os
import time
from urllib.parse import urlparse, parse_qs

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from webdriver_manager.chrome import ChromeDriverManager

from src.utils.config_loader import config
from src.utils.logger import logger

TOKEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "oauth_token.json"
)

AUTHORIZE_URL = "https://api.weibo.com/oauth2/authorize"
ACCESS_TOKEN_URL = "https://api.weibo.com/oauth2/access_token"
GET_UID_URL = "https://api.weibo.com/2/account/get_uid.json"


def _save_token(token_data):
    """保存token到本地文件"""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
    logger.info("access_token已保存到本地")


def _load_token():
    """从本地加载token"""
    if not os.path.exists(TOKEN_PATH):
        return None
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_token(access_token):
    """通过get_uid接口验证token是否有效"""
    try:
        resp = requests.get(GET_UID_URL, params={"access_token": access_token}, timeout=10)
        data = resp.json()
        if "uid" in data:
            logger.info(f"access_token有效，用户UID: {data['uid']}")
            return True
        logger.warning(f"access_token无效: {data}")
        return False
    except Exception as e:
        logger.error(f"验证token失败: {e}")
        return False


def _get_authorization_code():
    """通过Selenium引导用户授权，获取authorization code"""
    auth_url = (
        f"{AUTHORIZE_URL}"
        f"?client_id={config.app_key}"
        f"&redirect_uri={config.redirect_uri}"
        f"&response_type=code"
    )

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(auth_url)
        logger.info("=" * 50)
        logger.info("请在浏览器中完成微博OAuth授权")
        logger.info("授权后页面会跳转，程序将自动获取授权码")
        logger.info("=" * 50)

        # 等待授权完成，从回调URL中提取code
        timeout = 300
        start = time.time()
        while time.time() - start < timeout:
            current_url = driver.current_url
            if "code=" in current_url:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                code = params.get("code", [None])[0]
                if code:
                    logger.info(f"获取到授权码: {code[:10]}...")
                    return code
            time.sleep(1)

        logger.error("OAuth授权超时")
        return None
    finally:
        driver.quit()


def _exchange_token(code):
    """用authorization code换取access_token"""
    data = {
        "client_id": config.app_key,
        "client_secret": config.app_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
    }
    try:
        resp = requests.post(ACCESS_TOKEN_URL, data=data, timeout=10)
        token_data = resp.json()
        if "access_token" in token_data:
            # 记录获取时间，用于判断过期
            token_data["obtained_at"] = int(time.time())
            logger.info(f"获取access_token成功，有效期: {token_data.get('expires_in', '未知')}秒")
            return token_data
        logger.error(f"获取access_token失败: {token_data}")
        return None
    except Exception as e:
        logger.error(f"请求access_token异常: {e}")
        return None


def is_token_expired(token_data):
    """检查token是否已过期"""
    if not token_data:
        return True
    obtained_at = token_data.get("obtained_at", 0)
    expires_in = token_data.get("expires_in", 0)
    # 提前5分钟视为过期
    if isinstance(expires_in, str):
        expires_in = int(expires_in)
    return time.time() > obtained_at + expires_in - 300


def get_valid_token():
    """
    获取有效的access_token。
    优先使用本地缓存，过期则重新授权。
    返回access_token字符串，失败返回None。
    """
    token_data = _load_token()

    if token_data and not is_token_expired(token_data):
        access_token = token_data["access_token"]
        if verify_token(access_token):
            return access_token
        logger.warning("本地token验证失败，需要重新授权")

    # 重新授权
    if os.environ.get("DOCKER_ENV") == "1":
        logger.error("Docker环境下无法进行OAuth授权，请在本地授权后将 data/oauth_token.json 挂载到容器")
        return None

    logger.info("开始OAuth2授权流程...")
    code = _get_authorization_code()
    if not code:
        return None

    token_data = _exchange_token(code)
    if not token_data:
        return None

    _save_token(token_data)
    return token_data["access_token"]


def get_uid(access_token):
    """获取当前授权用户的UID"""
    try:
        resp = requests.get(GET_UID_URL, params={"access_token": access_token}, timeout=10)
        data = resp.json()
        return str(data.get("uid", ""))
    except Exception as e:
        logger.error(f"获取UID失败: {e}")
        return None
