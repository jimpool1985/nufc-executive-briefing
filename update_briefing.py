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
            "football PSR profit sustainability rules financial 2026",
            "Premier League FFP financial fair play ruling April 2026",
            "football club finance law regulation transfer April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Topics: PSR/FFP updates, financial regulations, legal rulings, transfer financial rules, significant sponsorship or broadcast deals, club accounts, arbitration outcomes. Sources: Law in Sport, Swiss Ramble, Deloitte, The Athletic, BBC Sport, Reuters, The Times, The Guardian."
    },
    {
        "id": "infra",
        "label": "Infrastructure & Development",
        "queries": [
            "football stadium development planning construction April 2026",
            "Premier League training ground facility April 2026",
            "Newcastle United St James Park stadium April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Topics: stadium renovation or rebuild projects, training ground developments, planning applications, construction milestones, technology investments, naming rights deals. Pay particular attention to Newcastle United infrastructure news. Sources: BBC Sport, The Athletic, Sky Sports, local newspapers, club official announcements."
    },
    {
        "id": "governing",
        "label": "Governing Bodies",
        "queries": [
            "Premier League FA UEFA FIFA rule decision announcement April 2026",
            "Independent Football Regulator IFR update April 2026",
            "football governing body disciplinary April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Topics: Premier League rule changes or votes, FA disciplinary decisions, UEFA regulation updates, FIFA policy announcements, IFR updates, VAR policy, squad registration changes, transfer window rules, agent regulations. Sources: Premier League official, FA official, UEFA official, FIFA official, BBC Sport, Sky Sports, The Athletic."
    },
    {
        "id": "europe",
        "label": "Big 5 European Leagues",
        "queries": [
            "La Liga Bundesliga Serie A Ligue 1 news April 10 2026",
            "Real Madrid Barcelona Bayern Munich PSG transfer news this week",
            "European football major news today April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Topics: major transfers, club financial developments, managerial changes, significant match results, financial regulation compliance, European competition results. Sources: Reuters, AFP, The Athletic, Sky Sports, BBC Sport."
    },
    {
        "id": "world",
        "label": "World Football",
        "queries": [
            "FIFA Club World Cup news April 2026",
            "Saudi Pro League MLS international football April 2026",
            "World Cup 2026 news update April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Topics: FIFA decisions, Saudi Pro League, MLS, World Cup 2026, international tournaments, global transfer trends. Sources: Reuters, BBC Sport, FIFA official, The Athletic, ESPN."
    },
    {
        "id": "premier",
        "label": "Premier League",
        "queries": [
            "Premier League results standings April 10 2026",
            "Premier League transfer news confirmed April 2026",
            "Premier League club news manager injury April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Exclude Newcastle United stories. Topics: match results and table standings, confirmed transfers, managerial news, injuries, club financial announcements, broadcast deals. Sources: BBC Sport, Sky Sports, The Athletic, Premier League official, The Guardian, The Times."
    },
    {
        "id": "newcastle",
        "label": "Newcastle United",
        "queries": [
            "Newcastle United news April 10 2026",
            "Newcastle United transfer squad news April 2026",
            "NUFC Eddie Howe team news April 2026",
        ],
        "instruction": "Find news published in the last 48 hours only. Topics: match results, transfers, Eddie Howe press conference, player injuries, PIF ownership, commercial deals, St James' Park, academy, women's team. Sources: Chronicle Live, BBC Sport Newcastle, Sky Sports, The Athletic, Newcastle United official."
    },
]

def get_day_info():
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    day_label = today.strftime("%A %d %B %Y")
    date_label = today.strftime("%-d %B %Y")
    today_str = today.strftime("%d %B %Y")
    yesterday_str = yesterday.strftime("%d %B %Y")
    return day_label, date_label, today_str, yesterday_str

def search_category(client, category, today_str, yesterday_str):
    print(f"  Searching: {category['label']}...")

    combined_queries = " | ".join(category['queries'])

    prompt = f"""You are a senior intelligence analyst preparing a daily briefing for the Executive team at Newcastle United Football Club. Today is {today_str}.

Search for news in this category: {category['label']}

Search queries: {combined_queries}

{category['instruction']}

STRICT DATE RULE: Only include articles published on {today_str} or {yesterday_str}. 
Reject any article older than 48 hours. If the publication date is unclear, do not include it.
If there are genuinely no articles from the last 48 hours in this category, return an empty array [].
Do NOT backfill with older articles.

For each current item return ONLY a JSON array (no other text, no markdown):

[
  {{
    "category": "{category['id']}",
    "badge": "News",
    "title": "Specific, informative headline",
    "summary": "2-3 sentences covering what happened, key facts and numbers. Written for a senior football club executive.",
    "exec_note": "1-2 sentences on the business, legal or strategic implication for a Premier League club. General observation — do not address any specific role.",
    "source": "Publication name, {today_str} or {yesterday_str}",
    "link": "https://actual-url"
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
        print(f"    Rate limit hit — waiting 60 seconds...")
        time.sleep(60)
        return []
    except Exception as e:
        print(f"    Warning: could not parse {category['label']}: {e}")

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

    day_label, date_label, today_str, yesterday_str = get_day_info()
    print(f"\nGenerating briefing for: {day_label}")
    print(f"Accepted dates: {today_str} or {yesterday_str}\n")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_items = []
    for i, category in enumerate(CATEGORIES):
        if i > 0:
            print(f"    Pausing 30 seconds...")
            time.sleep(30)
        items = search_category(client, category, today_str, yesterday_str)
        print(f"    Found {len(items)} items for {category['label']}")
        all_items.extend(items)

    if not all_items:
        print("\nNo current items found. Preserving existing content.")
        return

    print(f"\nTotal items: {len(all_items)}")

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
