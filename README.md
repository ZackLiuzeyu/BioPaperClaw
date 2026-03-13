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

### 推荐数据源（医学场景必备）

> 医学场景不应只依赖 arXiv，默认采用“医学数据库 + 预印本 + 引用网络”的组合检索。

**必加数据源**：
- **PubMed / Entrez API**：医学主检索入口（MeSH + 临床研究类型过滤）
- **Europe PMC**：摘要与开放全文获取更友好，补充生命科学覆盖
- **bioRxiv / medRxiv**：追踪热点预印本
- **Crossref**：补 DOI、期刊、出版日期、ISSN 等元数据
- **OpenAlex / Semantic Scholar**：补引用网络、影响力与主题关系

### 推荐检索主题

- 生物信息学基础模型：`protein language model`, `genomic foundation model`, `single-cell foundation model`
- 临床与转化方向：`clinical prediction model`, `electronic health record representation learning`
- 药物研发方向：`drug-target interaction`, `de novo drug design`, `multimodal drug discovery`

### 医学评审优先关注（证据导向）

在医学场景中，默认优先回答以下问题，再考虑模型结构新颖性：
- 研究类型：基础研究 / 转化研究 / 临床研究 / 系统综述
- 研究设计：RCT、cohort、case-control、meta-analysis 等
- 证据来源：人群研究、动物实验、细胞实验、数据库挖掘
- 证据质量：样本量、偏倚风险、期刊与证据等级

### 医学专用评分模板（双模板）

**A. 临床医学论文模板（7维）**
- 临床问题重要性
- 研究设计强度
- 样本量与代表性
- 偏倚风险
- 统计分析合理性
- 临床可推广性
- 指南/实践价值

**B. 生物信息学论文模板（7维）**
- 数据来源可靠性
- 队列规模与外部验证
- 生物学解释力度
- 方法新颖性
- 可复现性（代码/流程）
- 过拟合风险
- 转化潜力

**专属扣分项（示例）**
- 单数据库且无外部验证
- ROC/AUC 高但机制解释弱
- 仅分子对接/MD，无细胞或组织验证
- 生存分析显著但混杂校正不足
- 泛癌分析堆砌但主线不聚焦

### 已实现：医学多源检索脚本（可直接运行）

### 检索策略升级（三层）

- **主题词层**：自由词 + MeSH + 同义词扩展（如 AKI / acute kidney injury）
- **研究类型层**：Clinical Trial、Review、Meta-analysis、Cohort、Case-control、Practice guideline
- **排除词层**：veterinary、dentistry、imaging-only、pregnancy（按课题可选）
- **生信方法标签**：WGCNA、DEGs、LASSO/Cox、GSEA/GSVA/ssGSEA、CIBERSORT、scRNA-seq、CellChat/Monocle/SCENIC、docking/MD simulation、pan-cancer、external validation

```bash
# 多源检索（默认含 PubMed/Europe PMC/bioRxiv/medRxiv/Crossref/OpenAlex/Semantic Scholar）
python agents/surrogate-modeling/skills/medical-literature-search/scripts/search_medical_literature.py   --batch --limit 8 --top 20

# 每日任务切换为医学多源模式
python agents/surrogate-modeling/skills/daily-search/scripts/daily_paper_search.py   --search-mode medical --top 3 --dry-run
```
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
│       │   ├── medical-literature-search/ # 医学多源检索（PubMed/Europe PMC/...）
│       │   ├── arxiv-search/     # 兼容旧流程的检索技能
│       │   ├── semantic-scholar/ # 引用数据 API（可与 OpenAlex/Crossref 联用）
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
| 🔍 **每日检索** | 聚合 PubMed/Europe PMC/bioRxiv/medRxiv，自动去重，精选 Top 3 | 每天 20:00 (Asia/Singapore) |
| 📝 **医学阅读卡片** | 按固定医学总结模板输出（含答辩话术/开题引用价值） | 检索后自动执行 |
| 📊 **医学多维评分** | 临床模板/生信模板 + 扣分项 + Date-Citation 权衡 | 总结后自动执行 |
| 📰 **周报生成** | Top 3 精选论文报告，推送通知 | 每周日 10:00 |

---

## 🤖 评分体系

### 医学多维基础评分 + Date-Citation 影响力评分（含扣分项）

```
最终评分 = 调整后基础评分 × 0.9 + 影响力评分 × 0.1

基础评分 = 所有维度均分（临床7维/生信7维）
调整后基础评分 = 基础评分 - 扣分项
```

**Date-Citation 调整因子**（示例，可领域定制）：
- ≤3个月新论文：+0.2
- 3-24个月 + 引用≥50：+0.5
- >24个月 + 引用≥200：+0.5
- 引用密度≥10次/月：额外 +0.2

**医学模板示例**：
- **临床医学模板**：临床问题重要性、研究设计强度、样本代表性、偏倚风险、统计合理性、可推广性、指南价值
- **生物信息学模板**：数据可靠性、外部验证、生物解释、方法新颖性、可复现性、过拟合风险、转化潜力

详见 `skills/paper-expert-generator/references/domain-adaptation-guide.md`

---

## 🛠️ 创建新领域智能体

参考 `skills/paper-expert-generator/SKILL.md` 的 8 步工作流：

1. **领域访谈** — 收集研究域、子方向、方法论、排除词
2. **关键词库** — 构建 PubMed/Europe PMC + bioRxiv/medRxiv 组合查询
3. **评分维度** — 在临床模板/生信模板中选择并细化7个维度 + 扣分项
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
- ✅ 医学阅读卡片式总结（固定栏目）
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
