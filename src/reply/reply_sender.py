"""
回复评论发送模块

支持两种回复方式：
1. UI模拟方式（推荐）：在收件箱页面点击回复按钮 → 弹窗输入 → 发送，由前端处理正确的评论ID
2. API方式（fallback）：直接构造AJAX请求发送回复
"""

import time
import json

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.comment.publisher import RateLimitError
from src.utils.logger import logger

COMMENT_REPLY_URL = "https://www.weibo.com/ajax/comments/reply"


def send_reply(driver, weibo_mid, comment_id, reply_text, root_comment_id=None, **_kwargs):
    """
    通过微博网页AJAX接口回复指定评论。

    参数：
        driver: Selenium WebDriver 实例（需已登录微博）
        weibo_mid: 微博ID
        comment_id: 要回复的评论ID
        reply_text: 回复内容
        root_comment_id: 楼中楼时的根评论ID（可选）。
            传入时：cid=root_comment_id, reply_id=comment_id（回复子评论）
            不传时：cid=comment_id（回复根评论）

    返回：
        成功返回API响应dict，失败返回None
    """
    try:
        safe_comment = _js_escape(reply_text)
        safe_mid = _js_escape(str(weibo_mid))

        # 楼中楼：cid=根评论ID, reply_id=子评论ID
        # 直接评论：cid=评论ID, reply_id=评论ID
        if root_comment_id:
            safe_cid = _js_escape(str(root_comment_id))
            safe_reply_id = _js_escape(str(comment_id))
        else:
            safe_cid = _js_escape(str(comment_id))
            safe_reply_id = safe_cid

        result = driver.execute_script(f"""
            try {{
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '{COMMENT_REPLY_URL}', false);
                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                xhr.setRequestHeader('client-version', '3.0.0');
                xhr.setRequestHeader('server-version', 'v2026.04.03.1');
                var xsrf = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
                if (xsrf) {{
                    xhr.setRequestHeader('X-XSRF-TOKEN', decodeURIComponent(xsrf[1]));
                }}
                var params = 'id={safe_mid}&cid={safe_cid}&reply_id={safe_reply_id}&comment=' + encodeURIComponent('{safe_comment}') + '&pic_id=&is_repost=0&comment_ori=0&is_comment=0';
                xhr.send(params);
                return JSON.stringify({{status: xhr.status, body: xhr.responseText}});
            }} catch(e) {{
                return JSON.stringify({{status: 0, body: e.message}});
            }}
        """)

        if not result:
            logger.error("回复发送失败：浏览器未返回结果")
            return None

        resp = json.loads(result)
        status = resp.get("status", 0)
        body_text = resp.get("body", "")

        if status == 200:
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                logger.error(f"回复响应解析失败: {body_text[:200]}")
                return None

            if "id" in body:
                logger.info(f"回复发送成功！评论ID: {comment_id}, 回复ID: {body['id']}")
                return body
            elif body.get("ok") == 1:
                logger.info(f"回复发送成功！评论ID: {comment_id}, msg: {body.get('msg', '')}")
                return body
            else:
                error_code = body.get("error_code", body.get("errno", "未知"))
                error_msg = body.get("error", body.get("msg", "未知错误"))
                logger.error(f"回复发送失败 - 错误码: {error_code}, 信息: {error_msg}")
                return None
        elif status == 403:
            logger.warning("回复发送被拒绝(403)，可能触发频率限制")
            raise RateLimitError("回复频率限制: HTTP 403")
        elif status == 414:
            logger.warning("回复发送触发频率限制(414)")
            raise RateLimitError("回复频率限制: HTTP 414")
        else:
            logger.error(f"回复发送HTTP错误: {status}, 响应: {body_text[:200]}")
            return None

    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"回复发送异常: {e}")
        return None


def _js_escape(text):
    """转义文本用于嵌入JS字符串（单引号包裹）"""
    return (text
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "\\r"))


def send_reply_via_ui(driver, comment_user_name, comment_text_snippet, reply_text):
    """
    通过UI模拟方式在收件箱页面回复评论。

    在当前inbox页面找到匹配的评论卡片，点击footer的"回复"按钮打开弹窗，
    输入回复内容并发送。由微博前端处理正确的评论ID参数。

    参数：
        driver: Selenium WebDriver 实例（需当前页面为 comment/inbox）
        comment_user_name: 评论者昵称（用于匹配卡片）
        comment_text_snippet: 评论内容前30字（用于匹配卡片）
        reply_text: 回复内容

    返回：
        成功返回 True，失败返回 None
    """
    try:
        safe_user = _js_escape(comment_user_name)
        safe_snippet = _js_escape(comment_text_snippet)

        # 确保当前在inbox页面
        current_url = driver.current_url
        if "comment/inbox" not in current_url:
            logger.info("当前不在收件箱页面，重新导航...")
            driver.get("https://www.weibo.com/comment/inbox")
            time.sleep(4)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.wbpro-scroller-item"))
            )

        # Step 1: 找到匹配的卡片并点击footer回复按钮
        click_result = driver.execute_script(f"""
            var cards = document.querySelectorAll('div.wbpro-scroller-item');
            var targetUser = '{safe_user}';
            var targetSnippet = '{safe_snippet}';

            for (var i = 0; i < cards.length; i++) {{
                var card = cards[i];

                // 匹配用户名
                var nameEl = card.querySelector('[class*="_h3_"] a');
                if (!nameEl) continue;
                var userName = nameEl.textContent.trim();
                if (userName !== targetUser) continue;

                // 匹配评论文本（前N字）
                var textEl = card.querySelector('[class*="_wbtext_"]');
                if (!textEl) continue;
                var cardText = textEl.textContent.trim();
                // 去掉"回复@xxx:"前缀后匹配
                var cleanText = cardText.replace(/^回复@[^:：]+[:：]/, '').trim();
                if (!cleanText.startsWith(targetSnippet) && !cardText.includes(targetSnippet)) continue;

                // 找到匹配卡片，点击footer的回复按钮
                var commentIcon = card.querySelector('i[class*="_commentIcon_"]');
                if (!commentIcon) return 'ERROR:card_found_but_no_reply_icon';

                var wrapDiv = commentIcon.closest('[class*="_wrap_"]');
                if (wrapDiv) {{
                    wrapDiv.click();
                    return 'OK:' + i;
                }}
                commentIcon.click();
                return 'OK_ICON:' + i;
            }}
            return 'ERROR:card_not_found';
        """)

        if not click_result or click_result.startswith("ERROR:"):
            logger.error(f"UI回复失败 - 找不到匹配卡片: user={comment_user_name}, text={comment_text_snippet}, result={click_result}")
            return None

        logger.debug(f"点击回复按钮: {click_result}")

        # Step 2: 等待textarea弹窗出现
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea"))
            )
        except Exception:
            logger.error("UI回复失败 - 回复弹窗未出现")
            return None

        # 额外等待弹窗动画
        time.sleep(0.5)

        # Step 3: 用Selenium原生方式输入（触发React状态更新）
        textareas = driver.find_elements(By.CSS_SELECTOR, "textarea")
        target_ta = None
        for ta in textareas:
            if ta.is_displayed():
                target_ta = ta
                break

        if not target_ta:
            logger.error("UI回复失败 - 未找到可见的textarea")
            return None

        target_ta.click()
        target_ta.clear()
        target_ta.send_keys(reply_text)
        time.sleep(0.5)

        # Step 4: 点击发送按钮（文字为"回复"且class含flat的button）
        send_result = driver.execute_script("""
            var btns = document.querySelectorAll('button');
            for (var btn of btns) {
                var rect = btn.getBoundingClientRect();
                var text = btn.textContent.trim();
                if (rect.height > 0 && text === '回复'
                    && btn.className.includes('flat')
                    && btn.className.includes('primary')) {
                    btn.click();
                    return 'OK';
                }
            }
            return 'ERROR:send_button_not_found';
        """)

        if send_result != "OK":
            logger.error(f"UI回复失败 - 发送按钮未找到: {send_result}")
            return None

        # Step 5: 等待发送完成（弹窗关闭 / textarea消失）
        time.sleep(3)

        # 检查textarea是否已消失（弹窗关闭 = 发送成功）
        visible_ta = driver.execute_script("""
            var tas = document.querySelectorAll('textarea');
            for (var ta of tas) {
                var rect = ta.getBoundingClientRect();
                if (rect.height > 0) return true;
            }
            return false;
        """)

        if visible_ta:
            # textarea仍在，可能发送失败，但也可能是弹窗没有自动关闭
            logger.warning("UI回复 - 弹窗未自动关闭，尝试关闭弹窗")
            # 点击弹窗关闭按钮（如果有）
            driver.execute_script("""
                var closeBtn = document.querySelector('[class*="woo-dialog"] [class*="close"]')
                    || document.querySelector('[class*="modal"] [class*="close"]');
                if (closeBtn) closeBtn.click();
            """)
            time.sleep(0.5)

        logger.info(f"UI回复发送完成: @{comment_user_name}")
        return True

    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"UI回复异常: {e}")
        return None
