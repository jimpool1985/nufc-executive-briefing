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
        "searches": [
            "Premier League PSR profit sustainability rules news site:bbc.co.uk OR site:theathletic.com OR site:theguardian.com OR site:skysports.com",
            "football club finance transfer spending FFP financial fair play 2026",
            "Premier League club accounts revenue sponsorship deal 2026",
            "football legal ruling arbitration tribunal 2026",
            "Swiss Ramble football finance analysis 2026",
        ],
        "instruction": "Search all major UK sports and news outlets for football financial and legal news from the last 7 days. Include: PSR updates, FFP, club revenue announcements, major sponsorship deals, broadcasting rights news, legal rulings, transfer financial rules, wage data, club accounts published, arbitration outcomes. Cast the net wide — BBC Sport, Sky Sports, The Guardian, The Times, The Telegraph, The Athletic, Reuters, Financial Times, Law in Sport, Swiss Ramble are all valid."
    },
    {
        "id": "infra",
        "label": "Infrastructure & Development",
        "searches": [
            "football stadium development planning approval 2026 site:bbc.co.uk OR site:skysports.com OR site:theguardian.com",
            "Premier League training ground new facility construction 2026",
            "Newcastle United stadium St James Park development plans 2026",
            "football club naming rights deal facility upgrade 2026",
            "Everton stadium Spurs Arsenal Liverpool Manchester City ground 2026",
        ],
        "instruction": "Search all major news outlets and local newspapers for football infrastructure news from the last 7 days. Include: stadium builds or renovations, training ground developments, planning permission news, construction updates, naming rights deals, hospitality upgrades, technology investments at clubs, any North East England football infrastructure news. Sources: BBC Sport, Sky Sports, local newspapers (Chronicle Live, Manchester Evening News, Liverpool Echo etc), The Athletic, Construction Enquirer, StadiumDB, club official sites."
    },
    {
        "id": "governing",
        "label": "Governing Bodies",
        "searches": [
            "Premier League FA announcement decision rule change 2026 site:bbc.co.uk OR site:premierleague.com OR site:thefa.com",
            "UEFA FIFA announcement decision regulation 2026",
            "Independent Football Regulator IFR England update 2026",
            "football VAR referee disciplinary points deduction 2026",
            "Premier League club meeting vote agenda 2026",
        ],
        "instruction": "Search official governing body sites and major news outlets for news from the last 7 days. Include: Premier League rule changes or votes, FA cup disciplinary decisions, UEFA regulation updates, FIFA policy announcements, IFR updates and consultations, VAR policy changes, points deductions, squad registration changes, transfer window amendments, agent regulations, safeguarding policies. Sources: Premier League official, FA official, UEFA official, FIFA official, BBC Sport, Sky Sports, The Athletic, The Guardian."
    },
    {
        "id": "europe",
        "label": "Big 5 European Leagues",
        "searches": [
            "La Liga news transfer result April 2026 site:bbc.co.uk OR site:skysports.com OR site:marca.com",
            "Bundesliga news transfer result April 2026",
            "Serie A news transfer result April 2026",
            "Ligue 1 news transfer result April 2026",
            "Real Madrid Barcelona Bayern Munich PSG Inter Milan Juventus news this week",
            "Champions League Europa League news result April 2026",
        ],
        "instruction": "Search all major sports news outlets for Big 5 European league news from the last 7 days. Include: match results and league table updates, major transfer completions or negotiations, managerial appointments or sackings, significant club financial news, European competition results, fan protests, disciplinary cases. Sources: BBC Sport, Sky Sports, Reuters, AFP, The Athletic, Marca (English), Goal.com, L'Equipe (English), Kicker (English), Gazzetta dello Sport (English), ESPN."
    },
    {
        "id": "world",
        "label": "World Football",
        "searches": [
            "FIFA Club World Cup 2025 news result standings this week",
            "Saudi Pro League transfer news Al Nassr Al Hilal Al Ittihad 2026",
            "MLS Major League Soccer news transfer April 2026",
            "World Cup 2026 preparation host city news April 2026",
            "international football news global transfer April 2026",
            "CONCACAF CONMEBOL AFC CAF football news April 2026",
        ],
        "instruction": "Search major global sports outlets for world football news from the last 7 days. Include: FIFA Club World Cup results and standings (this is currently ongoing — prioritise), Saudi Pro League transfers and results, MLS news, World Cup 2026 host preparations, AFC/CAF/CONCACAF news, major global transfers, FIFA disciplinary cases, international break results. Sources: Reuters, BBC Sport, FIFA official, The Athletic, Sky Sports, ESPN, AP Sport, Al Jazeera Sport, Goal.com."
    },
    {
        "id": "premier",
        "label": "Premier League",
        "searches": [
            "Premier League results table standings April 2026 site:bbc.co.uk OR site:skysports.com",
            "Premier League transfer news signing confirmed April 2026",
            "Premier League manager sacked appointed news April 2026",
            "Premier League injury team news April 2026",
            "Arsenal Chelsea Manchester City Liverpool Manchester United news April 2026",
            "Premier League relegation title race news April 2026",
        ],
        "instruction": "Search all major UK sports outlets for Premier League news from the last 7 days. EXCLUDE Newcastle United stories (they go in the Newcastle category). Include: match results and full table standings, transfer confirmed or rumoured from credible journalists, managerial changes, player injury updates, title race and relegation battle updates, VAR controversies, club boardroom news, fan protests, commercial deals. Sources: BBC Sport, Sky Sports, The Athletic, The Guardian, The Times, The Telegraph, Mirror Sport, The Sun Sport, talkSPORT, Premier League official."
    },
    {
        "id": "newcastle",
        "label": "Newcastle United",
        "searches": [
            "Newcastle United news April 2026 site:chroniclelive.co.uk OR site:bbc.co.uk OR site:skysports.com",
            "Newcastle United NUFC transfer news April 2026",
            "Eddie Howe press conference team news injury April 2026",
            "Newcastle United PIF Saudi Arabia ownership news 2026",
            "Newcastle United match result performance April 2026",
            "Newcastle United commercial deal sponsor academy women 2026",
        ],
        "instruction": "Search all major UK sports outlets and Newcastle-specific sources for NUFC news from the last 7 days. This is the most important category — be thorough. Include: match results and analysis, transfer ins and outs (confirmed and credible rumours), Eddie Howe quotes and team news, player fitness and injury updates, PIF ownership developments, commercial partnerships, St James' Park development, academy signings and results, women's team news, supporter trust news, any club disciplinary matters. Sources: Chronicle Live, ChronicleLive.co.uk, BBC Sport Newcastle, Sky Sports, The Athletic, talkSPORT, The Guardian, The Times, NUFC official site, NUFC The Mag, Shearer's NUFC blog."
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
    s = source_str.lower()
    today = datetime.date.today()

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

    if re.search(r"\d+\s+(months?|years?)\s+ago", s):
        return today - datetime.timedelta(days=365)
    if re.search(r"(last\s+month|last\s+year|months?\s+ago|years?\s+ago)", s):
        return today - datetime.timedelta(days=365)

    patterns = [
        r"(january|february|march|april|may|june|july|august|september|october|november|december"
        r"|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"\s+(\d{1,2})(?:[,\s]+(\d{4}))?",
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

    return None

def is_acceptable(source_str, today, cutoff):
    s = source_str.lower()

    # Hard reject any pre-2026 year
    if re.search(r"\b(2025|2024|2023|2022|2021|2020|2019|2018)\b", s):
        return False

    article_date = parse_date_from_source(source_str, today.year)

    if article_date is None:
        return None  # Uncertain — keep with warning

    if article_date > today:
        return None  # Parsing error — keep with warning

    return article_date >= cutoff

def filter_items(items, today, cutoff):
    kept = []
    seen_titles = set()
    for item in items:
        # Deduplicate by title
        title = item.get("title", "").lower().strip()
        if title in seen_titles:
            print(f"    ✗ Duplicate removed: {title[:60]}")
            continue
        seen_titles.add(title)

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

    # Build search context from multiple queries
    search_context = "\n".join([f"- {q}" for q in category['searches']])

    prompt = f"""You are a senior intelligence analyst. Today is {today_str}.

Your task: Find the most significant and relevant news for this briefing category: {category['label']}

ACTIVELY SEARCH the web using ALL of these search queries — do not rely on memory:
{search_context}

{category['instruction']}

STRICT RULES:
- Only include articles published between {cutoff_str} and {today_str} (last 7 days)
- Do not include anything from 2025 or earlier
- Only include credible, factual reporting — no fabrication, no clickbait
- Unverified transfer rumours only from Tier 1 journalists (Fabrizio Romano, David Ornstein, The Athletic)
- There IS always football news in every category every week — search broadly and thoroughly
- Return 3-5 items

Return ONLY a JSON array (no other text, no markdown code fences):

[
  {{
    "category": "{category['id']}",
    "badge": "News",
    "title": "Specific informative headline",
    "summary": "2-3 sentences. Key facts and numbers for a senior football executive.",
    "exec_note": "1-2 sentences on the business or strategic implication. General observation, no specific roles mentioned.",
    "source": "Publication name, exact date e.g. BBC Sport, 10 April 2026",
    "link": "https://actual-url"
  }}
]

Badge options: "News", "Official update", "Regulatory", "Financial", "Transfer", "Legal ruling", "Development", "Analysis", "Match report", "Data"

Return ONLY the JSON array."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
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
    print(f"\nDate   : {day_label}")
    print(f"Cutoff : {cutoff_str} (7-day rolling window)")
    print()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_items = []
    for i, category in enumerate(CATEGORIES):
        if i > 0:
            print(f"    Pausing 30 seconds...")
            time.sleep(30)

        raw = search_category(client, category, today_str, cutoff_str)
        filtered = filter_items(raw, today, cutoff)
        print(f"    {category['label']}: {len(raw)} found → {len(filtered)} kept")
        all_items.extend(filtered)

    print(f"\nTotal items: {len(all_items)}")

    if not all_items:
        print("No items found. Preserving existing content.")
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
