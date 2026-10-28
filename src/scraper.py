"""Scraper pentru pagini de listare Auto.ro (ex. https://www.auto.ro/masini-second-hand/).

Pastreaza aceeasi schema SQLite (listings + snapshots) ca autovit_scraper.py
pentru a salva ambele surse in acelasi fisier cars.db.

Exemple:
    # Colecteaza 250 de masini (cate 100 pe pagina -> doar 3 cereri HTTP)
    python scraper_02.py --url https://www.auto.ro/masini-second-hand --per-page 100 --max-cars 250

    # Colecteaza 10 pagini a cate 100 de masini (1000 de anunturi) si salveaza si in JSONL
    python scraper_02.py --url https://www.auto.ro/masini-second-hand --per-page 100 --max-pages 10 --jsonl autoro.jsonl

    # Offline, pe un fisier salvat din browser
    python scraper_02.py --html-file autoro_p1.html

Instalare: pip install requests beautifulsoup4
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
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SOURCE = "autoro"
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

FUEL_MAP = {
    "benzina": "petrol",
    "benzină": "petrol",
    "diesel": "diesel",
    "motorina": "diesel",
    "hibrid": "hybrid",
    "electric": "electric",
    "gpl": "lpg",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ parsare
def _digits_int(text):
    if not text:
        return None
    d = re.sub(r"[^\d]", "", text)
    return int(d) if d else None


def _parse_price(text):
    if not text:
        return None, None
    # Ex: "11.190 EUR" -> price=11190.0, currency="EUR"
    m = re.search(r"([\d\.,]+)\s*([A-Z]{3}|€|EUR|RON|LEI)", text.strip(), re.I)
    if not m:
        return _digits_int(text), None
    raw_val, curr = m.group(1), m.group(2).upper()
    clean_val = raw_val.replace(".", "").replace(",", ".")
    if curr == "€":
        curr = "EUR"
    try:
        return float(clean_val), curr
    except ValueError:
        return None, curr


def _parse_make_model_from_url(url, title):
    """Extrage make si model din URL-ul auto.ro: /land_rover-range_rover_evoque/3090824.html"""
    if url:
        path = urlparse(url).path.strip("/")
        slug_part = path.split("/")[0] if "/" in path else ""
        if "-" in slug_part:
            make_slug, model_slug = slug_part.split("-", 1)
            make = make_slug.replace("_", " ").title()
            model = model_slug.replace("_", " ").title()
            if make.upper() in ("BMW", "VW", "AUDI", "SEAT", "MINI", "MG", "DS"):
                make = make.upper() if make.upper() != "AUDI" else "Audi"
            return make, model
    if title:
        parts = title.strip().split(" ", 1)
        return parts[0], (parts[1] if len(parts) > 1 else None)
    return None, None


def parse_card(card):
    # 1. URL & Titlu
    h2_a = card.select_one("h2 a")
    checkbox = card.select_one("input.compara")
    url = h2_a["href"].strip() if (h2_a and h2_a.has_attr("href")) else None
    title = h2_a.get_text(strip=True) if h2_a else (checkbox.get("name") if checkbox else None)

    # 2. ID Anunt
    listing_id = checkbox.get("value") if (checkbox and checkbox.has_attr("value")) else None
    if not listing_id and url:
        m_id = re.search(r"/(\d+)\.html", url)
        if m_id:
            listing_id = m_id.group(1)
    if not listing_id:
        return None

    # 3. Marca & Model
    make, model = _parse_make_model_from_url(url, title)

    # 4. An, Rulaj, Pret
    year_el = card.select_one("span.list_an")
    km_el = card.select_one("span.list_km")
    price_el = card.select_one("span.list_pret")

    year = _digits_int(year_el.get_text()) if year_el else None
    mileage_km = _digits_int(km_el.get_text()) if km_el else None
    price, currency = _parse_price(price_el.get_text()) if price_el else (None, None)

    # 5. Combustibil & Descriere scurta
    descr_el = card.select_one("div.car_descr")
    fuel = None
    short_description = None
    if descr_el:
        strong_el = descr_el.find("strong")
        if strong_el:
            strong_text = strong_el.get_text(strip=True)
            m_fuel = re.search(r"Carburant:\s*(.+)", strong_text, re.I)
            if m_fuel:
                raw_fuel = m_fuel.group(1).strip().lower()
                fuel = FUEL_MAP.get(raw_fuel, raw_fuel)
            strong_el.extract()  # Scoatem tagul strong pentru a ramane doar cu descrierea
        short_description = re.sub(r"\s+", " ", descr_el.get_text(strip=True)) or None

    # 6. Locatie (ex: fori="Romania - BUCURESTI")
    flag_el = card.select_one("div.listing_flag")
    region = None
    if flag_el and flag_el.has_attr("fori"):
        fori_text = flag_el["fori"]
        if "-" in fori_text:
            region = fori_text.split("-", 1)[1].strip().title()
        else:
            region = fori_text.strip().title()

    # 7. Tip vanzator (prezenta logo dealer in div.off_rg)
    off_rg = card.select_one("div.off_rg")
    has_dealer_logo = bool(off_rg and (off_rg.find("img") or "logo_off" not in off_rg.get("class", [])))
    seller_type = "ProfessionalSeller" if has_dealer_logo else "PrivateSeller"

    return {
        "listing_id": str(listing_id),
        "url": url,
        "title": title,
        "short_description": short_description,
        "created_at": None,
        "make": make,
        "model": model,
        "version": None,
        "year": year,
        "mileage_km": mileage_km,
        "fuel": fuel,
        "engine_cc": None,
        "power_hp": None,
        "vat": None,
        "city": region,
        "region": region,
        "seller_id": None,
        "seller_name": None,
        "seller_type": seller_type,
        "price": price,
        "currency": currency,
        "price_is_gross": None,
        "price_evaluation": None,
        "price_drop_pct": None,
        "is_promoted": 0,
        "bump_date": None,
    }


def parse_page(html):
    """Intoarce (lista de dict-uri plate, meta)."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.listing_cars")
    rows = []
    for c in cards:
        parsed = parse_card(c)
        if parsed:
            rows.append(parsed)
    return rows, {"total": None, "page_size": len(rows)}


# ------------------------------------------------------------------ stocare
LISTING_COLS = ["url", "title", "short_description", "created_at", "make", "model", "version",
                "year", "mileage_km", "fuel", "engine_cc", "power_hp", "vat", "city", "region",
                "seller_id", "seller_name", "seller_type"]


def store(db, rows, page, search_url):
    t = now()
    for rank, r in enumerate(rows, 1):
        cols = ", ".join(LISTING_COLS)
        qs = ", ".join("?" * len(LISTING_COLS))
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
    """Construieste URL-ul de paginare pentru auto.ro:
    Pagina 1: https://www.auto.ro/masini-second-hand/
    Pagina N: https://www.auto.ro/masini-second-hand/pagina-N.html
    """
    clean_base = re.sub(r"/pagina-\d+\.html$", "", base.rstrip("/"))
    if page <= 1:
        return clean_base + "/"
    return f"{clean_base}/pagina-{page}.html"


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


def fetch(session, url, post_data=None):
    if post_data:
        r = session.post(url, data=post_data, timeout=30)
    else:
        r = session.get(url, timeout=30)
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
    ap.add_argument("--url", default="https://www.auto.ro/masini-second-hand/",
                    help="URL de categorie (default: https://www.auto.ro/masini-second-hand/)")
    ap.add_argument("--per-page", type=int, choices=[20, 50, 100], default=100,
                    help="anunturi pe pagina: 20, 50 sau 100 (default 100)")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="nr. maxim de pagini (daca nu e dat, se calculeaza din --max-cars sau default 3)")
    ap.add_argument("--max-cars", "-n", type=int, default=None,
                    help="nr. maxim de autovehicule de colectat (ex. 25, 200, 1000)")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--delay", type=float, nargs=2, default=(3.0, 6.0), metavar=("MIN", "MAX"),
                    help="pauza aleatorie intre cereri, secunde (default 3 6)")
    ap.add_argument("--db", default="cars.db")
    ap.add_argument("--jsonl", help="optional: scrie si un fisier JSONL cu anunturile")
    ap.add_argument("--save-raw", action="store_true", help="salveaza HTML-ul brut in data/raw/")
    ap.add_argument("--html-file", help="parseaza un singur fisier HTML salvat local")
    ap.add_argument("--html-dir", help="parseaza toate fisierele *.html dintr-un director")
    args = ap.parse_args()

    # Calcul automat pentru max_pages daca nu a fost specificat explicit
    if args.max_pages is None:
        if args.max_cars:
            args.max_pages = (args.max_cars // args.per_page) + 2
        else:
            args.max_pages = 3

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
        db.close()
        if jsonl:
            jsonl.close()
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
            # Trimitem POST cu perPage=100 (echivalent cu selectarea 100 in form-ul fPaginator2)
            html = fetch(s, url, post_data={"perPage": str(args.per_page)})
        except PermissionError as e:
            print("\n!!", e)
            break
        except requests.RequestException as e:
            print("eroare retea:", e)
            break

        if args.save_raw:
            p = Path("data/raw") / SOURCE / f"{datetime.now():%Y-%m-%d}" / f"masini_sh_p{page}.html"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(html, encoding="utf-8")

        rem = (args.max_cars - seen_total) if args.max_cars else None
        rows, _ = handle(html, page, url, rem)
        if not rows:
            print(f"pagina {page}: niciun anunt gasit, ma opresc.")
            break

        seen_total += len(rows)
        print(f"pagina {page}: {len(rows)} anunturi salvate (total adunate: {seen_total})")

        if args.max_cars and seen_total >= args.max_cars:
            print(f"Limita de {args.max_cars} autovehicule a fost atinsa. Ma opresc.")
            break

        time.sleep(random.uniform(lo, hi))

    db.close()
    if jsonl:
        jsonl.close()


if __name__ == "__main__":
    main()