"""
Qwen大模型评论生成器

使用OpenAI SDK（兼容Qwen API）根据微博内容生成自然评论。
"""

import random
from collections import deque

from openai import OpenAI

from src.utils.config_loader import config
from src.utils.logger import logger

# 记录最近的评论，用于去重
_recent_comments = deque(maxlen=20)

# 多样性修饰词，随机附加到prompt中
_style_variants = [
    "这次语气更轻松一些",
    "这次可以带一点感叹",
    "这次用比较简短的方式回复",
    "这次稍微认真一点回复",
    "这次可以用反问的语气",
    "这次表达一下共鸣",
    "这次可以开个小玩笑",
    "这次表示羡慕或者向往",
]

_IDENTITY_VARIANTS = [
    "你是刚刷到这条微博的路人",
    "你是深夜刷微博的用户",
    "你是在评论区潜水已久的人",
    "你是看完忍不住想说一句的网友",
    "你是刷到这条内容有点共鸣的人",
]

def _build_messages(weibo_text, prompt_name=None):
    """构建Qwen API的消息列表"""
    base_prompt = config.get_prompt("weibo_base")
    style_prompt = config.get_prompt(prompt_name)

    identity = random.choice(_IDENTITY_VARIANTS)

    system_prompt = f"""
    {base_prompt}

    你的当前状态：
    {identity}

    {style_prompt}
    """.strip()

    # 随机加入多样性修饰
    # variant = random.choice(_style_variants)
    # system_prompt += f"\n额外要求：{variant}。"

    #user_prompt = f"请对以下微博内容生成一条自然的评论：\n\n{weibo_text}"
    user_prompt = f"微博内容：\n{weibo_text}\n\n请直接给出评论，不要解释。"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _is_duplicate(comment):
    """检查评论是否与最近的评论重复或相似度过高"""
    for recent in _recent_comments:
        if comment == recent:
            return True
        # 简单的相似度检查：如果前10个字相同就认为重复
        if len(comment) >= 10 and len(recent) >= 10 and comment[:10] == recent[:10]:
            return True
    return False


def _validate_comment(comment):
    """验证评论内容是否合规"""
    if not comment or not comment.strip():
        return False
    # 长度检查：不超过140字
    if len(comment) > 140:
        return False
    # 不应该包含明显的AI痕迹
    ai_markers = ["作为AI", "作为一个AI", "我是AI", "语言模型", "我无法"]
    for marker in ai_markers:
        if marker in comment:
            return False
    return True


def generate_comment(weibo_text, prompt_name=None, max_retries=3):
    """
    根据微博内容生成评论。

    参数：
        weibo_text: 微博正文内容
        prompt_name: 评论风格名称，None则使用默认风格
        max_retries: 最大重试次数

    返回：
        评论文本字符串，失败返回None
    """
    client = OpenAI(
        api_key=config.qwen_api_key,
        base_url=config.qwen_base_url,
    )

    for attempt in range(max_retries):
        try:
            messages = _build_messages(weibo_text, prompt_name)
            response = client.chat.completions.create(
                model=config.qwen_model,
                messages=messages,
                max_tokens=config.qwen_max_tokens,
                temperature=0.9,  # 高温度增加多样性
            )

            comment = response.choices[0].message.content.strip()

            # 去除可能的引号包裹
            if comment.startswith('"') and comment.endswith('"'):
                comment = comment[1:-1]
            if comment.startswith("'") and comment.endswith("'"):
                comment = comment[1:-1]

            # 截断超长评论
            if len(comment) > 140:
                comment = comment[:137] + "..."

            # 合规检查
            if not _validate_comment(comment):
                logger.warning(f"生成的评论不合规，重试（第{attempt + 1}次）: {comment}")
                continue

            # 去重检查
            if _is_duplicate(comment):
                logger.warning(f"生成的评论与近期评论重复，重试（第{attempt + 1}次）")
                continue

            _recent_comments.append(comment)
            logger.info(f"评论生成成功: {comment}")
            return comment

        except Exception as e:
            logger.error(f"调用Qwen API失败（第{attempt + 1}次）: {e}")

    logger.error(f"评论生成失败，已重试{max_retries}次")
    return None
