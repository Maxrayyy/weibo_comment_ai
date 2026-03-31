# 微博全自动评论系统

基于 Selenium + 微博官方API + Qwen大模型 的全自动微博评论机器人。监控好友发布的新微博，使用AI智能生成评论并自动发布。

## 功能特性

- **智能评论生成** — 使用Qwen大模型根据微博内容生成自然、多样的评论
- **混合抓取方案** — Selenium抓取好友微博（绕过API限制），官方API发布评论（更稳定）
- **随机间隔轮询** — 5~15分钟随机间隔，模拟真人行为
- **白名单/黑名单** — 灵活控制评论范围
- **多种评论风格** — 友好互动、走心评论、简短捧场，可自定义
- **风控策略** — 每日上限、工作时段、随机延迟、评论去重
- **Cookie自动管理** — 首次手动登录，之后自动维持

## 项目结构

```
weibo_comment_ai/
├── config/
│   ├── config.yaml           # 主配置文件
│   └── prompts.yaml          # 评论风格模板
├── src/
│   ├── auth/                 # 登录与OAuth认证
│   ├── scraper/              # 微博页面抓取与解析
│   ├── comment/              # AI评论生成与发布
│   ├── scheduler/            # 随机间隔调度器
│   ├── storage/              # 已评论记录存储
│   └── utils/                # 日志、配置加载
├── data/                     # 运行时数据（Cookie、记录）
├── logs/                     # 运行日志
├── main.py                   # 程序入口
└── requirements.txt
```

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/Maxrayyy/weibo_comment_ai.git
cd weibo_comment_ai
```

### 2. 创建虚拟环境

```bash
python3.10 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 4. 安装Chrome浏览器

Selenium需要Chrome浏览器，ChromeDriver会由 `webdriver-manager` 自动管理。

## 配置

### 环境变量

设置以下环境变量（建议写入 `.env` 或 shell profile）：

```bash
export WEIBO_APP_KEY="你的微博App Key"
export WEIBO_APP_SECRET="你的微博App Secret"
export DASHSCOPE_API_KEY="你的Qwen API Key"
```

### 微博开放平台

1. 访问 [open.weibo.com](https://open.weibo.com) 注册开发者应用
2. 在应用的「高级信息」中设置授权回调页为：`https://api.weibo.com/oauth2/default.html`

### 评论策略

编辑 `config/config.yaml`：

```yaml
strategy:
  mode: "whitelist"           # whitelist 或 blacklist
  whitelist: [1234567890]     # 要评论的好友UID列表
  daily_limit: 50             # 每日评论上限
  skip_repost: true           # 跳过转发微博

timing:
  poll_min: 300               # 轮询最小间隔（秒）
  poll_max: 900               # 轮询最大间隔（秒）
```

### 评论风格

编辑 `config/prompts.yaml` 自定义评论风格，或在 `config.yaml` 中切换：

```yaml
default_prompt: "friendly"    # friendly / thoughtful / brief
```

## 使用

```bash
source venv/bin/activate
python main.py
```

**首次运行：**
1. 程序会打开Chrome浏览器，请手动完成微博登录（包括验证码）
2. 登录成功后，程序自动保存Cookie
3. 接着会弹出OAuth授权页面，点击授权即可
4. 之后程序进入自动轮询模式

**后续运行：**
- 程序自动加载已保存的Cookie和Token
- 过期时会提示重新登录/授权

**退出：** `Ctrl+C` 优雅退出

## 注意事项

- 微博 access_token 有效期仅 **2小时**，过期后需重新OAuth授权
- Cookie有效期通常较长，但也可能过期需重新登录
- 建议初期用白名单模式测试 1-2 个好友，稳定后再扩大范围
- 合理设置每日评论上限和轮询间隔，避免触发风控

## 技术栈

- **Python 3.10**
- **Selenium** — 浏览器自动化抓取
- **BeautifulSoup4** — HTML解析
- **Qwen API** (OpenAI SDK兼容) — AI评论生成
- **微博开放平台API** — 评论发布
- **APScheduler** — 任务调度

## License

MIT
