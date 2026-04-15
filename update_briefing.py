"""
NUFC Executive Intelligence Briefing — Daily Automation
Redesigned: 3 broad searches instead of 7 narrow ones.
Faster, more reliable, better coverage.
"""

import os
import json
import re
import datetime
import anthropic
import time

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
HTML_PATH = "NUFC - Executive Intelligence Briefing.html"

DATA_BLOCK_START = "// ── DATA BLOCK START"
DATA_BLOCK_END   = "// ── DATA BLOCK END"

MONTH_NAMES = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,
    "sep":9,"oct":10,"nov":11,"dec":12
}

# Three broad search prompts — each covers multiple categories
SEARCH_BLOCKS = [
    {
        "name": "Block 1: NUFC + Premier League + Governing Bodies",
        "prompt_template": """Today is {today}. You are compiling a daily intelligence briefing for senior executives at Newcastle United FC.

Search the web thoroughly for football news published in the last 7 days (since {cutoff}).

SEARCH 1: Newcastle United — search "Newcastle United news {today_month} 2026" and "NUFC transfer team news {today_month} 2026"
Sources to check: Chronicle Live, BBC Sport, Sky Sports, The Athletic, NUFC official, talkSPORT, The Guardian, The Times

SEARCH 2: Premier League — search "Premier League news results {today_month} 2026" and "Premier League transfer injury {today_month} 2026"
Sources: BBC Sport, Sky Sports, The Athletic, Premier League official, The Guardian, The Times, Mirror Sport
Exclude Newcastle United stories from this search.

SEARCH 3: Governing Bodies — search "Premier League FA UEFA FIFA announcement rule {today_month} 2026" and "Independent Football Regulator IFR 2026"
Sources: PL official, FA official, UEFA official, FIFA official, BBC Sport, Sky Sports, The Athletic

Return a JSON array of ALL items found across all three searches. Use these category IDs:
- "newcastle" for Newcastle United news
- "premier" for Premier League news (non-Newcastle)
- "governing" for governing body news

For each item:
{{
  "category": "newcastle|premier|governing",
  "badge": "News|Official update|Transfer|Regulatory|Match report|Financial",
  "title": "Specific headline",
  "summary": "2-3 sentences with key facts for a senior football executive.",
  "exec_note": "1-2 sentences on the strategic or business implication. No specific role names.",
  "source": "Publication, Day Month Year e.g. BBC Sport, 14 April 2026",
  "link": "https://actual-url"
}}

RULES:
- Only articles from the last 7 days (since {cutoff})
- No articles from 2025 or earlier
- Aim for 3-5 items per category — that is 9-15 items total
- Return ONLY the JSON array, no other text"""
    },
    {
        "name": "Block 2: Big 5 Leagues + World Football",
        "prompt_template": """Today is {today}. You are compiling a daily intelligence briefing for senior executives at Newcastle United FC.

Search the web thoroughly for football news published in the last 7 days (since {cutoff}).

SEARCH 1: Big 5 European Leagues — search "La Liga Bundesliga Serie A Ligue 1 news {today_month} 2026" and "Champions League Europa League results {today_month} 2026" and "Real Madrid Barcelona Bayern Munich PSG news this week"
Sources: BBC Sport, Sky Sports, Reuters, The Athletic, Marca (English), Goal.com, ESPN, UEFA official

SEARCH 2: World Football — search "FIFA Club World Cup 2025 news results this week" and "Saudi Pro League MLS international football {today_month} 2026" and "World Cup 2026 news {today_month}"
Sources: Reuters, BBC Sport, FIFA official, The Athletic, ESPN, Sky Sports, Al Jazeera Sport

Return a JSON array of ALL items found across both searches. Use these category IDs:
- "europe" for Big 5 European league news
- "world" for world/global football news

For each item:
{{
  "category": "europe|world",
  "badge": "News|Transfer|Match report|Official update|Financial",
  "title": "Specific headline",
  "summary": "2-3 sentences with key facts for a senior football executive.",
  "exec_note": "1-2 sentences on the strategic or business implication. No specific role names.",
  "source": "Publication, Day Month Year e.g. Sky Sports, 14 April 2026",
  "link": "https://actual-url"
}}

RULES:
- Only articles from the last 7 days (since {cutoff})
- No articles from 2025 or earlier
- Aim for 3-5 items per category — that is 6-10 items total
- Return ONLY the JSON array, no other text"""
    },
    {
        "name": "Block 3: Legal/Financial + Infrastructure",
        "prompt_template": """Today is {today}. You are compiling a daily intelligence briefing for senior executives at Newcastle United FC.

Search the web thoroughly for football news published in the last 7 days (since {cutoff}).

SEARCH 1: Legal & Financial — search "football finance PSR FFP financial rules {today_month} 2026" and "Premier League club revenue sponsorship deal accounts 2026" and "football legal ruling transfer financial news {today_month} 2026"
Sources: Law in Sport, Swiss Ramble, The Athletic, BBC Sport, Reuters, The Times, The Guardian, Financial Times, Deloitte

SEARCH 2: Infrastructure & Development — search "football stadium training ground development {today_month} 2026" and "Premier League club facility planning construction 2026" and "Newcastle United St James Park stadium development 2026"
Sources: BBC Sport, The Athletic, Sky Sports, local newspapers, club official announcements, StadiumDB, Construction Enquirer

Return a JSON array of ALL items found across both searches. Use these category IDs:
- "legal" for financial and legal football news
- "infra" for stadium and infrastructure news

For each item:
{{
  "category": "legal|infra",
  "badge": "News|Financial|Regulatory|Development|Legal ruling|Official update",
  "title": "Specific headline",
  "summary": "2-3 sentences with key facts for a senior football executive.",
  "exec_note": "1-2 sentences on the strategic or business implication. No specific role names.",
  "source": "Publication, Day Month Year e.g. Law in Sport, 12 April 2026",
  "link": "https://actual-url"
}}

RULES:
- Only articles from the last 7 days (since {cutoff})
- No articles from 2025 or earlier
- Aim for 3-5 items per category — that is 6-10 items total
- Return ONLY the JSON array, no other text"""
    },
]

def get_day_info():
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=7)
    day_label = today.strftime("%A %d %B %Y")
    date_label = today.strftime("%-d %B %Y")
    today_str = today.strftime("%d %B %Y")
    cutoff_str = cutoff.strftime("%d %B %Y")
    today_month = today.strftime("%B")
    return day_label, date_label, today, cutoff, today_str, cutoff_str, today_month

def parse_date_from_source(source_str, current_year, today):
    s = source_str.lower()

    if re.search(r"\b(today|just now|breaking)\b", s):
        return today
    if "yesterday" in s:
        return today - datetime.timedelta(days=1)

    m = re.search(r"(\d+)\s+days?\s+ago", s)
    if m:
        return today - datetime.timedelta(days=int(m.group(1)))

    if re.search(r"\d+\s+(hours?|minutes?)\s+ago", s):
        return today

    if re.search(r"1\s+week\s+ago", s):
        return today - datetime.timedelta(days=7)

    m = re.search(r"(\d+)\s+weeks?\s+ago", s)
    if m:
        return today - datetime.timedelta(weeks=int(m.group(1)))

    if re.search(r"\d+\s+(months?|years?)\s+ago|last\s+(month|year)|months?\s+ago|years?\s+ago", s):
        return today - datetime.timedelta(days=365)

    # Try to parse absolute date
    patterns = [
        r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:[,\s]+(\d{4}))?",
        r"(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:[,\s]+(\d{4}))?",
    ]
    for i, pattern in enumerate(patterns):
        m = re.search(pattern, s)
        if m:
            if i == 0:
                month_str, day_str = m.group(1), m.group(2)
                year = int(m.group(3)) if m.group(3) else current_year
            else:
                day_str, month_str = m.group(1), m.group(2)
                year = int(m.group(3)) if m.group(3) else current_year
            month = MONTH_NAMES.get(month_str)
            if not month:
                continue
            try:
                return datetime.date(year, int(day_str), month)
            except ValueError:
                continue

    return None

def is_acceptable(source_str, today, cutoff):
    s = source_str.lower()

    # Hard reject pre-2026
    if re.search(r"\b(2025|2024|2023|2022|2021|2020|2019|2018)\b", s):
        return False

    article_date = parse_date_from_source(source_str, today.year, today)

    if article_date is None:
        return None  # Uncertain — keep with warning

    if article_date > today:
        return None  # Parsing error — keep

    return article_date >= cutoff

def filter_items(items, today, cutoff):
    kept = []
    seen = set()
    for item in items:
        title = item.get("title", "").lower().strip()[:80]
        if title in seen:
            continue
        seen.add(title)

        source = item.get("source", "")
        result = is_acceptable(source, today, cutoff)
        if result is True:
            kept.append(item)
        elif result is None:
            print(f"    ⚠ Date unclear, keeping: {source[:60]}")
            kept.append(item)
        else:
            print(f"    ✗ Rejected (old): {source[:60]}")
    return kept

def run_search_block(client, block, today_str, cutoff_str, today_month):
    print(f"\n  Running {block['name']}...")

    prompt = block['prompt_template'].format(
        today=today_str,
        cutoff=cutoff_str,
        today_month=today_month
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block_content in response.content:
            if hasattr(block_content, "text"):
                full_text += block_content.text

        clean = full_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-z]*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        items = json.loads(clean)
        if isinstance(items, list):
            print(f"    Returned {len(items)} items")
            return items

    except anthropic.RateLimitError:
        print(f"    Rate limit hit — waiting 60 seconds...")
        time.sleep(60)
        return []
    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {e}")
        print(f"    Raw text (first 300): {full_text[:300] if 'full_text' in dir() else 'N/A'}")
        return []
    except Exception as e:
        print(f"    Error: {e}")
        return []

    return []

def load_current_html():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()

def extract_current_data(html):
    today_match = re.search(r"const TODAY=(\{.*?\});", html, re.DOTALL)
    arch_match  = re.search(r"const ARCHIVE=(\[.*?\]);",  html, re.DOTALL)
    today_data = json.loads(today_match.group(1)) if today_match else None
    archive = json.loads(arch_match.group(1)) if arch_match else []
    return today_data, archive

def build_new_html(html, new_today, new_archive):
    start = html.index(DATA_BLOCK_START)
    end   = html.index(DATA_BLOCK_END) + len(DATA_BLOCK_END)
    today_json   = json.dumps(new_today,   ensure_ascii=False)
    archive_json = json.dumps(new_archive, ensure_ascii=False)
    new_block = (
        f"{DATA_BLOCK_START} — replaced automatically on each daily update ————\n"
        f"// {'=' * 76}\n"
        f"const TODAY={today_json};\n"
        f"const ARCHIVE={archive_json};\n"
        f"// {'=' * 76}\n"
        f"{DATA_BLOCK_END}"
    )
    return html[:start] + new_block + html[end:]

def main():
    print("=" * 60)
    print("NUFC Executive Intelligence Briefing — Daily Automation")
    print("=" * 60)

    day_label, date_label, today, cutoff, today_str, cutoff_str, today_month = get_day_info()
    print(f"\nDate   : {day_label}")
    print(f"Cutoff : {cutoff_str} (7-day rolling window)")
    print(f"Month  : {today_month}")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_raw = []
    for i, block in enumerate(SEARCH_BLOCKS):
        if i > 0:
            print(f"\n  Pausing 20 seconds between blocks...")
            time.sleep(20)
        raw = run_search_block(client, block, today_str, cutoff_str, today_month)
        all_raw.extend(raw)

    print(f"\nTotal raw items from all searches: {len(all_raw)}")

    # Apply date filter to everything
    all_items = filter_items(all_raw, today, cutoff)
    print(f"Total items after date filter   : {len(all_items)}")

    # Summary by category
    from collections import Counter
    cats = Counter(item.get("category","?") for item in all_items)
    for cat, n in sorted(cats.items()):
        print(f"  {cat}: {n} items")

    if not all_items:
        print("\nNo items passed filter. Preserving existing content.")
        return

    html = load_current_html()
    current_today, current_archive = extract_current_data(html)

    new_archive = current_archive
    if current_today and current_today.get("items"):
        new_archive = [current_today] + current_archive
        new_archive = new_archive[:14]
        print(f"\nArchived: {current_today['day']} ({len(current_today['items'])} items)")

    new_today = {"day": day_label, "date": date_label, "items": all_items}
    updated_html = build_new_html(html, new_today, new_archive)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(updated_html)

    print(f"\n✓ Done: {day_label} — {len(all_items)} items across {len(cats)} categories")

if __name__ == "__main__":
    main()
