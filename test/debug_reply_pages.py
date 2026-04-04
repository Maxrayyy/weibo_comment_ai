"""
调试脚本：抓取评论收件箱和发出评论页面，分析回复按钮的AJAX请求参数。
"""

import time
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.auth.login_manager import get_valid_cookies, load_cookies
from src.scraper.weibo_scraper import WeiboScraper
from src.utils.logger import logger


def main():
    cookies = get_valid_cookies()
    if not cookies:
        logger.error("Cookie无效")
        return

    scraper = WeiboScraper()
    scraper.start()
    driver = scraper.driver

    try:
        # === 1. 抓取评论收件箱 ===
        logger.info("=" * 60)
        logger.info("抓取评论收件箱 inbox")
        logger.info("=" * 60)
        driver.get("https://www.weibo.com/comment/inbox")
        time.sleep(5)

        # 保存截图和HTML
        driver.save_screenshot("data/debug_inbox.png")
        with open("data/debug_inbox.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("inbox 截图和HTML已保存到 data/")

        # === 2. 抓取发出评论页面 ===
        logger.info("=" * 60)
        logger.info("抓取发出评论 outbox")
        logger.info("=" * 60)
        driver.get("https://www.weibo.com/comment/outbox")
        time.sleep(5)

        driver.save_screenshot("data/debug_outbox.png")
        with open("data/debug_outbox.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("outbox 截图和HTML已保存到 data/")

        # === 3. 注入XHR拦截器，捕获回复按钮的AJAX请求 ===
        logger.info("=" * 60)
        logger.info("注入XHR拦截器，分析回复接口参数")
        logger.info("=" * 60)

        # 回到inbox页面
        driver.get("https://www.weibo.com/comment/inbox")
        time.sleep(5)

        # 注入拦截器
        driver.execute_script("""
            window.__captured_requests = [];
            const origOpen = XMLHttpRequest.prototype.open;
            const origSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(method, url, ...args) {
                this._capturedMethod = method;
                this._capturedUrl = url;
                return origOpen.call(this, method, url, ...args);
            };
            XMLHttpRequest.prototype.send = function(body) {
                if (this._capturedUrl && (this._capturedUrl.includes('comment') || this._capturedUrl.includes('reply'))) {
                    window.__captured_requests.push({
                        method: this._capturedMethod,
                        url: this._capturedUrl,
                        body: body
                    });
                }
                return origSend.call(this, body);
            };

            // 同样拦截 fetch
            const origFetch = window.fetch;
            window.fetch = function(url, options) {
                if (url && (url.toString().includes('comment') || url.toString().includes('reply'))) {
                    window.__captured_requests.push({
                        method: (options && options.method) || 'GET',
                        url: url.toString(),
                        body: options && options.body
                    });
                }
                return origFetch.apply(this, arguments);
            };
            console.log('XHR/Fetch拦截器已注入');
        """)
        logger.info("XHR/Fetch拦截器已注入")

        # === 4. 查找回复按钮并分析 ===
        logger.info("=" * 60)
        logger.info("分析页面中的回复按钮")
        logger.info("=" * 60)

        # 提取所有回复按钮的信息
        buttons_info = driver.execute_script("""
            var results = [];
            // 找所有可能的回复按钮
            var allElements = document.querySelectorAll('*');
            for (var el of allElements) {
                var text = el.textContent.trim();
                if (text === '回复' && el.children.length === 0) {
                    var parent = el.closest('[class*="scroller-item"]') || el.closest('[class*="card"]') || el.parentElement;
                    results.push({
                        tag: el.tagName,
                        className: el.className,
                        parentClassName: parent ? parent.className : '',
                        onclick: el.getAttribute('onclick') || '',
                        href: el.getAttribute('href') || '',
                        dataAttrs: JSON.stringify(Object.fromEntries(
                            Array.from(el.attributes).filter(a => a.name.startsWith('data-')).map(a => [a.name, a.value])
                        )),
                        outerHTML: el.outerHTML.substring(0, 300)
                    });
                }
            }
            return results;
        """)

        logger.info(f"找到 {len(buttons_info)} 个回复按钮:")
        for i, btn in enumerate(buttons_info):
            logger.info(f"  [{i}] tag={btn['tag']}, class={btn['className'][:80]}")
            logger.info(f"       href={btn['href'][:100]}")
            logger.info(f"       data-attrs={btn['dataAttrs'][:200]}")
            logger.info(f"       html={btn['outerHTML'][:200]}")

        # === 5. 分析outbox中已发出的回复 ===
        logger.info("=" * 60)
        logger.info("分析outbox中已发出的回复")
        logger.info("=" * 60)
        driver.get("https://www.weibo.com/comment/outbox")
        time.sleep(5)

        outbox_info = driver.execute_script("""
            var results = [];
            var items = document.querySelectorAll('div.wbpro-scroller-item');
            for (var item of items) {
                var textEl = item.querySelector('[class*="wbtext"]');
                var nameEl = item.querySelector('[class*="_h3_"] a');
                var fromEl = item.querySelector('[class*="_from_"] a');
                results.push({
                    text: textEl ? textEl.textContent.trim().substring(0, 100) : '',
                    target: nameEl ? nameEl.textContent.trim() : '',
                    link: fromEl ? fromEl.getAttribute('href') : '',
                    linkText: fromEl ? fromEl.textContent.trim() : ''
                });
            }
            return results;
        """)

        logger.info(f"发出评论/回复 {len(outbox_info)} 条:")
        for i, item in enumerate(outbox_info):
            logger.info(f"  [{i}] → @{item['target']}: {item['text']}")
            logger.info(f"       链接: {item['link']}")

    finally:
        scraper.stop()


if __name__ == "__main__":
    main()
