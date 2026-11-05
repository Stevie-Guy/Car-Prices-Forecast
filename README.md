# Proiect: Colectare si Analiza Anunturi Auto (Romania)

Echipa este formata din: Bogdan, Claudiu, Mario and Stefan.

Acest repository contine scripturile de web scraping pentru extragerea automata a anunturilor auto de pe **Autovit.ro** (`src/scraper_autovit.py`) si **Auto.ro** (`src/scraper_autoro.py`). Datele sunt structurate si salvate automat in `data/autovit/cars_autovit.db`, respectiv `data/autoro/cars_autoro.db` (aceeasi schema, unificabile cu `src/database_merger.py`).

## 1. Instalare

Inainte de a rula scripturile, asigurati-va ca aveti Python instalat si rulati comanda pentru a instala bibliotecile necesare:

```bash
pip install requests beautifulsoup4
```

---

## 2. Cum se foloseste Scraperul pentru Auto.ro (`src/scraper_autoro.py`)

Scriptul extrage anunturile de pe Auto.ro, le salveaza in tabela `listings` si inregistreaza un istoric in `snapshots` din `data/autoro/cars_autoro.db`.

### Comenzi uzuale:

* **Colectare rapida (ex. 50 de masini, cate 100 pe pagina):**

  ```bash
  python src/scraper_autoro.py --url https://www.auto.ro/masini-second-hand --per-page 100 --max-cars 50
  ```
* **Colectare completa cu salvare in JSONL si fisier HTML brut (pentru debugging):**

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
* `--db FILE`: Fisierul SQLite pentru salvare (default: `data/autoro/cars_autoro.db`).
* `--jsonl FILE`: Optional, exporta datele colectate si intr-un fisier format JSON Lines.
* `--save-raw`: Salveaza o copie locala a codului HTML brut in folderul `data/raw/`.
* `--html-file FILE` / `--html-dir DIR`: Activeaza modul offline pe fisiere HTML locale (sare peste conexiunea de retea).

---

## 3. Cum se foloseste Scraperul pentru Autovit (`src/scraper_autovit.py`)

Autovit foloseste extragerea directa din JSON-ul incorporat in pagina (`__NEXT_DATA__`), fiind foarte rapid si stabil.

### Comanda uzuala:

```bash
python src/scraper_autovit.py --url https://www.autovit.ro/autoturisme/audi --max-pages 5 --jsonl autovit_audi.jsonl
```

### Argumente disponibile pentru `src/scraper_autovit.py`:

* `--url URL`: URL-ul categoriei/marcii de pe Autovit.
* `--max-cars N` (sau `-n N`): Numarul maxim de autovehicule de colectat (32 de anunturi pe pagina).
* `--max-pages N`: Numarul maxim de pagini de listare (daca nu este specificat, se calculeaza din `--max-cars`, altfel `3`).
* `--start-page N`: Pagina de la care se incepe (default: `1`).
* `--delay MIN MAX`: Pauza aleatorie in secunde intre cereri (default: `3.0 6.0`) pentru a preveni blocarea (WAF).
* `--db FILE`: Baza de date SQLite tinta (default: `data/autovit/cars_autovit.db`).
* `--jsonl FILE`: Export optional in format JSONL.
* `--save-raw`: Salveaza HTML-ul brut.
* `--html-file` / `--html-dir`: Modul de parsare offline.

---

## 4. Verificarea datelor in Baza de Date

Puteti verifica rapid continutul bazei de date din terminalul Python:

```bash
python -c "import sqlite3; conn = sqlite3.connect('data/autovit/cars_autovit.db'); print(conn.execute('SELECT source, COUNT(*) FROM listings GROUP BY source').fetchall())"
```
