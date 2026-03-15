#!/usr/bin/env python3
"""Interactive onboarding wizard for BioPaperClaw (bpc onboard)."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from typing import Dict, List

PROMPT_START = "<!-- BPC_PROMPT_OVERRIDE_START -->"
PROMPT_END = "<!-- BPC_PROMPT_OVERRIDE_END -->"
DEFAULT_SOURCES = ["pubmed", "europe_pmc", "biorxiv", "medrxiv", "crossref", "openalex", "semantic_scholar"]


def parse_csv(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def parse_synonyms(value: str) -> List[List[str]]:
    groups: List[List[str]] = []
    for grp in value.split(";"):
        terms = [x.strip() for x in grp.split("|") if x.strip()]
        if terms:
            groups.append(terms)
    return groups


def read_default_strategy(file_path: Path) -> Dict:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_STRATEGY":
                    return ast.literal_eval(node.value)
    raise ValueError("DEFAULT_STRATEGY not found")


def replace_dict_assignment(file_path: Path, var_name: str, new_dict: Dict) -> None:
    text = file_path.read_text(encoding="utf-8")
    marker = f"{var_name} = {{"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"{var_name} assignment not found in {file_path}")

    brace_start = text.find("{", start)
    depth = 0
    end = -1
    for i in range(brace_start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        raise ValueError(f"Could not parse braces for {var_name}")

    rendered = f"{var_name} = {repr(new_dict)}"
    new_text = text[:start] + rendered + text[end + 1 :]
    file_path.write_text(new_text, encoding="utf-8")


def update_daily_sources(file_path: Path, sources: List[str]) -> None:
    text = file_path.read_text(encoding="utf-8")
    py_list = "[" + ", ".join(repr(s) for s in sources) + "]"
    csv_value = ",".join(sources)

    text, n1 = re.subn(
        r"medical_sources\s*=\s*sources\s*or\s*\[[^\]]*\]",
        f"medical_sources = sources or {py_list}",
        text,
        count=1,
        flags=re.S,
    )
    text, n2 = re.subn(
        r"(parser\.add_argument\('--sources',\s*type=str,\s*default=')([^']*)(')",
        rf"\g<1>{csv_value}\g<3>",
        text,
        count=1,
    )

    if n1 == 0 or n2 == 0:
        raise ValueError("Unable to update sources in daily_paper_search.py")

    file_path.write_text(text, encoding="utf-8")


def update_agent_prompt(agent_md: Path, prompt_text: str) -> None:
    content = agent_md.read_text(encoding="utf-8")
    block = (
        f"\n## 用户自定义提示词（由 bpc onboard 管理）\n"
        f"{PROMPT_START}\n{prompt_text.strip()}\n{PROMPT_END}\n"
    )

    pattern = re.compile(re.escape(PROMPT_START) + r".*?" + re.escape(PROMPT_END), re.S)
    if pattern.search(content):
        content = pattern.sub(f"{PROMPT_START}\n{prompt_text.strip()}\n{PROMPT_END}", content)
    else:
        content = content.rstrip() + "\n" + block

    agent_md.write_text(content, encoding="utf-8")


def prompt_with_default(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def run_onboard(agent_root: Path) -> None:
    medical_file = agent_root / "skills" / "medical-literature-search" / "scripts" / "search_medical_literature.py"
    daily_file = agent_root / "skills" / "daily-search" / "scripts" / "daily_paper_search.py"
    agent_md = agent_root / "agent" / "AGENT.md"

    for path in (medical_file, daily_file, agent_md):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    print("\n🧭 BioPaperClaw Setup Wizard (bpc onboard)")
    print(f"Agent root: {agent_root}\n")

    strategy = read_default_strategy(medical_file)

    print("1) 配置医学检索关键词（DEFAULT_STRATEGY）")
    strategy["topic_terms"] = parse_csv(prompt_with_default("- topic_terms (逗号分隔)", ",".join(strategy.get("topic_terms", []))))
    strategy["mesh_terms"] = parse_csv(prompt_with_default("- mesh_terms (逗号分隔)", ",".join(strategy.get("mesh_terms", []))))
    synonyms_default = ";".join("|".join(g) for g in strategy.get("synonym_groups", []))
    strategy["synonym_groups"] = parse_synonyms(prompt_with_default("- synonym_groups (组间用; 组内用|)", synonyms_default))
    strategy["study_filters"] = parse_csv(prompt_with_default("- study_filters (逗号分隔)", ",".join(strategy.get("study_filters", []))))
    strategy["method_tags"] = parse_csv(prompt_with_default("- method_tags (逗号分隔)", ",".join(strategy.get("method_tags", []))))
    strategy["exclude_terms"] = parse_csv(prompt_with_default("- exclude_terms (逗号分隔)", ",".join(strategy.get("exclude_terms", []))))
    replace_dict_assignment(medical_file, "DEFAULT_STRATEGY", strategy)

    print("\n2) 配置每日检索数据源（daily_paper_search.py）")
    source_default = ",".join(DEFAULT_SOURCES)
    source_input = prompt_with_default("- sources (逗号分隔)", source_default)
    sources = parse_csv(source_input)
    update_daily_sources(daily_file, sources)

    print("\n3) 配置 AGENT 提示词可编辑区")
    prompt_text = prompt_with_default(
        "- 输入给 Agent 的提示词补充（可写多句）",
        "请优先解释检索策略、输出可追溯来源，并在不确定时明确说明假设。",
    )
    update_agent_prompt(agent_md, prompt_text)

    print("\n✅ 初始化完成！已更新：")
    print(f"- {medical_file}")
    print(f"- {daily_file}")
    print(f"- {agent_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="BioPaperClaw setup wizard")
    parser.add_argument("--agent-root", type=str, default="~/agents/med-bioinformatics", help="Agent root path")
    args = parser.parse_args()
    run_onboard(Path(args.agent_root).expanduser())


if __name__ == "__main__":
    main()
