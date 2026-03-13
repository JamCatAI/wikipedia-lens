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
    m = re.match(r"https?://([a-z]+)\.wikipedia\.org/wiki/(.+)", source)
    if m:
        lang = m.group(1)
        title = urllib.parse.unquote(m.group(2)).replace("_", " ")
        return title, lang
    return source.strip(), "en"


def _wikitext_to_plain(wikitext: str) -> str:
    """Convert raw wikitext to readable plain text."""
    text = wikitext

    # remove <ref>...</ref> blocks
    text = re.sub(r"<ref[^>]*/?>.*?</ref>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<ref[^>]*/?>", " ", text, flags=re.IGNORECASE)

    # remove tables {| ... |}
    text = re.sub(r"\{\|.*?\|\}", " ", text, flags=re.DOTALL)

    # remove nested templates iteratively (up to 5 levels)
    for _ in range(5):
        text = re.sub(r"\{\{[^{}]*\}\}", " ", text)

    # remove remaining {{ }} fragments
    text = re.sub(r"\{\{.*?\}\}", " ", text, flags=re.DOTALL)

    # wiki links: [[File:...]] [[Image:...]] — remove entirely
    text = re.sub(r"\[\[(File|Image|Media):[^\]]*\]\]", " ", text, flags=re.IGNORECASE)

    # [[link|label]] → label,  [[link]] → link
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

    # external links [url label] → label
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)

    # headings == Title == → Title
    text = re.sub(r"={2,6}\s*(.+?)\s*={2,6}", r"\n\n\1\n", text)

    # bold/italic
    text = re.sub(r"'{2,3}", "", text)

    # HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    # remove lines that are purely wikitext noise (category, file lines)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("[[Category:", "[[File:", "[[Image:", "|", "!")):
            continue
        lines.append(stripped)

    text = "\n".join(lines)
    # collapse whitespace
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch(source: str) -> dict:
    title, lang = parse_title(source)

    # metadata: url, length, categories, external links, last edit
    meta_data = _api({
        "action": "query",
        "titles": title,
        "prop": "info|revisions|categories|extlinks",
        "inprop": "url|length",
        "rvprop": "size|timestamp|user",
        "rvlimit": 1,
        "cllimit": 20,
        "ellimit": 20,
        "redirects": True,
    }, lang)

    pages = meta_data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))

    if "missing" in page:
        print(f"error: article not found: {title!r}", file=sys.stderr)
        sys.exit(1)

    # edit history — last 50 revisions
    hist_data = _api({
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "timestamp|user|comment|size|flags",
        "rvlimit": 50,
        "redirects": True,
    }, lang)
    hist_pages = hist_data.get("query", {}).get("pages", {})
    revisions  = next(iter(hist_pages.values())).get("revisions", [])

    # full wikitext — source of truth for both text and metrics
    wt_data = _api({
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "redirects": True,
    }, lang)
    wt_pages = wt_data.get("query", {}).get("pages", {})
    wt_page  = next(iter(wt_pages.values()))
    wikitext = (wt_page.get("revisions", [{}])[0]
                .get("slots", {}).get("main", {}).get("*", ""))

    # metrics from raw wikitext
    ref_count    = len(re.findall(r"<ref", wikitext, re.IGNORECASE))
    cite_needed  = len(re.findall(r"\{\{citation needed", wikitext, re.IGNORECASE))
    npov_tags    = len(re.findall(r"\{\{(pov|neutrality|bias|unbalanced)", wikitext, re.IGNORECASE))
    stub_tags    = len(re.findall(r"\{\{stub", wikitext, re.IGNORECASE))
    cleanup_tags = len(re.findall(r"\{\{(cleanup|rewrite|expand|improve)", wikitext, re.IGNORECASE))
    dead_links   = len(re.findall(r"\{\{(dead link|broken link)", wikitext, re.IGNORECASE))

    # convert wikitext → plain text (fixes the truncation bug)
    text = _wikitext_to_plain(wikitext)

    # edit history metrics
    unique_editors = len({r.get("user", "") for r in revisions})
    revert_count   = sum(1 for r in revisions
                         if re.search(r"\brevert\b|\brvv?\b|\bundid\b", r.get("comment", ""), re.IGNORECASE))
    sizes = [r.get("size", 0) for r in revisions if "size" in r]
    size_delta = (sizes[0] - sizes[-1]) if len(sizes) >= 2 else 0
    recent_editors = list({r.get("user", "") for r in revisions[:10]})[:8]
    edit_comments  = [r.get("comment", "").strip() for r in revisions[:15] if r.get("comment", "").strip()]

    categories = [c["title"].replace("Category:", "") for c in page.get("categories", [])]
    ext_links  = [l["*"] for l in page.get("extlinks", [])]

    return {
        "title": page.get("title", title),
        "lang": lang,
        "url": page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}"),
        "length_bytes": page.get("length", 0),
        "word_count": len(text.split()),
        "text": text[:8000],
        "categories": categories[:15],
        "external_links": ext_links[:10],
        "last_edited": (page.get("revisions", [{}])[0].get("timestamp", "unknown")),
        "last_editor": (page.get("revisions", [{}])[0].get("user", "unknown")),
        "edit_count_sampled": len(revisions),
        "unique_editors": unique_editors,
        "revert_count": revert_count,
        "size_delta_recent": size_delta,
        "recent_editors": recent_editors,
        "edit_comments": edit_comments,
        "ref_count": ref_count,
        "citation_needed_count": cite_needed,
        "npov_tags": npov_tags,
        "stub_tags": stub_tags,
        "cleanup_tags": cleanup_tags,
        "dead_links": dead_links,
    }
