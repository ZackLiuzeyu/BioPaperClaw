# PaperClaw - 医学与生物信息学论文专属工具

> 基于 OpenClaw 的医学论文与生物信息学论文自动检索、总结、评估智能体框架。
> 提供面向生物医药场景的默认关键词、评估维度与落地流程。

<div align="center">

[![OpenClaw](https://img.shields.io/badge/OpenClaw-Agent-blue)](https://github.com/openclaw/openclaw)
[![Python](https://img.shields.io/badge/Python-3.8+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

[中文](README.md) | [English](README_EN.md)
## 🎯 项目定位

PaperClaw 是一个**医学与生物信息学论文专家智能体框架**：

- **如果你要追踪医学/生信论文** → 使用本文档中的默认配置快速落地
- **如果你要扩展子领域**（如多组学、临床 NLP、药物发现）→ 使用 `skills/paper-expert-generator/` 继续定制
- **如果你想了解工作机制** → 查看 `agents/surrogate-modeling/` 作为完整示例

---

## 🧬 医学 + 生物信息学默认配置

### 推荐检索主题

- 生物信息学基础模型：`protein language model`, `genomic foundation model`, `single-cell foundation model`
- 临床与转化方向：`clinical prediction model`, `electronic health record representation learning`
- 药物研发方向：`drug-target interaction`, `de novo drug design`, `multimodal drug discovery`

### 推荐四维评分体系

1. **生物学有效性**：是否符合生物机制与实验事实
2. **临床/转化价值**：对诊断、预后、治疗或药物开发的潜在影响
3. **方法学创新与可解释性**：创新程度、可解释性与可复现性
4. **数据与评测严谨性**：数据质量、基准全面性、统计显著性

### 一键生成医学生信专属 Agent

```bash
python skills/paper-expert-generator/scripts/init_domain_agent.py \
  --domain "med-bioinformatics" \
  --output ~/agents/med-bioinformatics \
  --paperclaw-skills ./skills
```

生成后，优先填写 `agent/AGENT.md` 中以下内容：

- 细分方向（如肿瘤组学、蛋白结构预测、临床风险预测）
- 排除关键词（如纯化学合成、与医学无关的通用推荐系统）
- 周报接收对象（PI/课题组/医工联合团队）

---

## 📁 目录结构

```
PaperClaw/
├── skills/
│   └── paper-expert-generator/     # Skill：生成领域论文专家智能体
│       ├── SKILL.md               # 使用指南（8步工作流）
│       ├── scripts/
│       │   └── init_domain_agent.py   # 自动脚手架脚本
│       ├── references/
│       │   ├── domain-adaptation-guide.md  # 8个领域关键词/评分维度示例
│       │   └── agent-template-guide.md     # AGENT.md 撰写指南
│       └── assets/templates/      # 模板文件
│           ├── AGENT.md.template
│           ├── models.json
│           └── schedules.json
│
├── agents/
│   └── surrogate-modeling/        # Demo：3D几何代理建模领域专家
│       ├── agent/
│       │   ├── AGENT.md          # Agent 角色定义（Scientific ML + 3D几何）
│       │   ├── models.json       # LLM 配置
│       │   └── schedules.json    # 定时任务（每日20:00 + 周日10:00）
│       ├── skills/               # 5个核心技能
│       │   ├── arxiv-search/     # arXiv 批量搜索 + 去重
│       │   ├── semantic-scholar/ # 引用数据 API
│       │   ├── paper-review/     # 论文评估 + 安全写入
│       │   ├── daily-search/     # 每日自动检索
│       │   └── weekly-report/    # 周报生成
│       ├── docs/
│       │   ├── architecture.md   # 系统架构详解
│       │   └── evaluation_system.md  # 评分系统详解
│       └── examples/             # 示例数据（DeepONet评分报告）
│
└── [项目文档]
    ├── README.md                 # 本文档（中文）
    ├── README_EN.md              # 英文文档
    ├── INSTALLATION.md           # 安装指南
    ├── CONFIGURATION.md          # 配置说明
    └── QUICKSTART.md             # 快速入门
```

---

## 🚀 快速开始

### 方式一：为已有领域生成智能体（推荐）

如果你已有明确的研究领域，使用 `paper-expert-generator` skill：

```bash
# 1. 运行脚手架脚本
python skills/paper-expert-generator/scripts/init_domain_agent.py \
  --domain "bioinfo-ml" \
  --output ~/agents/bioinfo-ml \
  --paperclaw-skills ./skills

# 2. 根据 prompts 填写 AGENT.md 中的 {{占位符}}
# 3. 设置 API key
# 4. 启动 OpenClaw，指向新 agent
```

### 方式二：直接使用 Demo（了解工作流程）

查看 `agents/surrogate-modeling/` 作为完整示例：

```bash
cd agents/surrogate-modeling

# 每日检索（手动触发）
python skills/daily-search/scripts/daily_paper_search.py --top 3

# 周报生成
python skills/weekly-report/scripts/generate_weekly_report_v2.py
```

---

## 🏗️ 系统架构

### 单 Agent 内部架构

```
┌─────────────────────────────────────────────────────────────┐
│                    PaperClaw Agent                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │daily-search│ │arxiv-search│ │paper-review│ │weekly-rpt│ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  workspace/papers/                                          │
│  ├── {paper}/metadata.json  ← 结构化评分数据                │
│  ├── {paper}/summary.md     ← 深度总结                      │
│  ├── {paper}/scores.md      ← 评分报告                      │
│  └── evaluated_papers.json  ← 去重索引                      │
└─────────────────────────────────────────────────────────────┘
```

### 从 Skill 到 Agent 的生成流程

```
┌────────────────────────┐      ┌──────────────────────────┐
│ paper-expert-generator │ ──→  │  Your Domain Agent       │
│        Skill           │      │  (bioinfo-ml/cv-3d/...)  │
└────────────────────────┘      └──────────────────────────┘
        │                                    │
        ├── init_domain_agent.py            ├── agent/AGENT.md
        ├── domain-adaptation-guide.md      ├── agent/models.json
        ├── agent-template-guide.md         ├── agent/schedules.json
        └── templates/                      └── skills/
                                              (5个技能，按需适配)
```

---

## 📊 核心功能

| 功能 | 说明 | 触发方式 |
|------|------|---------|
| 🔍 **每日检索** | 批量搜索 arXiv，自动去重，精选 Top 3 | 每天 20:00 (Asia/Singapore) |
| 📝 **深度总结** | 回答 10 个核心问题，生成 summary.md | 检索后自动执行 |
| 📊 **四维评分** | 领域定制维度 + Date-Citation 权衡 | 总结后自动执行 |
| 📰 **周报生成** | Top 3 精选论文报告，推送通知 | 每周日 10:00 |

---

## 🤖 评分体系

### 四维基础评分 + Date-Citation 影响力评分

```
最终评分 = 四维基础评分 × 0.9 + 影响力评分 × 0.1

四维基础评分 = (维度1 + 维度2 + 维度3 + 维度4) / 4
```

**Date-Citation 调整因子**（示例，可领域定制）：
- ≤3个月新论文：+0.2
- 3-24个月 + 引用≥50：+0.5
- >24个月 + 引用≥200：+0.5
- 引用密度≥10次/月：额外 +0.2

**领域定制评分维度示例**：
- **Scientific ML**（默认）：工程应用、架构创新、理论贡献、可靠性
- **生物信息学**：生物学合理性、计算可扩展性、基准质量、转化潜力
- **计算机视觉**：架构创新、基准性能、泛化能力、实用性

详见 `skills/paper-expert-generator/references/domain-adaptation-guide.md`

---

## 🛠️ 创建新领域智能体

参考 `skills/paper-expert-generator/SKILL.md` 的 8 步工作流：

1. **领域访谈** — 收集研究域、子方向、方法论、排除词
2. **关键词库** — 构建 arXiv `ti:` 查询
3. **评分维度** — 设计4个领域专属评分维度
4. **脚手架** — 运行 `init_domain_agent.py`
5. **写 AGENT.md** — 填充角色定位、关键词、4大任务
6. **改 SKILL.md** — 适配关键词列表和评分维度
7. **配置模型** — 填入 API credentials
8. **验证交付** — checklist 确认

---

## 🔄 更新日志

### v2.0.0 (2026-03-11) - 框架化重构

**🎯 架构升级**
- ✅ 新增 `paper-expert-generator` Skill，支持任意研究领域
- ✅ 目录重构：`skills/`（可复用组件） + `agents/`（领域示例）
- ✅ `surrogate-modeling` 作为首个 Demo Agent（Scientific ML + 3D几何）

### v1.1.0 (2026-03-04) - 架构优化

**🚀 核心改进**
- ✅ 消除正则解析依赖，从 JSON 直接读取结构化数据
- ✅ 安全并发写入（文件锁 + 去重检查）
- ✅ 强制思维链（`<think>` 标签）

### v1.0.0 (2026-03-01) - 初始版本

- ✅ arXiv 论文自动检索
- ✅ 论文深度总结（10个问题）
- ✅ 四维评分系统
- ✅ 周报自动生成

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

**贡献方向**：
- 新的领域适配示例（添加到 `agents/`）
- `paper-expert-generator` Skill 的功能增强
- 更多领域的关键词库和评分维度（`domain-adaptation-guide.md`）

---

## 📄 许可证

MIT License

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐️ Star！**

</div>
