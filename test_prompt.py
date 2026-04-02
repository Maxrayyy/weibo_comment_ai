"""测试隐式判断 prompt 的评论生成效果"""

from src.comment.ai_generator import generate_comment
from src.utils.logger import logger

test_weibos = [
    "幸福就是打开一本新书时发现：哇 完全是我的菜",
    "无论如何，生命都会重新开始。",
    "很不喜欢团内无cp就硬把剩下的两个人凑一起的行为",
    "今天去吃了一家超好吃的火锅！！锅底绝了 牛肉卷入口即化",
    "加班到凌晨两点…回家路上一个人都没有…好累啊",
    "什么时候能取下扩弓器啊",
    "突然翻到大学时候的照片 那时候真好啊 无忧无虑的",
]

if __name__ == "__main__":
    for i, weibo in enumerate(test_weibos, 1):
        logger.info(f"=== 测试 {i} ===")
        logger.info(f"原文：{weibo}")
        comment = generate_comment(weibo)
        logger.info(f"评论：{comment}")
        logger.info("")
    logger.info("测试完成")
