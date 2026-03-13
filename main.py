#!/usr/bin/env python3
"""wikipedia-lens — AI editorial analysis of any Wikipedia article."""
import argparse
import os
import sys

# auto-load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROVIDERS = ["gemini", "claude", "openai", "groq"]
API_KEY_MAP = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq":   "GROQ_API_KEY",
}


def main():
    parser = argparse.ArgumentParser(
        prog="wikipedia-lens",
        description="AI editorial analysis of any Wikipedia article.",
        epilog="""examples:
  python main.py "Roman Empire"
  python main.py https://en.wikipedia.org/wiki/Chernobyl_disaster
  python main.py "Lukashenko" --provider claude --format md -o report.md
  python main.py https://fr.wikipedia.org/wiki/Paris --provider gemini
        """,
    )
    parser.add_argument("article", help="Wikipedia article title or URL")
    parser.add_argument("--provider", choices=PROVIDERS, default="gemini")
    parser.add_argument("--format", choices=["console", "md"], default="console", dest="fmt")
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    key = API_KEY_MAP[args.provider]
    if not os.environ.get(key):
        print(f"error: {key} not set", file=sys.stderr)
        sys.exit(2)

    from fetcher import fetch
    from analyzer import analyze

    print(f"Fetching: {args.article}", file=sys.stderr)
    article = fetch(args.article)
    print(f"✓ {article['title']} — {article['word_count']} words, "
          f"{article['ref_count']} refs, "
          f"{article['citation_needed_count']} citation-needed tags", file=sys.stderr)

    print(f"Analyzing with {args.provider}...", file=sys.stderr)
    analysis = analyze(article, args.provider)
    print("✓ Analysis complete", file=sys.stderr)

    sep = "─" * 72
    if args.fmt == "console":
        BOLD = "\033[1m"; CYAN = "\033[96m"; RESET = "\033[0m"
        output = (
            f"{sep}\n"
            f"  {BOLD}wikipedia-lens{RESET}  "
            f"{CYAN}{article['title']}{RESET}  "
            f"· {article['word_count']} words · {article['ref_count']} refs\n"
            f"  {article['url']}\n"
            f"  analyzed by {BOLD}{args.provider}{RESET}\n"
            f"{sep}\n\n"
            f"{analysis}\n\n{sep}"
        )
    else:
        output = (
            f"# wikipedia-lens: {article['title']}\n\n"
            f"**URL:** {article['url']}  \n"
            f"**Words:** {article['word_count']} · **Refs:** {article['ref_count']} · "
            f"**Analyzed by:** `{args.provider}`\n\n---\n\n"
            f"{analysis}\n"
        )

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
