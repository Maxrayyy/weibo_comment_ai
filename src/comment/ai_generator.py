"""
大模型评论生成器

单阶段隐式判断：一次调用，模型自主感受微博氛围，
边判断接话方式、边生成评论，不输出分析过程。
"""

from collections import deque

from openai import OpenAI

from src.utils.config_loader import config
from src.utils.logger import logger
from src.emotion.emotion_manager import get_emotion_prompt_text

# 记录最近的评论，用于去重
_recent_comments = deque(maxlen=20)

def _build_messages(weibo_text):
    """构建消息列表（单阶段隐式判断，无需外部指定风格）"""
    system_prompt = config.get_prompt(config.base_prompt_name).strip()

    user_prompt = f"微博内容：\n{weibo_text}\n\n请直接给出评论，不要解释。"

    # 注入可用表情列表
    emotion_hint = get_emotion_prompt_text()
    if emotion_hint:
        user_prompt += emotion_hint

    # 注入近期评论引导多样性
    if _recent_comments:
        recent = list(_recent_comments)[-5:]
        avoid_text = "、".join(f'"{c[:8]}"' for c in recent)
        recent_starts = set(c[0] for c in recent if c)
        avoid_starts = "".join(recent_starts)
        user_prompt += f'\n\n注意：不要和这些已有评论雷同：{avoid_text}。不要用"{avoid_starts}"中的任何字开头。'

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _is_duplicate(comment):
    """检查评论是否与最近的评论重复或相似度过高"""
    for recent in _recent_comments:
        if comment == recent:
            return True
        if len(comment) >= 10 and len(recent) >= 10 and comment[:10] == recent[:10]:
            return True
    return False


MIN_COMMENT_LENGTH = 12


def _validate_comment(comment):
    """验证评论内容是否合规"""
    if not comment or not comment.strip():
        return False
    if len(comment) < MIN_COMMENT_LENGTH:
        return False
    if len(comment) > 140:
        return False
    ai_markers = ["作为AI", "作为一个AI", "我是AI", "语言模型", "我无法"]
    for marker in ai_markers:
        if marker in comment:
            return False
    return True


def generate_comment(weibo_text, prompt_name=None, max_retries=3):
    """
    根据微博内容生成评论（单阶段隐式判断）。

    参数：
        weibo_text: 微博正文内容
        prompt_name: 已废弃，保留参数兼容性
        max_retries: 最大重试次数

    返回：
        评论文本字符串，失败返回None
    """
    client = OpenAI(
        api_key=config.generate_api_key,
        base_url=config.generate_base_url,
    )

    for attempt in range(max_retries):
        try:
            messages = _build_messages(weibo_text)
            response = client.chat.completions.create(
                model=config.generate_model,
                messages=messages,
                max_tokens=config.generate_max_tokens,
                temperature=0.89,
            )

            comment = response.choices[0].message.content.strip()

            # 去除可能的引号包裹
            if comment.startswith('"') and comment.endswith('"'):
                comment = comment[1:-1]
            if comment.startswith("'") and comment.endswith("'"):
                comment = comment[1:-1]

            if len(comment) > 140:
                comment = comment[:137] + "..."

            if not _validate_comment(comment):
                logger.warning(f"生成的评论不合规，重试（第{attempt + 1}次）: {comment}")
                continue

            if _is_duplicate(comment):
                logger.warning(f"生成的评论与近期评论重复，重试（第{attempt + 1}次）")
                continue

            _recent_comments.append(comment)
            logger.info(f"评论生成成功: {comment}")
            return comment

        except Exception as e:
            logger.error(f"调用LLM API失败（第{attempt + 1}次）: {e}")

    logger.error(f"评论生成失败，已重试{max_retries}次")
    return None
