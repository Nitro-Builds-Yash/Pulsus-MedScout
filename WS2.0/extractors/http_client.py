import os
import time
import random
import logging
from typing import Optional

log = logging.getLogger("extraction.http_client")

# Research Email & Standardized Polite User-Agent
RESEARCH_EMAIL = os.getenv("RESEARCH_CONTACT_EMAIL", "outreach@pulsus.com")
POLITE_USER_AGENT = (
    f"Pulsus-MedScout/2.0 (Biomedical Literature & Author Intelligence; mailto:{RESEARCH_EMAIL})"
)

DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def polite_jitter(min_seconds: float = 0.3, max_seconds: float = 0.7):
    """
    Automated Request Jitter:
    Injects a randomized pause (300ms - 700ms) between paper fetches in loops
    to avoid triggering bot detection or aggressive burst rate limiters.
    """
    sleep_duration = random.uniform(min_seconds, max_seconds)
    time.sleep(sleep_duration)


try:
    import requests
    from urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter

    def create_resilient_session(
        retries: int = 3,
        backoff_factor: float = 1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        user_agent: str = POLITE_USER_AGENT
    ) -> requests.Session:
        """
        Creates a requests.Session with:
        - Connection pooling
        - Exponential Backoff on 429 & 5xx: automatically waits (backoff_factor * 2 ** attempt)s
        - Verified Polite Header configuration declaring the research email
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            raise_on_status=False,
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=15, pool_maxsize=25)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session

    # Shared polite session with exponential backoff & connection pool
    http_session = create_resilient_session()

    def get_with_backoff(url: str, params: Optional[dict] = None, headers: Optional[dict] = None, timeout: int = 15, max_retries: int = 3):
        """
        Executes a GET request with explicit exponential backoff on HTTP 429:
        Waits (2 ** attempt) seconds up to max_retries before giving up or skipping.
        Also automatically injects a polite jitter prior to dispatch.
        """
        polite_jitter()
        req_headers = {"User-Agent": POLITE_USER_AGENT}
        if headers:
            req_headers.update(headers)

        for attempt in range(max_retries):
            try:
                resp = http_session.get(url, params=params, headers=req_headers, timeout=timeout)
                if resp.status_code == 429:
                    wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                    log.warning(f"[RateLimit 429] Received 429 on {url[:60]}. Backing off for {wait_time:.1f}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                return resp
            except Exception as e:
                wait_time = (2 ** attempt) + random.uniform(0.1, 0.5)
                log.warning(f"[HTTP Error] {e} on {url[:60]}. Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)

        # Final attempt
        try:
            return http_session.get(url, params=params, headers=req_headers, timeout=timeout)
        except Exception:
            return None

except ImportError:
    class DummySession:
        def get(self, *args, **kwargs):
            raise RuntimeError("The 'requests' package is not installed.")
        def post(self, *args, **kwargs):
            raise RuntimeError("The 'requests' package is not installed.")
    http_session = DummySession()
    get_with_backoff = None
