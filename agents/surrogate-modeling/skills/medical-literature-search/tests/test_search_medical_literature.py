import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_medical_literature.py"
spec = importlib.util.spec_from_file_location("search_medical_literature", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class TestRssSourceParsing(TestCase):
    def test_valid_rss_response_parses_records(self):
        xml = """<?xml version='1.0' encoding='UTF-8'?>
        <rss><channel>
          <item>
            <title>Acute kidney injury biomarkers</title>
            <description>Study mentions DOI 10.1101/2024.01.01.123456</description>
            <link>https://www.biorxiv.org/content/10.1101/2024.01.01.123456v1</link>
            <pubDate>2024-01-01</pubDate>
          </item>
        </channel></rss>
        """
        with patch.object(mod, "http_get_response", return_value={
            "status": 200,
            "content_type": "application/rss+xml; charset=utf-8",
            "body": xml.encode("utf-8"),
        }):
            rows = mod.search_rss("biorxiv", "https://example.test/feed.xml", "kidney", limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "biorxiv")
        self.assertIn("Acute kidney injury", rows[0]["title"])
        self.assertEqual(rows[0]["doi"], "10.1101/2024.01.01.123456")

    def test_empty_response_returns_empty_list(self):
        with patch.object(mod, "http_get_response", return_value={
            "status": 200,
            "content_type": "application/rss+xml",
            "body": b"",
        }):
            rows = mod.search_rss("medrxiv", "https://example.test/feed.xml", "sepsis", limit=10)

        self.assertEqual(rows, [])

    def test_malformed_response_returns_empty_list(self):
        malformed = b"<?xml version='1.0'?><rss><channel><item><title>bad\x00title</title></item>"
        with patch.object(mod, "http_get_response", return_value={
            "status": 200,
            "content_type": "application/xml",
            "body": malformed,
        }):
            rows = mod.search_rss("medrxiv", "https://example.test/feed.xml", "sepsis", limit=10, debug=True)

        self.assertEqual(rows, [])


class TestSemanticScholarResilience(TestCase):
    def test_semantic_scholar_returns_empty_when_retries_exhausted(self):
        with patch.object(mod, "request_with_retry", return_value={
            "ok": False,
            "url": "https://api.semanticscholar.org/graph/v1/paper/search?q=test",
            "status_code": 429,
            "content_type": "application/json",
            "elapsed_ms": 1234,
            "error_type": "HTTPError",
            "error_message": "HTTP Error 429: Too Many Requests",
        }):
            rows = mod.search_semantic_scholar("aki", limit=1, max_retries=2, debug=True)

        self.assertEqual(rows, [])

    def test_semantic_scholar_valid_response_parses_records(self):
        payload = {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "AKI biomarker modeling",
                    "authors": [{"name": "Alice"}],
                    "abstract": "acute kidney injury model",
                    "year": 2024,
                    "externalIds": {"DOI": "10.1000/test.doi"},
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "openAccessPdf": {"url": "https://example.org/paper.pdf"},
                }
            ]
        }
        with patch.object(mod, "request_with_retry", return_value={
            "ok": True,
            "status_code": 200,
            "content_type": "application/json",
            "body": mod.json.dumps(payload).encode("utf-8"),
            "elapsed_ms": 88,
        }):
            rows = mod.search_semantic_scholar("aki", limit=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "semantic_scholar")
        self.assertEqual(rows[0]["doi"], "10.1000/test.doi")


class TestSourceWrapper(TestCase):
    def test_execute_source_handles_exceptions_gracefully(self):
        def _boom(_q):
            raise RuntimeError("boom")

        rows = mod.execute_source("crossref", "aki", _boom, debug=True)
        self.assertEqual(rows, [])
