# BioPaperClaw - Medical & Bioinformatics Paper Expert Agent Framework

> An OpenClaw-based framework for medical and bioinformatics paper retrieval, summary cards, and evaluation.
> Includes biomedical defaults for data sources, retrieval strategy, and scoring templates.

<div align="center">

[![OpenClaw](https://img.shields.io/badge/OpenClaw-Agent-blue)](https://github.com/openclaw/openclaw)
[![Python](https://img.shields.io/badge/Python-3.8+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

[中文](README.md) | [English](README_EN.md)

## ℹ️ About

**BioPaperClaw** is built for medical and bioinformatics literature workflows with:
- Multi-source retrieval (PubMed, Europe PMC, bioRxiv, medRxiv, Crossref, OpenAlex, Semantic Scholar)
- 3-layer retrieval strategy (topic terms + study/method filters + exclusion terms)
- Medical dual scoring templates (clinical / bioinformatics) with deduction rules
- A fixed 12-section medical reading card for summary output (including defense one-liner and proposal/review citation value)


---

## 🎯 Project Overview

BioPaperClaw is a **medical & bioinformatics paper expert agent framework**:

- **If you have a specific research domain** → Use `skills/paper-expert-generator/` to quickly create your own agent
- **If you want to understand how it works** → Check `agents/surrogate-modeling/` as a complete example

---

## 📁 Directory Structure

```
BioPaperClaw/
├── skills/
│   └── paper-expert-generator/     # Skill: Generate domain paper expert agents
│       ├── SKILL.md               # Usage guide (8-step workflow)
│       ├── scripts/
│       │   └── init_domain_agent.py   # Automated scaffolding script
│       ├── references/
│       │   ├── domain-adaptation-guide.md  # Keyword/scoring examples for 8 domains
│       │   └── agent-template-guide.md     # AGENT.md authoring guide
│       └── assets/templates/      # Template files
│           ├── AGENT.md.template
│           ├── models.json
│           └── schedules.json
│
├── agents/
│   └── surrogate-modeling/        # Demo: 3D Geometry Surrogate Modeling Expert
│       ├── agent/
│       │   ├── AGENT.md          # Agent role definition (Scientific ML + 3D Geometry)
│       │   ├── models.json       # LLM configuration
│       │   └── schedules.json    # Scheduled tasks (Daily 20:00 + Sunday 10:00)
│       ├── skills/               # 5 core skills
│       │   ├── arxiv-search/     # arXiv batch search + deduplication
│       │   ├── semantic-scholar/ # Citation data API
│       │   ├── paper-review/     # Paper evaluation + safe write
│       │   ├── daily-search/     # Daily automated search
│       │   └── weekly-report/    # Weekly report generation
│       ├── docs/
│       │   ├── architecture.md   # System architecture details
│       │   └── evaluation_system.md  # Scoring system details
│       └── examples/             # Sample data (DeepONet evaluation report)
│
└── [Project Documentation]
    ├── README.md                 # This document (Chinese)
    ├── README_EN.md              # This document (English)
    ├── INSTALLATION.md           # Installation guide
    ├── CONFIGURATION.md          # Configuration guide
    └── QUICKSTART.md             # Quick start guide
```

---

## 🚀 Quick Start

### Option 1: Generate Agent for Existing Domain (Recommended)

If you have a specific research domain, use the `paper-expert-generator` skill:

```bash
# 1. Run the scaffolding script
python skills/paper-expert-generator/scripts/init_domain_agent.py \
  --domain "bioinfo-ml" \
  --output ~/agents/bioinfo-ml \
  --paperclaw-skills ./skills

# 2. Fill in the {{placeholders}} in AGENT.md according to prompts
# 3. Set API key
# 4. Launch OpenClaw pointing to the new agent
```

### Option 2: Use the Demo (Understand the Workflow)

Explore `agents/surrogate-modeling/` as a complete working example:

```bash
cd agents/surrogate-modeling

# Daily search (manual trigger)
python skills/daily-search/scripts/daily_paper_search.py --top 3

# Weekly report generation
python skills/weekly-report/scripts/generate_weekly_report_v2.py
```

---

## 🏗️ System Architecture

### Single Agent Internal Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  BioPaperClaw Agent                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │daily-search│ │arxiv-search│ │paper-review│ │weekly-rpt│ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  workspace/papers/                                          │
│  ├── {paper}/metadata.json  ← Structured scoring data       │
│  ├── {paper}/summary.md     ← Deep summary                  │
│  ├── {paper}/scores.md      ← Scoring report                │
│  └── evaluated_papers.json  ← Deduplication index           │
└─────────────────────────────────────────────────────────────┘
```

### From Skill to Agent Generation Flow

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
                                              (5 skills, adapt as needed)
```

---

## 📊 Core Features

| Feature | Description | Trigger |
|---------|-------------|---------|
| 🔍 **Daily Search** | Multi-source medical search, auto-dedup, Top 3 selection | Daily 20:00 (Asia/Singapore) |
| 📝 **Medical Reading Card** | Fixed 12-section summary card output | Auto after search |
| 📊 **Medical Multi-Dimensional Scoring** | Clinical/Bioinformatics templates + deductions + Date-Citation weighting | Auto after summary |
| 📰 **Weekly Report** | Top 3 curated papers, push notification | Every Sunday 10:00 |

---

## 📐 Scoring System

### Medical Multi-Dimensional Base Score + Date-Citation Impact Score

```
Final Score = Adjusted Base Score × 0.9 + Impact Score × 0.1

Base Score = mean(all dimensions)
Adjusted Base Score = Base Score - deduction penalties
```

**Medical dual templates**:
- **Clinical template (7 dims)**: Clinical Importance, Design Strength, Sample Representativeness, Bias Risk, Statistical Rigor, Generalizability, Guideline/Practice Value
- **Bioinformatics template (7 dims)**: Data Reliability, External Validation, Biological Interpretability, Method Novelty, Reproducibility, Overfitting Risk, Translational Potential

**Common medical deductions** (example):
- Single database without external validation
- Good ROC/AUC but weak mechanism evidence
- Docking/MD only without wet-lab or tissue-level validation
- Significant survival analysis with insufficient confounder adjustment
- Pan-cancer analysis with weakly focused storyline

## 🛠️ Creating a New Domain Agent

Follow the 8-step workflow in `skills/paper-expert-generator/SKILL.md`:

1. **Domain Interview** — Collect research domain, sub-directions, methods, exclusions
2. **Keyword Library** — Build a PubMed/Europe PMC + bioRxiv/medRxiv combined retrieval strategy
3. **Scoring Dimensions** — Choose clinical/bioinformatics template and refine 7 dimensions + deductions
4. **Scaffolding** — Run `init_domain_agent.py`
5. **Write AGENT.md** — Fill in role definition, keywords, and core tasks
6. **Adapt SKILL.md** — Customize keyword list and scoring dimensions
7. **Configure Model** — Input API credentials
8. **Validate & Deliver** — Checklist confirmation

---

## 🔄 Changelog

### v2.0.0 (2026-03-11) - Framework Refactor

**🎯 Architecture Upgrade**
- ✅ Added `paper-expert-generator` Skill, supporting any research domain
- ✅ Directory restructure: `skills/` (reusable components) + `agents/` (domain examples)
- ✅ `surrogate-modeling` as the first Demo Agent (Scientific ML + 3D Geometry)

### v1.1.0 (2026-03-04) - Architecture Optimization

**🚀 Core Improvements**
- ✅ Eliminated regex parsing dependency, read structured data directly from JSON
- ✅ Safe concurrent write (file locking + dedup check)
- ✅ Mandatory reasoning chain (` (`<think>` tags)

### v1.0.0 (2026-03-01) - Initial Release

- ✅ arXiv paper automated search
- ✅ Medical reading-card summarization (fixed 12 sections)
- ✅ Multi-dimensional scoring system (medical dual templates)
- ✅ Weekly report auto-generation

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

**Contribution Directions**:
- New domain adaptation examples (add to `agents/`)
- Feature enhancements for `paper-expert-generator` Skill
- More domain keyword libraries and scoring dimensions (`domain-adaptation-guide.md`)

---

## 📄 License

MIT License

---

<div align="center">

**If this project helps you, please give us a ⭐️ Star!**

</div>
