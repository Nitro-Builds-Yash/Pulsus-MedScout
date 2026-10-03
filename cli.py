import os
import sys
import argparse
import pandas as pd
from pathlib import Path

# Add WS2.0 to path
WS_DIR = Path(__file__).resolve().parent / "WS2.0"
if str(WS_DIR) not in sys.path:
    sys.path.insert(0, str(WS_DIR))

import config
from extractors.arxiv_fetcher import fetch_arxiv_papers
from extractors.plos_fetcher import fetch_plos_papers
from extractors.biorxiv_fetcher import fetch_biorxiv_papers
from extractors.crossref_fetcher import fetch_crossref_papers
from extractors.elife_fetcher import fetch_elife_papers
from extractors.europepmc_fetcher import fetch_europepmc_papers
from extractors.imedpub_fetcher import fetch_imedpub_papers
from extractors.openalex_fetcher import fetch_openalex_papers
from extractors.sciencedirect_fetcher import fetch_sciencedirect_papers
from extractors.pubmed_fetcher import fetch_pubmed_papers
from extractors.semanticscholar_fetcher import fetch_semanticscholar_papers
from extractors.email_verifier import check_email_deliverability

FETCHERS = {
    "arxiv": fetch_arxiv_papers,
    "plos": fetch_plos_papers,
    "pubmed": fetch_pubmed_papers,
    "semanticscholar": fetch_semanticscholar_papers,
    "biorxiv": fetch_biorxiv_papers,
    "crossref": fetch_crossref_papers,
    "elife": fetch_elife_papers,
    "europepmc": fetch_europepmc_papers,
    "imedpub": fetch_imedpub_papers,
    "openalex": fetch_openalex_papers,
    "sciencedirect": fetch_sciencedirect_papers,
}

def run_cli():
    parser = argparse.ArgumentParser(
        description="Academic Author & Email Extractor CLI Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python cli.py --source arxiv --topic "machine learning in healthcare" --count 10
  python cli.py --source plos --topic "immunology" --count 20 --verify-emails --output immunology.csv
  python cli.py --source openalex --topic "quantum computing" --year-from 2023 --output quantum.xlsx
        """
    )
    parser.add_argument("--source", "-s", required=True, choices=list(FETCHERS.keys()),
                        help="Target academic journal / database source")
    parser.add_argument("--topic", "-t", required=True, help="Topic or keyword query")
    parser.add_argument("--count", "-n", type=int, default=10, help="Number of papers to retrieve (default: 10)")
    parser.add_argument("--output", "-o", help="Output file path (.csv or .xlsx)")
    parser.add_argument("--year-from", type=int, help="Filter papers published from year (e.g., 2022)")
    parser.add_argument("--year-to", type=int, help="Filter papers published up to year (e.g., 2026)")
    parser.add_argument("--verify-emails", action="store_true", help="Perform MX and mailbox verification on extracted emails")
    parser.add_argument("--download-dir", default=str(config.PDFS_DIR), help="Custom directory for saved PDFs")

    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f" Academic Author & Email Extractor — CLI")
    print(f" Source: {args.source.upper()} | Topic: '{args.topic}' | Count: {args.count}")
    print(f"=======================================================\n")

    filters = {}
    if args.year_from:
        filters["year_from"] = args.year_from
    if args.year_to:
        filters["year_to"] = args.year_to

    fetcher_fn = FETCHERS[args.source]
    os.makedirs(args.download_dir, exist_ok=True)

    print(f"[*] Querying {args.source} database...")
    try:
        results = fetcher_fn(args.topic, args.count, args.download_dir, filters=filters)
    except TypeError:
        # Some fetchers may take (topic, count, target_dir)
        try:
            results = fetcher_fn(args.topic, args.count, args.download_dir)
        except Exception as e:
            print(f"[!] Error executing fetcher: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"[!] Error executing fetcher: {e}")
        sys.exit(1)

    if not results:
        print("[-] No papers found or no emails extracted.")
        return

    print(f"[+] Retrieved {len(results)} paper record(s).\n")

    # If results is list of dicts with extracted contacts
    rows = []
    for item in results:
        if isinstance(item, dict):
            # Check if emails/authors are inside
            emails = item.get("emails", [])
            authors = item.get("authors", [])
            title = item.get("title", "N/A")
            doi = item.get("doi", item.get("url", "N/A"))

            if emails:
                for idx, email in enumerate(emails):
                    author = authors[idx] if idx < len(authors) else (authors[0] if authors else "Author")
                    status, reason = ("N/A", "Skipped")
                    if args.verify_emails:
                        status, reason = check_email_deliverability(email)
                    rows.append({
                        "Source": args.source,
                        "Title": title,
                        "Author": author,
                        "Email": email,
                        "DOI/URL": doi,
                        "Verification Status": status,
                        "Verification Reason": reason
                    })
            else:
                # Include paper even if email wasn't found directly in search dict
                rows.append({
                    "Source": args.source,
                    "Title": title,
                    "Author": ", ".join(authors) if isinstance(authors, list) else str(authors),
                    "Email": "N/A",
                    "DOI/URL": doi,
                    "Verification Status": "No Email",
                    "Verification Reason": "PDF parsing required or email not listed"
                })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    if args.output:
        out_path = Path(args.output)
        if out_path.suffix.lower() == ".xlsx":
            df.to_excel(out_path, index=False)
        else:
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"\n[✓] Results successfully exported to: {out_path.resolve()}")

if __name__ == "__main__":
    run_cli()
