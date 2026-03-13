# Medical Literature Search Skill

## 功能
跨多个医学/生信数据源进行论文检索并统一输出，包含：
- PubMed / Entrez API
- Europe PMC
- bioRxiv
- medRxiv
- Crossref
- OpenAlex
- Semantic Scholar

## 脚本
`skills/medical-literature-search/scripts/search_medical_literature.py`

## 用法

```bash
# 批量使用内置医学查询词
python skills/medical-literature-search/scripts/search_medical_literature.py \
  --batch --limit 10 --top 30

# 自定义查询
python skills/medical-literature-search/scripts/search_medical_literature.py \
  --query "randomized controlled trial oncology biomarker" \
  --sources pubmed,europe_pmc,medrxiv,crossref,openalex,semantic_scholar \
  --limit 10 --top 20 --output medical_search_results.json
```

## 输出字段
- `source`: 来源站点
- `paper_id`: 来源内主键（pmid/semantic paperId/openalex id 等）
- `title`, `authors`, `summary`, `published`
- `doi`, `url`, `pdf_url`
- `relevance_score`


## 三层检索策略（已实现）
1. **主题词层**：自由词 + MeSH + 同义词扩展
2. **研究类型/方法层**：Clinical Trial、Review、Meta-Analysis、Cohort、Case-Control 与生信方法标签
3. **排除词层**：如 veterinary、dentistry、imaging-only、pregnancy 等

### 示例：按课题工作流检索
```bash
python skills/medical-literature-search/scripts/search_medical_literature.py \
  --batch \
  --topic-terms "AKI,ferroptosis,sepsis" \
  --mesh-terms "Acute Kidney Injury,Sepsis" \
  --synonyms "acute kidney injury|acute renal injury|AKI" \
  --study-filters "Clinical Trial,Meta-Analysis,Cohort,Case-Control,Practice Guideline" \
  --method-tags "WGCNA,DEGs,LASSO,Cox,Random Forest,GSEA,GSVA,ssGSEA,CIBERSORT,MCP-counter,scRNA-seq,CellChat,Monocle,SCENIC,docking,MD simulation,pan-cancer,external validation" \
  --exclude-terms "veterinary,dentistry,imaging-only,pregnancy" \
  --limit 10 --top 30
```
