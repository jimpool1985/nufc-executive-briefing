"""
NUFC Executive Intelligence Briefing — Daily Automation
Runs every day at 9am via GitHub Actions.
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
            "football PSR financial rules April 2026",
            "Premier League club finance law April 10 2026",
        ],
        "instruction": "Topics: PSR/FFP updates, financial regulations, legal rulings, sponsorship deals, broadcast revenue, club accounts. Sources: Law in Sport, Swiss Ramble, The Athletic, BBC Sport, Reuters, The Times."
    },
    {
        "id": "infra",
        "label": "Infrastructure & Development",
        "queries": [
            "football stadium training ground development April 2026",
            "Newcastle United St James Park infrastructure April 2026",
        ],
        "instruction": "Topics: stadium projects, training ground developments, planning applications, construction milestones, naming rights. Pay particular attention to Newcastle United infrastructure news. Sources: BBC Sport, The Athletic, Sky Sports, local newspapers, club official announcements."
    },
    {
        "id": "governing",
        "label": "Governing Bodies",
        "queries": [
            "Premier League FA UEFA FIFA decision rule April 10 2026",
            "football governing body announcement April 2026",
        ],
        "instruction": "Topics: Premier League rule changes, FA disciplinary decisions, UEFA/FIFA policy announcements, IFR updates, VAR policy, transfer window rules. Sources: PL official, FA official, UEFA official, FIFA official, BBC Sport, Sky Sports."
    },
    {
        "id": "europe",
        "label": "Big 5 European Leagues",
        "queries": [
            "La Liga Bundesliga Serie A Ligue 1 news April 10 2026",
            "European football transfer result news today April 2026",
        ],
        "instruction": "Topics: major transfers, club financial news, managerial changes, significant results, European competition. Sources: Reuters, The Athletic, Sky Sports, BBC Sport."
    },
    {
        "id": "world",
        "label": "World Football",
        "queries": [
            "FIFA Club World Cup Saudi Pro League news April 2026",
            "international football World Cup 2026 news April 10 2026",
        ],
        "instruction": "Topics: FIFA Club World Cup, Saudi Pro League, MLS, World Cup 2026, global football news. Sources: Reuters, BBC Sport, FIFA official, The Athletic, ESPN."
    },
    {
        "id": "premier",
        "label": "Premier League",
        "queries": [
            "Premier League results standings news April 10 2026",
            "Premier League transfer injury manager news April 2026",
        ],
        "instruction": "Topics: match results, table standings, confirmed transfers, managerial news, injuries, club announcements. Exclude Newcastle United. Sources: BBC Sport, Sky Sports, The Athletic, The Guardian."
    },
    {
        "id": "newcastle",
        "label": "Newcastle United",
        "queries": [
            "Newcastle United NUFC news April 10 2026",
            "Newcastle United transfer team news April 2026",
        ],
        "instruction": "Topics: match results, transfers, Eddie Howe press conference, player injuries, PIF ownership, commercial deals, St James' Park. Sources: Chronicle Live, BBC Sport, Sky Sports, The Athletic, NUFC official."
    },
]

# Month name to number mapping for date parsing
MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,
    "sep":9,"oct":10,"nov":11,"dec":12
}

def get_day_info():
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    day_label = today.strftime("%A %d %B %Y")
    date_label = today.strftime("%-d %B %Y")
    today_str = today.strftime("%d %B %Y")
    yesterday_str = yesterday.strftime("%d %B %Y")
    return day_label, date_label, today, yesterday, today_str, yesterday_str

def is_recent(source_str, today, yesterday):
    """
    Parse the source field and check if the article date is today or yesterday.
    Returns True if recent, False if old, None if date cannot be determined.
    """
    s = source_str.lower()

    # Reject obvious old year markers
    for old_year in ["2024", "2023", "2022", "2021", "2020"]:
        if old_year in s:
            return False

    # Check for relative terms
    if any(x in s for x in ["today", "just now", "hours ago", "hour ago", "minutes ago"]):
        return True
    if "1 day ago" in s or "yesterday" in s:
        return True
    if re.search(r"\b[2-9] days? ago\b", s):
        return False
    if re.search(r"\b[1-9]\d+ days? ago\b", s):
        return False
    if "week ago" in s or "weeks ago" in s or "month ago" in s or "months ago" in s:
        return False

    # Try to extract a date with day + month (+ optional year)
    # Patterns: "April 10", "10 April", "10 Apr", "Apr 10"
    pattern = re.search(
        r"(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"
        r"(?:\s+(\d{4}))?",
        s
    )
    if not pattern:
        pattern = re.search(
            r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"
            r"\s+(\d{1,2})(?:\s+(\d{4}))?",
            s
        )
        if pattern:
            month_str = pattern.group(1)
            day = int(pattern.group(2))
            year = int(pattern.group(3)) if pattern.group(3) else today.year
        else:
            # Can't determine date — allow through but flag
            return None
    else:
        day = int(pattern.group(1))
        month_str = pattern.group(2)
        year = int(pattern.group(3)) if pattern.group(3) else today.year

    month = MONTHS.get(month_str)
    if not month:
        return None

    try:
        article_date = datetime.date(year, month, day)
    except ValueError:
        return None

    # Accept today or yesterday only
    return article_date >= yesterday

def filter_recent_items(items, today, yesterday):
    """Remove any items that are not from today or yesterday."""
    kept = []
    for item in items:
        source = item.get("source", "")
        result = is_recent(source, today, yesterday)
        if result is True:
            kept.append(item)
        elif result is None:
            # Date unclear — include it but flag in console
            print(f"    ⚠ Date unclear, including: {source[:60]}")
            kept.append(item)
        else:
            print(f"    ✗ Rejected old article: {source[:60]}")
    return kept

def search_category(client, category, today_str, yesterday_str):
    print(f"  Searching: {category['label']}...")

    combined_queries = " | ".join(category['queries'])

    prompt = f"""You are a senior intelligence analyst. Today is {today_str}.

Search for news in this category: {category['label']}

Queries: {combined_queries}

{category['instruction']}

CRITICAL DATE RULE: Only return articles published on {today_str} or {yesterday_str}.
Reject any article from before {yesterday_str}. If unsure of publication date, exclude it.
Return between 2 and 4 items. If no genuinely recent articles exist, return [].

Return ONLY a JSON array, no other text:

[
  {{
    "category": "{category['id']}",
    "badge": "News",
    "title": "Headline",
    "summary": "2-3 sentences. Key facts and numbers for a senior football executive.",
    "exec_note": "1-2 sentences on the business or strategic implication. General observation, no specific roles mentioned.",
    "source": "Publication name, {today_str} or {yesterday_str}",
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
    today = json.loads(today_match.group(1)) if today_match else None
    archive = json.loads(arch_match.group(1)) if arch_match else []
    return today, archive

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

    day_label, date_label, today, yesterday, today_str, yesterday_str = get_day_info()
    print(f"\nDate: {day_label}")
    print(f"Accepting articles from: {today_str} or {yesterday_str}\n")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_items = []
    for i, category in enumerate(CATEGORIES):
        if i > 0:
            print(f"    Pausing 30 seconds...")
            time.sleep(30)

        raw_items = search_category(client, category, today_str, yesterday_str)
        # Python-side date filter — removes anything old regardless of what the model returned
        filtered = filter_recent_items(raw_items, today, yesterday)
        print(f"    {category['label']}: {len(raw_items)} found, {len(filtered)} passed date filter")
        all_items.extend(filtered)

    if not all_items:
        print("\nNo current items passed date filter. Preserving existing content.")
        return

    print(f"\nTotal current items: {len(all_items)}")

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
