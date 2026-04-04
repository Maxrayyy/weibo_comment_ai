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

def _build_messages(weibo_text, pic_url=None):
    """构建消息列表（单阶段隐式判断，无需外部指定风格）"""
    system_prompt = config.get_prompt(config.base_prompt_name).strip()

    # 有图片时追加图片评论指引
    if pic_url:
        system_prompt += (
            "\n\n## 图片相关\n"
            "如果微博配了图片，可以自然地评论图片中的内容（表情、场景、食物等），\n"
            "不要说\"从图片中可以看到\"这种分析式的话，就像朋友发了张图你随口接一句。"
        )

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

    # 有图片时使用多模态格式，无图片用纯文本
    if pic_url:
        user_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": pic_url}},
        ]
    else:
        user_content = user_prompt

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
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


def generate_comment(weibo_text, pic_url=None, prompt_name=None, max_retries=3):
    """
    根据微博内容生成评论（单阶段隐式判断，支持多模态图片输入）。

    参数：
        weibo_text: 微博正文内容
        pic_url: 微博第一张图片URL（可选，传入则使用多模态生成）
        prompt_name: 已废弃，保留参数兼容性
        max_retries: 最大重试次数

    返回：
        评论文本字符串，失败返回None
    """
    # 有图片时使用多模态模型，无图片用纯文字模型
    if pic_url:
        client = OpenAI(
            api_key=config.multimodal_api_key,
            base_url=config.multimodal_base_url,
        )
        model = config.multimodal_model
        max_tokens = config.multimodal_max_tokens
    else:
        client = OpenAI(
            api_key=config.text_api_key,
            base_url=config.text_base_url,
        )
        model = config.text_model
        max_tokens = config.text_max_tokens

    for attempt in range(max_retries):
        try:
            messages = _build_messages(weibo_text, pic_url=pic_url)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
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
