"""AI-powered Wikipedia article analyzer."""
import os

SYSTEM = """You are an experienced Wikipedia editor and content analyst.
You understand Wikipedia's core policies: NPOV (Neutral Point of View), Verifiability, No Original Research.
You are direct and specific. You cite exact phrases from the article when identifying issues.
You do not pad your analysis with compliments."""

ANALYSIS_PROMPT = """Analyze this Wikipedia article as an experienced editor would.

## Article Metadata
- Title: {title}
- URL: {url}
- Word count: {word_count}
- References: {ref_count}
- "Citation needed" tags: {citation_needed_count}
- NPOV/bias tags: {npov_tags}
- Cleanup tags: {cleanup_tags}
- Dead links: {dead_links}
- Categories: {categories}
- Last edited: {last_edited} by {last_editor}

## Article Text (first 8000 chars)
{text}

---

Write a structured editorial analysis:

## Quality Rating
Rate this article on Wikipedia's own scale: **Stub / Start / C / B / Good / Featured**
One sentence justification.

## Score
| Dimension | Score | Note |
|-----------|-------|------|
| Neutrality (NPOV) | /10 | |
| Verifiability | /10 | |
| Coverage & Depth | /10 | |
| Writing Quality | /10 | |
| Structure | /10 | |
| **Overall** | **/10** | |

## Neutrality Issues
List specific phrases or sections that show bias, loaded language, or one-sided framing.
Quote exact text. If none: "No neutrality issues found."

## Citation Gaps
Where does the article make claims without sources? Be specific — name the claim, not just "needs more citations."

## Missing Perspectives
What viewpoints, regions, time periods, or groups are underrepresented or absent?

## Factual Concerns
Any claims that seem questionable, outdated, or contradicted by the categories/context?

## Top 3 Editing Priorities
Concrete, actionable improvements an editor should make first.

## Verdict
One sentence: is this article trustworthy as a reference for a general reader?"""


def analyze(article: dict, provider: str) -> str:
    prompt = ANALYSIS_PROMPT.format(
        title=article["title"],
        url=article["url"],
        word_count=article["word_count"],
        ref_count=article["ref_count"],
        citation_needed_count=article["citation_needed_count"],
        npov_tags=article["npov_tags"],
        cleanup_tags=article["cleanup_tags"],
        dead_links=article["dead_links"],
        categories=", ".join(article["categories"]),
        last_edited=article["last_edited"],
        last_editor=article["last_editor"],
        text=article["text"],
    )

    if provider == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=3000,
            thinking={"type": "adaptive"},
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            msg = stream.get_final_message()
            for block in reversed(msg.content):
                if block.type == "text":
                    return block.text
            return ""

    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=SYSTEM)
        return model.generate_content(prompt).text

    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        return client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
        ).choices[0].message.content

    elif provider == "groq":
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
        ).choices[0].message.content

    raise ValueError(f"Unknown provider: {provider}")
