#!/usr/bin/env python
# coding: utf-8

# # Video Game Popularity Across Gaming Platforms: A GTA VI Case Study
# 
# ![Banner](./assets/banner.jpeg)

# ## Topic
# *What problem are you (or your stakeholder) trying to address?*
# 
# This analysis seeks to understand trends in popularity within video games. As Rockstar have confirmed that GTA VI will initially be released for PS5 and Xbox Series X/S, only console data will be considered. This can inform developers and publishers about popularity within games and how long popularity is likely to be sustained.
# 
# Primary metrics include active players on consoles, in a rolling 7 day period. Secondary metrics include game ranking. Historical metrics for PC games will also be explored, including owner count, reviews, price and play time. These do not represent sales on console, and cannot be taken as exact totals of players.
# 
# Xbox's official list of most played games, PlayStation Store download rankings, SteamSpy (providing up-to-date estimates of PC game popularity) and RAWG (providing metadata for specific modern and historical games) will be used to provide different views into game popularity.

# ## Project Question
# *What specific question are you seeking to answer with this project?*
# 
# - Which games are popular on Xbox and PlayStation?
# - Have there been differences in popularity between Xbox and PlayStation?
# - How has popularity changed over time after game release?
# - How does GTA V perform on different consoles, compared with other well-known games?
# - How does GTA VI perform, where data is available at release?
# - For games with historical metadata from Steam, do certain genres, % positive reviews and prices correlate to them being owned on PC?
# - How similar are the most popular games on Xbox in the sample compared to the official Xbox chart in the USA?
# - Which games are popular in monthly download charts on PS5 and PS4? How do rankings differ in the USA/Canada and EU?
# - Do newer genres of games, as given by RAWG, and their ratings correlate to popularity on consoles? 
# - How do estimates of game ownership from SteamSpy compare to the ownership in historical Steam data?

# ## What would an answer look like?
# *What is your hypothesized answer to your question?*
# 
# I expect top games will be present on both platforms, however there will be differences. Newer games will be more active initially. Some well known games will remain popular for longer. With PC data, it is expected that higher ownership rates correlate with higher percentages of reviews and playtimes. Price and genre may also correlate with ownership.
# 
# An answer could look like these:
# 
# | Question | Visualization | Output |
# | --- | --- | --- |
# | Which games most popular? | Grouped bar chart | Sampled % activity by platform for matched games |
# | How do popularity trends look? | Line chart | Trends in popularity of GTA V, GTA VI, and similar games. |
# | Does age affect popularity?  | Scatter plot | Days since release versus sampled activity percentage |
# | Is price correlated to popularity on PC? | Scatter plots and Correlations | Midpoint of Steam ownership against price and % positive reviews. |

# ## Data Sources
# *What 3 data sources have you identified for this project?*
# *How are you going to relate these datasets?*
# 
# | Source | Type | Variables | Purpose / key |
# | --- | --- | --- | --- |
# | [Console Activity Charts](https://github.com/olonadtrolo/charts) | CSV | Platform, date, rank, title ID, title, sampled players, percentage, release date | Main activity dataset; platform + title_id |
# | [Steam Store Games](https://www.kaggle.com/datasets/nikdavis/steam-store-games) | CSV | App ID, historical price (GBP), reviews, owners, genres, playtime | PC historical comparison; appid |
# | [Steam Web API](https://partner.steamgames.com/doc/webapi/ISteamUserStats) | JSON API | Current concurrent players | PC snapshot; appid |
# | [SteamSpy](https://steamspy.com/api.php) | JSON API | Estimated owners, reviews, playtime, developer, publisher | Current PC estimates; appid |
# | [Xbox Most Played](https://www.xbox.com/en-US/games/browse/Popular) / [Microsoft Store](https://www.microsoft.com/en-us/store/most-popular/games/xbox) | HTML scraping | US storefront chart order, title, retrieval date, source URL | Compare with sampled Xbox charts; title-match candidates |
# | [PlayStation Blog](https://blog.playstation.com/tag/top-downloads/) | HTML scraping | Month, PS5/PS4/free-to-play, region, download rank, title | Monthly trends; title-match candidates |
# | [RAWG](https://rawg.io/apidocs) | JSON API | Game ID, name, genres, rating, release date, platforms | Cross-platform metadata; title-match candidates |
# 
# Seven data sources. Xbox and PlayStation archives grouped as one source. The official charts for each console are additional sources. Data from SteamSpy and historical CSV are not independent. RAWG requires a free license for personal usage. Official Xbox chart gives a snapshot of current data in the US. Monthly rankings on PlayStation show number of downloads, not activity. Console archive shows sample of activity, not total population.
# 
# Data from console sources and PC sources merged by platform and title_id, and appid respectively. Data from different sources matched by unique title. Before interpretation, platform, edition and release date should be checked. Source, region, date and metric are preserved. Unmatched titles remain in the dataset. If data is missing, it is not imputed as 0.

# ### Setup

# In[1]:


from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
import os
import re
import time
import unicodedata

import pandas as pd
import requests
from bs4 import BeautifulSoup
from getpass import getpass
from urllib.parse import urljoin

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4.element import Tag
from urllib.parse import urlparse

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE = "https://raw.githubusercontent.com/olonadtrolo/charts/main/"
errors = []


def read_csv_source(url, filename, required, **kwargs):
    """Read a local cache or download and validate a public CSV."""
    path = DATA_DIR / filename
    if path.exists():
        frame = pd.read_csv(path, **kwargs)
    else:
        response = requests.get(url, timeout=25)
        response.raise_for_status()
        frame = pd.read_csv(BytesIO(response.content), **kwargs)
        if frame.empty or not set(required).issubset(frame.columns):
            raise ValueError(f"Invalid or empty CSV: {url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    if frame.empty or not set(required).issubset(frame.columns):
        raise ValueError(f"Invalid or empty CSV: {path}")
    return frame


def normalize_title(value):
    if pd.isna(value):
        return pd.NA
    value = re.sub(r"[™®©]", "", str(value))
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]+", " ", value).strip() or pd.NA


# In[2]:


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def read_snapshot(filename, required):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or not set(required).issubset(frame.columns):
        raise ValueError(f"Invalid cache: {path}")
    return frame


def save_snapshot(frame, filename):
    if not frame.empty:
        frame.to_csv(DATA_DIR / filename, index=False)


def fetch_html(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}, timeout=25)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


# ### Source 1: Xbox and PlayStation activity charts

# In[3]:


platforms = {"Xbox": ("xbox", "data_xbox.csv"),
             "PlayStation": ("ps", "data_playstation.csv")}
chart_dates = pd.date_range("2026-08-30", "2026-11-15", freq="7D")
chart_dates = chart_dates.append(pd.DatetimeIndex(["2026-11-20"]))
chart_columns = ["rank", "title_id", "title", "players", "percentage"]
catalog_columns = ["title_id", "title_name", "release_date"]
charts, catalogs = [], []

for platform, (folder, catalog_file) in platforms.items():
    try:
        catalog = read_csv_source(ARCHIVE + catalog_file, catalog_file,
                                  catalog_columns, dtype={"title_id": "string"})
        catalogs.append(catalog.assign(platform=platform))
    except (requests.RequestException, ValueError, OSError) as error:
        errors.append((platform, "catalog", str(error)))
    for date in chart_dates:
        day = date.strftime("%Y-%m-%d")
        relative_path = f"charts/{folder}/7_days/{day}.csv"
        try:
            frame = read_csv_source(ARCHIVE + relative_path, relative_path,
                                    chart_columns, dtype={"title_id": "string"})
            charts.append(frame.assign(platform=platform, chart_date=date))
        except (requests.RequestException, ValueError, OSError) as error:
            errors.append((platform, day, str(error)))

console_charts = (pd.concat(charts, ignore_index=True) if charts else
                  pd.DataFrame(columns=chart_columns + ["platform", "chart_date"]))
console_catalog = (pd.concat(catalogs, ignore_index=True) if catalogs else
                   pd.DataFrame(columns=catalog_columns + ["platform"]))
print("Console chart shape:", console_charts.shape)
print("Console catalog shape:", console_catalog.shape)
print(console_charts.groupby("platform")["chart_date"].nunique())
console_charts.head()


# ### Source 2: Historical Steam Store Games CSV

# In[4]:


steam_url = "https://raw.githubusercontent.com/genlikan/SteamAnalysis/main/Steam/steam.csv"
steam_columns = ["appid", "name", "release_date", "genres", "price", "owners",
                 "positive_ratings", "negative_ratings", "average_playtime"]
try:
    steam_df = read_csv_source(steam_url, "steam.csv", steam_columns)
except (requests.RequestException, ValueError, OSError) as error:
    errors.append(("Steam CSV", "2019", str(error)))
    steam_df = pd.DataFrame(columns=steam_columns)
print("Historical Steam shape:", steam_df.shape)
steam_df.head()


# ### Source 3: Steam Web API (JSON)

# In[5]:


comparison_ids = [271590, 12210, 292030, 489830, 377160, 105600,
                  413150, 620, 49520, 570, 440, 550]
players_url = ("https://api.steampowered.com/ISteamUserStats/"
               "GetNumberOfCurrentPlayers/v1/")
player_columns = ["appid", "current_players", "retrieved_at_utc"]
player_cache = DATA_DIR / "steam_players_snapshot.csv"
if player_cache.exists():
    steam_players = pd.read_csv(player_cache)
else:
    player_records = []
    for appid in comparison_ids:
        try:
            response = requests.get(players_url, params={"appid": appid}, timeout=15)
            response.raise_for_status()
            result = response.json()["response"]
            if result.get("result") != 1 or "player_count" not in result:
                raise ValueError("Player count unavailable")
            player_records.append({"appid": appid,
                                   "current_players": result["player_count"],
                                   "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            errors.append(("Steam API", appid, str(error)))
        time.sleep(0.5)
    steam_players = pd.DataFrame(player_records, columns=player_columns)
    if not steam_players.empty:
        steam_players.to_csv(player_cache, index=False)
print("Steam API shape:", steam_players.shape)
steam_players.head()


# ### Source 4: SteamSpy API

# In[6]:


spy_columns = ["appid", "spy_name", "spy_owners", "spy_positive", "spy_negative",
               "spy_average_forever", "spy_average_2weeks", "spy_developer",
               "spy_publisher", "spy_retrieved_at_utc"]
spy_frames = []
for appid in comparison_ids:
    filename = f"steamspy_{appid}.csv"
    try:
        cached = read_snapshot(filename, spy_columns)
        if cached is None:
            response = requests.get("https://steamspy.com/api.php",
                                    params={"request": "appdetails", "appid": appid}, timeout=20)
            try:
                response.raise_for_status()
                game = response.json()
                if int(game.get("appid", -1)) != appid or not game.get("name") or not game.get("owners"):
                    raise ValueError("Missing app details")
                row = {"appid": appid, "spy_retrieved_at_utc": timestamp()}
                for field in ["name", "owners", "positive", "negative", "average_forever",
                              "average_2weeks", "developer", "publisher"]:
                    row[f"spy_{field}"] = game.get(field)
                cached = pd.DataFrame([row], columns=spy_columns)
                save_snapshot(cached, filename)
            finally:
                time.sleep(1.2)
        spy_frames.append(cached)
    except (requests.RequestException, ValueError, OSError, KeyError, TypeError) as error:
        errors.append(("SteamSpy", appid, str(error)))
steamspy_df = pd.concat(spy_frames, ignore_index=True) if spy_frames else pd.DataFrame(columns=spy_columns)
print("SteamSpy shape:", steamspy_df.shape)
steamspy_df.head()


# ### Source 5: Official Xbox Most Played chart

# In[7]:


# Source 5 — official US Xbox Most Played rankings (no API key needed)
# Microsoft Store is usually server-rendered; xbox.com is a secondary fallback.
xbox_urls = [
    "https://www.microsoft.com/en-us/store/most-popular/games/xbox",
    "https://www.xbox.com/en-US/games/browse/Popular",
]
xbox_columns = ["title", "rank", "region", "retrieved_at_utc", "source_url", "product_url"]
XBOX_FORCE_REFRESH = False  # Set True only when you want to refresh the cached chart


def fetch_xbox_html(url):
    """GET with one short retry for transient Microsoft/network errors."""
    retry = Retry(
        total=1, connect=1, read=1, status=1,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        response = session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=(8, 12),
        )
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")


def xbox_product_url(node, base_url):
    """Find a Microsoft/Xbox game-product link in or near a game card."""
    for parent in [node, *list(node.parents)[:3]]:
        if not isinstance(parent, Tag) or parent.name in {"main", "body", "html", "[document]", "nav", "aside"}:
            continue
        if parent is not node and len(parent.find_all(["h3", "h4"], limit=2)) > 1:
            continue
        links = ([parent] if parent.name == "a" else []) + parent.find_all("a", href=True, limit=12)
        for link in links:
            href = link.get("href", "")
            full = urljoin(base_url, href)
            parts = urlparse(full)
            host = (parts.hostname or "").lower()
            if not (host.endswith("microsoft.com") or host.endswith("xbox.com")):
                continue
            # Microsoft's /en-us/p/title/id and Xbox's /games/store/title/id.
            if re.search(r"/(?:games/store|p|store/p|store/detail)/[^/?#]+", parts.path, re.I):
                return full
    return ""


def parse_xbox_chart(soup, url):
    """Read the first visible chart page in DOM order; never infer player counts."""
    chart_head = soup.find(
        lambda t: isinstance(t, Tag) and t.name in {"h1", "h2", "h3"}
        and re.search(r"\bmost played games\b", t.get_text(" ", strip=True), re.I)
    )
    if chart_head is None:
        raise ValueError("No 'Most played games' heading (possibly JS-only or blocked)")

    # Result counts occur *after* sidebar filters and before the actual game cards.
    # This avoids accidentally ranking links in the page navigation/sidebar.
    result_marker = soup.find(string=lambda text: bool(text and re.search(
        r"(?:Showing\s+1\s*[-–]\s*\d+\s+of\s+\d+\s+items|\d+\s+games shown out of)",
        str(text), re.I
    )))
    start = result_marker if result_marker is not None else chart_head
    marker_text = str(result_marker or "")
    count_match = re.search(r"Showing\s+1\s*[-–]\s*(\d+)|(?:^|\s)(\d+)\s+games shown out of", marker_text, re.I)
    page_limit = min(int(next(x for x in count_match.groups() if x)), 50) if count_match else 50

    candidates = []
    for node in start.find_all_next(["h2", "h3", "h4"]):
        if node.name == "h2" and re.search(r"^(?:Back To Top|Recommended|Recently viewed)$", node.get_text(" ", strip=True), re.I):
            break
        if node.name != "h3":
            continue
        title = node.get_text(" ", strip=True)
        if (not title or not any(char.isalnum() for char in title)
                or title.lower() in {"charts", "departments", "games", "subscriptions", "filter", "filters", "most played games"}):
            continue
        link = xbox_product_url(node, url)
        candidates.append((title, link))
        if len(candidates) >= page_limit:  # Respect the first-page result count
            break

    # When cards do not use <h3>, recover titles from product links in DOM order.
    if len(candidates) < 10:
        candidates = []
        for anchor in start.find_all_next("a", href=True):
            link = xbox_product_url(anchor, url)
            if not link:
                continue
            card = anchor
            for ancestor in [anchor, *list(anchor.parents)[:4]]:
                if isinstance(ancestor, Tag) and ancestor.name not in {"main", "body", "html", "nav", "aside", "[document]"} and ancestor.find(["h3", "h4"]):
                    card = ancestor
                    break
            heading = card.find(["h3", "h4"]) if isinstance(card, Tag) else None
            title = (heading.get_text(" ", strip=True) if heading else
                     anchor.get("aria-label") or anchor.get("title") or anchor.get_text(" ", strip=True))
            title = re.sub(r"\s+", " ", title).strip()
            if title and any(c.isalnum() for c in title):
                candidates.append((title, link))
            if len(candidates) >= page_limit:
                break

    seen, rows = set(), []
    for title, link in candidates:
        # Product URL distinguishes console editions; title is fallback only.
        identity = link.lower().split("?", 1)[0] if link else normalize_title(title)
        if identity in seen:
            continue
        seen.add(identity)
        rows.append({
            "title": title,
            "rank": len(rows) + 1,
            "region": "US",
            "retrieved_at_utc": timestamp(),
            "source_url": url,
            "product_url": link,
        })
    if len(rows) < 10:
        raise ValueError(f"Found only {len(rows)} chart games; site may be blocked or layout changed")
    return pd.DataFrame(rows, columns=xbox_columns)


# Remove stale errors if this cell is rerun, without touching other sources.
errors[:] = [item for item in errors if item[0] != "Xbox official"]
xbox_official = None
if not XBOX_FORCE_REFRESH:
    try:
        xbox_official = read_snapshot("xbox_official.csv", xbox_columns)
        if xbox_official is not None and len(xbox_official) < 10:
            raise ValueError("Cached chart has fewer than 10 games")
        if xbox_official is not None:
            print("Loaded cached official Xbox chart; set XBOX_FORCE_REFRESH=True to update")
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        errors.append(("Xbox official", "local cache", str(exc)))
        xbox_official = None

if xbox_official is None:
    for url in xbox_urls:
        print(f"Trying official Xbox chart: {url}", flush=True)
        try:
            xbox_official = parse_xbox_chart(fetch_xbox_html(url), url)
            save_snapshot(xbox_official, "xbox_official.csv")
            print(f"Imported {len(xbox_official)} Xbox ranked games", flush=True)
            break
        except (requests.RequestException, ValueError, OSError) as exc:
            errors.append(("Xbox official", url, f"{type(exc).__name__}: {exc}"))
            print(f"Could not import this page: {type(exc).__name__}: {str(exc)[:160]}")

if xbox_official is None:
    xbox_official = pd.DataFrame(columns=xbox_columns)
    print("No verified official Xbox ranking was imported. See import_errors below.")

print("Official Xbox shape:", xbox_official.shape)
print(xbox_official[["rank", "title", "source_url"]].head(10).to_string(index=False))


# ### Source 6: PlayStation Store monthly download charts

# In[8]:


ps_urls = {
    "2026-08": "https://blog.playstation.com/2026/09/04/playstation-store-august-2026s-top-downloads/",
    "2026-09": "https://blog.playstation.com/2026/10/22/playstation-store-september-2026s-top-downloads/",
    "2026-10": "https://blog.playstation.com/2026/11/04/playstation-store-october-2026s-top-downloads/",
}
ps_columns = ["title", "rank", "chart_category", "region", "chart_month", "source_url", "retrieved_at_utc"]


def parse_ps_charts(soup, month, url):
    rows, found = [], set()
    retrieved = timestamp()
    for table in soup.find_all("table"):
        heading = table.find_previous(["h2", "h3", "h4"])
        label = heading.get_text(" ", strip=True).casefold() if heading else ""
        if "free to play" in label or "free-to-play" in label:
            category = "Free to play (PS4/PS5)"
        elif "ps5" in label and "ps4" not in label:
            category = "PS5"
        elif "ps4" in label and "ps5" not in label:
            category = "PS4"
        else:
            continue
        table_rows = table.find_all("tr")
        if not table_rows:
            continue
        headers = [cell.get_text(" ", strip=True).upper() for cell in table_rows[0].find_all(["th", "td"])]
        if len(headers) != 2 or "US" not in headers[0] or "EU" not in headers[1]:
            continue
        if category in found:
            raise ValueError(f"Duplicate chart category: {category}")
        found.add(category)
        for rank, row in enumerate(table_rows[1:], 1):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != 2:
                continue
            for region, cell in zip(["US/Canada", "EU"], cells):
                title = cell.get_text(" ", strip=True)
                if title:
                    rows.append({"title": title, "rank": rank, "chart_category": category,
                                 "region": region, "chart_month": month, "source_url": url,
                                 "retrieved_at_utc": retrieved})
    frame = pd.DataFrame(rows, columns=ps_columns)
    if found != {"PS5", "PS4", "Free to play (PS4/PS5)"} or len(frame) < 30:
        raise ValueError("Expected three two-region charts not found; inspect page HTML")
    return frame


ps_frames = []
for month, url in ps_urls.items():
    try:
        filename = f"ps_downloads_{month}.csv"
        frame = read_snapshot(filename, ps_columns)
        if frame is None:
            frame = parse_ps_charts(fetch_html(url), month, url)
            save_snapshot(frame, filename)
        ps_frames.append(frame)
    except (requests.RequestException, ValueError, OSError) as error:
        errors.append(("PlayStation Blog", month, str(error)))
ps_downloads = pd.concat(ps_frames, ignore_index=True) if ps_frames else pd.DataFrame(columns=ps_columns)
print("PlayStation downloads shape:", ps_downloads.shape)
ps_downloads.head()


# ### Source 7: RAWG game metadata (API key needed)

# In[9]:


rawg_key = os.getenv("RAWG_API_KEY")
rawg_columns = ["rawg_id", "title", "release_date", "genres", "rating", "platforms", "retrieved_at_utc"]
rawg_titles = ["Grand Theft Auto V", "Grand Theft Auto VI", "Red Dead Redemption 2",
               "Cyberpunk 2077", "Elden Ring", "Fortnite"]
for platform in platforms:
    leaders = console_charts.loc[console_charts["platform"] == platform].copy()
    leaders["rank"] = pd.to_numeric(leaders["rank"], errors="coerce")
    rawg_titles.extend(leaders.sort_values("rank")["title"].dropna().drop_duplicates().head(30))
rawg_titles.extend(steam_df.loc[steam_df["appid"].isin(comparison_ids), "name"].dropna())
rawg_titles.extend(xbox_official["title"].dropna().head(15))
rawg_titles.extend(ps_downloads.loc[ps_downloads["chart_category"] == "PS5", "title"].dropna().drop_duplicates().head(20))
rawg_titles = list(dict.fromkeys(rawg_titles))[:20]
rawg_records = []
if rawg_key:
    for i, title in enumerate(rawg_titles, start=1):
        print(f"[{i}/{len(rawg_titles)}] Fetching {title}...", flush=True)
        try:
            response = requests.get("https://api.rawg.io/api/games",
                                    params={"key": rawg_key, "search": title, "page_size": 10}, timeout=20)
            response.raise_for_status()
            matches = [game for game in response.json().get("results", [])
                       if game.get("name") and normalize_title(game["name"]) == normalize_title(title)]
            if not matches:
                errors.append(("RAWG", title, "No exact title match"))
            for game in matches:
                rawg_records.append({"rawg_id": game["id"], "title": game["name"],
                                     "release_date": game.get("released"),
                                     "genres": ";".join(g["name"] for g in (game.get("genres") or [])),
                                     "rating": game.get("rating"),
                                     "platforms": ";".join(p["platform"]["name"] for p in (game.get("platforms") or [])),
                                     "retrieved_at_utc": timestamp()})
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            # Do not expose exception URLs containing the key.
            errors.append(("RAWG", title, type(error).__name__))
            if getattr(getattr(error, "response", None), "status_code", None) in (401, 403, 429):
                break
        finally:
            time.sleep(0.25)
else:
    errors.append(("RAWG", "API key", "Missing RAWG_API_KEY; source not imported"))
rawg_df = pd.DataFrame(rawg_records, columns=rawg_columns).drop_duplicates("rawg_id")
print("RAWG shape:", rawg_df.shape)
# Summaries only: avoid publishing raw RAWG records in committed notebook output.
print("Exact-name searches attempted up to:", len(rawg_titles))


# ### Import verification

# In[10]:


source_status = pd.DataFrame([
    {"source": "Console archive: Xbox activity", "rows": len(console_charts.query("platform == 'Xbox'")), "coverage": console_charts.query("platform == 'Xbox'")["chart_date"].nunique(), "expected": len(chart_dates)},
    {"source": "Console archive: PlayStation activity", "rows": len(console_charts.query("platform == 'PlayStation'")), "coverage": console_charts.query("platform == 'PlayStation'")["chart_date"].nunique(), "expected": len(chart_dates)},
    {"source": "Console archive: Xbox catalog", "rows": len(console_catalog.query("platform == 'Xbox'")), "coverage": int(not console_catalog.query("platform == 'Xbox'").empty), "expected": 1},
    {"source": "Console archive: PlayStation catalog", "rows": len(console_catalog.query("platform == 'PlayStation'")), "coverage": int(not console_catalog.query("platform == 'PlayStation'").empty), "expected": 1},
    {"source": "Steam historical CSV", "rows": len(steam_df), "coverage": int(not steam_df.empty), "expected": 1},
    {"source": "Steam Web API", "rows": len(steam_players), "coverage": steam_players["appid"].nunique(), "expected": len(comparison_ids)},
    {"source": "SteamSpy", "rows": len(steamspy_df), "coverage": steamspy_df["appid"].nunique(), "expected": len(comparison_ids)},
    {"source": "Xbox official", "rows": len(xbox_official), "coverage": int(not xbox_official.empty), "expected": 1},
    {"source": "PlayStation Blog", "rows": len(ps_downloads), "coverage": ps_downloads["chart_month"].nunique(), "expected": len(ps_urls)},
    {"source": "RAWG", "rows": len(rawg_df), "coverage": rawg_df["title"].map(normalize_title).nunique(), "expected": len({normalize_title(t) for t in rawg_titles})},
])
source_status["status"] = ["Missing" if rows == 0 else "Partial" if coverage < expected else "Imported"
                            for rows, coverage, expected in source_status[["rows", "coverage", "expected"]].itertuples(index=False, name=None)]
import_errors = pd.DataFrame(errors, columns=["source", "item", "error"])
print(source_status.to_string(index=False))
print("Request errors or unmatched lookups:", len(import_errors))
import_errors.head(20)


# ## Approach and Analysis
# *What is your approach to answering your project question?*
# *How will you use the identified data to answer your project question?*
# 
# Xbox, Playstation and PC games will be matched together using standardised names. Each name has been checked to ensure it is unique to its platform. Matches will be tentative links. Games with differing editions, localised names or release dates will need to be manually checked. Unmatched records have been left in.
# 
# Missing data, outliers, ages, correlations, and distributions will be explored. Historical player activity, age and platform will be explored to determine if they can be used to accurately predict if a game will be in the top 100 in the following week. Data will be divided in chronological order so predictions do not include future data. If a game does not have any valid data on what it was in the following week, it will not be automatically labelled as being unpopular. GTA VI will be considered as an individual case study and not used as evidence of a prediction for its launch.
# 
# Final comparisons will be made between official rankings on Xbox, and historical player activity. After checking editions, download data from Playstation will be grouped by region, generation and month. Data from Steam will be merged using appid. Genre, ratings and release dates from RAWG will be added so that cross platform comparisons can be made. As popularity is measured differently in each source, popularity (ownership, downloads, player activity and rankings) will be kept separate. Only data available at the time of observation will be used in historical predictions.

# In[11]:


# Join each console chart to its own platform catalog and remove ambiguous catalog IDs.
keys = ["platform", "title_id"]
unique_catalog = (console_catalog.dropna(subset=keys).drop_duplicates()
                  .drop_duplicates(subset=keys, keep=False))
console_data = console_charts.merge(unique_catalog[keys + ["release_date"]],
                                   on=keys, how="left", validate="many_to_one")
console_data["chart_date"] = pd.to_datetime(console_data["chart_date"], errors="coerce")
# Preserve the original string and explicitly mask the source's year-9998
# placeholder dates. Some pandas versions can parse 9998 as a valid date,
# which otherwise inflates pre-release counts and hides unusable dates.
console_data["release_date_raw"] = console_data["release_date"].astype("string").str.strip()
source_dates = console_data["release_date_raw"]
placeholder_dates = source_dates.str.fullmatch(r"9998-\d{2}-\d{2}", na=False)
console_data["release_date"] = pd.to_datetime(
    source_dates.mask(placeholder_dates), format="%Y-%m-%d", errors="coerce"
)
console_data["unusable_release_date"] = console_data["release_date"].isna()
console_data["days_since_release"] = (
    console_data["chart_date"] - console_data["release_date"]
).dt.days
console_data["title_key"] = console_data["title"].map(normalize_title)
console_data.head()


# In[12]:


# Title match candidates for later verification.
console_titles = unique_catalog[keys + ["title_name"]].copy()
console_titles["title_key"] = console_titles["title_name"].map(normalize_title)
console_titles = (console_titles.dropna(subset=["title_key"])
                  .drop_duplicates(["platform", "title_key"], keep=False))
steam_titles = steam_df.copy()
steam_titles["title_key"] = steam_titles["name"].map(normalize_title)
steam_titles = steam_titles.dropna(subset=["title_key"]).drop_duplicates("title_key", keep=False)

xbox_titles = console_titles.query("platform == 'Xbox'")
ps_titles = console_titles.query("platform == 'PlayStation'")
console_match_candidates = xbox_titles.merge(ps_titles, on="title_key", how="inner",
                                             suffixes=("_xbox", "_ps"), validate="one_to_one")
steam_match_candidates = console_titles.merge(
    steam_titles[["title_key", "appid", "name", "release_date", "genres"]],
    on="title_key", how="inner", validate="many_to_one")
print("Console match candidates:", len(console_match_candidates))
print("Steam match candidates:", len(steam_match_candidates))
console_match_candidates.head()


# In[13]:


# Outer merge retains modern/current Steam titles absent in the 2019 snapshot.
comparison_df = steam_df[steam_df["appid"].isin(comparison_ids)].copy()
for frame in (comparison_df, steam_players, steamspy_df):
    frame["appid"] = pd.to_numeric(frame["appid"], errors="coerce").astype("Int64")
comparison_df = comparison_df.merge(steam_players, on="appid", how="outer", validate="one_to_one")
comparison_df = comparison_df.merge(steamspy_df, on="appid", how="outer", validate="one_to_one")
print("Steam comparison rows:", len(comparison_df))
comparison_df[["appid", "name", "owners", "spy_owners", "current_players"]].head()


# ### Candidate matches for external sources

# In[14]:


xbox_match_candidates = xbox_official.assign(title_key=xbox_official["title"].map(normalize_title)).merge(
    xbox_titles[["title_key", "title_id", "title_name"]], on="title_key", how="left", validate="many_to_one")
ps_match_candidates = ps_downloads.assign(title_key=ps_downloads["title"].map(normalize_title)).merge(
    ps_titles[["title_key", "title_id", "title_name"]], on="title_key", how="left", validate="many_to_one")
rawg_unique = rawg_df.assign(title_key=rawg_df["title"].map(normalize_title)).dropna(subset=["title_key"])
rawg_unique = rawg_unique.drop_duplicates("title_key", keep=False)
console_rawg_candidates = console_titles.merge(
    rawg_unique[["title_key", "rawg_id", "release_date", "genres", "rating", "platforms"]],
    on="title_key", how="left", validate="many_to_one")
steam_rawg_candidates = steam_titles[["appid", "name", "title_key"]].merge(
    rawg_unique[["title_key", "rawg_id", "platforms", "genres", "rating"]],
    on="title_key", how="left", validate="many_to_one")
print("Xbox official rows with archive title candidates:", xbox_match_candidates["title_id"].notna().sum())
print("PlayStation official rows with archive title candidates:", ps_match_candidates["title_id"].notna().sum())
print("Console title candidates with RAWG metadata:", console_rawg_candidates["rawg_id"].notna().sum())
print("Steam title candidates with RAWG metadata:", steam_rawg_candidates["rawg_id"].notna().sum())


# ### 1. Exploratory Data Analysis (EDA)
# 
# #### 1.1 Source coverage, statistical summaries, and initial issues

# In[15]:


import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import display

sns.set_theme(style="whitegrid", context="notebook")

# Work on copies; keep the original checkpoint's raw data and joins available.
eda_console = console_data.copy()
# Reconstruct both flags from source strings so partial runs and pandas
# versions cannot interpret the year-9998 placeholders as real dates.
eda_dates_raw = eda_console["release_date_raw"].astype("string").str.strip()
eda_placeholder = eda_dates_raw.str.fullmatch(r"9998-\d{2}-\d{2}", na=False)
eda_console["release_date"] = pd.to_datetime(
    eda_dates_raw.mask(eda_placeholder), format="%Y-%m-%d", errors="coerce"
)
eda_console["unusable_release_date"] = eda_console["release_date"].isna()
eda_console["days_since_release"] = (
    eda_console["chart_date"] - eda_console["release_date"]
).dt.days
eda_console["rank"] = pd.to_numeric(eda_console["rank"], errors="coerce")
eda_console["players"] = pd.to_numeric(eda_console["players"], errors="coerce")
eda_console["percentage"] = pd.to_numeric(eda_console["percentage"], errors="coerce")
eda_console["pre_release_flag"] = eda_console["days_since_release"].lt(0).fillna(False)

console_key = ["platform", "chart_date", "title_id"]
console_audit = eda_console.groupby("platform").agg(
    observations=("rank", "size"),
    games=("title_id", "nunique"),
    chart_dates=("chart_date", "nunique"),
    unusable_release_dates=("unusable_release_date", "sum"),
    prerelease_observations=("pre_release_flag", "sum"),
    median_sampled_pct=("percentage", "median"),
    max_sampled_pct=("percentage", "max"),
)
# All year-9998 placeholders must be categorized as unusable, not pre-release.
assert not eda_console.loc[eda_placeholder, "pre_release_flag"].any()
assert eda_console.loc[eda_placeholder, "unusable_release_date"].all()
print("Console observation-key duplicates:", int(eda_console.duplicated(console_key).sum()))
print("Fully duplicated console rows:", int(eda_console.duplicated().sum()))
print("Console rows missing any required analysis metric:", int(
    eda_console[["rank", "players", "percentage", "chart_date", "title_id", "platform"]]
    .isna().any(axis=1).sum()))
print("Negative players / ranks <= 0 / percentages outside (0, 100]:",
      int((eda_console["players"] < 0).sum()),
      int((eda_console["rank"] <= 0).sum()),
      int(((eda_console["percentage"] <= 0) | (eda_console["percentage"] > 100)).sum()))
print("Console observations by platform (two release-date quality flags):")
display(console_audit.round(4))
print("Sampled activity percentiles (percent, not percentage fractions):")
display(eda_console.groupby("platform")["percentage"]
        .quantile([0.25, 0.50, 0.75, 0.95, 0.99])
        .unstack(level=-1).round(4))
print("Data types:")
display(eda_console[["platform", "chart_date", "title_id", "rank", "players",
                     "percentage", "release_date", "days_since_release"]].dtypes.to_frame("dtype"))


# **Summary of observations in data** 
# 
# There are 126749 observations in total (65670 for Xbox and 61079 for Playstation). There are no exact duplicate rows within the data and therefore no duplicate rows for 'platform', 'date' and ‘title_id’. There is severe skewness. The median number of players sampling the title is very low at 0.0014% (Xbox) and 0.0010% (Playstation). However, there are very large maximum values of 35.9142% (Xbox), and 39.3005% (Playstation).
# 
# **Missing and anomalous data** 
# 
# Within the joined data, 2189 rows are missing valid release dates (454 for Xbox, 1735 for Playstation). This means that trend analysis can be conducted on these rows, but it will not be possible to carry out analysis on how old the titles were at launch. 676 observations have negative values for days since release (-ve values in column days_since_release) (282 for Xbox, 394 for Playstation). This indicates inconsistencies in meta-data, or listing/playing the game before launch, or anomalies from particular sources. It cannot be assumed that these observations are pre-launch gameplay. For example, titles such as Grand Theft Auto VI are present on Xbox in the data before the release date listed. These should be noted and removed from the data when considering ages of titles at launch. Within the downloaded files, there are no missing rank, sampled player numbers, or percentage of players. Similarly, there are no invalid percentages or negative player numbers. This was checked as shown above.

# In[16]:


# Diagnose outliers and monotonic feature relationships without removing popular games.
outlier_rows = []
association_rows = []
for platform, group in eda_console.groupby("platform"):
    quartile_1 = group["percentage"].quantile(0.25)
    quartile_3 = group["percentage"].quantile(0.75)
    upper_fence = quartile_3 + 1.5 * (quartile_3 - quartile_1)
    outlier_rows.append({
        "platform": platform, "Q1_pct": quartile_1, "Q3_pct": quartile_3,
        "upper_iqr_fence_pct": upper_fence,
        "above_upper_fence": int(group["percentage"].gt(upper_fence).sum()),
    })
    valid_age = group.loc[group["days_since_release"].ge(0)]
    association_rows.append({
        "platform": platform,
        "spearman_rank_vs_percentage": group["rank"].corr(group["percentage"], method="spearman"),
        "spearman_players_vs_percentage": group["players"].corr(group["percentage"], method="spearman"),
        "spearman_release_age_vs_percentage": valid_age["days_since_release"].corr(
            valid_age["percentage"], method="spearman"),
    })
print("IQR outlier audit (no upper-fence rows removed):")
display(pd.DataFrame(outlier_rows).round(4))
print("Within-platform Spearman associations (descriptive, not causal):")
display(pd.DataFrame(association_rows).round(3))


# **Outliers and correlations**
# 
# Using the 1.5IQR method, many data points are identified as outliers in the upper tail of the data (10,729 from Xbox, 10,175 from PlayStation). However, this does not indicate any erroneous data since the upper tails have been formed by popular games. These outliers are therefore noted, but not removed. Within each platform there is a strong negative relationship between rank and sample % (rS ~ -0.98) as rank is based on popularity. There is also strong positive correlation between sample % and player count (r ~ +0.99). This is not an independent causal relationship. A weak positive relationship exists between sample % and release age (Xbox r ~ +0.12, PlayStation r ~ +0.09). Therefore, the assumption that newer games will be more popular is not entirely valid. As this data set was obtained through repeated observations, it is impossible to determine the precise effect of release age on popularity from only this information.

# In[17]:


# Steam historical dataset is a different population and a different time period.
eda_steam = steam_df.copy()
owner_limits = eda_steam["owners"].astype("string").str.extract(r"^(\d+)-(\d+)$")
eda_steam["owner_lower"] = pd.to_numeric(owner_limits[0], errors="coerce")
eda_steam["owner_upper"] = pd.to_numeric(owner_limits[1], errors="coerce")
eda_steam["owner_midpoint"] = (eda_steam["owner_lower"] + eda_steam["owner_upper"]) / 2
eda_steam["log10_owner_midpoint"] = np.log10(eda_steam["owner_midpoint"].where(
    eda_steam["owner_midpoint"] > 0))
eda_steam["total_reviews"] = (pd.to_numeric(eda_steam["positive_ratings"], errors="coerce")
                              + pd.to_numeric(eda_steam["negative_ratings"], errors="coerce"))
eda_steam["positive_review_share"] = (
    pd.to_numeric(eda_steam["positive_ratings"], errors="coerce")
    / eda_steam["total_reviews"].replace(0, np.nan)
)
print("Steam rows:", len(eda_steam), "unique app IDs:", eda_steam["appid"].nunique(),
      "duplicate app IDs:", int(eda_steam["appid"].duplicated().sum()))
print("Unparseable owner ranges:", int(eda_steam["owner_midpoint"].isna().sum()))
print("Zero-review games:", int(eda_steam["total_reviews"].eq(0).sum()))
print("Missing developer/publisher:", int(eda_steam["developer"].isna().sum()),
      int(eda_steam["publisher"].isna().sum()))
display(eda_steam[["price", "owner_midpoint", "positive_review_share",
                   "average_playtime"]].describe(percentiles=[0.5, 0.9, 0.99]).round(3))


# **Steam**
# 
# Each entry corresponds to one app in the Steam Store. For owners, we have a range rather than exact numbers. We can approximate a representative number from the middle of the range. Price is taken directly from the Steam Store. Reviews are proportions of positive reviews in total. Play time is based on historical game data. Note that these values cannot be directly compared to current console player numbers. If there was no information on a game’s developers/publishers from Steam, then an unknown value has been used.

# #### 1.2 Visualization 1 — Distribution of sampled console activity

# In[18]:


distribution_data = eda_console.loc[eda_console["percentage"].gt(0),
                                    ["platform", "percentage"]].copy()
distribution_data["log10_sampled_pct"] = np.log10(distribution_data["percentage"])
fig, ax = plt.subplots(figsize=(10, 5))
sns.histplot(data=distribution_data, x="log10_sampled_pct", hue="platform",
             bins=55, element="step", stat="density", common_norm=False,
             alpha=0.3, ax=ax)
ax.set(title="Console game-week activity: highly skewed distribution",
       xlabel="log10(sampled player activity, percent)",
       ylabel="Density of game-week observations")
plt.tight_layout()
plt.show()


# #### 1.3 Visualization 2 — Matched popular titles on the last snapshot

# In[19]:


last_date = eda_console["chart_date"].max()
latest_console = eda_console.loc[eda_console["chart_date"].eq(last_date)].copy()
# One record per title key and platform is required for an unambiguous display join.
unique_latest = latest_console.dropna(subset=["title_key"]).drop_duplicates(
    ["platform", "title_key"], keep=False)
shared_keys = (unique_latest.groupby("title_key")["platform"].nunique()
               .loc[lambda s: s.eq(2)].index)
plot_latest = unique_latest.loc[unique_latest["title_key"].isin(shared_keys)].copy()
top_shared_keys = (plot_latest.groupby("title_key")["percentage"].mean()
                   .nlargest(10).index)
plot_latest = plot_latest.loc[plot_latest["title_key"].isin(top_shared_keys)]
plot_latest["game"] = plot_latest["title_key"].map(
    plot_latest.groupby("title_key")["title"].first())
order = (plot_latest.groupby("game")["percentage"].mean().sort_values(ascending=False).index)
fig, ax = plt.subplots(figsize=(10, 6))
sns.barplot(data=plot_latest, x="percentage", y="game", hue="platform",
            order=order, errorbar=None, ax=ax)
ax.set(title=f"Top shared game names on {last_date:%Y-%m-%d}",
       xlabel="Sampled players active in game (%)", ylabel="")
plt.tight_layout()
plt.show()
print("Matched exact normalized names in the last observation:", len(shared_keys))


# #### 1.4 Visualization 3 — GTA V versus GTA VI over time

# In[20]:


gta_names = ["Grand Theft Auto V", "Grand Theft Auto VI"]
gta_plot = eda_console.loc[eda_console["title"].isin(gta_names)].copy()
gta_plot = gta_plot.loc[~(gta_plot["title"].eq("Grand Theft Auto VI")
                          & gta_plot["pre_release_flag"])].copy()
fig, ax = plt.subplots(figsize=(11, 5))
styles = {("Xbox", "Grand Theft Auto V"): ("-", "o"),
          ("PlayStation", "Grand Theft Auto V"): ("-", "s"),
          ("Xbox", "Grand Theft Auto VI"): ("--", "o"),
          ("PlayStation", "Grand Theft Auto VI"): ("--", "s")}
for (platform, title), group in gta_plot.groupby(["platform", "title"]):
    style, marker = styles[(platform, title)]
    ordered = group.sort_values("chart_date")
    ax.plot(ordered["chart_date"], ordered["percentage"],
            linestyle=style, marker=marker, label=f"{platform} | {title}")
ax.set(title="GTA sampled activity through November 20 (pre-release flags excluded)",
       xlabel="Chart observation date", ylabel="Sampled player activity (%)")
ax.tick_params(axis="x", rotation=30)
ax.legend(fontsize=8, ncol=2)
plt.tight_layout()
plt.show()
print("GTA VI chart rows excluded as pre-release:",
      int((eda_console["title"].eq("Grand Theft Auto VI") & eda_console["pre_release_flag"]).sum()))
print("GTA latest observation:")
display(latest_console.loc[latest_console["title"].isin(gta_names),
                           ["platform", "title", "rank", "percentage"]]
        .sort_values(["title", "platform"]))


# #### 1.5 Visualization 4 — Historical PC correlations

# In[21]:


steam_features = ["log10_owner_midpoint", "price", "positive_review_share",
                  "average_playtime"]
steam_corr = eda_steam[steam_features].corr(method="spearman")
fig, ax = plt.subplots(figsize=(7.5, 5.5))
sns.heatmap(steam_corr, annot=True, fmt=".2f", cmap="vlag", center=0,
            vmin=-1, vmax=1, square=True, ax=ax)
ax.set_title("Historical Steam: Spearman feature associations")
plt.tight_layout()
plt.show()
display(steam_corr.round(3))


# #### 1.6 Visualization 5 — Steam store price and ownership-proxy scatter

# In[22]:


steam_scatter = eda_steam.dropna(subset=["price", "log10_owner_midpoint"])
price_display_limit = float(steam_scatter["price"].quantile(0.99))
plot_steam = steam_scatter.loc[steam_scatter["price"].le(price_display_limit)]
if len(plot_steam) > 6000:
    plot_steam = plot_steam.sample(n=6000, random_state=4063)
fig, ax = plt.subplots(figsize=(9.5, 5))
ax.scatter(plot_steam["price"], plot_steam["log10_owner_midpoint"],
           s=9, alpha=0.18)
ax.set(title="Historical Steam: price versus estimated ownership range midpoint",
       xlabel="Historical Steam price (GBP; <= 99th percentile shown)",
       ylabel="log10(ownership-range midpoint)")
plt.tight_layout()
plt.show()
print("Full-data Steam Spearman(price, log10 owner midpoint):",
      round(float(steam_corr.loc["price", "log10_owner_midpoint"]), 3))


# #### 1.7 Contextual ranking sources and observable limitations
# 
# Only 50 titles are present in the official Xbox ranking (retrieved 22nd November) meaning that it cannot be directly compared to the archive (last chart retrieved 20th November). In the PlayStation Blog download rankings there are 300 title region genre month positions recorded between August – October. As such, the download rankings have measured a different event to the sampled live player data. Matches from Checkpoint 1 were not confirmed, and there is no official ground truth provided. There are also issues with bias within samples, overlapping time periods, unclear differentiations between versions of games and incomplete information from RAWG.

# ### 2. Data cleaning and transformation

# In[23]:


# Clean console observations without treating missing metadata as no popularity.
console_clean = console_data.copy()
rows_before = len(console_clean)
console_clean["chart_date"] = pd.to_datetime(console_clean["chart_date"], errors="coerce")
# Apply the same explicit placeholder rule as EDA. This avoids pandas
# version differences when the release-date audit is recomputed here.
clean_dates_raw = console_clean["release_date_raw"].astype("string").str.strip()
clean_placeholder = clean_dates_raw.str.fullmatch(r"9998-\d{2}-\d{2}", na=False)
console_clean["release_date"] = pd.to_datetime(
    clean_dates_raw.mask(clean_placeholder), format="%Y-%m-%d", errors="coerce"
)
console_clean["unusable_release_date"] = console_clean["release_date"].isna()
console_clean["rank"] = pd.to_numeric(console_clean["rank"], errors="coerce")
console_clean["players"] = pd.to_numeric(console_clean["players"], errors="coerce")
console_clean["percentage"] = pd.to_numeric(console_clean["percentage"], errors="coerce")

# Only same-platform/snapshot/ID duplicates can legitimately be deduplicated.
console_dup_count = int(console_clean.duplicated(["platform", "chart_date", "title_id"]).sum())
console_clean = console_clean.drop_duplicates(["platform", "chart_date", "title_id"], keep="first")
invalid_console = (console_clean[["platform", "chart_date", "title_id", "rank",
                                   "players", "percentage"]].isna().any(axis=1)
                   | console_clean["rank"].le(0) | console_clean["players"].lt(0)
                   | console_clean["percentage"].le(0)
                   | console_clean["percentage"].gt(100))
invalid_console_count = int(invalid_console.sum())
console_clean = console_clean.loc[~invalid_console].copy()
console_clean["rank"] = console_clean["rank"].astype("int64")
console_clean["players"] = console_clean["players"].astype("int64")
console_clean["percentage"] = console_clean["percentage"].astype("float64")
console_clean["release_age_days"] = (
    console_clean["chart_date"] - console_clean["release_date"]).dt.days
console_clean["pre_release_flag"] = console_clean["release_age_days"].lt(0).fillna(False)
console_clean["valid_release_age_days"] = console_clean["release_age_days"].where(
    console_clean["release_age_days"].ge(0))
console_clean["log10_sampled_pct"] = np.log10(console_clean["percentage"])
console_clean = console_clean.sort_values(["platform", "chart_date", "rank"]).reset_index(drop=True)

# Steam: parse bracket ranges; positive review proportion undefined for 0 reviews.
steam_clean = steam_df.copy().drop_duplicates(subset=["appid"]).copy()
steam_clean["appid"] = pd.to_numeric(steam_clean["appid"], errors="coerce").astype("Int64")
steam_clean["release_date"] = pd.to_datetime(steam_clean["release_date"], errors="coerce")
steam_clean["price"] = pd.to_numeric(steam_clean["price"], errors="coerce")
owner_bounds = steam_clean["owners"].astype("string").str.extract(r"^(\d+)-(\d+)$")
steam_clean["owners_low"] = pd.to_numeric(owner_bounds[0], errors="coerce")
steam_clean["owners_high"] = pd.to_numeric(owner_bounds[1], errors="coerce")
steam_clean["owners_midpoint"] = (steam_clean["owners_low"] + steam_clean["owners_high"]) / 2
steam_clean["log10_owners_midpoint"] = np.log10(
    steam_clean["owners_midpoint"].where(steam_clean["owners_midpoint"].gt(0)))
steam_clean["reviews_total"] = (pd.to_numeric(steam_clean["positive_ratings"], errors="coerce")
                                + pd.to_numeric(steam_clean["negative_ratings"], errors="coerce"))
steam_clean["positive_review_share"] = (
    pd.to_numeric(steam_clean["positive_ratings"], errors="coerce")
    / steam_clean["reviews_total"].replace(0, np.nan))
steam_clean["release_year"] = steam_clean["release_date"].dt.year.astype("Int64")

cleaning_report = pd.DataFrame([
    {"issue": "Duplicate console observation keys", "before": console_dup_count,
     "action": "Remove only repeated platform/date/title IDs", "removed": console_dup_count},
    {"issue": "Invalid/absent core console metrics", "before": invalid_console_count,
     "action": "Exclude from console analysis", "removed": invalid_console_count},
    {"issue": "Unusable release dates", "before": int(console_clean["unusable_release_date"].sum()),
     "action": "Retain activity; exclude from release-age analysis", "removed": 0},
    {"issue": "Pre-release observations", "before": int(console_clean["pre_release_flag"].sum()),
     "action": "Flag; exclude from post-release-age analysis", "removed": 0},
    {"issue": "Unparseable Steam owner range", "before": int(steam_clean["owners_midpoint"].isna().sum()),
     "action": "Keep raw range; derived proxy left missing", "removed": 0},
    {"issue": "Steam missing developer/publisher", "before": int(steam_clean[["developer", "publisher"]].isna().sum().sum()),
     "action": "Retain as unknown; do not fabricate categories", "removed": 0},
])
print("Console rows before/after:", rows_before, len(console_clean))
print("Steam rows before/after:", len(steam_df), len(steam_clean))
display(cleaning_report)
assert not console_clean.duplicated(["platform", "chart_date", "title_id"]).any()
assert console_clean["percentage"].between(0, 100, inclusive="right").all()


# #### **Cleaning**
# **Missing data** - No imputation performed on core console variables. The 2189 missing release date fields will be excluded from correlation/analysis involving age. Similarly, very few missing values exist within the developer and publisher fields in the Steam dataset, so these will be left as missing. Note that missing != “unknown publisher.” The proportion of positive reviews in games with 0 reviews is undefined, and so these will also be left as missing.
# 
# **Duplicate Data** - Duplicates may occur based on natural keys. Within the data provided, no duplicate core console keys or Steam application IDs exist. Code has been included to avoid accidental duplication. Similar strings in game names do not cause two entries with similar names to be merged.
# 
# **Outliers** - Heavy tails exist in activity % data due to the nature of the project. High ranked/active games are desired so these will not be removed. However, 676 negative values exist in release ages. These will be excluded from analysis concerning release age and launch, but will be present in the raw chart. Ranks and percentages have been checked for validity, rather than Winsorised.
# 
# **Type conversions** - Chart and release dates converted to datetime format. Ranks, players and activity % converted into integer/float types. The start and end of the range of Steam owners are converted into numerical values. Reviews converted into positive fractions. Log transformations represent different features in analysis. Missing release dates and incomplete RAWG data can be seen.

# ### 3. Machine Learning Plan
# 
# - **Binary Classification Problem** - Given a video game observed on a week on date t, predict whether it will be in the top 100 on the same platform on the next appropriate week. We wish to predict ranking class. For labelling, we can only label data for games that were observed on both weeks. If the game is not observed in the second archive, we do not know what the label should be. This means that our data may be skewed towards games which remain in the top 100, and this should be stated. Ensure that the data spans exactly one week. For example, 15th Nov to 20th Nov would not be an appropriate one week span.
# 
# - **Feature Engineering** - Current_rank, activity_percent, users_sampled, platform, appropriate release age, previously observed ranks/activity percentages and changes in trend. Where release age features are missing, metadata was uncertain. Where pre_release_flag is true, do not include release age features in models specific to launch. Do not include data from subsequent rows, subsequent week rank/users, future data from steam, or monthly data from PlayStation. Do not include title_id as a numerical feature. Only include RAWG genre information where it is verified and known by date t.
# 
# - **Processing** - Construct a feature set of platform, date and title_id. For each platform and title_id, lag the target by exactly one week. Only label data with known labels. Sort data in chronological order. Split data into training data and validation/test data rather than randomly. Impute, scale and encode features using only training data in scikit-learn Pipelines/ColumnTransformers. One hot encode platform and genre. Include a baseline feature. Compare logistic regression with random forest. Perform forward-chaining validation. Consider class imbalance.
# 
# - **Model Evaluation** - Report precision, recall, f1, balanced accuracy, confusion matrix and PR AUC for predicting whether a game is in top 100. Report these metrics for each platform and compare with baseline. Where there is class imbalance, ROC AUC may be included as well as PR AUC. Consider trade-off between false positives and negatives for publishers. Do not report test accuracy until after training. Do not suggest that models have been implemented.
# 
# - **Potential Issues / Solutions** - Biased sampling and varying panel sizes. Consider within-platform and track denominator values. Many titles with low activity. Class imbalance. Mitigate using PR AUC, stratified metrics. Try class weighting (only on training data). Overlapping windows. Chronological split, and lagged appropriately. Missing or edition-specific release dates. Include flags. Do not guess missing data. Incomplete follow-up data, biased sampling. Data with unknown target excluded. State coverage. Drifting data sources. Date-specific holdout. Short time period since GTA-VI. Descriptive analysis only. Cannot make robust predictions for GTA-VI retention.

# ### 4. Prior feedback and updates
# - Warm: Positive feedback on the GTA topic and readable code; kept both strengths.
# - Cool: Chose seven-day console activity percentage as the main popularity metric, clarified dataset joins, and added a clearer title and source links.
# - Hard: Removed the outdated video_games.csv, incorporated API/HTML sources alongside CSV, and used GTA V as the released comparison for GTA VI.
# - Code: The reported Steam header and Backloggd index issues concerned earlier files. The current Steam columns were checked; Backloggd is not used.

# ## Resources and References
# - Rockstar Games: [GTA VI official site](https://www.rockstargames.com/VI) and [November 19, 2026 release announcement](https://www.rockstargames.com/newswire/article/ak3ak31a49a221/grand-theft-auto-vi-is-now-set-to-launch-november-19-2026).
# - olonadtrolo: [Xbox and PlayStation Console Activity Charts, methodology and CSV archive](https://github.com/olonadtrolo/charts).
# - Nik Davis: [Steam Store Games dataset](https://www.kaggle.com/datasets/nikdavis/steam-store-games); [CSV mirror](https://github.com/genlikan/SteamAnalysis).
# - Valve: [Steam Web API, GetNumberOfCurrentPlayers](https://partner.steamgames.com/doc/webapi/ISteamUserStats).
# - RAWG: [API documentation](https://rawg.io/apidocs).
# - Microsoft: [Xbox Most Played Games](https://www.xbox.com/en-US/games/browse/Popular).
# - Sony: [PlayStation Blog](https://blog.playstation.com/) (monthly download charts).
# - SteamSpy: [API](https://steamspy.com/api.php), [methodology and limitations](https://steamspy.com/about).
# - Microsoft: [US Microsoft Store Most Played](https://www.microsoft.com/en-us/store/most-popular/games/xbox).
# - Sony: [August](https://blog.playstation.com/2026/09/04/playstation-store-august-2026s-top-downloads/), [September](https://blog.playstation.com/2026/10/22/playstation-store-september-2026s-top-downloads/), [October](https://blog.playstation.com/2026/11/04/playstation-store-october-2026s-top-downloads/) 2026 charts.

# In[26]:


# ⚠️ Make sure you run this cell at the end of your notebook before every submission!
get_ipython().system('jupyter nbconvert --to python source.ipynb')

