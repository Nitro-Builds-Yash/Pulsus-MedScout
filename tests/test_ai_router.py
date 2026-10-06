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
    extract_with_gemini,
    _get_free_openrouter_models,
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

    @patch("extractors.ai_extractor_router._get_free_openrouter_models")
    @patch("extractors.ai_extractor_router.requests.post")
    def test_openrouter_extraction(self, mock_post, mock_models):
        mock_models.return_value = [{"id": "test/free-model:free", "context_length": 32000}]
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
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["Authorization"],
            "Bearer fake-api-key",
        )

    @patch("extractors.ai_extractor_router._get_free_openrouter_models")
    @patch("extractors.ai_extractor_router.requests.post")
    def test_openrouter_tries_next_free_model_after_failure(self, mock_post, mock_models):
        mock_models.return_value = [
            {"id": "test/first:free", "context_length": 64000},
            {"id": "test/backup:free", "context_length": 32000},
        ]
        unavailable = MagicMock(status_code=429)
        success = MagicMock(status_code=200)
        success.json.return_value = {
            "choices": [{
                "message": {
                    "content": '[{"name": "Dr. Li", "email": "li@tsinghua.edu.cn"}]'
                }
            }]
        }
        mock_post.side_effect = [unavailable, success]

        results = extract_with_openrouter("Paper text", "fake-api-key")

        self.assertEqual(results[0]["email"], "li@tsinghua.edu.cn")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[0].kwargs["json"]["model"], "test/first:free")
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"]["model"], "test/backup:free")

    @patch("extractors.ai_extractor_router._openrouter_catalog_checked_at", 0)
    @patch("extractors.ai_extractor_router._openrouter_free_models", [])
    @patch("extractors.ai_extractor_router.requests.get")
    def test_free_model_discovery_filters_paid_and_non_text_models(self, mock_get):
        response = MagicMock()
        response.json.return_value = {
            "data": [
                {
                    "id": "test/large:free",
                    "context_length": 64000,
                    "architecture": {"modality": "text->text"},
                    "pricing": {"prompt": "0", "completion": "0"},
                },
                {
                    "id": "test/small:free",
                    "context_length": 8000,
                    "architecture": {"modality": "text->text"},
                    "pricing": {"prompt": "0", "completion": "0"},
                },
                {
                    "id": "test/paid",
                    "context_length": 128000,
                    "architecture": {"modality": "text->text"},
                    "pricing": {"prompt": "0.01", "completion": "0.02"},
                },
                {
                    "id": "test/image:free",
                    "context_length": 128000,
                    "architecture": {"modality": "text->image"},
                    "pricing": {"prompt": "0", "completion": "0"},
                },
            ]
        }
        mock_get.return_value = response

        models = _get_free_openrouter_models()

        self.assertEqual([model["id"] for model in models], [
            "test/large:free",
            "test/small:free",
        ])
        mock_get.assert_called_once()

if __name__ == "__main__":
    unittest.main()
