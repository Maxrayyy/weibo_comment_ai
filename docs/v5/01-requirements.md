# V5 需求文档 — Docker容器化部署

## 背景
项目需要部署到Linux服务器，将4个独立功能模式构建为Docker镜像，实现服务器端自动运行。

## 功能需求

### 1. Docker镜像构建
- 构建统一基础镜像（Python + Chrome + ChromeDriver）
- 4个独立服务可按需启动：
  - `weibo-timeline` — 时间线评论（API模式，无Selenium）
  - `weibo-friend-group` — 好友圈评论（Selenium）
  - `weibo-reply` — 自动回复评论（Selenium）
  - `weibo-chaohua` — 超话签到/发帖/评论（Selenium）

### 2. 代码适配Linux
- ChromeDriver路径从Windows硬编码改为自动检测（webdriver-manager）
- User-Agent适配（移除Windows标识或使用通用UA）
- Docker环境下跳过手动登录流程，使用预置Cookie/Token

### 3. 数据持久化
- `data/` 目录（cookies、token、评论记录）通过Docker volume挂载
- `config/` 目录通过volume挂载，支持外部修改配置
- `.env` 文件通过volume或env_file方式注入

## 约束条件
- 首次登录（Cookie获取、OAuth授权）必须在本地完成，生成文件后挂载到容器
- Docker容器中无图形界面，所有浏览器操作必须为headless模式
- 镜像应尽量小，使用python:3.11-slim作为基础
