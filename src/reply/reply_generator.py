"""
回复评论生成器

根据微博原文和评论内容，生成针对性的回复。
"""

from collections import deque

from openai import OpenAI

from src.utils.config_loader import config
from src.utils.logger import logger
from src.emotion.emotion_manager import get_emotion_prompt_text

_recent_replies = deque(maxlen=20)


def _build_messages(weibo_text, comment_text, reply_comment_text=None):
    """构建回复场景的消息列表"""
    system_prompt = config.get_prompt(config.reply_prompt_name).strip()

    # 构建用户消息
    parts = [f"我的微博原文：\n{weibo_text}"]

    if reply_comment_text:
        # 楼中楼场景：别人回复了我的评论
        parts.append(f"\n我之前的评论：\n{reply_comment_text}")
        parts.append(f"\n对方回复：\n{comment_text}")
        parts.append("\n请回复对方的这条回复，不要解释。")
    else:
        # 直接评论场景：别人评论了我的微博
        parts.append(f"\n对方评论：\n{comment_text}")
        parts.append("\n请回复这条评论，不要解释。")

    user_prompt = "".join(parts)

    # 注入表情
    emotion_hint = get_emotion_prompt_text()
    if emotion_hint:
        user_prompt += emotion_hint

    # 注入近期回复引导多样性
    if _recent_replies:
        recent = list(_recent_replies)[-5:]
        avoid_text = "、".join(f'"{r[:8]}"' for r in recent)
        user_prompt += f"\n\n注意：不要和这些已有回复雷同：{avoid_text}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _is_duplicate(reply):
    """检查回复是否与近期回复重复"""
    for recent in _recent_replies:
        if reply == recent:
            return True
        if len(reply) >= 8 and len(recent) >= 8 and reply[:8] == recent[:8]:
            return True
    return False


MIN_REPLY_LENGTH = 4


def _validate_reply(reply):
    """验证回复内容是否合规"""
    if not reply or not reply.strip():
        return False
    if len(reply) < MIN_REPLY_LENGTH:
        return False
    if len(reply) > 140:
        return False
    ai_markers = ["作为AI", "作为一个AI", "我是AI", "语言模型", "我无法"]
    for marker in ai_markers:
        if marker in reply:
            return False
    return True


def generate_reply(weibo_text, comment_text, reply_comment_text=None, max_retries=3):
    """
    根据微博内容和评论内容生成回复。

    参数：
        weibo_text: 微博原文
        comment_text: 需要回复的评论
        reply_comment_text: 楼中楼场景下被回复的原始评论（可选）
        max_retries: 最大重试次数

    返回：
        回复文本字符串，失败返回None
    """
    client = OpenAI(
        api_key=config.generate_api_key,
        base_url=config.generate_base_url,
    )

    for attempt in range(max_retries):
        try:
            messages = _build_messages(weibo_text, comment_text, reply_comment_text)
            response = client.chat.completions.create(
                model=config.generate_model,
                messages=messages,
                max_tokens=config.generate_max_tokens,
                temperature=0.89,
            )

            reply = response.choices[0].message.content.strip()

            # 去除可能的引号包裹
            if reply.startswith('"') and reply.endswith('"'):
                reply = reply[1:-1]
            if reply.startswith("'") and reply.endswith("'"):
                reply = reply[1:-1]

            if len(reply) > 140:
                reply = reply[:137] + "..."

            if not _validate_reply(reply):
                logger.warning(f"生成的回复不合规，重试（第{attempt + 1}次）: {reply}")
                continue

            if _is_duplicate(reply):
                logger.warning(f"生成的回复与近期回复重复，重试（第{attempt + 1}次）")
                continue

            _recent_replies.append(reply)
            logger.info(f"回复生成成功: {reply}")
            return reply

        except Exception as e:
            logger.error(f"调用LLM API失败（第{attempt + 1}次）: {e}")

    logger.error(f"回复生成失败，已重试{max_retries}次")
    return None
