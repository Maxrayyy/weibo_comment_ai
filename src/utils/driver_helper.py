"""
ChromeDriver Service & Chrome Options 统一获取

自动适配 Docker / Linux / Windows 环境：
- Docker：使用系统安装的 chromedriver
- 本地 Linux/Windows：优先检测系统 PATH，回退到 webdriver-manager 自动下载
"""

import os
import platform
import shutil

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

IS_WINDOWS = platform.system() == "Windows"
IS_DOCKER = os.environ.get("DOCKER_ENV") == "1"


def get_chrome_service():
    """获取 ChromeDriver Service，自动适配 Docker/Linux/Windows 环境"""
    if IS_DOCKER:
        return Service("/usr/bin/chromedriver")

    if not IS_WINDOWS:
        # Linux 本地：优先使用系统已安装的 chromedriver
        system_path = shutil.which("chromedriver")
        if system_path:
            return Service(system_path)

    # Windows 或 Linux 无系统 chromedriver：用 webdriver-manager 自动匹配版本
    from webdriver_manager.chrome import ChromeDriverManager
    return Service(ChromeDriverManager().install())


def get_chrome_options(headless=False):
    """获取 Chrome Options，自动适配平台差异"""
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    # Linux/Docker 专用参数（Windows 上不需要）
    if not IS_WINDOWS:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    # 平台匹配的 User-Agent
    if IS_WINDOWS:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    else:
        ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    options.add_argument(f"--user-agent={ua}")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options