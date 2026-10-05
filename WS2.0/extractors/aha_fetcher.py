import os
import re
import logging
from .europepmc_fetcher import fetch_europepmc_papers
from .http_client import polite_jitter

log = logging.getLogger("extraction.aha")

def fetch_aha_papers(topic, limit, target_dir, filters=None):
    """
    Dedicated fetcher for AHA Journals (American Heart Association).
    AHA Journals aggressively blocks automated PDF downloads (403 Forbidden via Cloudflare).
    We use EuropePMC / PMC open-access mirrors to fetch metadata and PDFs,
    and enforce strict randomized delays to ensure the bot is completely undetected.
    """
    log.info("[AHA Journals] Initiating stealth fetch via EuropePMC proxy (bypassing 403)...")
    
    # Query AHA Journals specifically
    # Publisher is usually "Lippincott Williams & Wilkins", "Ovid Technologies (Wolters Kluwer Health)", 
    # or "American Heart Association". We can also target common AHA journals like Circulation, Stroke, etc.
    # But a broad publisher query is safer.
    
    enhanced_topic = f'({topic}) AND (PUBLISHER:"American Heart Association" OR PUBLISHER:"Lippincott Williams & Wilkins" OR JOURNAL:"Circulation" OR JOURNAL:"Stroke" OR JOURNAL:"Hypertension" OR JOURNAL:"Arteriosclerosis, Thrombosis, and Vascular Biology")'
    
    # Strict anti-detection delay
    polite_jitter(3.0, 5.0)
    
    results = fetch_europepmc_papers(enhanced_topic, limit, target_dir, filters)
    
    log.info(f"[AHA Journals] Retrieved {len(results)} records using stealth delays.")
    return results
