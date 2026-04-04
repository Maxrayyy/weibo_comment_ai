"""
深度调试：检查好友圈页面的网络请求、JS错误、DOM变化。
"""
import sys
import os
import re
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.auth.login_manager import load_cookies, apply_cookies
from src.utils.config_loader import config
from src.utils.driver_helper import get_chrome_service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1920,1080")
options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
options.add_experimental_option("excludeSwitches", ["enable-automation"])

service = get_chrome_service()
driver = webdriver.Chrome(service=service, options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        window.chrome = {runtime: {}};
    """
})

# 启用网络监控
driver.execute_cdp_cmd("Network.enable", {})

cookies = load_cookies()
if cookies:
    apply_cookies(driver, cookies)
    print(f"[OK] Cookie已加载，共 {len(cookies)} 条")

# 列出所有cookie
print("\n=== 1. Cookie详情 ===")
driver.get("https://weibo.com")
time.sleep(2)
all_cookies = driver.get_cookies()
print(f"浏览器中共 {len(all_cookies)} 条Cookie:")
for c in all_cookies:
    print(f"  {c['name']}: {c['value'][:30]}... (domain: {c.get('domain', '?')})")

# 访问好友圈
print("\n=== 2. 加载好友圈 ===")
gid = config.friend_group_gid
url = f"https://www.weibo.com/mygroups?gid={gid}"
driver.get(url)

# 记录初始article数量
time.sleep(3)
initial_articles = len(driver.find_elements(By.CSS_SELECTOR, "article"))
print(f"3秒后: {initial_articles} 篇article")

# 等待更长时间看DOM是否变化
time.sleep(5)
after_wait_articles = len(driver.find_elements(By.CSS_SELECTOR, "article"))
print(f"8秒后: {after_wait_articles} 篇article")

time.sleep(5)
final_articles = len(driver.find_elements(By.CSS_SELECTOR, "article"))
print(f"13秒后: {final_articles} 篇article")

# 检查第一条微博内容
first_text = driver.execute_script("""
    var articles = document.querySelectorAll('article');
    if (articles.length > 0) {
        var textElem = articles[0].querySelector('[class*="_wbtext_"]');
        var nickElem = articles[0].querySelector('[class*="_nick_"]');
        var nick = nickElem ? nickElem.textContent.trim() : '?';
        var text = textElem ? textElem.textContent.trim().substring(0, 60) : '';
        return nick + ' | ' + text;
    }
    return '无内容';
""")
print(f"第一条: {first_text}")

# 检查JS控制台错误
print("\n=== 3. 浏览器控制台日志 ===")
try:
    logs = driver.get_log("browser")
    errors = [l for l in logs if l["level"] in ("SEVERE", "WARNING")]
    if errors:
        for e in errors[:15]:
            print(f"  [{e['level']}] {e['message'][:200]}")
    else:
        print("  无错误/警告")
except Exception as e:
    print(f"  获取日志失败: {e}")

# 检查网络请求中的API调用
print("\n=== 4. 网络请求分析 ===")
try:
    perf_logs = driver.get_log("performance")
    api_calls = []
    for entry in perf_logs:
        try:
            log = json.loads(entry["message"])
            msg = log.get("message", {})
            method = msg.get("method", "")
            params = msg.get("params", {})

            if method == "Network.responseReceived":
                resp = params.get("response", {})
                url = resp.get("url", "")
                status = resp.get("status", 0)
                if "api" in url or "ajax" in url or "mygroups" in url or "group" in url or "feed" in url:
                    api_calls.append({"url": url[:150], "status": status})

            if method == "Network.requestWillBeSent":
                req = params.get("request", {})
                url = req.get("url", "")
                if "api" in url or "ajax" in url or "mygroups" in url or "group" in url or "feed" in url:
                    api_calls.append({"url": url[:150], "status": "pending"})
        except:
            continue

    if api_calls:
        print(f"  找到 {len(api_calls)} 个API相关请求:")
        seen = set()
        for call in api_calls:
            key = call["url"]
            if key not in seen:
                seen.add(key)
                print(f"    [{call['status']}] {call['url']}")
    else:
        print("  未发现API请求（可能SPA的数据请求未触发）")
except Exception as e:
    print(f"  获取性能日志失败: {e}")

# 尝试手动触发feed刷新
print("\n=== 5. 手动触发页面刷新 ===")
driver.execute_script("window.scrollTo(0, 0);")
time.sleep(1)
driver.refresh()
time.sleep(8)

try:
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
    )
except:
    pass

refreshed_articles = len(driver.find_elements(By.CSS_SELECTOR, "article"))
first_text_after = driver.execute_script("""
    var articles = document.querySelectorAll('article');
    if (articles.length > 0) {
        var textElem = articles[0].querySelector('[class*="_wbtext_"]');
        var nickElem = articles[0].querySelector('[class*="_nick_"]');
        var nick = nickElem ? nickElem.textContent.trim() : '?';
        var text = textElem ? textElem.textContent.trim().substring(0, 60) : '';
        return nick + ' | ' + text;
    }
    return '无内容';
""")
print(f"刷新后: {refreshed_articles} 篇article")
print(f"第一条: {first_text_after}")

driver.quit()
print("\n完成")
