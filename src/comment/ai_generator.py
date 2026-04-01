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
_STYLE_VARIANTS = [
    "直接说感受，像'好想…''受不了…''绝了'这样",
    "用反问句，像'不是吧''谁懂啊''还有这种事？'",
    "简短回复，五六个字就够",
    "认真一点回复，像朋友之间的对话",
    "表达共鸣，像'我也是''一模一样''被说中了'",
    "调侃或开玩笑，带点损但不伤人",
    "表达羡慕或向往，像'好羡慕''什么时候轮到我'",
    "像在接对方的话往下说，像在聊天",
    "吐槽，像'离谱''服了''无语'这种风格",
    "用省略号或感叹号表达情绪，像'啊…''！！！'",
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
    base_prompt = config.get_prompt(config.base_prompt_name)
    style_prompt = config.get_prompt(prompt_name)

    identity = random.choice(_IDENTITY_VARIANTS)

    # 随机选一个多样性修饰
    variant = random.choice(_STYLE_VARIANTS)

    system_prompt = f"""
    {base_prompt}

    你的当前状态：
    {identity}

    {style_prompt}

    额外要求：{variant}
    """.strip()

    # 注入近期评论，引导模型避免雷同
    user_prompt = f"微博内容：\n{weibo_text}\n\n请直接给出评论，不要解释。"
    if _recent_comments:
        recent = list(_recent_comments)[-5:]  # 最近5条
        avoid_text = "、".join(f'"{c[:8]}"' for c in recent)
        # 提取近期评论的开头字，显式要求避开
        recent_starts = set(c[0] for c in recent if c)
        avoid_starts = "".join(recent_starts)
        user_prompt += f'\n\n注意：不要和这些已有评论风格雷同：{avoid_text}。不要用\u201c{avoid_starts}\u201d中的任何字开头。'

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
