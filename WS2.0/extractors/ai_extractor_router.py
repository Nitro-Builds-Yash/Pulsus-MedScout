import os
import re
import json
import logging
import time
import requests

log = logging.getLogger("extraction.ai_router")

EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}')
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_CATALOG_TTL_SECONDS = 6 * 60 * 60
OPENROUTER_MAX_MODEL_ATTEMPTS = 3
OPENROUTER_MAX_INPUT_CHARS = 12000
_openrouter_free_models = []
_openrouter_catalog_checked_at = 0.0

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
    """Extract via free OpenRouter models, trying alternatives when one is unavailable."""
    try:
        models = _get_free_openrouter_models()
    except (requests.RequestException, ValueError, TypeError) as exc:
        log.warning("[AI Router] Could not load OpenRouter's free model catalog: %s", exc)
        return []

    preferred_model = model or os.getenv("OPENROUTER_MODEL")
    if preferred_model:
        selected = next((entry for entry in models if entry["id"] == preferred_model), None)
        if selected:
            models.remove(selected)
            models.insert(0, selected)
        else:
            log.warning(
                "[AI Router] Configured model %s is not listed as free; using free models only.",
                preferred_model,
            )
    models = models[:OPENROUTER_MAX_MODEL_ATTEMPTS]
    if not models:
        log.warning("[AI Router] OpenRouter returned no eligible free text models.")
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Nitro-Builds-Yash/Email-Scraping",
        "X-OpenRouter-Title": "Academic Author & Email Extractor"
    }
    for candidate in models:
        payload = {
            "model": candidate["id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Extract author contact metadata from this academic paper text:\n\n"
                        f"{text[:OPENROUTER_MAX_INPUT_CHARS]}"
                    )
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1200
        }
        try:
            resp = requests.post(
                OPENROUTER_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code != 200:
                log.warning(
                    "[AI Router] OpenRouter model %s returned HTTP %s; trying another free model.",
                    candidate["id"],
                    resp.status_code,
                )
                continue
            response_data = resp.json()
            content = response_data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                log.warning(
                    "[AI Router] OpenRouter model %s returned non-text output; trying another free model.",
                    candidate["id"],
                )
                continue
            results = parse_llm_json(content)
            if results:
                log.info("[AI Router] Extraction succeeded with free model %s.", candidate["id"])
                return results
            log.warning(
                "[AI Router] OpenRouter model %s returned no usable author data; trying another free model.",
                candidate["id"],
            )
        except requests.RequestException as exc:
            log.warning(
                "[AI Router] OpenRouter request to %s failed: %s; trying another free model.",
                candidate["id"],
                exc,
            )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning(
                "[AI Router] Could not read output from %s: %s; trying another free model.",
                candidate["id"],
                exc,
            )
    return []


def _get_free_openrouter_models() -> list:
    """Return free text models ordered by largest context, refreshing the catalog periodically."""
    global _openrouter_free_models, _openrouter_catalog_checked_at
    now = time.monotonic()
    if (
        _openrouter_free_models
        and now - _openrouter_catalog_checked_at < OPENROUTER_CATALOG_TTL_SECONDS
    ):
        return [dict(model) for model in _openrouter_free_models]

    response = requests.get(OPENROUTER_MODELS_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Unexpected response from OpenRouter models catalog.")

    free_models = []
    for item in data["data"]:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        architecture = item.get("architecture") or {}
        pricing = item.get("pricing") or {}
        try:
            is_free = (
                isinstance(model_id, str)
                and model_id.endswith(":free")
                and architecture.get("modality") == "text->text"
                and float(pricing.get("prompt", -1)) == 0
                and float(pricing.get("completion", -1)) == 0
                and int(item.get("context_length", 0)) > 0
            )
        except (TypeError, ValueError):
            is_free = False
        if is_free:
            free_models.append({
                "id": model_id,
                "context_length": int(item["context_length"]),
            })

    free_models.sort(key=lambda candidate: (-candidate["context_length"], candidate["id"]))
    _openrouter_free_models = free_models
    _openrouter_catalog_checked_at = now
    return [dict(model) for model in free_models]


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
        return ai_results

    # Heuristic Regex Fallback
    raw_emails = EMAIL_RE.findall(text)
    clean_emails = list({
        e.lower().rstrip(".") for e in raw_emails
        if not any(x in e.lower() for x in [".png", ".jpg", ".jpeg", ".gif", "example.com", "domain.com"])
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
