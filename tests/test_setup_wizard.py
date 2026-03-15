import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.setup_wizard import (
    PROMPT_END,
    PROMPT_START,
    replace_dict_assignment,
    update_agent_prompt,
    update_daily_sources,
)


class TestSetupWizardHelpers(unittest.TestCase):
    def test_replace_default_strategy(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "search_medical_literature.py"
            p.write_text("DEFAULT_STRATEGY = {'topic_terms': ['a'], 'mesh_terms': []}\n", encoding="utf-8")
            replace_dict_assignment(p, "DEFAULT_STRATEGY", {"topic_terms": ["x", "y"], "mesh_terms": ["m"]})
            data = p.read_text(encoding="utf-8")
            self.assertIn("'topic_terms': ['x', 'y']", data)
            self.assertIn("'mesh_terms': ['m']", data)

    def test_update_daily_sources(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "daily_paper_search.py"
            p.write_text(
                textwrap.dedent(
                    """
                    medical_sources = sources or ['pubmed', 'openalex']
                    parser.add_argument('--sources', type=str, default='pubmed,openalex', help='x')
                    """
                ),
                encoding="utf-8",
            )
            update_daily_sources(p, ["pubmed", "semantic_scholar"])
            out = p.read_text(encoding="utf-8")
            self.assertIn("medical_sources = sources or ['pubmed', 'semantic_scholar']", out)
            self.assertIn("default='pubmed,semantic_scholar'", out)

    def test_update_agent_prompt_insert_and_replace(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "AGENT.md"
            p.write_text("# Agent\n", encoding="utf-8")
            update_agent_prompt(p, "first prompt")
            once = p.read_text(encoding="utf-8")
            self.assertIn(PROMPT_START, once)
            self.assertIn("first prompt", once)

            update_agent_prompt(p, "second prompt")
            twice = p.read_text(encoding="utf-8")
            self.assertIn("second prompt", twice)
            self.assertNotIn("first prompt", twice)
            self.assertIn(PROMPT_END, twice)


if __name__ == "__main__":
    unittest.main()
