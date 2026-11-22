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
# - Does owning on PC correlate to owning the game on consoles?
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

# In[19]:


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

# In[20]:


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

# In[21]:


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

# In[ ]:


# Join each console chart to its own platform catalog and remove ambiguous catalog IDs.
keys = ["platform", "title_id"]
unique_catalog = (console_catalog.dropna(subset=keys).drop_duplicates()
                  .drop_duplicates(subset=keys, keep=False))
console_data = console_charts.merge(unique_catalog[keys + ["release_date"]],
                                   on=keys, how="left", validate="many_to_one")
console_data["chart_date"] = pd.to_datetime(console_data["chart_date"], errors="coerce")
console_data["release_date"] = pd.to_datetime(console_data["release_date"], errors="coerce")
console_data["days_since_release"] = (console_data["chart_date"] -
                                      console_data["release_date"]).dt.days
console_data["title_key"] = console_data["title"].map(normalize_title)
console_data.head()


# In[ ]:


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


# In[24]:


# Outer merge retains modern/current Steam titles absent in the 2019 snapshot.
comparison_df = steam_df[steam_df["appid"].isin(comparison_ids)].copy()
for frame in (comparison_df, steam_players, steamspy_df):
    frame["appid"] = pd.to_numeric(frame["appid"], errors="coerce").astype("Int64")
comparison_df = comparison_df.merge(steam_players, on="appid", how="outer", validate="one_to_one")
comparison_df = comparison_df.merge(steamspy_df, on="appid", how="outer", validate="one_to_one")
print("Steam comparison rows:", len(comparison_df))
comparison_df[["appid", "name", "owners", "spy_owners", "current_players"]].head()


# ### Candidate matches for external sources

# In[15]:


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

# In[16]:


# ⚠️ Make sure you run this cell at the end of your notebook before every submission!
get_ipython().system('jupyter nbconvert --to python source.ipynb')

