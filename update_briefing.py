"""
NUFC Executive Intelligence Briefing — Daily Automation
Runs every day at 9am via GitHub Actions.
Searches credible sources for relevant news and insights for
the Newcastle United senior leadership group.
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
            "Premier League financial fair play FFP ruling 2026",
            "football club finance law regulation transfer spending 2026",
        ],
        "instruction": """Find 3-5 significant items covering any of: financial regulations, legal rulings, PSR/FFP updates, transfer financial rules, tax law changes affecting football, significant club financial deals, sponsorship deals, broadcast revenue, wage bills, accounts published, arbitration outcomes, competition authority decisions.

Sources: Law in Sport, Swiss Ramble, Deloitte, The Athletic, BBC Sport, Sky Sports, Reuters, The Times, The Guardian, Financial Times.

TIME WINDOW: Search the last 72 hours. If genuinely limited new content, include the most significant recent item even if slightly older rather than returning empty."""
    },
    {
        "id": "infra",
        "label": "Infrastructure & Development",
        "queries": [
            "football stadium development planning construction 2026",
            "Premier League training ground facility investment 2026",
            "Newcastle United St James Park stadium development 2026",
        ],
        "instruction": """Find 3-5 significant items covering any of: stadium renovation or rebuild projects, training ground developments, planning applications, construction milestones, technology infrastructure at clubs, academy facility upgrades, naming rights deals, hospitality developments.

Pay particular attention to any Newcastle United or North East England infrastructure news.

Sources: BBC Sport, The Athletic, Sky Sports, local newspapers, club official announcements, Construction Enquirer.

TIME WINDOW: Search the last 72 hours. If limited new infrastructure news, include the most recently published significant item."""
    },
    {
        "id": "governing",
        "label": "Governing Bodies",
        "queries": [
            "Premier League FA UEFA FIFA rule change decision 2026",
            "Independent Football Regulator IFR England update 2026",
            "football governing body disciplinary announcement 2026",
        ],
        "instruction": """Find 3-5 significant items covering any of: Premier League rule changes or votes, FA disciplinary decisions, UEFA regulation updates, FIFA policy announcements, Independent Football Regulator (IFR) updates, VAR policy changes, squad registration rule changes, transfer window rules, agent regulations, player welfare policies.

Sources: Premier League official, FA official, UEFA official, FIFA official, BBC Sport, Sky Sports, The Athletic, Reuters.

TIME WINDOW: Search the last 72 hours. Cast the net broadly — governing body announcements are often published mid-week."""
    },
    {
        "id": "europe",
        "label": "Big 5 European Leagues",
        "queries": [
            "La Liga Spain Real Madrid Barcelona transfer news 2026",
            "Bundesliga Germany Bayern Munich transfer news 2026",
            "Serie A Italy transfer news major clubs 2026",
            "Ligue 1 France PSG transfer news 2026",
        ],
        "instruction": """Find 3-5 significant items from La Liga, Bundesliga, Serie A or Ligue 1 covering any of: major transfers, club financial developments, managerial changes, significant results, financial regulation compliance, club ownership changes, European competition results.

Sources: Reuters, AFP, The Athletic, Sky Sports, BBC Sport, Marca (English), Gazzetta (English), Kicker (English).

TIME WINDOW: Search the last 72 hours. European football generates daily news — there will always be relevant items."""
    },
    {
        "id": "world",
        "label": "World Football",
        "queries": [
            "FIFA Club World Cup 2025 results standings news",
            "Saudi Pro League transfer signing news 2026",
            "MLS international football transfer global news 2026",
            "World Cup 2026 preparation news update",
        ],
        "instruction": """Find 3-5 significant items covering any of: FIFA Club World Cup updates and results, Saudi Pro League major transfers, MLS developments, global transfer market trends, international tournament news, World Cup 2026 preparation, major club developments outside Europe.

The FIFA Club World Cup is a priority — include match results, group standings, player performance news.

Sources: Reuters, BBC Sport, FIFA official, The Athletic, Sky Sports, ESPN FC, AP Sport.

TIME WINDOW: Search the last 72 hours."""
    },
    {
        "id": "premier",
        "label": "Premier League",
        "queries": [
            "Premier League results table standings today 2026",
            "Premier League transfer news confirmed signing 2026",
            "Premier League manager injury club news 2026",
            "Premier League broadcast commercial deal 2026",
        ],
        "instruction": """Find 3-5 significant items from the Premier League — EXCLUDING Newcastle United (those go in the Newcastle category) — covering any of: match results and table standings, confirmed transfers, managerial appointments or sackings, injury news, club financial announcements, points deductions, broadcast deals, commercial partnerships, fan protests or ownership disputes.

Sources: BBC Sport, Sky Sports, The Athletic, Premier League official, talkSPORT, The Guardian, The Times.

TIME WINDOW: Search the last 72 hours. The Premier League generates multiple stories daily — always include current table context."""
    },
    {
        "id": "newcastle",
        "label": "Newcastle United",
        "queries": [
            "Newcastle United NUFC news latest 2026",
            "Newcastle United transfer signing departure rumour 2026",
            "Newcastle United Eddie Howe team news injury 2026",
            "NUFC PIF Saudi ownership commercial deal 2026",
        ],
        "instruction": """Find 3-5 significant items specifically about Newcastle United covering any of: match results and analysis, transfer news in or out, Eddie Howe press conference news, player injuries, PIF ownership news, commercial and sponsorship deals, St James' Park development, academy news, women's team news, disciplinary matters.

This is the most important category — search all queries thoroughly.

Sources: Chronicle Live, BBC Newcastle, Sky Sports, The Athletic, talkSPORT, Newcastle United official, The Guardian, The Times.

TIME WINDOW: Search the last 72 hours. Include both confirmed news and significant credible reports from reputable journalists."""
    },
]

def get_day_info():
    today = datetime.date.today()
    day_label = today.strftime("%A %d %B %Y")
    date_label = today.strftime("%-d %B %Y")
    return day_label, date_label

def search_category(client, category):
    """Use Claude with web search to find relevant news for a category."""
    print(f"  Searching: {category['label']}...")

    combined_queries = " | ".join(category['queries'][:3])

    prompt = f"""You are a senior intelligence analyst preparing a daily briefing for the Executive team at Newcastle United Football Club.

Search for credible, significant news in this category: {category['label']}

Run searches using these terms: {combined_queries}

{category['instruction']}

RULES:
- Only include credible stories from reputable sources — no fabrication or clickbait
- Do not include unverified transfer speculation unless from a highly credible source
- Return between 2 and 5 items — do not return an empty array unless there is genuinely nothing relevant at all in the last 72 hours
- If recent news is limited, include the most significant recent item even if a few days old

For each item return ONLY a JSON array in this exact format (no other text, no markdown code fences):

[
  {{
    "category": "{category['id']}",
    "badge": "News",
    "title": "Specific, informative headline",
    "summary": "2-3 sentences covering what happened, key facts and numbers. Written for a senior football club executive.",
    "exec_note": "1-2 sentences on why this matters to a Premier League club — the business, legal or strategic implication. Write as a general observation, not addressed to any specific role.",
    "source": "Publication name, date",
    "link": "https://actual-url"
  }}
]

Badge options: "News", "Official update", "Regulatory", "Financial", "Transfer", "Legal ruling", "Development", "Analysis", "Match report", "Data"

Return ONLY the JSON array. No preamble, no explanation, no markdown."""

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
        print(f"    Rate limit hit for {category['label']} — waiting 60 seconds...")
        time.sleep(60)
        return []
    except Exception as e:
        print(f"    Warning: Could not parse response for {category['label']}: {e}")

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

    day_label, date_label = get_day_info()
    print(f"\nGenerating briefing for: {day_label}\n")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_items = []
    for i, category in enumerate(CATEGORIES):
        if i > 0:
            print(f"    Pausing 30 seconds before next search...")
            time.sleep(30)

        items = search_category(client, category)
        print(f"    Found {len(items)} items for {category['label']}")
        all_items.extend(items)

    if not all_items:
        print("\nNo items found. Aborting update to preserve existing content.")
        return

    print(f"\nTotal items found: {len(all_items)}")

    html = load_current_html()
    current_today, current_archive = extract_current_data(html)

    new_archive = current_archive
    if current_today and current_today.get("items"):
        new_archive = [current_today] + current_archive
        new_archive = new_archive[:14]
        print(f"Moved {current_today['day']} to archive ({len(current_today['items'])} items)")

    new_today = {
        "day":   day_label,
        "date":  date_label,
        "items": all_items
    }

    updated_html = build_new_html(html, new_today, new_archive)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(updated_html)

    print(f"\n✓ Briefing updated: {day_label}")
    print(f"  Items today    : {len(all_items)}")
    print(f"  Days in archive: {len(new_archive)}")
    print("\nDone. GitHub Actions will commit and publish automatically.")

if __name__ == "__main__":
    main()
