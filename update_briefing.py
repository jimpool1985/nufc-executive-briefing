"""
NUFC Executive Intelligence Briefing — Daily Automation
Runs every weekday at 9am via GitHub Actions.
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
        "query": "football finance law regulation PSR FFP transfer rules contracts 2026",
        "instruction": "Focus on financial regulations, legal rulings, accounting changes, transfer financial rules, PSR/FFP updates, tax law changes affecting football clubs, or significant financial deals. Sources: Law in Sport, Swiss Ramble, Deloitte, KPMG, official league/UEFA financial reports, BBC, Reuters."
    },
    {
        "id": "infra",
        "label": "Infrastructure & Development",
        "query": "football stadium development training ground construction planning 2026",
        "instruction": "Focus on stadium projects, training ground developments, planning applications, construction milestones, technology infrastructure investments at football clubs. Include any developments relevant to Newcastle United or St James' Park specifically. Sources: The Athletic, BBC, local news, club official announcements."
    },
    {
        "id": "governing",
        "label": "Governing Bodies",
        "query": "Premier League FA UEFA FIFA rules regulations decisions governance 2026",
        "instruction": "Focus on official rule changes, governance decisions, disciplinary outcomes, policy announcements from the Premier League, FA, UEFA, FIFA or the new Independent Football Regulator. Only credible official sources. Sources: PL official, FA official, UEFA official, FIFA official, BBC Sport."
    },
    {
        "id": "europe",
        "label": "Big 5 European Leagues",
        "query": "La Liga Bundesliga Serie A Ligue 1 news transfers finance 2026",
        "instruction": "Focus on significant news from Spain, Germany, Italy and France — financial developments, major transfers, regulatory decisions, competitive developments that could affect European competition landscape. Sources: Reuters, AFP, The Athletic, Sky Sports, BBC Sport."
    },
    {
        "id": "world",
        "label": "World Football",
        "query": "FIFA Club World Cup international football global news 2026",
        "instruction": "Focus on significant global football developments — FIFA decisions, international tournament updates, global transfer market trends, major club news outside the Big 5, geopolitical impacts on football. Sources: Reuters, BBC Sport, FIFA official, The Athletic."
    },
    {
        "id": "premier",
        "label": "Premier League",
        "query": "Premier League news transfers clubs results standings 2026",
        "instruction": "Focus on Premier League-specific news — competitive updates, club transactions, official announcements, broadcast deals, commercial developments, table standings context. Exclude Newcastle United stories (those go in the Newcastle category). Sources: Premier League official, BBC Sport, Sky Sports, The Athletic."
    },
    {
        "id": "newcastle",
        "label": "Newcastle United",
        "query": "Newcastle United NUFC news transfers squad manager 2026",
        "instruction": "Focus specifically on Newcastle United — transfers in/out, squad news, commercial deals, ownership updates, infrastructure news, manager/coaching updates, academy developments. Sources: Chronicle, BBC Sport, Sky Sports, The Athletic, official club announcements."
    },
]

def get_day_info():
    today = datetime.date.today()
    day_label = today.strftime("%A %d %B %Y")
    date_label = today.strftime("%-d %B %Y")
    return day_label, date_label

def search_category(client, category):
    print(f"  Searching: {category['label']}...")

    prompt = f"""You are a senior intelligence analyst preparing a daily briefing for the Executive team at Newcastle United Football Club.

Search for the most significant and credible news stories published TODAY or in the last 24 hours in this category: {category['label']}

Search focus: {category['query']}

{category['instruction']}

STRICT RULES:
- Only include genuinely newsworthy, credible stories from reputable sources
- No gossip, rumour, clickbait or unverified transfer speculation
- No opinion pieces unless from a recognised expert
- Minimum 2 items, maximum 4 items
- If there are no genuinely significant stories today in this category, return an empty array []

For each item return ONLY a JSON array in this exact format (no other text, no markdown):

[
  {{
    "category": "{category['id']}",
    "badge": "News",
    "title": "Specific, informative headline — not clickbait",
    "summary": "2-3 sentences summarising what happened, the key facts and numbers. Written for a senior football club executive who needs to be informed quickly.",
    "exec_note": "1-2 sentences on why this matters to a Premier League club — the business, legal or strategic implication. Do not address or mention specific roles. Write as a general executive note.",
    "source": "Publication name, date",
    "link": "https://actual-url"
  }}
]

Badge options: "News", "Official update", "Regulatory", "Financial", "Transfer", "Legal ruling", "Development", "Analysis", "Interview", "Data"

Return ONLY the JSON array. No preamble, no explanation, no markdown code fences."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
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
            print(f"    Pausing 30 seconds...")
            time.sleep(30)

        items = search_category(client, category)
        print(f"    Found {len(items)} items for {category['label']}")
        all_items.extend(items)

    if not all_items:
        print("\nNo items found today. Aborting update.")
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
    print(f"  Items today   : {len(all_items)}")
    print(f"  Days in archive: {len(new_archive)}")
    print("\nDone. GitHub Actions will commit and publish automatically.")

if __name__ == "__main__":
    main()
