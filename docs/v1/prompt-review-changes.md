# Prompt 相关代码 Review 变更记录

## 修复的问题

### 1. `default_prompt` 重复定义

**问题**：`config/prompts.yaml` 末尾的 `default_prompt: friendly` 和 `config/config.yaml` 中的 `default_prompt: "friendly"` 重复定义。代码只从 `config.yaml` 读取，`prompts.yaml` 中的完全未被使用。

**风险**：`prompts.yaml` 中的 `default_prompt` 是一个字符串值（不是 dict），混在 prompt 风格定义中会导致 `available_prompts` 属性遍历时对字符串取 `["name"]` 而抛出 `TypeError`。

**修复**：删除 `prompts.yaml` 中的 `default_prompt: friendly`，只保留 `config.yaml` 中的配置。

### 2. `available_prompts` 对非 prompt 条目不安全

**问题**：`config_loader.py` 的 `available_prompts` 属性直接遍历 `self._prompts.items()` 并访问 `v["name"]`，未校验 `v` 是否为 dict。

**修复**：增加类型过滤条件 `if isinstance(v, dict) and "name" in v`。

### 3. `get_base_prompt()` 方法冗余

**问题**：`config_loader.py` 中的 `get_base_prompt()` 与 `get_prompt("weibo_base")` 功能完全一致，且从未被调用（调用处直接用的是 `get_prompt("weibo_base")`）。

**修复**：删除 `get_base_prompt()` 方法，新增 `base_prompt_name` 属性从 `config.yaml` 读取底座 prompt 名称。

### 4. `"weibo_base"` 硬编码

**问题**：`ai_generator.py` 中 `config.get_prompt("weibo_base")` 将底座 prompt 的 key 硬编码为字符串字面量。

**修复**：
- `config.yaml` 新增 `base_prompt: "weibo_base"` 配置项
- `config_loader.py` 新增 `base_prompt_name` 属性
- `ai_generator.py` 改为 `config.get_prompt(config.base_prompt_name)`

### 5. 命名风格不一致：`_style_variants` vs `_IDENTITY_VARIANTS`

**问题**：`ai_generator.py` 中两个模块级常量命名风格不统一——`_style_variants`（小写）和 `_IDENTITY_VARIANTS`（大写）。按 Python 惯例，模块级常量应全大写。

**修复**：`_style_variants` 重命名为 `_STYLE_VARIANTS`（含注释中的引用）。

### 6. `_style_variants` 已定义但未使用

**问题**：`_style_variants` 列表已定义，但使用它的代码已被注释掉，属于死代码。

**修复**：将整个 `_STYLE_VARIANTS` 定义也注释掉，与使用处保持一致。

## 涉及文件

| 文件 | 变更类型 |
|------|----------|
| `config/config.yaml` | 新增 `base_prompt` 配置项 |
| `config/prompts.yaml` | 删除多余的 `default_prompt` |
| `src/utils/config_loader.py` | 删除 `get_base_prompt()`，新增 `base_prompt_name` 属性，加固 `available_prompts` |
| `src/comment/ai_generator.py` | 消除硬编码，统一命名风格，注释未使用代码 |

## 当前 Prompt 构造逻辑

```
_build_messages(weibo_text, prompt_name)
│
├─ base_prompt  = config.get_prompt(config.base_prompt_name)   # 底座规则
├─ style_prompt = config.get_prompt(prompt_name or default)    # 风格指令
├─ identity     = random.choice(_IDENTITY_VARIANTS)            # 随机身份
│
├─ system_prompt = base_prompt + identity + style_prompt        # 拼接
└─ user_prompt   = 微博正文 + "请直接给出评论，不要解释。"
```