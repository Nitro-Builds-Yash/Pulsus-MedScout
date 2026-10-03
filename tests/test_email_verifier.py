import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add WS2.0 to sys.path
WS_DIR = Path(__file__).resolve().parent.parent / "WS2.0"
if str(WS_DIR) not in sys.path:
    sys.path.insert(0, str(WS_DIR))

# Create a mock dns module if dnspython is not installed in local python env
if "dns" not in sys.modules:
    mock_dns = types.ModuleType("dns")
    mock_dns_resolver = types.ModuleType("dns.resolver")
    class NXDOMAIN(Exception): pass
    class NoAnswer(Exception): pass
    mock_dns_resolver.NXDOMAIN = NXDOMAIN
    mock_dns_resolver.NoAnswer = NoAnswer
    mock_dns_resolver.resolve = MagicMock()
    mock_dns.resolver = mock_dns_resolver
    sys.modules["dns"] = mock_dns
    sys.modules["dns.resolver"] = mock_dns_resolver

import extractors.email_verifier as ev
ev.DNS_AVAILABLE = True
ev.dns = sys.modules["dns"]

from extractors.email_verifier import check_email_deliverability

class TestEmailVerifier(unittest.TestCase):

    def test_invalid_email_syntax(self):
        status, reason = check_email_deliverability("invalid-email-no-at-sign")
        self.assertEqual(status, "Undeliverable")
        self.assertIn("Invalid email syntax", reason)

        status2, reason2 = check_email_deliverability("")
        self.assertEqual(status2, "Undeliverable")

    @patch("dns.resolver.resolve")
    def test_nonexistent_domain(self, mock_resolve):
        mock_resolve.side_effect = sys.modules["dns.resolver"].NXDOMAIN
        status, reason = check_email_deliverability("author@thisdomaindoesnotexistatall12345.com")
        self.assertEqual(status, "Undeliverable")
        self.assertIn("Domain does not exist", reason)

    @patch("dns.resolver.resolve")
    @patch("smtplib.SMTP")
    def test_valid_smtp_250(self, mock_smtp_cls, mock_resolve):
        # Mock DNS
        mock_rec = MagicMock()
        mock_rec.preference = 10
        mock_rec.exchange = "mail.university.edu"
        mock_resolve.return_value = [mock_rec]

        # Mock SMTP
        mock_smtp = MagicMock()
        mock_smtp.rcpt.return_value = (250, b"2.1.5 Recipient OK")
        mock_smtp_cls.return_value = mock_smtp

        status, reason = check_email_deliverability("professor@university.edu")
        self.assertEqual(status, "Deliverable")
        self.assertIn("250 OK", reason)

if __name__ == "__main__":
    unittest.main()
