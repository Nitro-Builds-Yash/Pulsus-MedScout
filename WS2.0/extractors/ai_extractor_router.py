import os
import re
import json
import logging
import requests

log = logging.getLogger("extraction.ai_router")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')

SYSTEM_PROMPT = """You are an expert academic data extraction assistant.
Given unstructured text from a research paper (abstract, author footnote, or first page), identify all authors, their verified email addresses, institutional affiliations, and countries.

Respond ONLY with valid JSON in the following format:
[
  {
    "name": "Author Full Name",
    "email": "author.email@university.edu",
    "affiliation": "Department, University Name",
    "country": "Country Name",
    "is_corresponding": true
  }
]
If an author does not have an email listed, set "email": null.
Do NOT include markdown formatting or commentary outside the JSON.
"""

def extract_with_openrouter(text: str, api_key: str, model: str = None) -> list:
    """Extract authors and emails via OpenRouter API."""
    model = model or os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Nitro-Builds-Yash/Email-Scraping",
        "X-Title": "Academic Author & Email Extractor"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract author contact metadata from this academic paper text:\n\n{text[:4000]}"}
        ],
        "temperature": 0.1
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            return parse_llm_json(content)
        else:
            log.warning(f"[AI Router] OpenRouter error {resp.status_code}: {resp.text}")
    except Exception as e:
        log.error(f"[AI Router] OpenRouter request failed: {e}")
    return []

def extract_with_gemini(text: str, api_key: str) -> list:
    """Extract authors and emails via Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"{SYSTEM_PROMPT}\n\nAcademic paper text:\n{text[:4000]}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return parse_llm_json(raw_text)
        else:
            log.warning(f"[AI Router] Gemini API error {resp.status_code}: {resp.text}")
    except Exception as e:
        log.error(f"[AI Router] Gemini request failed: {e}")
    return []

def parse_llm_json(content: str) -> list:
    """Parse JSON array from LLM response safely."""
    try:
        # Strip markdown ```json ... ``` blocks if present
        clean = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean.strip(), flags=re.MULTILINE)
        data = json.loads(clean)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Sometimes models wrap in {"authors": [...]}
            for val in data.values():
                if isinstance(val, list):
                    return val
    except Exception as e:
        log.warning(f"[AI Router] Failed to parse JSON from LLM: {e}")
    return []

def extract_with_emergent(text: str, webhook_or_api_url: str = None, api_key: str = None) -> list:
    """Extract or process authors and emails using Emergent AI Agent (emergent.sh)."""
    url = webhook_or_api_url or os.getenv("EMERGENT_API_URL") or os.getenv("EMERGENT_WEBHOOK_URL")
    if not url:
        return []
    headers = {"Content-Type": "application/json"}
    key = api_key or os.getenv("EMERGENT_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "task": "academic_extraction",
        "system_prompt": SYSTEM_PROMPT,
        "input_text": text[:4000]
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                if "authors" in data:
                    return data["authors"]
                if "output" in data:
                    return parse_llm_json(str(data["output"]))
                if "choices" in data:
                    return parse_llm_json(data["choices"][0]["message"]["content"])
        else:
            log.warning(f"[AI Router] Emergent agent response status {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        log.error(f"[AI Router] Emergent Agent error: {e}")
    return []

def extract_authors_and_emails(text: str, fallback_authors: list = None) -> list:
    """
    Unified extraction router.
    Checks environment for AI API keys (EMERGENT_API_KEY/URL, OPENROUTER_API_KEY, GEMINI_API_KEY).
    If available, invokes AI extraction. Otherwise, falls back to fast heuristic regex extraction.
    """
    if not text:
        return []

    emergent_key = os.getenv("EMERGENT_API_KEY")
    emergent_url = os.getenv("EMERGENT_API_URL") or os.getenv("EMERGENT_WEBHOOK_URL")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    ai_results = []
    if emergent_url or emergent_key:
        log.info("[AI Router] Routing extraction via Emergent AI Agent (emergent.sh)...")
        ai_results = extract_with_emergent(text, emergent_url, emergent_key)

    if not ai_results and openrouter_key:
        log.info("[AI Router] Routing extraction via OpenRouter API...")
        ai_results = extract_with_openrouter(text, openrouter_key)
    elif not ai_results and gemini_key:
        log.info("[AI Router] Routing extraction via Gemini API...")
        ai_results = extract_with_gemini(text, gemini_key)

    if ai_results:
        # Filter out any email containing gmail.com
        filtered_ai = []
        for item in ai_results:
            em = item.get("email")
            if em and "gmail.com" in em.lower():
                item["email"] = None
            filtered_ai.append(item)
        return filtered_ai

    # Heuristic Regex Fallback
    raw_emails = EMAIL_RE.findall(text)
    clean_emails = list({
        e.lower().rstrip(".") for e in raw_emails
        if not any(x in e.lower() for x in [".png", ".jpg", ".jpeg", ".gif", "example.com", "domain.com", "gmail.com"])
    })

    fallback_authors = fallback_authors or ["Author"]
    results = []
    for idx, email in enumerate(clean_emails):
        author = fallback_authors[idx] if idx < len(fallback_authors) else fallback_authors[0]
        results.append({
            "name": author,
            "email": email,
            "affiliation": "N/A",
            "country": "N/A",
            "is_corresponding": True
        })

    return results
