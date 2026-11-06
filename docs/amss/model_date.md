# Modelul de date

Documentul descrie schema verificata in `data/autovit/cars_autovit.db`. Baza de date Auto.ro (`data/autoro/cars_autoro.db`) are aceleasi tabele, coloane, tipuri, chei si indexuri.

# Istoric

| Data Extragerii | Platformă / Sursă | Tabel (`listings`) | Tabel (`snapshots`) |
| :--- | :--- | :--- | :--- |
| **06.11.2026** | Autovit.ro | 44.947 | 57.920 | 
| **06.11.2026** | Auto.ro | 15.599 | 15.600 |

## 1. Tabela `listings`

Pastreaza datele curente si metadatele fiecarui anunt. Cheia primara este compusa din `(source, listing_id)`, deoarece ID-ul este furnizat de platforma si poate sa nu fie unic intre surse.

| Coloana               | Tip SQLite  | Constrangeri               | Descriere                                               |
| --------------------- | ----------- | -------------------------- | ------------------------------------------------------- |
| `listing_id`        | `TEXT`    | `NOT NULL`, parte din PK | ID-ul anuntului pe platforma sursa.                     |
| `source`            | `TEXT`    | `NOT NULL`, parte din PK | Platforma sursa, de exemplu `autovit` sau `autoro`. |
| `url`               | `TEXT`    | `NULLABLE`               | URL-ul paginii anuntului.                               |
| `title`             | `TEXT`    | `NULLABLE`               | Titlul anuntului.                                       |
| `short_description` | `TEXT`    | `NULLABLE`               | Descrierea scurta extrasa din anunt.                    |
| `created_at`        | `TEXT`    | `NULLABLE`               | Data publicarii furnizata de sursa.                     |
| `make`              | `TEXT`    | `NULLABLE`               | Marca autovehiculului.                                  |
| `model`             | `TEXT`    | `NULLABLE`               | Modelul autovehiculului.                                |
| `version`           | `TEXT`    | `NULLABLE`               | Versiunea, motorizarea sau echiparea.                   |
| `year`              | `INTEGER` | `NULLABLE`               | Anul autovehiculului.                                   |
| `mileage_km`        | `INTEGER` | `NULLABLE`               | Kilometrajul in kilometri.                              |
| `fuel`              | `TEXT`    | `NULLABLE`               | Tipul de combustibil normalizat de scraper.             |
| `engine_cc`         | `INTEGER` | `NULLABLE`               | Capacitatea cilindrica, in cm³.                        |
| `power_hp`          | `INTEGER` | `NULLABLE`               | Puterea, in cai putere.                                 |
| `vat`               | `TEXT`    | `NULLABLE`               | Informatii despre regimul TVA, daca sunt furnizate.     |
| `city`              | `TEXT`    | `NULLABLE`               | Orasul/localitatea anuntului.                           |
| `region`            | `TEXT`    | `NULLABLE`               | Judetul/regiunea anuntului.                             |
| `seller_id`         | `TEXT`    | `NULLABLE`               | ID-ul vanzatorului pe platforma, daca este disponibil.  |
| `seller_name`       | `TEXT`    | `NULLABLE`               | Numele vanzatorului, daca este disponibil.              |
| `seller_type`       | `TEXT`    | `NULLABLE`               | Categoria vanzatorului, daca este disponibila.          |
| `first_seen`        | `TEXT`    | `NOT NULL`               | Momentul primei colectari de catre scraper.             |
| `last_seen`         | `TEXT`    | `NOT NULL`               | Momentul celei mai recente colectari a anuntului.       |

`listing_id` este un identificator al anuntului, nu al masinii fizice. VIN-ul nu este prezent in schema si nu este expus in datele colectate.

## 2. Tabela `snapshots`

Pastreaza observatiile anunturilor la colectari succesive, inclusiv pretul si contextul extragerii. O noua colectare adauga un rand; pot exista mai multe observatii cu acelasi pret.

| Coloana              | Tip SQLite  | Constrangeri                      | Descriere                                                                      |
| -------------------- | ----------- | --------------------------------- | ------------------------------------------------------------------------------ |
| `id`               | `INTEGER` | PK, `AUTOINCREMENT`             | Identificatorul numeric al observatiei.                                        |
| `source`           | `TEXT`    | `NOT NULL`, parte din FK compus | Sursa anuntului.                                                               |
| `listing_id`       | `TEXT`    | `NOT NULL`, parte din FK compus | ID-ul anuntului.                                                               |
| `scraped_at`       | `TEXT`    | `NOT NULL`                      | Momentul colectarii observatiei.                                               |
| `price`            | `REAL`    | `NULLABLE`                      | Pretul numeric afisat.                                                         |
| `currency`         | `TEXT`    | `NULLABLE`                      | Moneda pretului.                                                               |
| `price_is_gross`   | `INTEGER` | `NULLABLE`                      | Indicator pentru pret brut/TVA inclus, daca sursa il furnizeaza (`1`/`0`). |
| `price_evaluation` | `TEXT`    | `NULLABLE`                      | Evaluarea pretului afisata de platforma, daca exista.                          |
| `price_drop_pct`   | `REAL`    | `NULLABLE`                      | Procentul de reducere furnizat de platforma, daca exista.                      |
| `is_promoted`      | `INTEGER` | `NULLABLE`                      | Indicator pentru promovarea anuntului, daca este disponibil (`1`/`0`).     |
| `bump_date`        | `TEXT`    | `NULLABLE`                      | Data reactualizarii anuntului, daca este furnizata.                            |
| `page`             | `INTEGER` | `NULLABLE`                      | Pagina rezultatelor din care a fost colectat anuntul.                          |
| `rank_on_page`     | `INTEGER` | `NULLABLE`                      | Pozitia anuntului in rezultatele colectate.                                    |
| `search_url`       | `TEXT`    | `NULLABLE`                      | URL-ul paginii de cautare folosite la colectare.                               |

Cheia externa este compusa: `(source, listing_id)` refera cheia primara cu aceeasi pereche din `listings`.

## 3. Indexuri si relatii

| Index                | Tabela        | Coloane                              | Scop                                                         |
| -------------------- | ------------- | ------------------------------------ | ------------------------------------------------------------ |
| `idx_l_make_model` | `listings`  | `(make, model, year)`              | Cautari dupa marca, model si an.                             |
| `idx_s_listing`    | `snapshots` | `(source, listing_id, scraped_at)` | Gasirea istoricului unei inregistrari in ordinea colectarii. |

Relatia dintre `listings` si `snapshots` este de tip ONE-TO-MANY : un anunt poate avea mai multe observatii in timp, iar fiecare observatie apartine perechii `(source, listing_id)` a unui anunt.

## 4. Limitele modelului

Nu exista in bazele curente o tabela separata pentru vehicule fizice. O eventuala deduplicare intre surse pe baza acestor atribute ar fi aproximativa si nu este implementata de schema descrisa aici.
