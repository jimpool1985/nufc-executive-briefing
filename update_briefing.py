"""
NUFC Executive Intelligence Briefing — Daily Automation
Runs every day at 9am BST via GitHub Actions.
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

CATEGORIES = [
    {
        "id": "legal",
        "label": "Legal & Financial",
        "queries": [
            "football PSR financial sustainability rules 2026",
            "Premier League club finance law regulation 2026",
        ],
        "instruction": "Topics: PSR/FFP updates, financial regulations, legal rulings, sponsorship deals, broadcast revenue, club accounts. Sources: Law in Sport, Swiss Ramble, The Athletic, BBC Sport, Reuters, The Times, The Guardian."
    },
    {
        "id": "infra",
        "label": "Infrastructure & Development",
        "queries": [
            "football stadium training ground development 2026",
            "Newcastle United St James Park infrastructure 2026",
        ],
        "instruction": "Topics: stadium projects, training ground developments, planning applications, construction milestones, naming rights deals. Pay particular attention to Newcastle United infrastructure news. Sources: BBC Sport, The Athletic, Sky Sports, local newspapers, club official announcements."
    },
    {
        "id": "governing",
        "label": "Governing Bodies",
        "queries": [
            "Premier League FA UEFA FIFA decision rule announcement 2026",
            "football governing body disciplinary IFR regulator 2026",
        ],
        "instruction": "Topics: Premier League rule changes, FA disciplinary decisions, UEFA/FIFA policy announcements, IFR updates, VAR policy, transfer window rules, agent regulations. Sources: PL official, FA official, UEFA official, FIFA official, BBC Sport, Sky Sports."
    },
    {
        "id": "europe",
        "label": "Big 5 European Leagues",
        "queries": [
            "La Liga Bundesliga Serie A Ligue 1 news 2026",
            "European football major transfer result news 2026",
        ],
        "instruction": "Topics: major transfers, club financial news, managerial changes, significant results, European competition. Sources: Reuters, The Athletic, Sky Sports, BBC Sport."
    },
    {
        "id": "world",
        "label": "World Football",
        "queries": [
            "FIFA Club World Cup Saudi Pro League news 2026",
            "World Cup 2026 international football news 2026",
        ],
        "instruction": "Topics: FIFA Club World Cup, Saudi Pro League, MLS, World Cup 2026 preparations, global football news. Sources: Reuters, BBC Sport, FIFA official, The Athletic, ESPN."
    },
    {
        "id": "premier",
        "label": "Premier League",
        "queries": [
            "Premier League results standings news 2026",
            "Premier League transfer injury manager club news 2026",
        ],
        "instruction": "Topics: match results, table standings, confirmed transfers, managerial news, injuries, club announcements. Exclude Newcastle United stories. Sources: BBC Sport, Sky Sports, The Athletic, The Guardian, The Times."
    },
    {
        "id": "newcastle",
        "label": "Newcastle United",
        "queries": [
            "Newcastle United NUFC news 2026",
            "Newcastle United transfer team news Eddie Howe 2026",
        ],
        "instruction": "Topics: match results, transfers, Eddie Howe press conference, player injuries, PIF ownership, commercial deals, St James Park, academy, women's team. Sources: Chronicle Live, BBC Sport, Sky Sports, The Athletic, NUFC official."
    },
]

MONTH_NAMES = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,
    "sep":9,"oct":10,"nov":11,"dec":12
}

def get_day_info():
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=7)
    day_label = today.strftime("%A %d %B %Y")
    date_label = today.strftime("%-d %B %Y")
    today_str = today.strftime("%d %B %Y")
    cutoff_str = cutoff.strftime("%d %B %Y")
    return day_label, date_label, today, cutoff, today_str, cutoff_str

def parse_date_from_source(source_str, current_year):
    """
    Try to extract a datetime.date from a source string.
    Returns a date object if successful, None otherwise.
    """
    s = source_str.lower()

    # Relative: today/yesterday
    today = datetime.date.today()
    if "today" in s or "just now" in s or "breaking" in s:
        return today
    if "yesterday" in s:
        return today - datetime.timedelta(days=1)

    # Relative: N days ago
    m = re.search(r"(\d+)\s+days?\s+ago", s)
    if m:
        return today - datetime.timedelta(days=int(m.group(1)))

    # Relative: N hours/minutes ago
    if re.search(r"\d+\s+(hours?|minutes?)\s+ago", s):
        return today

    # Relative: 1 week ago
    if re.search(r"1\s+week\s+ago", s):
        return today - datetime.timedelta(days=7)

    # Relative: N weeks ago — treat as too old
    m = re.search(r"(\d+)\s+weeks?\s+ago", s)
    if m:
        return today - datetime.timedelta(weeks=int(m.group(1)))

    # Relative: months/years ago — too old
    if re.search(r"\d+\s+(months?|years?)\s+ago", s):
        return today - datetime.timedelta(days=365)
    if re.search(r"(last\s+month|last\s+year|months?\s+ago|years?\s+ago)", s):
        return today - datetime.timedelta(days=365)

    # Absolute: try "Month Day Year" or "Day Month Year"
    # e.g. "April 10, 2026" or "10 April 2026" or "April 10" or "10 April"
    patterns = [
        # Month Day Year
        r"(january|february|march|april|may|june|july|august|september|october|november|december"
        r"|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"\s+(\d{1,2})(?:[,\s]+(\d{4}))?",
        # Day Month Year
        r"(\d{1,2})\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december"
        r"|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"(?:[,\s]+(\d{4}))?",
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

    return None  # Could not determine date

def is_acceptable(source_str, today, cutoff):
    """
    Returns True = keep, False = reject, None = uncertain.
    Uses fully dynamic date comparison — no hardcoded month names.
    """
    s = source_str.lower()

    # Hard reject any year before 2026
    if re.search(r"\b(2025|2024|2023|2022|2021|2020|2019|2018)\b", s):
        return False

    # Try to parse a date
    article_date = parse_date_from_source(source_str, today.year)

    if article_date is None:
        # Cannot determine date — allow through with warning
        return None

    if article_date > today:
        # Future date — parsing error, allow through
        return None

    # Accept if within the 7-day window
    return article_date >= cutoff

def filter_items(items, today, cutoff):
    kept = []
    for item in items:
        source = item.get("source", "")
        result = is_acceptable(source, today, cutoff)
        if result is True:
            kept.append(item)
        elif result is None:
            print(f"    ⚠ Date unclear, keeping: {source[:70]}")
            kept.append(item)
        else:
            print(f"    ✗ Rejected (too old): {source[:70]}")
    return kept

def search_category(client, category, today_str, cutoff_str):
    print(f"  Searching: {category['label']}...")

    combined_queries = " | ".join(category['queries'])

    prompt = f"""You are a senior intelligence analyst. Today is {today_str}.

Search for news in this category: {category['label']}

Search queries: {combined_queries}

{category['instruction']}

DATE RULE: Only return articles published between {cutoff_str} and {today_str}.
Do not include anything from 2025 or earlier.
Do not include anything more than 7 days old.
If genuinely no relevant news exists in the last 7 days, return [].

Return 2-4 items as a JSON array only (no other text, no markdown):

[
  {{
    "category": "{category['id']}",
    "badge": "News",
    "title": "Specific headline",
    "summary": "2-3 sentences. Key facts and numbers for a senior football executive.",
    "exec_note": "1-2 sentences on the business or strategic implication. General observation, no specific roles mentioned.",
    "source": "Publication name, exact date",
    "link": "https://url"
  }}
]

Badge options: "News", "Official update", "Regulatory", "Financial", "Transfer", "Legal ruling", "Development", "Analysis", "Match report", "Data"

Return ONLY the JSON array."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        clean = full_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-z]*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        items = json.loads(clean)
        if isinstance(items, list):
            return items

    except anthropic.RateLimitError:
        print(f"    Rate limit — waiting 60 seconds...")
        time.sleep(60)
        return []
    except Exception as e:
        print(f"    Warning: {category['label']}: {e}")

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

    day_label, date_label, today, cutoff, today_str, cutoff_str = get_day_info()
    print(f"\nDate      : {day_label}")
    print(f"Cutoff    : {cutoff_str} (7-day window, fully dynamic)")
    print()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_items = []
    for i, category in enumerate(CATEGORIES):
        if i > 0:
            print(f"    Pausing 30 seconds...")
            time.sleep(30)

        raw = search_category(client, category, today_str, cutoff_str)
        filtered = filter_items(raw, today, cutoff)
        print(f"    {category['label']}: {len(raw)} returned → {len(filtered)} kept")
        all_items.extend(filtered)

    print(f"\nTotal items after filtering: {len(all_items)}")

    if not all_items:
        print("No items passed date filter. Preserving existing content.")
        return

    html = load_current_html()
    current_today, current_archive = extract_current_data(html)

    new_archive = current_archive
    if current_today and current_today.get("items"):
        new_archive = [current_today] + current_archive
        new_archive = new_archive[:14]
        print(f"Archived: {current_today['day']} ({len(current_today['items'])} items)")

    new_today = {"day": day_label, "date": date_label, "items": all_items}
    updated_html = build_new_html(html, new_today, new_archive)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(updated_html)

    print(f"\n✓ Done: {day_label} — {len(all_items)} items, {len(new_archive)} days archived")

if __name__ == "__main__":
    main()
