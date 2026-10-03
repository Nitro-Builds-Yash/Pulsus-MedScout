import sys
import unittest
from pathlib import Path

# Add WS2.0 to sys.path
WS_DIR = Path(__file__).resolve().parent.parent / "WS2.0"
if str(WS_DIR) not in sys.path:
    sys.path.insert(0, str(WS_DIR))

from extractors.utils import normalise_doi

class TestExtractors(unittest.TestCase):

    def test_normalise_doi(self):
        # Standard DOI link
        self.assertEqual(
            normalise_doi("https://doi.org/10.1371/journal.pone.0123456"),
            "10.1371/journal.pone.0123456"
        )
        self.assertEqual(
            normalise_doi("http://doi.org/10.1016/j.cell.2023.01"),
            "10.1016/j.cell.2023.01"
        )

        # arXiv link (version stripped)
        self.assertEqual(
            normalise_doi("https://arxiv.org/abs/2304.10023v1"),
            "arxiv:2304.10023"
        )
        self.assertEqual(
            normalise_doi("http://arxiv.org/abs/2105.00001v3"),
            "arxiv:2105.00001"
        )

        # Raw DOI
        self.assertEqual(
            normalise_doi("10.1038/s41586-020-2649-2"),
            "10.1038/s41586-020-2649-2"
        )

        # Invalid / empty
        self.assertEqual(normalise_doi("N/A"), "")
        self.assertEqual(normalise_doi(""), "")
        self.assertEqual(normalise_doi(None), "")

if __name__ == "__main__":
    unittest.main()
