import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add WS2.0 to sys.path
WS_DIR = Path(__file__).resolve().parent.parent / "WS2.0"
if str(WS_DIR) not in sys.path:
    sys.path.insert(0, str(WS_DIR))

# Mock requests if not installed locally
if "requests" not in sys.modules:
    mock_req = types.ModuleType("requests")
    mock_req.post = MagicMock()
    mock_req.get = MagicMock()
    mock_req.Session = MagicMock()
    sys.modules["requests"] = mock_req

from extractors.ai_extractor_router import (
    parse_llm_json,
    extract_authors_and_emails,
    extract_with_openrouter,
    extract_with_gemini
)

class TestAIRouter(unittest.TestCase):

    def test_parse_llm_json_clean(self):
        raw = '[{"name": "Alice Smith", "email": "alice@univ.edu", "affiliation": "MIT", "country": "USA", "is_corresponding": true}]'
        parsed = parse_llm_json(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["name"], "Alice Smith")
        self.assertEqual(parsed[0]["email"], "alice@univ.edu")

    def test_parse_llm_json_markdown_wrapped(self):
        raw = '```json\n[{"name": "Bob Jones", "email": "bob@oxford.ac.uk", "affiliation": "Oxford", "country": "UK", "is_corresponding": true}]\n```'
        parsed = parse_llm_json(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["name"], "Bob Jones")
        self.assertEqual(parsed[0]["email"], "bob@oxford.ac.uk")

    def test_fallback_regex_when_no_api_key(self):
        sample_text = "Corresponding author: Sarah Jenkins (s.jenkins@stanford.edu), Department of Genetics."
        results = extract_authors_and_emails(sample_text, fallback_authors=["Sarah Jenkins"])
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["email"], "s.jenkins@stanford.edu")

    @patch("extractors.ai_extractor_router.requests.post")
    def test_openrouter_extraction(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": '[{"name": "Dr. Li", "email": "li@tsinghua.edu.cn", "affiliation": "Tsinghua", "country": "China", "is_corresponding": true}]'
                }
            }]
        }
        mock_post.return_value = mock_resp

        results = extract_with_openrouter("Paper text", "fake-api-key")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Dr. Li")
        self.assertEqual(results[0]["email"], "li@tsinghua.edu.cn")

if __name__ == "__main__":
    unittest.main()
