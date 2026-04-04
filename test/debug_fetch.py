"""
调试好友圈抓取：检查页面加载状态、登录状态、内容是否最新。
在Docker容器内运行。
"""
import sys
import os
import re
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.auth.login_manager import load_cookies, apply_cookies
from src.utils.config_loader import config
from src.utils.driver_helper import get_chrome_service
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 启动浏览器
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-cache")
options.add_argument("--disk-cache-size=0")
options.add_experimental_option("excludeSwitches", ["enable-automation"])

service = get_chrome_service()
driver = webdriver.Chrome(service=service, options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
})

# 加载Cookie
cookies = load_cookies()
if cookies:
    apply_cookies(driver, cookies)
    print(f"[OK] Cookie已加载，共 {len(cookies)} 条")
else:
    print("[ERROR] 无Cookie！")
    driver.quit()
    sys.exit(1)

# 检查登录状态
print("\n=== 1. 检查登录状态 ===")
driver.get("https://weibo.com")
time.sleep(3)
url = driver.current_url
page = driver.page_source

if "passport" in url or "login" in url:
    print(f"[ERROR] 被重定向到登录页: {url}")
    print("[结论] Cookie已失效，需要重新登录")
    driver.quit()
    sys.exit(1)

if "立即登录" in page and "我的首页" not in page:
    print("[ERROR] 页面包含'立即登录'，Cookie可能失效")
else:
    print("[OK] 登录状态正常")

# 访问好友圈
print("\n=== 2. 抓取好友圈页面 ===")
gid = config.friend_group_gid
url = f"https://www.weibo.com/mygroups?gid={gid}"
print(f"访问: {url}")

# 清除缓存后访问
driver.execute_cdp_cmd("Network.clearBrowserCache", {})
driver.get(url)
time.sleep(5)

# 检查页面标题和URL
print(f"当前URL: {driver.current_url}")
print(f"页面标题: {driver.title}")

# 等待SPA渲染
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
    )
    print("[OK] article元素已加载")
except:
    print("[WARNING] 等待article超时")

# 滚动加载
print("\n=== 3. 滚动加载 ===")
for i in range(3):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    height = driver.execute_script("return document.body.scrollHeight")
    print(f"第{i+1}次滚动，页面高度: {height}")

# 解析内容
print("\n=== 4. 解析结果 ===")
html = driver.page_source

# 保存HTML到data目录供检查
with open("data/debug_friend_group.html", "w", encoding="utf-8") as f:
    f.write(html)
print("[OK] 页面HTML已保存到 data/debug_friend_group.html")

soup = BeautifulSoup(html, "html.parser")
articles = soup.find_all("article")
print(f"找到 {len(articles)} 篇 article")

for i, article in enumerate(articles):
    # 提取用户名
    nick = article.find(class_=re.compile(r"_nick_"))
    name = nick.get_text(strip=True) if nick else "?"

    # 提取正文
    text_elem = article.find(class_=re.compile(r"_wbtext_"))
    text = text_elem.get_text(strip=True)[:60] if text_elem else ""

    # 提取时间
    time_link = article.find("a", href=re.compile(r"weibo\.com/\d+/\w+"))
    time_text = time_link.get_text(strip=True) if time_link else "无时间"

    print(f"  [{i+1}] @{name} | {time_text} | {text}")

# 检查页面是否有"暂无内容"等提示
print("\n=== 5. 异常检查 ===")
if "暂无内容" in html:
    print("[WARNING] 页面包含'暂无内容'")
if "请先登录" in html:
    print("[ERROR] 页面提示'请先登录'")
if "系统繁忙" in html:
    print("[WARNING] 页面提示'系统繁忙'")
if len(articles) == 0:
    print("[ERROR] 未找到任何微博内容")
else:
    print("[OK] 无明显异常")

driver.quit()
print("\n完成")
