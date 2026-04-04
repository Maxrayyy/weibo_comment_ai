"""
检查好友圈页面中所有 sinaimg.cn 图片的 src，区分头像和微博图片。
用于验证 _extract_first_pic 的头像过滤逻辑。
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.auth.login_manager import get_valid_cookies
from src.scraper.weibo_scraper import WeiboScraper
from src.utils.config_loader import config
from bs4 import BeautifulSoup

scraper = WeiboScraper()
scraper.start()

gid = config.friend_group_gid
url = f"https://www.weibo.com/mygroups?gid={gid}"
scraper.driver.get(url)

import time
time.sleep(5)

html = scraper.driver.page_source
soup = BeautifulSoup(html, "html.parser")

articles = soup.find_all("article")
print(f"\n共找到 {len(articles)} 篇 article\n")

for i, article in enumerate(articles):
    imgs = article.find_all("img", src=re.compile(r"sinaimg\.cn"))
    if imgs:
        print(f"--- Article {i+1} ---")
        for img in imgs:
            src = img.get("src", "")
            # 判断类型
            if "face" in src or "emoticon" in src:
                tag = "[表情]"
            elif "avatar" in src or "headicon" in src or "default" in src:
                tag = "[头像]"
            else:
                tag = "[图片]"
            print(f"  {tag} {src}")
        print()

scraper.stop()
