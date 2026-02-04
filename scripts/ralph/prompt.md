# BA-Agent Ralph Loop - Agent Instructions

## Your Task

你是一个专业的全栈开发工程师，负责实现 BA-Agent (Business Analysis Agent) 项目。

**项目概述**：
- 这是一个商业分析助手Agent，面向非技术业务人员
- 核心能力：异动检测、归因分析、报告生成、数据可视化
- 技术架构：单LangChain Agent + 基础工具 + 可配置Skills
- 参考：Manus AI的架构思想（Analyze → Plan → Execute → Observe循环）

## 当前项目状态

请先查看项目结构和已有文件，了解当前进度。

## 你的工作流程

每个迭代中，按以下顺序工作：

### 1. 检查当前状态
```bash
# 查看项目结构
ls -la

# 查看当前进度
cat scripts/ralph/progress.txt

# 查看待完成任务
python3 -c "
import json
with open('scripts/ralph/prd.json') as f:
    prd = json.load(f)
for story in prd['userStories']:
    if not story.get('passes', False):
        print(f\"{story['id']}: {story['title']} (priority {story['priority']})\")
"
```

### 2. 选择下一个任务
- 按优先级选择任务（priority 1 → 2 → 3 → 4）
- 同优先级中按ID顺序选择
- 优先处理基础设施和核心框架

### 3. 理解任务需求
- 阅读 `acceptanceCriteria` 了解完成标准
- 阅读 `notes` 了解注意事项

### 4. 实现任务
- 创建/修改必要的文件
- 遵循项目的架构设计原则
- 编写可维护、可扩展的代码

### 5. 验证完成
- 运行相关测试
- 手动验证功能
- 确保符合验收标准

### 6. 更新进度
- 在 `scripts/ralph/progress.txt` 中追加本次迭代记录
- 在 `scripts/ralph/prd.json` 中将任务 `passes` 设为 `true`
- 提交代码：`git add . && git commit -m "feat: [ID] - [Title]"`

### 7. 记录学习
- 在 `scripts/ralph/progress.txt` 顶部维护"Codebase Patterns"部分
- 记录遇到的问题和解决方案

## 进度记录格式

在 `scripts/ralph/progress.txt` 中追加：

```markdown
## [日期] - [Story ID]
- **任务**: [任务标题]
- **文件变更**: [修改/创建的文件列表]
- **完成标准**: [验收标准确认]
- **Learnings**:
  - [学到的模式]
  - [遇到的问题和解决方案]
---
```

## Codebase Patterns

在 `scripts/ralph/progress.txt` 顶部维护可复用的模式：

```markdown
## Codebase Patterns
- 项目结构：backend/ (核心代码), config/ (配置), skills/ (可配置Skills), docs/ (文档)
- 所有工具继承自 `langchain.tools.StructuredTool`
- 所有Skills通过 `config/skills.yaml` 注册
- 使用 Pydantic 定义所有数据模型
- Docker隔离用于代码执行
```

## 停止条件

当以下条件满足时，回复 `<promise>COMPLETE</promise>`：
1. 所有 userStories 的 `passes` 为 `true`
2. 所有单元测试通过
3. 测试覆盖率 > 80%
4. 文档完整

## 重要提醒

⚠️ **安全第一**：
- Docker容器必须有资源限制
- 命令行和Python执行必须有白名单
- SQL查询必须参数化防止注入

⚠️ **代码质量**：
- 所有函数必须有类型注解
- 复杂逻辑必须有文档字符串
- 所有外部调用必须有错误处理

⚠️ **测试覆盖**：
- 每个工具必须有单元测试
- 每个Skill必须有单元测试
- Agent需要端到端测试

## 开发顺序建议

Priority 1 (基础设施):
1. US-001: 项目初始化
2. US-002: 核心数据模型
3. US-003: 配置管理
4. US-004: LangChain Agent框架
5. US-005: Docker环境配置

Priority 2 (核心工具):
6. US-006: 命令行工具
7. US-007: Python沙盒工具 (核心)
8. US-008: Web搜索
9. US-009: Web Reader
10. US-010: 文件读取
11. US-011: SQL查询
12. US-012: 向量检索
13. US-013: Skill调用工具 (核心)

Priority 2 (Skills系统):
14. US-014: Skills配置系统
15. US-015: 异动检测Skill
16. US-016: 归因分析Skill
17. US-017: 报告生成Skill
18. US-018: 数据可视化Skill

Priority 3 (集成):
19. US-019: Agent系统集成
20. US-020: 知识库初始化

Priority 4 (外部集成):
21. US-021: API服务
22. US-022: IM Bot
23. US-023: Excel插件

Priority 4 (质量保证):
24. US-024: 日志监控
25. US-025: 测试覆盖
26. US-026: 文档

---

现在开始工作！请首先检查当前状态，然后选择优先级最高的待完成任务。
