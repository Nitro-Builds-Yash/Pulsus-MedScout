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

import extractors.http_client as hc
hc.http_session = MagicMock()

from extractors.pubmed_fetcher import fetch_pubmed_papers
from extractors.semanticscholar_fetcher import fetch_semanticscholar_papers

class TestAcademicSources(unittest.TestCase):

    @patch("extractors.pubmed_fetcher.http_session.get")
    def test_pubmed_fetcher_mock(self, mock_get):
        # Mock esearch response
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {
            "esearchresult": {"idlist": ["12345678"]}
        }

        # Mock efetch response XML
        mock_fetch_resp = MagicMock()
        mock_fetch_resp.status_code = 200
        mock_fetch_resp.content = b"""<?xml version="1.0"?>
        <PubmedArticleSet>
            <PubmedArticle>
                <MedlineCitation>
                    <PMID>12345678</PMID>
                    <Article>
                        <ArticleTitle>Neural Basis of Memory</ArticleTitle>
                        <AuthorList>
                            <Author>
                                <LastName>Smith</LastName>
                                <ForeName>John</ForeName>
                                <AffiliationInfo>
                                    <Affiliation>Department of Biology, Harvard. Email: jsmith@harvard.edu</Affiliation>
                                </AffiliationInfo>
                            </Author>
                        </AuthorList>
                    </Article>
                </MedlineCitation>
                <PubmedData>
                    <ArticleIdList>
                        <ArticleId IdType="doi">10.1038/s41586-024-0001</ArticleId>
                    </ArticleIdList>
                </PubmedData>
            </PubmedArticle>
        </PubmedArticleSet>
        """

        mock_get.side_effect = [mock_search_resp, mock_fetch_resp]

        papers = fetch_pubmed_papers("neural memory", limit=1)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Neural Basis of Memory")
        self.assertIn("jsmith@harvard.edu", papers[0]["emails"])

    @patch("extractors.semanticscholar_fetcher.http_session.get")
    def test_semanticscholar_fetcher_mock(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{
                "paperId": "abc12345",
                "title": "Quantum Error Correction",
                "authors": [{"name": "David Deutsch"}],
                "abstract": "Contact: d.deutsch@oxford.ac.uk for inquiries.",
                "year": 2024,
                "externalIds": {"DOI": "10.1103/PhysRev.99.1"},
                "openAccessPdf": {"url": "https://arxiv.org/pdf/2401.00001.pdf"}
            }]
        }
        mock_get.return_value = mock_resp

        papers = fetch_semanticscholar_papers("quantum error", limit=1)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Quantum Error Correction")
        self.assertIn("d.deutsch@oxford.ac.uk", papers[0]["emails"])

if __name__ == "__main__":
    unittest.main()
