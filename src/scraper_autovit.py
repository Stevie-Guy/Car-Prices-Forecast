"""Scraper pentru pagini de listare Autovit.ro (ex. https://www.autovit.ro/autoturisme).

Autovit e o aplicatie Next.js: fiecare pagina de listare contine JSON-ul complet al
anunturilor in <script id="__NEXT_DATA__"> (props.pageProps.urqlState -> advertSearch).
Il citim direct, fara sa parsam HTML-ul vizual, deci e rapid si stabil.

Pastreaza aceeasi schema SQLite (listings + snapshots) ca scraper_autoro.py,
astfel incat bazele de date ale celor doua surse pot fi unite cu database_merger.py.

Exemple:
    # Colecteaza 200 de masini (32 pe pagina -> 7 cereri HTTP)
    python src/scraper_autovit.py --url https://www.autovit.ro/autoturisme --max-cars 200

    # Colecteaza 5 pagini de Audi si salveaza si in JSONL
    python src/scraper_autovit.py --url https://www.autovit.ro/autoturisme/audi --max-pages 5 --jsonl autovit_audi.jsonl

    # Offline, pe un fisier salvat din browser
    python src/scraper_autovit.py --html-file autovit_p1.html

Instalare: pip install requests
"""
import argparse
import json
import random
import re
import sqlite3
import sys
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

SOURCE = "autovit"
# Baza implicita din repo, indiferent din ce folder e rulat scriptul
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data" / "autovit" / "cars_autovit.db"
BLOCK_HINTS = ("captcha", "access denied", "request blocked", "are you a robot", "cloudflare")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    listing_id TEXT NOT NULL, source TEXT NOT NULL, url TEXT, title TEXT,
    short_description TEXT, created_at TEXT,
    make TEXT, model TEXT, version TEXT, year INTEGER, mileage_km INTEGER,
    fuel TEXT, engine_cc INTEGER, power_hp INTEGER, vat TEXT,
    city TEXT, region TEXT, seller_id TEXT, seller_name TEXT, seller_type TEXT,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
    PRIMARY KEY (source, listing_id)
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL, listing_id TEXT NOT NULL, scraped_at TEXT NOT NULL,
    price REAL, currency TEXT, price_is_gross INTEGER,
    price_evaluation TEXT, price_drop_pct REAL,
    is_promoted INTEGER, bump_date TEXT,
    page INTEGER, rank_on_page INTEGER, search_url TEXT,
    FOREIGN KEY (source, listing_id) REFERENCES listings(source, listing_id)
);
CREATE INDEX IF NOT EXISTS idx_l_make_model ON listings(make, model, year);
CREATE INDEX IF NOT EXISTS idx_s_listing ON snapshots(source, listing_id, scraped_at);
"""

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ parsare
def _to_int(value):
    if value is None:
        return None
    d = re.sub(r"[^\d]", "", str(value))
    return int(d) if d else None


def _to_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _price_drop_pct(node):
    """priceDrop e null pe majoritatea anunturilor; cand exista, cautam procentul."""
    pd = node.get("priceDrop")
    if not isinstance(pd, dict):
        return None
    for key in ("percentage", "percent", "dropPercentage", "value"):
        v = _to_float(pd.get(key))
        if v is not None:
            return round(v, 2)
    return None


def parse_node(node, vas=None):
    """Transforma un `node` din advertSearch.edges intr-un dict plat."""
    listing_id = node.get("id")
    if not listing_id:
        return None
    vas = vas or {}

    # parameters: [{key, value, displayValue}, ...]
    params = {p.get("key"): p for p in node.get("parameters") or [] if p.get("key")}

    def disp(key):
        p = params.get(key)
        return p.get("displayValue") if p else None

    def val(key):
        p = params.get(key)
        return p.get("value") if p else None

    price = node.get("price") or {}
    amount = price.get("amount") or {}
    location = node.get("location") or {}
    seller = node.get("seller") or {}
    seller_link = node.get("sellerLink") or {}
    is_gross = price.get("isGross")

    return {
        "listing_id": str(listing_id),
        "url": node.get("url"),
        "title": node.get("title"),
        "short_description": node.get("shortDescription"),
        "created_at": node.get("createdAt"),
        "make": disp("make"),
        "model": disp("model"),
        "version": disp("version"),
        "year": _to_int(val("year")),
        "mileage_km": _to_int(val("mileage")),
        "fuel": val("fuel_type"),
        "engine_cc": _to_int(val("engine_capacity")),
        "power_hp": _to_int(val("engine_power")),
        "vat": val("vat"),
        "city": (location.get("city") or {}).get("name"),
        "region": (location.get("region") or {}).get("name"),
        "seller_id": seller_link.get("id"),
        "seller_name": seller_link.get("name"),
        "seller_type": seller.get("__typename"),
        "price": _to_float(amount.get("value") if amount.get("value") is not None else amount.get("units")),
        "currency": amount.get("currencyCode"),
        "price_is_gross": None if is_gross is None else int(bool(is_gross)),
        "price_evaluation": (node.get("priceEvaluation") or {}).get("indicator"),
        "price_drop_pct": _price_drop_pct(node),
        "is_promoted": int(bool(vas.get("isPromoted"))),
        "bump_date": vas.get("bumpDate"),
    }


def _find_advert_search(next_data):
    """Cauta in urqlState raspunsul GraphQL care contine advertSearch."""
    urql = (next_data.get("props", {}).get("pageProps", {}) or {}).get("urqlState") or {}
    for entry in urql.values():
        data = entry.get("data") if isinstance(entry, dict) else None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                continue
        if isinstance(data, dict) and isinstance(data.get("advertSearch"), dict):
            return data["advertSearch"]
    return None


def parse_page(html):
    """Intoarce (lista de dict-uri plate, meta)."""
    m = NEXT_DATA_RE.search(html)
    if not m:
        return [], {"total": None, "page_size": None}
    search = _find_advert_search(json.loads(m.group(1)))
    if not search:
        return [], {"total": None, "page_size": None}

    rows = []
    for edge in search.get("edges") or []:
        parsed = parse_node(edge.get("node") or {}, edge.get("vas"))
        if parsed:
            rows.append(parsed)
    page_info = search.get("pageInfo") or {}
    return rows, {"total": search.get("totalCount"), "page_size": page_info.get("pageSize")}


# ------------------------------------------------------------------ stocare
LISTING_COLS = ["url", "title", "short_description", "created_at", "make", "model", "version",
                "year", "mileage_km", "fuel", "engine_cc", "power_hp", "vat", "city", "region",
                "seller_id", "seller_name", "seller_type"]


def store(db, rows, page, search_url):
    t = now()
    cols = ", ".join(LISTING_COLS)
    qs = ", ".join("?" * len(LISTING_COLS))
    for rank, r in enumerate(rows, 1):
        db.execute(
            f"""INSERT INTO listings (listing_id, source, {cols}, first_seen, last_seen)
                VALUES (?, ?, {qs}, ?, ?)
                ON CONFLICT(source, listing_id) DO UPDATE SET last_seen=excluded.last_seen,
                    title=excluded.title, short_description=excluded.short_description""",
            [r["listing_id"], SOURCE, *[r[c] for c in LISTING_COLS], t, t])
        db.execute(
            """INSERT INTO snapshots (source, listing_id, scraped_at, price, currency, price_is_gross,
               price_evaluation, price_drop_pct, is_promoted, bump_date, page, rank_on_page, search_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (SOURCE, r["listing_id"], t, r["price"], r["currency"], r["price_is_gross"],
             r["price_evaluation"], r["price_drop_pct"], r["is_promoted"], r["bump_date"],
             page, rank, search_url))
    db.commit()


# ------------------------------------------------------------------ retea
def page_url(base, page):
    """Construieste URL-ul de paginare pentru autovit (pastreaza filtrele existente):
    Pagina 1: https://www.autovit.ro/autoturisme
    Pagina N: https://www.autovit.ro/autoturisme?page=N
    """
    u = urlparse(base)
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k != "page"]
    if page > 1:
        query.append(("page", str(page)))
    return urlunparse(u._replace(query=urlencode(query)))


def robots_ok(url):
    u = urlparse(url)
    robots_url = f"{u.scheme}://{u.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(robots_url, headers=HEADERS, timeout=15)
        if r.status_code in (401, 403):
            print(f"[robots] WAF-ul a returnat {r.status_code} pe robots.txt; continui cu prudenta")
            return True, None
        elif r.status_code >= 400:
            return True, None
        rp.parse(r.text.splitlines())
    except Exception as e:
        print(f"[robots] nu am putut citi robots.txt ({e}); continui cu prudenta")
        return True, None
    return rp.can_fetch(HEADERS["User-Agent"], url), rp.crawl_delay(HEADERS["User-Agent"])


def fetch(session, url):
    r = session.get(url, timeout=30)
    # Pagina contine mult JSON; cautam semne de blocare doar in inceputul documentului.
    if r.status_code in (403, 429, 503) or any(h in r.text[:4000].lower() for h in BLOCK_HINTS):
        raise PermissionError(
            f"HTTP {r.status_code} la {url}. Server-ul sau WAF-ul a blocat cererea. "
            f"Retry-After={r.headers.get('Retry-After')}, server={r.headers.get('server')}. "
            "Ma opresc; NU insista si nu ocoli protectia.")
    r.raise_for_status()
    return r.text


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--url", default="https://www.autovit.ro/autoturisme",
                    help="URL de categorie/marca (default: https://www.autovit.ro/autoturisme)")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="nr. maxim de pagini (daca nu e dat, se calculeaza din --max-cars sau default 3)")
    ap.add_argument("--max-cars", "-n", type=int, default=None,
                    help="nr. maxim de autovehicule de colectat (ex. 25, 200, 1000)")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--delay", type=float, nargs=2, default=(3.0, 6.0), metavar=("MIN", "MAX"),
                    help="pauza aleatorie intre cereri, secunde (default 3 6)")
    ap.add_argument("--db", default=str(DEFAULT_DB),
                    help=f"fisierul SQLite (default: {DEFAULT_DB.relative_to(REPO_ROOT)})")
    ap.add_argument("--jsonl", help="optional: scrie si un fisier JSONL cu anunturile")
    ap.add_argument("--save-raw", action="store_true", help="salveaza HTML-ul brut in data/raw/")
    ap.add_argument("--html-file", help="parseaza un singur fisier HTML salvat local")
    ap.add_argument("--html-dir", help="parseaza toate fisierele *.html dintr-un director")
    args = ap.parse_args()

    # Autovit afiseaza 32 de anunturi pe pagina (nu se poate schimba din URL)
    if args.max_pages is None:
        args.max_pages = (args.max_cars // 32) + 2 if args.max_cars else 3

    db = sqlite3.connect(args.db)
    db.executescript(SCHEMA)
    jsonl = open(args.jsonl, "a", encoding="utf-8") if args.jsonl else None

    def handle(html, page, search_url, remaining=None):
        rows, meta = parse_page(html)
        if remaining is not None:
            rows = rows[:remaining]
        store(db, rows, page, search_url)
        if jsonl:
            for r in rows:
                jsonl.write(json.dumps({**r, "source": SOURCE, "scraped_at": now(), "page": page},
                                       ensure_ascii=False) + "\n")
            jsonl.flush()
        return rows, meta

    try:
        # ---- mod offline
        if args.html_file or args.html_dir:
            files = [Path(args.html_file)] if args.html_file else sorted(Path(args.html_dir).glob("*.html"))
            seen_total = 0
            for i, f in enumerate(files, 1):
                rem = (args.max_cars - seen_total) if args.max_cars else None
                rows, _ = handle(f.read_text(encoding="utf-8", errors="ignore"), i, str(f), rem)
                seen_total += len(rows)
                print(f"{f.name}: {len(rows)} anunturi extrase (total: {seen_total})")
                if args.max_cars and seen_total >= args.max_cars:
                    break
            return

        # ---- mod online
        ok, crawl_delay = robots_ok(page_url(args.url, args.start_page))
        if not ok:
            sys.exit("robots.txt interzice aceasta cale pentru user-agent-ul curent. Ma opresc.")
        lo, hi = args.delay
        if crawl_delay:
            lo, hi = max(lo, crawl_delay), max(hi, crawl_delay + 2)

        s = requests.Session()
        s.headers.update(HEADERS)
        seen_total = 0

        for page in range(args.start_page, args.start_page + args.max_pages):
            url = page_url(args.url, page)
            try:
                html = fetch(s, url)
            except PermissionError as e:
                print("\n!!", e)
                break
            except requests.RequestException as e:
                print("eroare retea:", e)
                break

            if args.save_raw:
                p = Path("data/raw") / SOURCE / f"{datetime.now():%Y-%m-%d}" / f"autoturisme_p{page}.html"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(html, encoding="utf-8")

            rem = (args.max_cars - seen_total) if args.max_cars else None
            rows, meta = handle(html, page, url, rem)
            if not rows:
                print(f"pagina {page}: niciun anunt gasit (sau __NEXT_DATA__ lipseste), ma opresc.")
                break

            seen_total += len(rows)
            total = f" din {meta['total']}" if meta.get("total") else ""
            print(f"pagina {page}: {len(rows)} anunturi salvate (total adunate: {seen_total}{total})")

            if args.max_cars and seen_total >= args.max_cars:
                print(f"Limita de {args.max_cars} autovehicule a fost atinsa. Ma opresc.")
                break
            if meta.get("total") and meta.get("page_size") and page * meta["page_size"] >= meta["total"]:
                print("Am ajuns la ultima pagina de rezultate.")
                break

            time.sleep(random.uniform(lo, hi))
    finally:
        db.close()
        if jsonl:
            jsonl.close()


if __name__ == "__main__":
    main()
