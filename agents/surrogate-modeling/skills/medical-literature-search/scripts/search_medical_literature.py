#!/usr/bin/env python3
"""Multi-source medical literature search with 3-layer retrieval strategy.

Layers:
1) Topic terms (free text + MeSH + synonyms)
2) Study-type / methodology filters
3) Exclusion terms
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional

UA = "PaperClaw-MedicalSearch/1.1 (mailto:paperclaw@example.com)"
DEFAULT_SOURCES = ["pubmed", "europe_pmc", "biorxiv", "medrxiv", "crossref", "openalex", "semantic_scholar"]

DEFAULT_STRATEGY = {
    "topic_terms": ["protein language model", "single-cell", "drug-target interaction", "clinical prediction model"],
    "mesh_terms": ["Bioinformatics", "Precision Medicine", "Computational Biology"],
    "synonym_groups": [
        ["acute kidney injury", "acute renal injury", "AKI"],
        ["single-cell RNA-seq", "scRNA-seq", "single cell transcriptomics"],
    ],
    "study_filters": ["Clinical Trial", "Review", "Meta-Analysis", "Cohort", "Case-Control"],
    "method_tags": [
        "WGCNA", "DEGs", "LASSO", "Cox", "Random Forest", "GSEA", "GSVA", "ssGSEA",
        "CIBERSORT", "MCP-counter", "CellChat", "Monocle", "SCENIC", "docking", "MD simulation",
        "pan-cancer", "external validation",
    ],
    "exclude_terms": ["veterinary", "dentistry", "imaging-only"],
}


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def to_iso_date(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except Exception:
        return value


def tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 2]


def parse_csv(value: str) -> List[str]:
    if not value:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]


def parse_synonyms(value: str) -> List[List[str]]:
    """Format: 'a|b|c; x|y'"""
    if not value:
        return []
    groups = []
    for grp in value.split(";"):
        terms = [t.strip() for t in grp.split("|") if t.strip()]
        if terms:
            groups.append(terms)
    return groups


def build_queries(strategy: Dict) -> List[str]:
    topic_terms = strategy.get("topic_terms", [])
    mesh_terms = strategy.get("mesh_terms", [])
    synonym_groups = strategy.get("synonym_groups", [])
    study_filters = strategy.get("study_filters", [])
    method_tags = strategy.get("method_tags", [])
    exclude_terms = strategy.get("exclude_terms", [])

    topic_exprs = [f'"{t}"' for t in topic_terms]
    topic_exprs.extend(["(" + " OR ".join(f'"{s}"' for s in grp) + ")" for grp in synonym_groups])
    topic_exprs.extend([f'"{m}"[MeSH Terms]' for m in mesh_terms])

    study_expr = " OR ".join(f'"{f}"' for f in study_filters) if study_filters else ""
    method_expr = " OR ".join(f'"{m}"' for m in method_tags) if method_tags else ""
    exclude_expr = " ".join(f'NOT "{x}"' for x in exclude_terms)

    queries = []
    base_topic = " OR ".join(topic_exprs) if topic_exprs else '"medical bioinformatics"'

    if study_expr:
        queries.append(f"({base_topic}) AND ({study_expr}) {exclude_expr}".strip())
    if method_expr:
        queries.append(f"({base_topic}) AND ({method_expr}) {exclude_expr}".strip())
    queries.append(f"({base_topic}) {exclude_expr}".strip())

    # dedup while preserving order
    uniq = []
    seen = set()
    for q in queries:
        if q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq


def relevance_score(paper: Dict, query: str) -> int:
    q_tokens = set(tokenize(query))
    text = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
    score = 0
    for token in q_tokens:
        if token in text:
            score += 2
    if paper.get("doi"):
        score += 1
    if paper.get("pdf_url"):
        score += 1
    return score


def normalize_record(source: str, identifier: str, title: str, authors: Iterable[str], summary: str,
                     published: str, doi: str = "", url: str = "", pdf_url: str = "") -> Dict:
    title = (title or "").strip()
    return {
        "source": source,
        "paper_id": identifier or doi or title[:80],
        "arxiv_id": "",
        "title": title,
        "authors": [a.strip() for a in (authors or []) if a and a.strip()],
        "summary": (summary or "").strip(),
        "published": to_iso_date(published),
        "doi": (doi or "").strip(),
        "url": (url or "").strip(),
        "pdf_url": (pdf_url or "").strip(),
    }


def search_pubmed(query: str, limit: int = 20) -> List[Dict]:
    term = urllib.parse.quote(query)
    esearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi" \
              f"?db=pubmed&retmode=json&sort=pub+date&retmax={limit}&term={term}"
    ids = json.loads(http_get(esearch).decode("utf-8")).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    esummary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi" \
               f"?db=pubmed&retmode=json&id={urllib.parse.quote(','.join(ids))}"
    data = json.loads(http_get(esummary).decode("utf-8"))
    out = []
    for pmid in ids:
        item = data.get("result", {}).get(pmid, {})
        doi = ""
        for aid in item.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        out.append(normalize_record(
            "pubmed", pmid, item.get("title", ""), [a.get("name", "") for a in item.get("authors", [])], "",
            item.get("pubdate", ""), doi=doi, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        ))
    return out


def search_europe_pmc(query: str, limit: int = 20) -> List[Dict]:
    q = urllib.parse.quote(query)
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}&format=json&pageSize={limit}"
    data = json.loads(http_get(url).decode("utf-8"))
    out = []
    for r in data.get("resultList", {}).get("result", []):
        resolved_url = ""
        full_text_urls = r.get("fullTextUrlList", {}).get("fullTextUrl", [])
        if isinstance(full_text_urls, list) and full_text_urls:
            resolved_url = full_text_urls[0].get("url", "")
        out.append(normalize_record(
            (r.get("source", "EUROPEPMC") or "EUROPEPMC").lower(), r.get("id", ""), r.get("title", ""),
            (r.get("authorString") or "").replace(".", "").split(","), r.get("abstractText", ""),
            r.get("firstPublicationDate", "") or r.get("pubYear", ""), doi=r.get("doi", ""), url=resolved_url
        ))
    return out


def search_rss(source: str, feed_url: str, query: str, limit: int = 20) -> List[Dict]:
    root = ET.fromstring(http_get(feed_url))
    q_tokens = set(tokenize(query))
    out = []
    for item in root.findall(".//item"):
        title = item.findtext("title", default="")
        desc = item.findtext("description", default="")
        text = f"{title} {desc}".lower()
        if q_tokens and not any(t in text for t in q_tokens):
            continue
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I)
        doi = doi_match.group(0) if doi_match else ""
        link = item.findtext("link", default="")
        out.append(normalize_record(source, link, title, [], desc, item.findtext("pubDate", ""), doi=doi, url=link))
        if len(out) >= limit:
            break
    return out


def search_crossref(query: str, limit: int = 20) -> List[Dict]:
    q = urllib.parse.quote(query)
    url = f"https://api.crossref.org/works?query={q}&rows={limit}&sort=published&order=desc"
    data = json.loads(http_get(url).decode("utf-8"))
    out = []
    for item in data.get("message", {}).get("items", []):
        doi = item.get("DOI", "")
        pub_parts = item.get("issued", {}).get("date-parts", [[""]])[0]
        out.append(normalize_record(
            "crossref", doi,
            (item.get("title") or [""])[0],
            [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author", [])],
            "", "-".join(str(x) for x in pub_parts if x), doi=doi, url=f"https://doi.org/{doi}"
        ))
    return out


def search_openalex(query: str, limit: int = 20) -> List[Dict]:
    q = urllib.parse.quote(query)
    url = f"https://api.openalex.org/works?search={q}&per-page={limit}&sort=publication_date:desc"
    data = json.loads(http_get(url).decode("utf-8"))
    out = []
    for w in data.get("results", []):
        out.append(normalize_record(
            "openalex", w.get("id", ""), w.get("title", ""),
            [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])],
            w.get("abstract", ""), w.get("publication_date", ""),
            doi=(w.get("doi") or "").replace("https://doi.org/", ""),
            url=w.get("primary_location", {}).get("landing_page_url", "") or ""
        ))
    return out


def search_semantic_scholar(query: str, limit: int = 20) -> List[Dict]:
    q = urllib.parse.quote(query)
    fields = urllib.parse.quote("title,abstract,authors,year,externalIds,url,openAccessPdf")
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}&limit={limit}&fields={fields}"
    data = json.loads(http_get(url).decode("utf-8"))
    out = []
    for p in data.get("data", []):
        out.append(normalize_record(
            "semantic_scholar", p.get("paperId", ""), p.get("title", ""),
            [a.get("name", "") for a in p.get("authors", [])],
            p.get("abstract", ""), str(p.get("year", "")),
            doi=(p.get("externalIds") or {}).get("DOI", ""), url=p.get("url", ""),
            pdf_url=(p.get("openAccessPdf") or {}).get("url", "")
        ))
    return out


def deduplicate(records: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for r in records:
        key = (r.get("doi") or "").lower().strip() or re.sub(r"\W+", "", r.get("title", "").lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def apply_exclusions(records: List[Dict], exclude_terms: List[str]) -> List[Dict]:
    if not exclude_terms:
        return records
    terms = [t.lower() for t in exclude_terms]
    kept = []
    for r in records:
        text = f"{r.get('title', '')} {r.get('summary', '')}".lower()
        if any(term in text for term in terms):
            continue
        kept.append(r)
    return kept


def batch_search_medical(queries: List[str], per_source_limit: int = 10, delay_sec: float = 1.0,
                         sources: Optional[List[str]] = None, exclude_terms: Optional[List[str]] = None) -> List[Dict]:
    sources = sources or DEFAULT_SOURCES
    all_records: List[Dict] = []

    source_funcs = {
        "pubmed": lambda q: search_pubmed(q, per_source_limit),
        "europe_pmc": lambda q: search_europe_pmc(q, per_source_limit),
        "biorxiv": lambda q: search_rss("biorxiv", "https://connect.biorxiv.org/relate/feed/biorxiv.xml", q, per_source_limit),
        "medrxiv": lambda q: search_rss("medrxiv", "https://connect.medrxiv.org/relate/feed/medrxiv.xml", q, per_source_limit),
        "crossref": lambda q: search_crossref(q, per_source_limit),
        "openalex": lambda q: search_openalex(q, per_source_limit),
        "semantic_scholar": lambda q: search_semantic_scholar(q, per_source_limit),
    }

    for query in queries:
        for source in sources:
            fn = source_funcs.get(source)
            if not fn:
                continue
            try:
                rows = fn(query)
                for r in rows:
                    r["relevance_score"] = relevance_score(r, query)
                all_records.extend(rows)
                print(f"✅ {source:<16} query={query[:56]} -> {len(rows)}")
            except Exception as exc:
                print(f"⚠️ {source:<16} query={query[:56]} failed: {exc}")
            time.sleep(delay_sec)

    deduped = deduplicate(all_records)
    filtered = apply_exclusions(deduped, exclude_terms or [])
    filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return filtered


def resolve_strategy(args: argparse.Namespace) -> Dict:
    strategy = json.loads(json.dumps(DEFAULT_STRATEGY))

    if args.topic_terms:
        strategy["topic_terms"] = parse_csv(args.topic_terms)
    if args.mesh_terms:
        strategy["mesh_terms"] = parse_csv(args.mesh_terms)
    if args.synonyms:
        strategy["synonym_groups"] = parse_synonyms(args.synonyms)
    if args.study_filters:
        strategy["study_filters"] = parse_csv(args.study_filters)
    if args.method_tags:
        strategy["method_tags"] = parse_csv(args.method_tags)
    if args.exclude_terms:
        strategy["exclude_terms"] = parse_csv(args.exclude_terms)

    return strategy


def main():
    parser = argparse.ArgumentParser(description="Search medical literature across multiple sources")
    parser.add_argument("--query", type=str, help="single pre-built query")
    parser.add_argument("--batch", action="store_true", help="run strategy-built batch queries")
    parser.add_argument("--limit", type=int, default=10, help="per-source limit")
    parser.add_argument("--top", type=int, default=20, help="top output count")
    parser.add_argument("--sources", type=str, default=",".join(DEFAULT_SOURCES), help="comma-separated sources")
    parser.add_argument("--output", type=str, default="", help="save json output path")
    parser.add_argument("--topic-terms", type=str, default="", help="comma list, e.g. AKI,ferroptosis,sepsis")
    parser.add_argument("--mesh-terms", type=str, default="", help="comma list, e.g. Acute Kidney Injury,Sepsis")
    parser.add_argument("--synonyms", type=str, default="", help="groups: 'acute kidney injury|acute renal injury|AKI; sepsis|septic shock'")
    parser.add_argument("--study-filters", type=str, default="", help="comma list, e.g. Clinical Trial,Meta-Analysis,Cohort")
    parser.add_argument("--method-tags", type=str, default="", help="comma list, e.g. WGCNA,DEGs,LASSO,Cox")
    parser.add_argument("--exclude-terms", type=str, default="", help="comma list, e.g. veterinary,dentistry,pregnancy")
    args = parser.parse_args()

    strategy = resolve_strategy(args)
    queries = [args.query] if args.query else (build_queries(strategy) if args.batch else ["medical bioinformatics"])
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    records = batch_search_medical(
        queries=queries,
        per_source_limit=args.limit,
        sources=sources,
        exclude_terms=strategy.get("exclude_terms", []),
    )
    top = records[: args.top]

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(top, f, ensure_ascii=False, indent=2)
        print(f"💾 saved to {args.output}")
    else:
        print(json.dumps(top, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
