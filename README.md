# 🔬 Pulsus MedScout // OMICS International & Pulsus Group
## Biomedical Literature & Author Intelligence Platform

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.0-green.svg)](https://flask.palletsprojects.com/)
[![UI Theme](https://img.shields.io/badge/Theme-Dark%20Maroon%20%26%20White-800020.svg)](https://tailwindcss.com/)
[![Repositories](https://img.shields.io/badge/Sources-34%20Live%20Repositories-crimson.svg)](#-supported-academic--biomedical-repositories-34-platforms)
[![Author](https://img.shields.io/badge/Maintainer-Nitro--Builds--Yash-black.svg?logo=github)](https://github.com/Nitro-Builds-Yash)
[![Affiliation](https://img.shields.io/badge/Affiliation-OMICS%20%26%20Pulsus-red.svg)](https://www.pulsus.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**Pulsus MedScout** is a high-performance biomedical intelligence and author outreach platform engineered for **OMICS International** and **Pulsus Group**. It connects directly to **34 scientific repositories** to discover verified medical researchers, laboratory directors, and corresponding authors with strict institutional email validation and zero-tolerance Gmail filtering.

---

## 🌟 Key Features

* **🌐 34 Federated Scientific Repositories:** Unified real-time extraction across 34 clinical, preprint, and global academic engines with master "Select All" and category grouping (Biomedical, Preprints, Global).
* **🎨 Dark Maroon & Crisp White Interface:** Refined dark obsidian-maroon aesthetic (`#0B0205`, `#15040B`), glowing ruby indicators, and high-contrast pure white typography.
* **🛡️ Zero Gmail Policy & Quality Verification:** Excludes non-institutional domains (`@gmail.com`) to guarantee outreach deliverability to legitimate academic, university, and hospital departments.
* **🔒 Strict 3-Field Completeness Guarantee:** Enforces an absolute 3-column data contract: **Paper Title**, **Author Name**, and **Email ID**. Any incomplete or missing field is filtered out automatically.
* **📊 Direct Excel (.xlsx) & CSV Export:** Formatted Excel spreadsheets with auto-styled columns and instant clipboard copy.
* **🧠 Ephemeral PDF Processing:** PDF bytes are parsed in memory and temporary PDF files are deleted after a task. Set `KEEP_DOWNLOADED_PDFS=1` to retain downloaded PDFs for debugging.
* **🌍 Geographic Scope & Document Filtering:**
  * **Geographic Scope & Country:** 36+ global countries with live search and "Select All" controls.
  * **Document Classification:** *Research Article*, *Case Reports*, *Brief Reports*, *Systematic Reports*.
  * **Publication Window:** Custom year range with quick-select presets (Last 2 or 5 Years).
* **🤖 AI Extraction Router (Gemini & OpenRouter):** Intelligently extracts corresponding authors from unstructured full-text and XML layouts with heuristic fallback.
* **📬 Mailbox Verification:** Verifies DNS MX records and simulates SMTP handshakes (`250 OK`) to confirm deliverability.

---

## 📚 Supported Academic & Biomedical Repositories (34 Platforms)

| # | Repository | Category | API / Extraction Mode |
|---|------------|----------|-----------------------|
| 1 | **PLOS ONE** | Biomedical | Direct Search API |
| 2 | **PubMed / NCBI** | Biomedical | Entrez eUtils (XML) |
| 3 | **bioRxiv** | Preprints | Cold Spring Harbor REST API |
| 4 | **medRxiv** | Preprints | Health Sciences Preprints API |
| 5 | **Europe PMC** | Biomedical | EMBL-EBI REST API |
| 6 | **arXiv.org** | Preprints | Cornell arXiv e-Print API |
| 7 | **OpenAlex** | Global | Open Scholarly Graph (250M+ papers) |
| 8 | **Semantic Scholar** | Global | AI Knowledge Graph API |
| 9 | **Crossref** | Global | Official DOI Metadata Engine |
| 10 | **eLife** | Biomedical | Open-Access Life Sciences API |
| 11 | **Preprints.org** | Preprints | Multidisciplinary Preprints Engine |
| 12 | **ScienceDirect** | Global | Elsevier Open-Access Feed |
| 13 | **iMedPub Group** | Biomedical | Clinical & Medical Journals Engine |
| 14 | **OSF Preprints** | Preprints | Center for Open Science API |
| 15 | **ChemRxiv** | Preprints | Chemical Sciences Preprints |
| 16 | **PeerJ** | Biomedical | Peer-Reviewed Biological Sciences |
| 17 | **F1000Research** | Biomedical | Post-Publication Peer Review |
| 18 | **DOAJ** | Global | Directory of Open Access Journals |
| 19 | **BASE Search** | Global | Bielefeld Academic Search Engine |
| 20 | **CORE OA** | Global | Global Research Aggregator |
| 21 | **Zenodo** | Preprints | CERN Universal Repository |
| 22 | **ResearchGate** | Global | Academic Publication Index |
| 23 | **Frontiers** | Biomedical | Frontiers in Medicine & Science |
| 24 | **MDPI** | Biomedical | Open Access Publisher Index |
| 25 | **Hindawi** | Biomedical | Peer-Reviewed OA Journals |
| 26 | **BioMed Central (BMC)**| Biomedical | Springer Nature BMC Engine |
| 27 | **PMC (PubMed Central)**| Biomedical | Full-Text Biomedical Archive |
| 28 | **Springer Open** | Global | Springer Nature Open Engine |
| 29 | **Taylor & Francis** | Global | T&F Open Access Index |
| 30 | **SSRN** | Preprints | Social Science & Health Preprints |
| 31 | **EarthArXiv** | Preprints | Earth & Planetary Sciences |
| 32 | **ESSOAr** | Preprints | Space & Earth Science Archive |
| 33 | **SciELO** | Global | Latin America & Global Network |
| 34 | **HAL Open Archive**| Global | French National Open Archive |

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    A["User Topic Query & Filters"] --> B{"Interface"}
    B -->|"Web UI (Port 5000)"| C["Flask Server (Pulsus MedScout)"]
    B -->|"Headless CLI"| D["cli.py"]
    
    C --> E["Fetcher Registry (34 Repositories)"]
    D --> E
    
    E --> F["Parallel Multi-Engine Search"]
    F --> G["DOI Normalization & Dedup Engine"]
    G --> H["Open PDF Fetch"]
    H --> I["In-Memory pdfplumber Parser"]
    
    I --> J{"AI Router Available?"}
    J -->|"Yes (Gemini / OpenRouter)"| K["LLM Extractor & Entity Resolver"]
    J -->|"No / Fallback"| L["Heuristic Pattern & Layout Matcher"]
    
    K --> M["Strict 3-Field Validator (Title + Author + Email)"]
    L --> M
    M --> N["DNS MX & SMTP Verifier"]
    N --> O["Formatted Excel (.xlsx) & Live Table UI"]
```

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/Nitro-Builds-Yash/Pulsus-MedScout.git
cd Pulsus-MedScout

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Start the Web Application

```bash
python run.py
```
Open your browser and navigate to: **`http://localhost:5000`**

### 3. CLI Headless Usage

```bash
# Extract 15 oncology contacts from PubMed to CSV:
python cli.py --source pubmed --topic "immunotherapy oncology" --count 15 --output oncology.csv

# Query Semantic Scholar with year range and live email verification:
python cli.py --source semanticscholar --topic "cardiovascular genetics" --year-from 2023 --verify-emails --output cardio.xlsx
```

---

## 🤖 AI Router Setup (Optional)

To enable LLM-based entity extraction, create a `.env` file in the root directory:

```ini
# Google Gemini
GEMINI_API_KEY=AIzaSy...

# Or OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemini-2.0-flash-001
```

If no API keys are provided, Pulsus MedScout runs fully autonomously using its built-in regex and layout heuristic engine.

Downloaded PDFs are processed in memory and removed from the task's temporary source folders by default. To keep them for debugging, set `KEEP_DOWNLOADED_PDFS=1` in the environment before starting the app.

---

## 👤 Author & Maintainer

* **Yash** — GitHub: [@Nitro-Builds-Yash](https://github.com/Nitro-Builds-Yash)

---

## 👥 Contributions & Credits

| Contributor / System | Role & Focus | Share |
|:---|:---|:---:|
| **Yash** ([@Nitro-Builds-Yash](https://github.com/Nitro-Builds-Yash)) | Project Lead, Architecture, Pipeline & UI Engineering | **80%** |
| **Claude** (Anthropic) | System Architecture, Code Refactoring & Logic Optimization | **10%** |
| **Emergent AI** | Extraction Heuristics, Pattern Discovery & AI Router Integration | **10%** |

---

## ⚖️ License

Distributed under the **MIT License**. See `LICENSE` for details.
