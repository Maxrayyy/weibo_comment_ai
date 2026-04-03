# V5 任务拆分 — Docker容器化部署

## Phase 1: 代码适配
1. 改造ChromeDriver路径 — 3个文件使用webdriver-manager自动检测
   - `src/auth/login_manager.py`
   - `src/auth/oauth_manager.py`
   - `src/scraper/weibo_scraper.py`
2. 添加Docker环境检测 — 手动登录/OAuth在Docker中给出明确提示
3. 修复requirements.txt — 补充python-dotenv

## Phase 2: Docker配置文件
1. 编写 `Dockerfile`
2. 编写 `docker-compose.yml`
3. 编写 `.dockerignore`

## Phase 3: 验证
1. Python语法检查（py_compile）
2. 验证Dockerfile语法
3. 更新README部署说明

## 依赖关系
- Phase 2 依赖 Phase 1（代码适配后才能正确构建镜像）
- Phase 3 依赖 Phase 1 + Phase 2