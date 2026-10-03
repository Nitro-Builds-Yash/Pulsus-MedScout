import time
import logging

log = logging.getLogger("extraction.http_client")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

try:
    import requests
    from urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter

    def create_resilient_session(
        retries: int = 3,
        backoff_factor: float = 0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        user_agent: str = DEFAULT_USER_AGENT
    ) -> requests.Session:
        """
        Creates a requests.Session with automatic exponential backoff retries
        and standard connection pooling.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session

    http_session = create_resilient_session()

except ImportError:
    # Minimal fallback dummy session
    class DummySession:
        def get(self, *args, **kwargs):
            raise RuntimeError("The 'requests' package is not installed.")
        def post(self, *args, **kwargs):
            raise RuntimeError("The 'requests' package is not installed.")
    http_session = DummySession()
