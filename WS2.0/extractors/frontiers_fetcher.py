import os
import re
import logging
from .europepmc_fetcher import fetch_europepmc_papers
from .http_client import polite_jitter

log = logging.getLogger("extraction.frontiers")

def fetch_frontiers_papers(topic, limit, target_dir, filters=None):
    """
    Dedicated fetcher for Frontiers journals.
    Uses EuropePMC as the backend metadata & open-access PDF provider,
    but injects strict delays to avoid any bot detection or rate limiting.
    """
    log.info("[Frontiers] Initiating stealth fetch via EuropePMC proxy...")
    
    # We construct a query specific to Frontiers
    # Frontiers has many journals, they are all indexed in EuropePMC with publisher "Frontiers Media SA"
    # or journal titles starting with "Frontiers in"
    
    enhanced_topic = f'({topic}) AND (PUBLISHER:"Frontiers Media S.A." OR PUBLISHER:"Frontiers Media SA" OR JOURNAL:"Frontiers")'
    
    # Apply a strict pre-fetch delay to avoid bot detection
    polite_jitter(2.5, 4.5)
    
    results = fetch_europepmc_papers(enhanced_topic, limit, target_dir, filters)
    
    log.info(f"[Frontiers] Retrieved {len(results)} records using stealth delays.")
    return results
