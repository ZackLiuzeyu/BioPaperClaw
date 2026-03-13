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
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional, Set

UA = "PaperClaw-MedicalSearch/1.2 (mailto:paperclaw@example.com)"
DEFAULT_SOURCES = ["pubmed", "europe_pmc", "biorxiv", "medrxiv", "crossref", "openalex", "semantic_scholar"]
DEFAULT_TIMEOUT_SEC = 20
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SEC = 0.6

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


def log_debug(debug: bool, event: str, payload: Dict[str, Any]) -> None:
    if not debug:
        return
    print(json.dumps({"level": "debug", "event": event, **payload}, ensure_ascii=False))


def log_warning(event: str, payload: Dict[str, Any]) -> None:
    print(json.dumps({"level": "warning", "event": event, **payload}, ensure_ascii=False))


def decode_response_body(body: bytes, content_type: str = "") -> str:
    charsets = []
    if content_type:
        m = re.search(r"charset=([\w\-]+)", content_type, re.I)
        if m:
            charsets.append(m.group(1))
    charsets.extend(["utf-8", "utf-8-sig", "latin-1"])

    for enc in charsets:
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_response(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        headers = resp.headers
        return {
            "status": getattr(resp, "status", 200),
            "content_type": headers.get("Content-Type", ""),
            "body": body,
        }


def request_with_retry(url: str, source: str, query: str, timeout: int = DEFAULT_TIMEOUT_SEC,
                       max_retries: int = DEFAULT_MAX_RETRIES, backoff_base_sec: float = DEFAULT_BACKOFF_BASE_SEC,
                       debug: bool = False) -> Dict[str, Any]:
    retry_statuses = {429, 500, 502, 503, 504}
    attempts = max(1, max_retries + 1)
    start = time.time()

    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        status_code = None
        content_type = ""
        body = b""
        error_type = ""
        error_message = ""
        retryable = False

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = int(getattr(resp, "status", 200) or 200)
                content_type = resp.headers.get("Content-Type", "")
                body = resp.read()

            if status_code in retry_statuses:
                retryable = True
                error_type = "HTTPError"
                error_message = f"HTTP {status_code}"
            else:
                return {
                    "ok": True,
                    "url": url,
                    "status_code": status_code,
                    "content_type": content_type,
                    "body": body,
                    "attempt": attempt,
                    "elapsed_ms": int((time.time() - start) * 1000),
                    "error_type": "",
                    "error_message": "",
                }

        except urllib.error.HTTPError as exc:
            status_code = int(exc.code)
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            try:
                body = exc.read() or b""
            except Exception:
                body = b""
            retryable = status_code in retry_statuses
            error_type = "HTTPError"
            error_message = str(exc)
        except urllib.error.URLError as exc:
            retryable = True
            error_type = "URLError"
            error_message = str(exc)
        except Exception as exc:
            retryable = True
            error_type = type(exc).__name__
            error_message = str(exc)

        if retryable and attempt < attempts:
            sleep_sec = backoff_base_sec * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            log_warning("source_retry", {
                "source": source,
                "query": query,
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "elapsed_ms": int((time.time() - start) * 1000),
                "result_count": 0,
                "error_type": error_type,
                "error_message": error_message,
                "attempt": attempt,
                "next_backoff_sec": round(sleep_sec, 3),
            })
            time.sleep(sleep_sec)
            continue

        return {
            "ok": False,
            "url": url,
            "status_code": status_code,
            "content_type": content_type,
            "body": body,
            "attempt": attempt,
            "elapsed_ms": int((time.time() - start) * 1000),
            "error_type": error_type or "RequestFailed",
            "error_message": error_message or "request failed",
        }


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


def fusion_relevance_score(paper: Dict, query_tokens: Set[str]) -> int:
    """Cross-source reranking score after deduplication.

    The score fuses lexical match, data completeness and consensus signals from
    multiple sources / query variants.
    """
    title_tokens = set(tokenize(paper.get("title", "")))
    summary_tokens = set(tokenize(paper.get("summary", "")))

    token_hit = len(query_tokens & (title_tokens | summary_tokens))
    title_hit = len(query_tokens & title_tokens)

    score = token_hit * 2 + title_hit

    # Encourage complete/traceable records.
    if paper.get("doi"):
        score += 3
    if paper.get("pdf_url"):
        score += 1
    if paper.get("published"):
        score += 1

    # Consensus boost: the same paper returned by multiple sources/queries is
    # usually more robust than one-off hits.
    score += len(paper.get("matched_sources", [])) * 3
    score += len(paper.get("matched_queries", []))

    # Recency boost (soft).
    year_match = re.match(r"(\d{4})", paper.get("published", ""))
    if year_match:
        score += max(0, int(year_match.group(1)) - 2018)

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


def search_rss(source: str, feed_url: str, query: str, limit: int = 20, debug: bool = False,
               return_meta: bool = False) -> Any:
    try:
        response = http_get_response(feed_url)
    except urllib.error.HTTPError as exc:
        log_warning("rss_http_error", {"source": source, "url": feed_url, "status": exc.code, "error": str(exc)})
        return []
    except Exception as exc:
        log_warning("rss_request_failed", {"source": source, "url": feed_url, "error": str(exc)})
        return []

    status = int(response.get("status", 0) or 0)
    content_type = (response.get("content_type") or "").lower()
    body = response.get("body") or b""
    body_len = len(body)
    body_text = decode_response_body(body, content_type)

    log_debug(debug, "rss_response", {
        "source": source,
        "url": feed_url,
        "status": status,
        "content_type": content_type,
        "response_length": body_len,
        "preview": body_text[:500],
    })

    if status and status >= 400:
        log_warning("rss_bad_status", {"source": source, "url": feed_url, "status": status, "content_type": content_type, "response_length": body_len})
        return ([], {"url": feed_url, "status_code": status, "content_type": content_type}) if return_meta else []

    if body_len == 0:
        log_warning("rss_empty_body", {"source": source, "url": feed_url, "status": status, "content_type": content_type})
        return ([], {"url": feed_url, "status_code": status, "content_type": content_type}) if return_meta else []

    stripped = body_text.lstrip()
    if stripped.lower().startswith("<html") or "text/html" in content_type:
        log_warning("rss_html_response", {"source": source, "url": feed_url, "status": status, "content_type": content_type, "response_length": body_len})
        return ([], {"url": feed_url, "status_code": status, "content_type": content_type}) if return_meta else []

    if "xml" not in content_type and "rss" not in content_type and not stripped.startswith("<?xml") and "<rss" not in stripped[:200].lower():
        log_warning("rss_unexpected_content_type", {"source": source, "url": feed_url, "status": status, "content_type": content_type, "response_length": body_len})
        return ([], {"url": feed_url, "status_code": status, "content_type": content_type}) if return_meta else []

    try:
        root = ET.fromstring(body_text)
    except ET.ParseError as exc:
        log_warning("rss_parse_error", {"source": source, "url": feed_url, "status": status, "content_type": content_type, "response_length": body_len, "error": str(exc)})
        return ([], {"url": feed_url, "status_code": status, "content_type": content_type}) if return_meta else []

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
    return (out, {"url": feed_url, "status_code": status, "content_type": content_type}) if return_meta else out


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


def search_semantic_scholar(query: str, limit: int = 20, timeout: int = DEFAULT_TIMEOUT_SEC,
                          max_retries: int = DEFAULT_MAX_RETRIES, debug: bool = False,
                          return_meta: bool = False) -> Any:
    q = urllib.parse.quote(query)
    fields = urllib.parse.quote("title,abstract,authors,year,externalIds,url,openAccessPdf")
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}&limit={limit}&fields={fields}"

    response = request_with_retry(
        url=url,
        source="semantic_scholar",
        query=query,
        timeout=timeout,
        max_retries=max_retries,
        debug=debug,
    )

    if not response.get("ok"):
        log_warning("source_unavailable", {
            "source": "semantic_scholar",
            "query": query,
            "url": response.get("url", url),
            "status_code": response.get("status_code"),
            "content_type": response.get("content_type", ""),
            "elapsed_ms": response.get("elapsed_ms", 0),
            "result_count": 0,
            "error_type": response.get("error_type", "RequestFailed"),
            "error_message": response.get("error_message", "request failed"),
        })
        return ([], {
            "url": response.get("url", url),
            "status_code": response.get("status_code"),
            "content_type": response.get("content_type", ""),
        }) if return_meta else []

    body_text = decode_response_body(response.get("body", b""), response.get("content_type", ""))
    try:
        data = json.loads(body_text)
    except json.JSONDecodeError as exc:
        log_warning("source_parse_error", {
            "source": "semantic_scholar",
            "query": query,
            "url": url,
            "status_code": response.get("status_code"),
            "content_type": response.get("content_type", ""),
            "elapsed_ms": response.get("elapsed_ms", 0),
            "result_count": 0,
            "error_type": "JSONDecodeError",
            "error_message": str(exc),
        })
        return ([], {
            "url": url,
            "status_code": response.get("status_code"),
            "content_type": response.get("content_type", ""),
        }) if return_meta else []

    out = []
    for p in data.get("data", []):
        out.append(normalize_record(
            "semantic_scholar", p.get("paperId", ""), p.get("title", ""),
            [a.get("name", "") for a in p.get("authors", [])],
            p.get("abstract", ""), str(p.get("year", "")),
            doi=(p.get("externalIds") or {}).get("DOI", ""), url=p.get("url", ""),
            pdf_url=(p.get("openAccessPdf") or {}).get("url", "")
        ))
    return (out, {
        "url": url,
        "status_code": response.get("status_code"),
        "content_type": response.get("content_type", ""),
    }) if return_meta else out


def deduplicate(records: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for r in records:
        key = (r.get("doi") or "").lower().strip() or re.sub(r"\W+", "", r.get("title", "").lower())
        if not key:
            continue
        if key not in merged:
            merged[key] = dict(r)
            merged[key]["matched_sources"] = [r.get("source", "")]
            merged[key]["matched_queries"] = [r.get("matched_query", "")]
            merged[key]["raw_relevance_scores"] = [r.get("relevance_score", 0)]
            continue

        existing = merged[key]
        if len(r.get("summary", "")) > len(existing.get("summary", "")):
            existing["summary"] = r.get("summary", "")
        if not existing.get("doi") and r.get("doi"):
            existing["doi"] = r.get("doi")
        if not existing.get("pdf_url") and r.get("pdf_url"):
            existing["pdf_url"] = r.get("pdf_url")
        if not existing.get("url") and r.get("url"):
            existing["url"] = r.get("url")
        if (not existing.get("published") or existing.get("published") > r.get("published", "")) and r.get("published"):
            existing["published"] = r.get("published")

        existing["authors"] = list(dict.fromkeys((existing.get("authors") or []) + (r.get("authors") or [])))

        source = r.get("source", "")
        if source and source not in existing["matched_sources"]:
            existing["matched_sources"].append(source)

        matched_query = r.get("matched_query", "")
        if matched_query and matched_query not in existing["matched_queries"]:
            existing["matched_queries"].append(matched_query)

        existing["raw_relevance_scores"].append(r.get("relevance_score", 0))

    return list(merged.values())


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


def execute_source(source: str, query: str, fetch_fn, debug: bool = False) -> List[Dict]:
    start = time.time()
    rows: List[Dict] = []
    meta = {"url": "", "status_code": None, "content_type": ""}
    error_type = ""
    error_message = ""

    try:
        result = fetch_fn(query)
        if isinstance(result, tuple) and len(result) == 2:
            rows, meta = result
        else:
            rows = result
    except Exception as exc:
        rows = []
        error_type = type(exc).__name__
        error_message = str(exc)

    elapsed_ms = int((time.time() - start) * 1000)
    payload = {
        "source": source,
        "query": query,
        "url": meta.get("url", ""),
        "status_code": meta.get("status_code"),
        "content_type": meta.get("content_type", ""),
        "elapsed_ms": elapsed_ms,
        "result_count": len(rows),
        "error_type": error_type,
        "error_message": error_message,
    }

    if error_type:
        log_warning("source_execution", payload)
        return []

    log_debug(debug, "source_execution", payload)
    return rows



def batch_search_medical(queries: List[str], per_source_limit: int = 10, delay_sec: float = 1.0,
                         sources: Optional[List[str]] = None, exclude_terms: Optional[List[str]] = None,
                         debug: bool = False, timeout: int = DEFAULT_TIMEOUT_SEC,
                         max_retries: int = DEFAULT_MAX_RETRIES) -> List[Dict]:
    sources = sources or DEFAULT_SOURCES
    all_records: List[Dict] = []

    source_funcs = {
        "pubmed": lambda q: search_pubmed(q, per_source_limit),
        "europe_pmc": lambda q: search_europe_pmc(q, per_source_limit),
        "biorxiv": lambda q: search_rss("biorxiv", "https://connect.biorxiv.org/relate/feed/biorxiv.xml", q, per_source_limit, debug=debug, return_meta=True),
        "medrxiv": lambda q: search_rss("medrxiv", "https://connect.medrxiv.org/relate/feed/medrxiv.xml", q, per_source_limit, debug=debug, return_meta=True),
        "crossref": lambda q: search_crossref(q, per_source_limit),
        "openalex": lambda q: search_openalex(q, per_source_limit),
        "semantic_scholar": lambda q: search_semantic_scholar(q, per_source_limit, timeout=timeout, max_retries=max_retries, debug=debug, return_meta=True),
    }

    global_query_tokens: Set[str] = set()
    for query in queries:
        global_query_tokens.update(tokenize(query))
        for source in sources:
            fn = source_funcs.get(source)
            if not fn:
                continue
            rows = execute_source(source, query, fn, debug=debug)
            for r in rows:
                r["matched_query"] = query
                r["relevance_score"] = relevance_score(r, query)
            all_records.extend(rows)
            print(f"✅ {source:<16} query={query[:56]} -> {len(rows)}")
            time.sleep(delay_sec)

    deduped = deduplicate(all_records)
    filtered = apply_exclusions(deduped, exclude_terms or [])

    for paper in filtered:
        paper["source_count"] = len(paper.get("matched_sources", []))
        paper["query_hit_count"] = len(paper.get("matched_queries", []))
        paper["pre_fusion_score_max"] = max(paper.get("raw_relevance_scores", [0]))
        paper["relevance_score"] = fusion_relevance_score(paper, global_query_tokens)

    filtered.sort(
        key=lambda x: (
            x.get("relevance_score", 0),
            x.get("source_count", 0),
            x.get("query_hit_count", 0),
            x.get("pre_fusion_score_max", 0),
            x.get("published", ""),
        ),
        reverse=True,
    )
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
    parser.add_argument("--debug", action="store_true", help="enable structured debug logging")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC, help="HTTP timeout seconds")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="max retries for retryable HTTP errors")
    args = parser.parse_args()

    strategy = resolve_strategy(args)
    queries = [args.query] if args.query else (build_queries(strategy) if args.batch else ["medical bioinformatics"])
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    records = batch_search_medical(
        queries=queries,
        per_source_limit=args.limit,
        sources=sources,
        exclude_terms=strategy.get("exclude_terms", []),
        debug=args.debug,
        timeout=max(1, args.timeout),
        max_retries=max(0, args.max_retries),
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
