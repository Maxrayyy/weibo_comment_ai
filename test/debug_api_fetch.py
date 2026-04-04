"""
调试好友圈 AJAX API：验证API调用能获取最新微博数据。
在Docker容器内运行：
  docker compose run --rm friend-group python test/debug_api_fetch.py
"""
import sys
import os
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
from src.scraper.parser import parse_group_timeline_api
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1920,1080")
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

cookies = load_cookies()
if cookies:
    apply_cookies(driver, cookies)
    print(f"[OK] Cookie已加载，共 {len(cookies)} 条")

# 先访问微博主页确保cookie生效
print("\n=== 1. 确保cookie域生效 ===")
driver.get("https://weibo.com")
time.sleep(3)

# 调用AJAX API
print("\n=== 2. 调用好友圈 AJAX API ===")
gid = config.friend_group_gid
api_url = f"https://www.weibo.com/ajax/feed/groupstimeline?list_id={gid}&refresh=4&fast_refresh=1&count=25"
print(f"API URL: {api_url}")

result = driver.execute_script(f"""
    try {{
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '{api_url}', false);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send();
        if (xhr.status === 200) {{
            return xhr.responseText;
        }} else {{
            return 'ERROR:' + xhr.status;
        }}
    }} catch(e) {{
        return 'ERROR:' + e.message;
    }}
""")

if not result or result.startswith("ERROR:"):
    print(f"[ERROR] API请求失败: {result}")
    driver.quit()
    sys.exit(1)

data = json.loads(result)

# 保存原始JSON供检查
with open("data/debug_api_response.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("[OK] API响应已保存到 data/debug_api_response.json")

# 检查数据结构
statuses = data.get("statuses", [])
print(f"\n=== 3. API返回 {len(statuses)} 条微博 ===")

# 打印第一条的完整字段名（便于确认数据结构）
if statuses:
    first = statuses[0]
    print(f"\n第一条微博的顶层字段: {list(first.keys())}")
    if "user" in first:
        print(f"user字段: {list(first['user'].keys())[:10]}...")
    if "pic_infos" in first:
        print(f"pic_infos字段: 有 {len(first.get('pic_ids', []))} 张图")

# 使用解析函数
print("\n=== 4. 解析结果 ===")
weibos = parse_group_timeline_api(data)
print(f"解析成功 {len(weibos)} 条微博:")
for i, w in enumerate(weibos):
    pic_tag = " [有图]" if w.get("pic_url") else ""
    repost_tag = " [转发]" if w.get("is_repost") else ""
    print(f"  [{i+1}] @{w['user_name']} (UID:{w['user_id']}) mid={w['mid']}{pic_tag}{repost_tag}")
    print(f"       {w['text'][:80]}")
    print(f"       时间: {w['created_at']}")
    if w.get("pic_url"):
        print(f"       图片: {w['pic_url'][:80]}")

driver.quit()
print("\n完成")
