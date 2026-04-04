import os
import re
import yaml

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")

_ENV_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env(value):
    """递归解析配置值中的 ${ENV_VAR} 占位符"""
    if isinstance(value, str):
        match = _ENV_PATTERN.fullmatch(value)
        if match:
            return os.environ.get(match.group(1), value)
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def _load_yaml(filename):
    filepath = os.path.join(CONFIG_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return _resolve_env(data)


class Config:
    """全局配置管理，加载 config.yaml 和 prompts.yaml"""

    def __init__(self):
        # 优先加载 config.prod.yaml（生产环境），不存在则回退到 config.yaml
        prod_path = os.path.join(CONFIG_DIR, "config.prod.yaml")
        config_file = "config.prod.yaml" if os.path.exists(prod_path) else "config.yaml"
        self._config = _load_yaml(config_file)
        self._prompts = _load_yaml("prompts.yaml")

    # --- 微博配置 ---
    @property
    def app_key(self):
        return self._config["weibo"]["app_key"]

    @property
    def app_secret(self):
        return self._config["weibo"]["app_secret"]

    @property
    def redirect_uri(self):
        return self._config["weibo"]["redirect_uri"]

    # --- LLM配置（纯文字 + 多模态） ---
    def _llm(self, mode):
        """获取指定模式的LLM配置"""
        return self._config.get("llm", {}).get(mode, {})

    @property
    def text_api_key(self):
        return self._llm("text").get("api_key", "")

    @property
    def text_base_url(self):
        return self._llm("text").get("base_url", "")

    @property
    def text_model(self):
        return self._llm("text").get("model", "")

    @property
    def text_max_tokens(self):
        return self._llm("text").get("max_tokens", 150)

    @property
    def multimodal_api_key(self):
        return self._llm("multimodal").get("api_key", "")

    @property
    def multimodal_base_url(self):
        return self._llm("multimodal").get("base_url", "")

    @property
    def multimodal_model(self):
        return self._llm("multimodal").get("model", "")

    @property
    def multimodal_max_tokens(self):
        return self._llm("multimodal").get("max_tokens", 150)

    # --- 策略配置 ---
    @property
    def strategy_mode(self):
        return self._config["strategy"]["mode"]

    @property
    def whitelist(self):
        return self._config["strategy"]["whitelist"]

    @property
    def blacklist(self):
        return self._config["strategy"]["blacklist"]

    @property
    def daily_limit(self):
        return self._config["strategy"]["daily_limit"]

    @property
    def skip_repost(self):
        return self._config["strategy"]["skip_repost"]

    @property
    def work_hour_start(self):
        return self._config["strategy"]["work_hours"]["start"]

    @property
    def work_hour_end(self):
        return self._config["strategy"]["work_hours"]["end"]

    # --- 时间配置 ---
    @property
    def poll_min(self):
        return self._config["timing"]["poll_min"]

    @property
    def poll_max(self):
        return self._config["timing"]["poll_max"]

    @property
    def comment_delay_min(self):
        return self._config["timing"]["comment_delay_min"]

    @property
    def comment_delay_max(self):
        return self._config["timing"]["comment_delay_max"]

    # --- 评论风格 ---
    @property
    def base_prompt_name(self):
        return self._config["base_prompt"]

    @property
    def default_prompt_name(self):
        return self._config["default_prompt"]

    def get_prompt(self, name=None):
        """获取评论风格prompt，默认返回配置中指定的风格"""
        name = name or self.default_prompt_name
        prompt_data = self._prompts.get(name)
        if not prompt_data:
            raise ValueError(f"未找到评论风格: {name}，可用: {list(self._prompts.keys())}")
        return prompt_data["system_prompt"]

    @property
    def available_prompts(self):
        return {k: v["name"] for k, v in self._prompts.items()
                if isinstance(v, dict) and "name" in v}

    # --- 好友圈配置 ---
    @property
    def friend_group_enabled(self):
        return self._config.get("friend_group", {}).get("enabled", False)

    @property
    def friend_group_gid(self):
        return self._config.get("friend_group", {}).get("gid", "")

    @property
    def friend_group_scroll_times(self):
        return self._config.get("friend_group", {}).get("scroll_times", 3)

    @property
    def friend_group_poll_min(self):
        return self._config.get("friend_group", {}).get("poll_min", 60)

    @property
    def friend_group_poll_max(self):
        return self._config.get("friend_group", {}).get("poll_max", 120)

    # --- 回复评论配置 ---
    def _reply_config(self):
        return self._config.get("reply", {})

    @property
    def reply_enabled(self):
        return self._reply_config().get("enabled", False)

    @property
    def reply_daily_limit(self):
        return self._reply_config().get("daily_limit", 30)

    @property
    def reply_poll_min(self):
        return self._reply_config().get("poll_min", 60)

    @property
    def reply_poll_max(self):
        return self._reply_config().get("poll_max", 180)

    @property
    def reply_delay_min(self):
        return self._reply_config().get("reply_delay_min", 5)

    @property
    def reply_delay_max(self):
        return self._reply_config().get("reply_delay_max", 15)

    @property
    def reply_prompt_name(self):
        return self._reply_config().get("prompt", "weibo_reply")

    # --- 超话配置 ---
    @property
    def chaohua_enabled(self):
        return self._config.get("chaohua", {}).get("enabled", False)

    @property
    def chaohua_sign_config(self):
        return self._config.get("chaohua", {}).get("sign", {})

    @property
    def chaohua_post_config(self):
        return self._config.get("chaohua", {}).get("post", {})

    @property
    def chaohua_comment_config(self):
        return self._config.get("chaohua", {}).get("comment", {})


config = Config()
