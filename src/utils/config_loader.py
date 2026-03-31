import os
import yaml

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")


def _load_yaml(filename):
    filepath = os.path.join(CONFIG_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Config:
    """全局配置管理，加载 config.yaml 和 prompts.yaml"""

    def __init__(self):
        self._config = _load_yaml("config.yaml")
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

    # --- Qwen配置 ---
    @property
    def qwen_api_key(self):
        return self._config["qwen"]["api_key"]

    @property
    def qwen_base_url(self):
        return self._config["qwen"]["base_url"]

    @property
    def qwen_model(self):
        return self._config["qwen"]["model"]

    @property
    def qwen_max_tokens(self):
        return self._config["qwen"]["max_tokens"]

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
        return {k: v["name"] for k, v in self._prompts.items()}


config = Config()
