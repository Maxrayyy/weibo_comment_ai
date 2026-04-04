"""
ChromeDriver Service 统一获取

Docker 环境：使用系统安装的 /usr/bin/chromedriver
本地环境：使用 webdriver-manager 自动下载
"""

import os
import shutil

from selenium.webdriver.chrome.service import Service


def get_chrome_service():
    """获取 ChromeDriver Service，自动适配 Docker/本地环境"""
    if os.environ.get("DOCKER_ENV") == "1":
        return Service("/usr/bin/chromedriver")

    # 本地环境：优先检测系统已有的 chromedriver
    system_path = shutil.which("chromedriver")
    if system_path:
        return Service(system_path)

    # 回退到 webdriver-manager 自动下载
    from webdriver_manager.chrome import ChromeDriverManager
    return Service(ChromeDriverManager().install())