"""Fetch Wikipedia article content and metadata via the MediaWiki API."""
import json
import re
import urllib.parse
import urllib.request
import sys


def _api(params: dict, lang: str = "en") -> dict:
    base = f"https://{lang}.wikipedia.org/w/api.php"
    params["format"] = "json"
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "wikipedia-lens/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def parse_title(source: str) -> tuple[str, str]:
    """Return (title, lang) from a URL or plain title."""
    # https://en.wikipedia.org/wiki/Roman_Empire
    m = re.match(r"https?://([a-z]+)\.wikipedia\.org/wiki/(.+)", source)
    if m:
        lang = m.group(1)
        title = urllib.parse.unquote(m.group(2)).replace("_", " ")
        return title, lang
    # plain title — default to English
    return source.strip(), "en"


def fetch(source: str) -> dict:
    title, lang = parse_title(source)

    # plain text extract
    data = _api({
        "action": "query",
        "titles": title,
        "prop": "extracts|info|revisions|categories|links|extlinks",
        "exintro": False,
        "explaintext": True,
        "inprop": "url|length",
        "rvprop": "size|timestamp|user",
        "rvlimit": 1,
        "cllimit": 20,
        "pllimit": 50,
        "ellimit": 20,
        "redirects": True,
    }, lang)

    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))

    if "missing" in page:
        print(f"error: article not found: {title!r}", file=sys.stderr)
        sys.exit(1)

    # citation count from wikitext
    wikitext_data = _api({
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "redirects": True,
    }, lang)
    wt_pages = wikitext_data.get("query", {}).get("pages", {})
    wt_page  = next(iter(wt_pages.values()))
    wikitext = (wt_page.get("revisions", [{}])[0]
                .get("slots", {}).get("main", {}).get("*", ""))

    ref_count      = len(re.findall(r"<ref", wikitext, re.IGNORECASE))
    cite_needed    = len(re.findall(r"\{\{citation needed", wikitext, re.IGNORECASE))
    npov_tags      = len(re.findall(r"\{\{(pov|neutrality|bias|unbalanced)", wikitext, re.IGNORECASE))
    stub_tags      = len(re.findall(r"\{\{stub", wikitext, re.IGNORECASE))
    cleanup_tags   = len(re.findall(r"\{\{(cleanup|rewrite|expand|improve)", wikitext, re.IGNORECASE))
    dead_links     = len(re.findall(r"\{\{(dead link|broken link)", wikitext, re.IGNORECASE))

    text = page.get("extract", "")
    categories = [c["title"].replace("Category:", "") for c in page.get("categories", [])]
    ext_links  = [l["*"] for l in page.get("extlinks", [])]

    return {
        "title": page.get("title", title),
        "lang": lang,
        "url": page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}"),
        "length_bytes": page.get("length", 0),
        "word_count": len(text.split()),
        "text": text[:8000],  # cap for LLM
        "categories": categories[:15],
        "external_links": ext_links[:10],
        "last_edited": (page.get("revisions", [{}])[0].get("timestamp", "unknown")),
        "last_editor": (page.get("revisions", [{}])[0].get("user", "unknown")),
        "ref_count": ref_count,
        "citation_needed_count": cite_needed,
        "npov_tags": npov_tags,
        "stub_tags": stub_tags,
        "cleanup_tags": cleanup_tags,
        "dead_links": dead_links,
    }
