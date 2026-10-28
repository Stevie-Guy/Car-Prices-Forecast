# Dataset presentation: anunturi auto din Romania

Materia: Ingineria Algoritmilor pentru AI

Echipa: Balica Bogdan, Filimon Stefan, Grigore Mario, Mironescu Claudiu

## 1. De ce acest dataset

Construim un set de anunturi de autoturisme din Romania, cu specificatii tehnice si pret cerut, ca sa modelam cum scade pretul unei masini cu varsta si rulajul. L-ar putea folosi cumparatori, vanzatori si dealeri pentru a estima un pret corect, dar si studenti care vor date tabulare reale, cu valori lipsa si zgomot.

Seturile existente de masini second-hand, de exemplu pe Kaggle, sunt din cate stim statice si vin de pe alte piete. Piata din Romania are particularitati, cum ar fi TVA-ul deductibil si numarul mare de vanzatori privati, pe care un set strain nu le reflecta.

O colectare da preturi cerute la un singur moment, nu preturi de tranzactie si nu o serie temporala. Deprecierea o estimam deci comparand masini de varste si rulaje diferite din acelasi moment. Schema pastreaza cate un rand per anunt per colectare, asa ca, daca repetam colectarea, putem urmari si evolutia preturilor in timp.

## 2. Surse

| Sursa   | Link                                   | Licenta / termeni                                                                                                                                                            | Dimensiune                                                                   |
| ------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Autovit | https://www.autovit.ro/autoturisme     | Date publice web (supuse Termenilor si Conditiilor autovit.ro; extragere exclusiv in scop academic/educational, fara republicarea continutului protejat sau a datelor brute) | ~45.000 de anunturi in total; colectat pana acum: 1.600 (cars_autovit_02.db) |
| auto.ro | https://www.auto.ro/masini-second-hand | Date publice web (supuse Termenilor si Conditiilor auto.ro; extragere exclusiv in scop academic/educational, fara republicarea continutului protejat sau a datelor brute)    | ~15.000 de anunturi in total; colectat pana acum: 1.100 (cars_autoro_01.db) |

## 3. Date sensibile

Din esantionul public scoatem `seller_name` si `seller_id`, pentru ca pot identifica persoane fizice, si pastram doar `seller_type`. VIN-ul nu se publica. Descrierile pot contine telefoane si VIN-uri, asa ca le curatam cu regex sau le excludem din esantion. Locatia ramane la nivel de oras si judet.

## 4. Schema

Doua tabele: `listings` (atribute stabile ale anuntului) si `snapshots` (pretul si starea anuntului la fiecare colectare).

| Camp                                                                              | Tip        |
| --------------------------------------------------------------------------------- | ---------- |
| `listing_id`, `source`, `url`, `title`, `created_at`                    | str        |
| `make`, `model`, `version`, `fuel`, `city`, `region`, `seller_type` | str        |
| `year`, `mileage_km`, `engine_cc`, `power_hp`                             | int        |
| `price`, `currency`                                                           | float, str |
| `price_evaluation` (evaluarea site-ului: ABOVE / IN / BELOW)                    | str        |

Exemple din esantion:

```json
{
  "listing_id": "7060893101",
  "make": "BMW",
  "model": "Seria 3",
  "version": "330i Aut. M Sport",
  "year": 2019,
  "mileage_km": 228000,
  "fuel": "petrol",
  "engine_cc": 1998,
  "power_hp": 258,
  "region": "Arges",
  "seller_type": "PrivateSeller",
  "price": 22990.0,
  "currency": "EUR",
  "price_evaluation": "IN"
}
```

```json
{
  "listing_id": "7060925772",
  "make": "Volkswagen",
  "model": "Golf",
  "version": "2.0 TDI DSG Life",
  "year": 2022,
  "mileage_km": 226539,
  "fuel": "diesel",
  "engine_cc": 1968,
  "power_hp": 116,
  "region": "Bucuresti",
  "seller_type": "ProfessionalSeller",
  "price": 13990.0,
  "currency": "EUR",
  "price_evaluation": "IN"
}
```

```json
{
  "listing_id": "7060795948",
  "make": "BMW",
  "model": "Seria 3",
  "version": "318i Aut. M Sport",
  "year": 2018,
  "mileage_km": 250163,
  "fuel": "petrol",
  "engine_cc": 1499,
  "power_hp": 136,
  "region": "Bucuresti",
  "seller_type": "PrivateSeller",
  "price": 9900.0,
  "currency": "EUR",
  "price_evaluation": "BELOW"
}
```

## 5. Cum aratam ca setul e util

Antrenam o regresie simpla (pret in functie de varsta, rulaj, marca/model, combustibil, putere) si o comparam cu un baseline naiv, pretul mediu per model. Validam pe modele sau ani lasati deoparte si raportam MAE si MAPE.

Etapele urmatoare: deduplicare, outlieri, provenienta campurilor si evaluarea formala.
