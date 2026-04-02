"""
V4功能调试脚本：自动回复评论（Selenium版）

逐项测试：
1. 配置加载（reply相关配置）
2. Selenium抓取评论收件箱
3. AI生成回复（直接评论 + 楼中楼场景）
4. 记录存储
"""

import sys
import os

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.utils.config_loader import config
from src.utils.rip_provider import get_rip
from src.auth.login_manager import get_valid_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.reply.reply_fetcher import fetch_comments_to_me
from src.reply.reply_generator import generate_reply
from src.storage.record_store import record_store


def test_config():
    """测试1: 配置加载"""
    logger.info("=" * 60)
    logger.info("[TEST 1] Reply配置加载")
    logger.info("=" * 60)

    items = {
        "reply_enabled": config.reply_enabled,
        "reply_daily_limit": config.reply_daily_limit,
        "reply_poll_min": config.reply_poll_min,
        "reply_poll_max": config.reply_poll_max,
        "reply_delay_min": config.reply_delay_min,
        "reply_delay_max": config.reply_delay_max,
        "reply_prompt_name": config.reply_prompt_name,
    }
    for k, v in items.items():
        logger.info(f"  {k}: {v}")

    prompt = config.get_prompt(config.reply_prompt_name)
    logger.info(f"  prompt长度: {len(prompt)} 字符")

    logger.info("[TEST 1] PASS")
    return True


def test_fetch_comments(driver, my_uid):
    """测试2: Selenium抓取评论收件箱"""
    logger.info("=" * 60)
    logger.info("[TEST 2] Selenium抓取评论收件箱")
    logger.info("=" * 60)

    comments = fetch_comments_to_me(driver=driver, scroll_times=2)

    if not comments:
        logger.warning("没有获取到评论")
        return []

    # 过滤掉自己的评论
    my_uid_str = str(my_uid)
    filtered = [c for c in comments if c["comment_user_id"] != my_uid_str]
    if len(filtered) < len(comments):
        logger.info(f"过滤掉 {len(comments) - len(filtered)} 条自己的评论")

    logger.info(f"获取到 {len(filtered)} 条他人评论：")
    for i, c in enumerate(filtered[:10]):
        reply_tag = " [楼中楼]" if c.get("reply_comment_text") else ""
        logger.info(f"  [{i+1}]{reply_tag} @{c['comment_user_name']} (cid={c['comment_id']})")
        logger.info(f"       评论: {c['comment_text'][:60]}")
        logger.info(f"       微博: {c['weibo_text'][:60]}")
        if c.get("reply_comment_text"):
            logger.info(f"       被回复: {c['reply_comment_text'][:60]}")

    logger.info("[TEST 2] PASS")
    return filtered


def test_generate_reply(comments):
    """测试3: AI生成回复"""
    logger.info("=" * 60)
    logger.info("[TEST 3] AI生成回复")
    logger.info("=" * 60)

    if not comments:
        logger.info("无真实评论，使用模拟数据测试...")

        logger.info("\n--- 场景A: 直接评论 ---")
        reply_a = generate_reply(
            weibo_text="今天天气真好，出去走走",
            comment_text="好羡慕啊，我还在加班",
        )
        if reply_a:
            logger.info(f"  生成回复: {reply_a}")
        else:
            logger.error("  回复生成失败")
            return False

        logger.info("\n--- 场景B: 楼中楼回复 ---")
        reply_b = generate_reply(
            weibo_text="今天天气真好，出去走走",
            comment_text="哈哈去哪里玩了",
            reply_comment_text="好羡慕啊，我还在加班",
        )
        if reply_b:
            logger.info(f"  生成回复: {reply_b}")
        else:
            logger.error("  回复生成失败")
            return False

        logger.info("[TEST 3] PASS (模拟数据)")
        return True

    # 使用真实评论测试
    success = 0
    test_count = min(3, len(comments))
    for c in comments[:test_count]:
        reply_tag = "楼中楼" if c.get("reply_comment_text") else "直接评论"
        logger.info(f"\n--- [{reply_tag}] @{c['comment_user_name']}: {c['comment_text'][:40]} ---")

        reply = generate_reply(
            weibo_text=c["weibo_text"],
            comment_text=c["comment_text"],
            reply_comment_text=c.get("reply_comment_text"),
        )
        if reply:
            logger.info(f"  生成回复: {reply}")
            success += 1
        else:
            logger.warning(f"  回复生成失败")

    logger.info(f"\n回复生成: {success}/{test_count} 成功")
    if success > 0:
        logger.info("[TEST 3] PASS")
        return True
    else:
        logger.error("[TEST 3] FAIL")
        return False


def test_record_store():
    """测试4: 记录存储"""
    logger.info("=" * 60)
    logger.info("[TEST 4] 回复记录存储")
    logger.info("=" * 60)

    logger.info(f"  当前since_id: {record_store.get_reply_since_id()}")
    logger.info(f"  今日回复数: {record_store.get_reply_today_count()}")
    logger.info(f"  is_replied('999999'): {record_store.is_replied('999999')}")

    logger.info("[TEST 4] PASS")
    return True


def main():
    logger.info("=" * 60)
    logger.info("V4 功能验证: 自动回复评论 (Selenium版)")
    logger.info("=" * 60)

    # 初始化认证
    rip = get_rip()
    if not rip:
        logger.error("无法获取公网IP")
        return
    logger.info(f"公网IP: {rip}")

    cookies = get_valid_cookies()
    if not cookies:
        logger.error("Cookie无效")
        return
    logger.info("Cookie验证通过 ✓")

    access_token = get_valid_token()
    if not access_token:
        logger.error("OAuth失败")
        return
    my_uid = get_uid(access_token)
    logger.info(f"OAuth认证通过 ✓ (UID: {my_uid})")

    # 启动Selenium
    scraper = WeiboScraper()
    scraper.start()
    logger.info("Selenium浏览器启动 ✓")

    results = {}

    try:
        # TEST 1: 配置
        results["config"] = test_config()

        # TEST 2: Selenium抓取评论
        comments = test_fetch_comments(scraper.driver, my_uid)
        results["fetch"] = len(comments) > 0

        # TEST 3: AI生成回复
        results["generate"] = test_generate_reply(comments)

        # TEST 4: 记录存储
        results["record"] = test_record_store()

    finally:
        scraper.stop()

    # 汇总
    logger.info("=" * 60)
    logger.info("测试结果汇总：")
    for name, passed in results.items():
        status = "PASS ✓" if passed else "FAIL ✗" if passed is False else "SKIP -"
        logger.info(f"  {name}: {status}")
    logger.info("=" * 60)

    all_pass = all(v is not False for v in results.values())
    if all_pass:
        logger.info("V4功能验证通过！可以运行 python run_reply.py 启动自动回复")
    else:
        logger.warning("部分测试未通过，请检查日志")


if __name__ == "__main__":
    main()
