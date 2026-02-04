# BA-Agent

商业分析助手Agent - Business Analysis Agent

## 项目简介

面向非技术业务人员的智能数据分析助手，通过自然语言交互提供：
- 🔍 异动检测与解释
- 📊 归因分析
- 📄 报告自动生成
- 📈 数据可视化

## 技术架构

- **单Agent**: LangChain + Claude 3.5 Sonnet
- **基础工具**: 命令行、Python沙盒、Web搜索、Web Reader、文件读取、SQL查询、向量检索
- **可配置Skills**: 异动检测、归因分析、报告生成、数据可视化（用户可扩展）

## 快速开始

### 安装
```bash
# 克隆项目
git clone <repository-url>
cd ba-agent

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入API密钥
```

### 运行
```bash
# 启动API服务
uvicorn backend.api.main:app --reload

# 运行Ralph Loop自动开发
bash scripts/ralph/ralph.sh 50
```

## 项目结构

```
ba-agent/
├── backend/
│   ├── agents/          # Agent实现
│   ├── tools/           # 基础工具
│   └── models/          # 数据模型
├── skills/              # 可配置分析Skills
│   ├── anomaly_detection/
│   ├── attribution/
│   ├── report_gen/
│   └── visualization/
├── config/             # 配置文件
│   ├── settings.yaml
│   └── skills.yaml
├── scripts/ralph/      # Ralph Loop脚本
├── docs/               # 文档
├── tests/              # 测试
└── requirements.txt
```

## 文档

- [产品PRD](docs/PRD.md)
- [API文档](http://localhost:8000/docs)
- [开发指南](docs/DEVELOPMENT.md)

## 许可证

MIT License
