# Claude Code 项目规范

## 大型需求工作流（必须严格执行）

当用户提出涉及新功能、新模块、架构变更等大型需求时，**必须按以下阶段顺序执行**，不可跳过：

### 阶段一：调研
- 分析现有代码架构和相关模块
- 调研涉及的外部接口、第三方API、页面结构等
- 如需抓取网页或查阅参考资料，先完成调研再动手

### 阶段二：文档编写
在 `docs/` 目录下按版本创建以下文档（如 `docs/v3/`）：
1. **需求文档**（`01-requirements.md`）— 功能描述、约束条件
2. **技术方案**（`02-technical-design.md`）— 架构设计、接口分析、配置方案
3. **任务拆分**（`03-task-breakdown.md`）— 分Phase的开发任务和依赖关系

### 阶段三：编码实现
- 使用 TaskCreate/TaskUpdate 跟踪进度
- 每完成一个小任务（一个Phase或一个独立功能点）立即执行一次 git 提交和 push

### 阶段四：验证
- 编码完成后必须运行代码验证，确保无语法错误、导入错误
- 验证方式：`python -c "import main"` 或 `python -m py_compile <file>` 检查关键文件
- 如有测试用例则运行测试
- 发现问题立即修复后再提交

## Git 提交规范（每次都必须执行）

1. 每完成一个小任务（功能点、bug修复、文档更新）立即提交，不要积攒多个改动
2. 提交后自动尝试 `git push`
3. 如果 push 失败（网络问题等），**明确提示用户手动执行 `git push`**
4. commit message 使用中文描述，格式：`<type>: <描述>`
   - feat: 新功能
   - fix: 修复
   - refactor: 重构
   - docs: 文档
   - chore: 杂项

## 部署环境

- **生产服务器**：Ubuntu @ 150.158.112.53，SSH密钥 `C:\Users\zhidong_huang\weibo_douzi.pem`
- **部署方式**：Docker Compose，4个服务独立容器（friend-group、reply、chaohua、timeline）
- **本地开发**：Windows 11，代码兼容 Windows/Linux 双平台运行

## 项目结构

- 语言：Python
- 入口文件：`main.py`（时间线模式）、`run_friend_group.py`（好友圈模式）、`run_reply.py`（回复模式）、`run_chaohua.py`（超话模式）
- 配置：`config/config.yaml` + `config/prompts.yaml`
- 环境变量：`.env`
