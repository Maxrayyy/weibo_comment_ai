"""A/B测试：对比 prompt × model 四种组合"""

import time
from src.utils.config_loader import config
from src.utils.logger import logger
from openai import OpenAI

test_weibos = [
    "幸福就是打开一本新书时发现：哇 完全是我的菜",
    "无论如何，生命都会重新开始。",
    "很不喜欢团内无cp就硬把剩下的两个人凑一起的行为",
    "今天去吃了一家超好吃的火锅！！锅底绝了 牛肉卷入口即化",
    "加班到凌晨两点…回家路上一个人都没有…好累啊",
    "什么时候能取下扩弓器啊",
    "突然翻到大学时候的照片 那时候真好啊 无忧无虑的",
]

PROMPTS = ["weibo_base", "weibo_friend"]
MODELS = ["qwen3.5-flash", "qwen3.5-plus"]


def generate(weibo_text, prompt_name, model):
    """用指定prompt和model生成评论"""
    client = OpenAI(
        api_key=config.generate_api_key,
        base_url=config.generate_base_url,
    )
    system_prompt = config.get_prompt(prompt_name).strip()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"微博内容：\n{weibo_text}\n\n请直接给出评论，不要解释。"},
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=config.generate_max_tokens,
        temperature=0.89,
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    combos = [(p, m) for p in PROMPTS for m in MODELS]
    # 标签简写
    labels = {
        ("weibo_base", "qwen3.5-flash"): "base+flash",
        ("weibo_base", "qwen3.5-plus"): "base+plus",
        ("weibo_friend", "qwen3.5-flash"): "friend+flash",
        ("weibo_friend", "qwen3.5-plus"): "friend+plus",
    }

    for i, weibo in enumerate(test_weibos, 1):
        logger.info(f"=== 测试 {i} ===")
        logger.info(f"原文：{weibo}")
        for prompt_name, model in combos:
            label = labels[(prompt_name, model)]
            try:
                start = time.time()
                comment = generate(weibo, prompt_name, model)
                elapsed = time.time() - start
                logger.info(f"  [{label}] ({elapsed:.1f}s) {comment}")
            except Exception as e:
                logger.error(f"  [{label}] 生成失败: {e}")
        logger.info("")
    logger.info("A/B测试完成（4组对比）")
