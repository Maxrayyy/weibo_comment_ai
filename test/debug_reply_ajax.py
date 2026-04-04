"""
调试脚本：拦截微博网页版回复评论的AJAX请求，查看真实参数。
不会实际发送回复 — 拦截后阻止请求并打印参数。
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

from src.auth.login_manager import get_valid_cookies
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
        # 打开评论收件箱
        logger.info("打开评论收件箱...")
        driver.get("https://www.weibo.com/comment/inbox")
        time.sleep(5)

        # 方法1：在页面JS中搜索reply相关的API调用代码
        logger.info("=" * 60)
        logger.info("搜索页面JS中的回复API端点和参数")
        logger.info("=" * 60)

        js_info = driver.execute_script("""
            var results = [];

            // 搜索所有 script 标签内容
            var scripts = document.querySelectorAll('script');
            for (var s of scripts) {
                var text = s.textContent || s.innerText || '';
                if (text.includes('comments/reply') || text.includes('comment/reply')) {
                    // 提取包含 reply 的行
                    var lines = text.split('\\n');
                    for (var line of lines) {
                        if (line.includes('reply') && (line.includes('ajax') || line.includes('comment') || line.includes('cid') || line.includes('rid'))) {
                            results.push(line.trim().substring(0, 500));
                        }
                    }
                }
            }

            // 搜索所有外部JS的src
            var jsSrcs = [];
            for (var s of scripts) {
                if (s.src && (s.src.includes('comment') || s.src.includes('reply'))) {
                    jsSrcs.push(s.src);
                }
            }

            return {results: results, jsSrcs: jsSrcs};
        """)

        if js_info.get("results"):
            for line in js_info["results"][:20]:
                logger.info(f"  JS: {line}")
        else:
            logger.info("  未在内联script中找到reply相关代码")

        if js_info.get("jsSrcs"):
            for src in js_info["jsSrcs"]:
                logger.info(f"  JS SRC: {src}")

        # 方法2：注入拦截器，捕获所有发往 /ajax/ 的请求
        logger.info("=" * 60)
        logger.info("注入XHR拦截器")
        logger.info("=" * 60)

        driver.execute_script("""
            window.__ajax_log = [];

            // 拦截 XMLHttpRequest
            var origXHROpen = XMLHttpRequest.prototype.open;
            var origXHRSend = XMLHttpRequest.prototype.send;
            var origXHRSetHeader = XMLHttpRequest.prototype.setRequestHeader;

            XMLHttpRequest.prototype.open = function(method, url) {
                this._url = url;
                this._method = method;
                this._headers = {};
                return origXHROpen.apply(this, arguments);
            };
            XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                this._headers[name] = value;
                return origXHRSetHeader.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function(body) {
                if (this._url && this._url.includes('/ajax/')) {
                    window.__ajax_log.push({
                        method: this._method,
                        url: this._url,
                        headers: this._headers,
                        body: body,
                        timestamp: new Date().toISOString()
                    });
                }
                return origXHRSend.apply(this, arguments);
            };

            // 拦截 fetch
            var origFetch = window.fetch;
            window.fetch = function(input, init) {
                var url = typeof input === 'string' ? input : input.url;
                if (url && url.includes('/ajax/')) {
                    window.__ajax_log.push({
                        method: (init && init.method) || 'GET',
                        url: url,
                        headers: init && init.headers ? JSON.parse(JSON.stringify(init.headers)) : {},
                        body: init && init.body,
                        timestamp: new Date().toISOString()
                    });
                }
                return origFetch.apply(this, arguments);
            };

            console.log('拦截器已注入');
        """)
        logger.info("XHR/Fetch拦截器已注入")

        # 方法3：找到回复按钮，模拟点击触发回复面板，然后输入文字并发送
        logger.info("=" * 60)
        logger.info("尝试点击回复按钮，触发回复面板")
        logger.info("=" * 60)

        # 找到第一个回复按钮并点击
        clicked = driver.execute_script("""
            // 找到操作栏中的回复按钮（不是评论文本中的"回复"文字）
            var items = document.querySelectorAll('[class*="_item_j8div"]');
            for (var item of items) {
                var span = item.querySelector('[class*="_num_"]');
                if (span && span.textContent.trim() === '回复') {
                    span.click();
                    return 'clicked: ' + item.className;
                }
            }
            return 'not found';
        """)
        logger.info(f"点击结果: {clicked}")
        time.sleep(2)

        # 截图看看回复面板
        driver.save_screenshot("data/debug_reply_panel.png")
        logger.info("回复面板截图已保存: data/debug_reply_panel.png")

        # 查找回复输入框
        textarea_info = driver.execute_script("""
            var textareas = document.querySelectorAll('textarea');
            var results = [];
            for (var ta of textareas) {
                results.push({
                    placeholder: ta.placeholder,
                    className: ta.className,
                    name: ta.name,
                    id: ta.id,
                    visible: ta.offsetParent !== null,
                    parentClass: ta.parentElement ? ta.parentElement.className : ''
                });
            }
            return results;
        """)
        logger.info(f"找到 {len(textarea_info)} 个textarea:")
        for ta in textarea_info:
            logger.info(f"  placeholder={ta['placeholder']}, visible={ta['visible']}, class={ta['className'][:80]}")

        # 在textarea中输入测试文字
        typed = driver.execute_script("""
            var textareas = document.querySelectorAll('textarea');
            for (var ta of textareas) {
                if (ta.offsetParent !== null) {  // visible
                    // 模拟React input
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeInputValueSetter.call(ta, '测试回复_debug');
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                    return 'typed in: ' + ta.placeholder;
                }
            }
            return 'no visible textarea';
        """)
        logger.info(f"输入结果: {typed}")
        time.sleep(1)

        # 找到发送按钮并点击
        sent = driver.execute_script("""
            // 找发送/回复提交按钮
            var buttons = document.querySelectorAll('button, [role="button"], a');
            for (var btn of buttons) {
                var text = btn.textContent.trim();
                if ((text === '回复' || text === '发送' || text === '评论') && btn.offsetParent !== null) {
                    // 检查是否在回复面板中
                    var parent = btn.closest('[class*="compose"], [class*="reply"], [class*="editor"]');
                    if (parent || btn.className.includes('submit') || btn.className.includes('send')) {
                        btn.click();
                        return 'clicked submit: ' + text + ' class=' + btn.className.substring(0, 100);
                    }
                }
            }
            // 备选：找所有包含"回复"的可点击元素
            var allBtns = [];
            for (var btn of buttons) {
                if (btn.offsetParent !== null && btn.textContent.trim().length < 10) {
                    allBtns.push(btn.textContent.trim() + ' | ' + btn.className.substring(0, 60));
                }
            }
            return 'not found, visible buttons: ' + allBtns.join('; ');
        """)
        logger.info(f"发送结果: {sent}")
        time.sleep(3)

        # 检查拦截到的请求
        logger.info("=" * 60)
        logger.info("拦截到的AJAX请求")
        logger.info("=" * 60)

        ajax_log = driver.execute_script("return window.__ajax_log;")
        if ajax_log:
            for req in ajax_log:
                logger.info(f"  {req['method']} {req['url']}")
                logger.info(f"    headers: {json.dumps(req.get('headers', {}), ensure_ascii=False)}")
                logger.info(f"    body: {req.get('body', '')}")
        else:
            logger.info("  没有拦截到AJAX请求")

        # 再截图看最终状态
        driver.save_screenshot("data/debug_reply_result.png")
        logger.info("最终截图: data/debug_reply_result.png")

    finally:
        scraper.stop()


if __name__ == "__main__":
    main()
