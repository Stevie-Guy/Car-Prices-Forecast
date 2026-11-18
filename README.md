# Proiect: Colectare si Analiza Anunturi Auto (Romania)

Echipa este formata din: Bogdan, Claudiu, Mario si Stefan.

Acest repository contine scripturile de web scraping pentru extragerea automata a anunturilor auto de pe **Autovit.ro** (`src/scraper_autovit.py`) si **Auto.ro** (`src/scraper_autoro.py`), plus un utilitar pentru unirea bazelor de date (`src/database_merger.py`). Scopul final este modelarea pretului unei masini in functie de varsta, rulaj si specificatii (detalii in [docs/data-proposal.md](docs/data-proposal.md)).

## Stadiul datelor

Toate anunturile disponibile pe ambele site-uri au fost colectate (ultima colectare: 5 noiembrie 2026):

| Sursa    | Fisier                          | Anunturi (`listings`) | Inregistrari pret (`snapshots`) |
| -------- | ------------------------------- | --------------------- | ------------------------------- |
| Autovit  | `data/autovit/cars_autovit.db`  | 44.947                | 57.920                          |
| Auto.ro  | `data/autoro/cars_autoro.db`    | 15.599                | 15.600                          |

## Structura proiectului

```
data/
  autovit/cars_autovit.db   # baza de date Autovit
  autoro/cars_autoro.db     # baza de date Auto.ro
docs/
  data-proposal.md          # prezentarea dataset-ului (surse, schema, date sensibile)
src/
  scraper_autovit.py        # scraper Autovit.ro
  scraper_autoro.py         # scraper Auto.ro
  database_merger.py        # uneste mai multe fisiere .db si elimina duplicatele
```

---

## 1. Instalare

Inainte de a rula scripturile, asigurati-va ca aveti Python 3 instalat. Optional, creati un mediu virtual, apoi instalati bibliotecile necesare:

```bash
python -m venv venv
venv\Scripts\activate          # Windows (pe Linux/macOS: source venv/bin/activate)
pip install requests beautifulsoup4
```

`beautifulsoup4` este necesar doar pentru scraperul Auto.ro; cel pentru Autovit foloseste doar `requests`.

---

## 2. Schema bazei de date

Ambele scrapere folosesc aceeasi schema SQLite, astfel incat bazele pot fi unite direct:

* **`listings`** – atributele stabile ale anuntului (cheie primara `(source, listing_id)`): `url`, `title`, `short_description`, `created_at`, `make`, `model`, `version`, `year`, `mileage_km`, `fuel`, `engine_cc`, `power_hp`, `vat`, `city`, `region`, `seller_id`, `seller_name`, `seller_type`, `first_seen`, `last_seen`.
* **`snapshots`** – pretul si starea anuntului la fiecare colectare: `scraped_at`, `price`, `currency`, `price_is_gross`, `price_evaluation`, `price_drop_pct`, `is_promoted`, `bump_date`, `page`, `rank_on_page`, `search_url`.

Rularea repetata a unui scraper actualizeaza `last_seen` in `listings` si adauga un nou rand in `snapshots`, deci se poate urmari evolutia pretului in timp.

Ambele scrapere verifica `robots.txt` inainte de colectare, respecta `Crawl-delay` si se opresc automat daca detecteaza o pagina de blocare (captcha / WAF).

---

## 3. Cum se foloseste Scraperul pentru Auto.ro (`src/scraper_autoro.py`)

Scriptul extrage anunturile de pe Auto.ro si le salveaza in `data/autoro/cars_autoro.db`.

### Comenzi uzuale:

* **Colectare rapida (ex. 250 de masini, cate 100 pe pagina -> 3 cereri HTTP):**

  ```bash
  python src/scraper_autoro.py --url https://www.auto.ro/masini-second-hand --per-page 100 --max-cars 250
  ```
* **Colectare pe 10 pagini cu salvare in JSONL si fisier HTML brut (pentru debugging):**

  ```bash
  python src/scraper_autoro.py --url https://www.auto.ro/masini-second-hand --per-page 100 --max-pages 10 --save-raw --jsonl autoro_data.jsonl
  ```
* **Rulare Offline (pe o pagina HTML salvata anterior local in browser):**

  ```bash
  python src/scraper_autoro.py --html-file pagina_salvata.html --max-cars 20
  ```

### Argumente disponibile pentru `src/scraper_autoro.py`:

* `--url URL`: URL-ul de categorie de pe care se face colectarea (default: `https://www.auto.ro/masini-second-hand/`).
* `--per-page {20,50,100}`: Numarul de anunturi afisate pe o pagina (default: `100`, trimis automat prin POST).
* `--max-cars N` (sau `-n N`): Numarul maxim de autovehicule de colectat inainte de oprire.
* `--max-pages N`: Numarul maxim de pagini parcurse (daca nu este specificat, se calculeaza automat din `--max-cars`).
* `--start-page N`: Pagina de la care se incepe (default: `1`) – util pentru a relua o colectare intrerupta.
* `--delay MIN MAX`: Pauza aleatorie in secunde intre cereri (default: `3.0 6.0`).
* `--db FILE`: Fisierul SQLite pentru salvare (default: `data/autoro/cars_autoro.db`).
* `--jsonl FILE`: Optional, exporta datele colectate si intr-un fisier format JSON Lines.
* `--save-raw`: Salveaza o copie locala a codului HTML brut in folderul `data/raw/`.
* `--html-file FILE` / `--html-dir DIR`: Activeaza modul offline pe fisiere HTML locale (sare peste conexiunea de retea).

---

## 4. Cum se foloseste Scraperul pentru Autovit (`src/scraper_autovit.py`)

Autovit foloseste extragerea directa din JSON-ul incorporat in pagina (`__NEXT_DATA__`), fiind foarte rapid si stabil. Site-ul afiseaza 32 de anunturi pe pagina (valoare fixa). Filtrele existente din URL sunt pastrate la paginare.

### Comenzi uzuale:

* **Colectare a 200 de masini (7 cereri HTTP):**

  ```bash
  python src/scraper_autovit.py --url https://www.autovit.ro/autoturisme --max-cars 200
  ```
* **Colectare pe 5 pagini pentru o marca, cu export JSONL:**

  ```bash
  python src/scraper_autovit.py --url https://www.autovit.ro/autoturisme/audi --max-pages 5 --jsonl autovit_audi.jsonl
  ```
* **Rulare Offline:**

  ```bash
  python src/scraper_autovit.py --html-file autovit_p1.html
  ```

### Argumente disponibile pentru `src/scraper_autovit.py`:

* `--url URL`: URL-ul categoriei/marcii de pe Autovit (default: `https://www.autovit.ro/autoturisme`).
* `--max-cars N` (sau `-n N`): Numarul maxim de autovehicule de colectat.
* `--max-pages N`: Numarul maxim de pagini de listare (daca nu este specificat, se calculeaza din `--max-cars`, altfel `3`).
* `--start-page N`: Pagina de la care se incepe (default: `1`).
* `--delay MIN MAX`: Pauza aleatorie in secunde intre cereri (default: `3.0 6.0`) pentru a preveni blocarea (WAF).
* `--db FILE`: Baza de date SQLite tinta (default: `data/autovit/cars_autovit.db`).
* `--jsonl FILE`: Export optional in format JSONL.
* `--save-raw`: Salveaza HTML-ul brut in `data/raw/autovit/<data>/`.
* `--html-file FILE` / `--html-dir DIR`: Modul de parsare offline.

Scraperul se opreste automat cand ajunge la ultima pagina de rezultate.

---

## 5. Unirea bazelor de date (`src/database_merger.py`)

Combina oricate fisiere `.db` cu aceeasi structura intr-un singur fisier si elimina randurile duplicate. Accepta fisiere, foldere (toate `.db` din folder) sau wildcard-uri.

```bash
# Uneste cele doua surse intr-o singura baza de date
python src/database_merger.py data/autovit/cars_autovit.db data/autoro/cars_autoro.db -o data/cars_all.db

# Toate fisierele .db dintr-un folder
python src/database_merger.py data/autovit/ -o merged.db
```

* `inputs`: fisiere `.db`, foldere sau wildcard-uri (numar nelimitat).
* `-o FILE` / `--output FILE`: fisierul rezultat (default: `merged.db`).

La final, scriptul afiseaza pentru fiecare tabela cate randuri au fost citite, pastrate si cate duplicate au fost eliminate.

---

## 6. Verificarea datelor in Baza de Date

Puteti verifica rapid continutul unei baze de date din terminal:

```bash
python -c "import sqlite3; conn = sqlite3.connect('data/autovit/cars_autovit.db'); print(conn.execute('SELECT source, COUNT(*) FROM listings GROUP BY source').fetchall())"
```
