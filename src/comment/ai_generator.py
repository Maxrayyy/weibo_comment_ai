"""
Qwen大模型评论生成器

两阶段生成：
1. 分析微博内容（情绪、语气、句式、话题）
2. 根据分析结果动态构建prompt，生成个性化评论
"""

import json
import random
from collections import deque

from openai import OpenAI

from src.utils.config_loader import config
from src.utils.logger import logger

# 记录最近的评论，用于去重
_recent_comments = deque(maxlen=20)

# ===== 第一阶段：微博分析 =====

_ANALYZE_PROMPT = """你是一个微博内容分析器。分析以下微博，返回JSON格式结果。

必须严格返回以下JSON格式，不要有任何其他内容：
{
  "emotion": "情绪类型",
  "tone": "语气风格",
  "style": "句式特征",
  "topic": "话题类型",
  "strategy": "建议的回复策略"
}

各字段取值说明：
- emotion: happy/sad/angry/nostalgic/complain/show_off/curious/tired/excited/amused/neutral
  注意：有趣搞笑的内容用amused，不要用tired；炫耀好事用show_off或excited
- tone: casual/serious/humorous/sarcastic/cute/melancholy/energetic
- style: short_fragments/questions/exclamations/ellipsis/emoji_heavy/literary/conversational/mixed
- topic: daily/food/travel/work/emotion/entertainment/pets/study/sports/other
- strategy: 从以下选一个最合适的回复策略（注意匹配情绪）
  - empathy（共鸣共情）— 适合sad/tired/complain
  - humor（幽默调侃）— 适合amused/happy/日常趣事
  - envy（表达羡慕）— 适合show_off/excited的好事
  - comfort（安慰鼓励）— 适合sad/tired/complain
  - tease（损友式吐槽）— 适合amused/complain/日常吐槽
  - follow_up（接话往下聊）— 适合food/travel/日常分享
  - mimic（模仿对方句式回复）— 适合句式有特色的微博
  - surprise（表达惊讶）— 适合出人意料的内容"""


def _analyze_weibo(client, weibo_text):
    """
    第一阶段：分析微博内容。
    返回分析结果dict，失败返回None。
    """
    try:
        response = client.chat.completions.create(
            model=config.qwen_model,
            messages=[
                {"role": "system", "content": _ANALYZE_PROMPT},
                {"role": "user", "content": weibo_text},
            ],
            max_tokens=200,
            temperature=0.3,  # 低温度保证分析稳定
        )
        result_text = response.choices[0].message.content.strip()

        # 提取JSON（可能被包裹在```json```中）
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        analysis = json.loads(result_text)
        logger.debug(f"微博分析结果: {analysis}")
        return analysis

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"微博分析失败，使用默认策略: {e}")
        return None


# ===== 第二阶段：动态Prompt构建 =====

# 回复策略 → 具体指令
_STRATEGY_INSTRUCTIONS = {
    "empathy": "表达强烈共鸣，像'我也是''完全懂这种感觉''被说中了'。用相似的情绪回应。",
    "humor": "用幽默的方式回复，可以调侃、玩梗、夸张化。让人看了想笑。",
    "envy": "表达羡慕或向往，像'好羡慕''什么时候轮到我''酸了'。可以带点戏剧化。",
    "comfort": "温柔地安慰或鼓励，但不要说教。像朋友拍拍肩膀，简短真诚。",
    "tease": "损友式吐槽，带点毒舌但不伤人。像关系很好的朋友才会说的话。",
    "follow_up": "像在接对方的话继续聊，自然地往下接。像对话的下一句。",
    "mimic": "模仿对方微博的句式和表达风格来回复，用相似的语气、标点、节奏。",
    "surprise": "表达惊讶或震惊，像'不是吧''啊？？''还有这种事'。",
}

# 情绪 → 补充指令
_EMOTION_HINTS = {
    "happy": "对方心情很好，回复要积极正面，可以一起嗨。",
    "sad": "对方心情低落，回复要温柔，不要讲大道理。",
    "angry": "对方在生气/愤怒，可以附和或帮腔，不要反驳。",
    "nostalgic": "对方在感慨怀旧，可以共情或分享类似感受。",
    "complain": "对方在抱怨吐槽，可以附和吐槽或调侃化解。",
    "show_off": "对方在炫耀/分享好事，可以捧场、羡慕或适度酸一下。",
    "curious": "对方在好奇/提问，可以一起好奇或给出有趣回应。",
    "tired": "对方很累/疲惫，简短安慰即可，不要长篇大论。",
    "excited": "对方很兴奋，回复也要有能量，一起激动。",
    "amused": "对方在分享有趣的事，回复要有趣味，可以哈哈大笑或接梗。",
}

# 句式 → 风格指令
_STYLE_HINTS = {
    "short_fragments": "用简短的碎片句回复，不要写完整长句。",
    "questions": "回复中也可以用反问或疑问句。",
    "exclamations": "多用感叹号表达情绪！",
    "ellipsis": "可以用省略号营造意犹未尽的感觉…",
    "emoji_heavy": "可以适当使用1-2个emoji，但不要堆砌。",
    "literary": "稍微文艺一点，但不要过度。",
    "conversational": "像在面对面聊天一样自然。",
}

_IDENTITY_VARIANTS = [
    "你是刚刷到这条微博的路人",
    "你是深夜刷微博的用户",
    "你是在评论区潜水已久的人",
    "你是看完忍不住想说一句的网友",
    "你是刷到这条内容有点共鸣的人",
]


def _build_messages(weibo_text, analysis=None, prompt_name=None):
    """根据分析结果动态构建消息列表"""
    base_prompt = config.get_prompt(config.base_prompt_name)
    style_prompt = config.get_prompt(prompt_name)
    identity = random.choice(_IDENTITY_VARIANTS)

    # 动态策略指令
    if analysis:
        strategy = analysis.get("strategy", "follow_up")
        emotion = analysis.get("emotion", "neutral")
        style = analysis.get("style", "mixed")

        strategy_instruction = _STRATEGY_INSTRUCTIONS.get(strategy, _STRATEGY_INSTRUCTIONS["follow_up"])
        emotion_hint = _EMOTION_HINTS.get(emotion, "")
        style_hint = _STYLE_HINTS.get(style, "")

        dynamic_section = f"""
    回复策略：{strategy_instruction}
    {f'情绪提示：{emotion_hint}' if emotion_hint else ''}
    {f'句式要求：{style_hint}' if style_hint else ''}"""
    else:
        # 分析失败时的降级：随机选策略（兼容旧逻辑）
        fallback_variants = [
            "直接说感受，像'好想…''受不了…''绝了'这样",
            "用反问句，像'不是吧''谁懂啊''还有这种事？'",
            "认真一点回复，像朋友之间的对话",
            "表达共鸣，像'我也是''一模一样''被说中了'",
            "调侃或开玩笑，带点损但不伤人",
            "像在接对方的话往下说，像在聊天",
            "吐槽，像'离谱''服了''无语'这种风格",
        ]
        dynamic_section = f"\n    额外要求：{random.choice(fallback_variants)}"

    system_prompt = f"""
    {base_prompt}

    你的当前状态：
    {identity}

    {style_prompt}
    {dynamic_section}
    """.strip()

    # 用户消息
    user_prompt = f"微博内容：\n{weibo_text}\n\n请直接给出评论，不要解释。"
    if _recent_comments:
        recent = list(_recent_comments)[-5:]
        avoid_text = "、".join(f'"{c[:8]}"' for c in recent)
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
    两阶段评论生成：先分析微博，再根据分析结果生成个性化评论。

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

    # 第一阶段：分析微博
    analysis = _analyze_weibo(client, weibo_text)
    if analysis:
        logger.info(f"微博分析: 情绪={analysis.get('emotion')} 策略={analysis.get('strategy')} "
                     f"句式={analysis.get('style')} 话题={analysis.get('topic')}")

    # 第二阶段：生成评论
    for attempt in range(max_retries):
        try:
            messages = _build_messages(weibo_text, analysis, prompt_name)
            response = client.chat.completions.create(
                model=config.qwen_model,
                messages=messages,
                max_tokens=config.qwen_max_tokens,
                temperature=0.9,
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
            logger.error(f"调用Qwen API失败（第{attempt + 1}次）: {e}")

    logger.error(f"评论生成失败，已重试{max_retries}次")
    return None
