# Cap 1. Formularea problemei și cerințe

## Beneficiari

| Tip de Beneficiar                    | Use Case                                                                                                                                                                    |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cumpărători de autoturisme         | Analizează evoluția prețurilor în timp pentru a stabili prețul corect pe piață asociat specificațiilor unui anumit model de mașină, în vederea achiziției sale. |
| Dealeri auto și persoane fizice     | Estimează și adaptează prețul propriilor autovehicule supuse la vânzare în funcție de tendințele curente și concurența de pe piață.                             |
| Analiști și pasionați de economie | Urmăresc evoluția temporală a pieței pentru a identifica comportamente economice, cum ar fi ratele de depreciere ale modelelor sau fluctuațiile generale de preț.     |

## Obiective

Sistemul urmărește îndeplinirea următoarelor obiective:

- Crearea unei platforme care colectează și normalizează informații despre anunțurile de pe piața auto din România **(Autovit, Auto.ro)**, pentru a permite o analiză centralizată a pieței.
- Păstrarea unui istoric al anunțurilor pe parcursul timpului pentru a surprinde fluctuațiile de preț și dinamica ofertelor.
- Oferirea unei modalități obiective de a prezice prețul unei mașini pe baza specificațiilor sale tehnice și a contextului actual al pieței.
- Punerea la dispoziția utilizatorilor a unui panou interactiv care transpune datele brute în informații ușor de înțeles privind deprecierea, cererea și inflația modelelor auto.

## Limite

Sistemul are urmatoarele limite:

- Sistemul monitorizează și analizează exclusiv **piața auto din România**, deci **NU** se vor prelua date de pe platforme internaționale.
- Aplicația are un rol strict de **observare și analiză**. **NU** permite tranzacții financiare, rezervări de autovehicule și **NU** oferă un canal de comunicare directă între cumpărător și proprietarul anunțului.
- Autenticitatea anunțurilor nu poate fi validată în totalitate. Sistemul depinde de acuratețea datelor furnizate de site-urile sursă și analizează informațiile exact așa cum au fost expuse public.
- **VIN-ul NU este disponibil** în datele extrase de pe platforme. Prin urmare, sistemul identifică anunțurile însă **NU** deduplică în mod sigur aceeași mașină publicată pe site-uri diferite.
- Limitările de trafic impuse de site-urile sursă împiedică actualizările în timp real ale datelor. Acestea vor fi realizate periodic la un interval de tip prestablit.

## Cerinte Verificabile

- Când scraperul identifică din nou un anunț cu același ID pe aceeași platformă, actualizează datele curente ale anunțului și adaugă o observație în `snapshots`, fără să suprascrie observațiile anterioare. Identificarea se face prin perechea `(source, listing_id)`. Aceeași mașină publicată pe platforme diferite poate apărea ca două anunțuri distincte.
- Când utilizatorul solicită o predicție de preț prin dashboard, dacă nu furnizează atributele obligatorii, sistemul respinge cererea și afișează un mesaj care indică exact câmpul lipsă.
- Când o platformă sursă blochează accesul (eroare timeout sau rate-limit), sistemul întrerupe extragerea doar pentru acea sursă și salvează datele parțiale obținute, fără a bloca funcționarea dashboard-ului pentru utilizatori.

## Ipoteze

- ID-ul unui anunț furnizat de platformă rămâne constant pe durata valabilității sale în cadrul acelei platforme.
- Modificările de preț operate de vânzător nu generează un URL nou pe platforma sursă.

## Intrebari Deschise

- Dacă dorim să deduplicăm aceeași mașină publicată pe platforme diferite, ce metodă de potrivire aproximativă folosim pe baza atributelor vizibile? VIN-ul nu este disponibil, iar potrivirea poate produce rezultate incerte.
- Ce strategie aplicăm atunci când o platformă își schimbă brusc structura codului HTML?
- Cum identificam daca un anunt este postat cu un pret cu mult sub piata doar pentru a aparea primul in pagina ?

## Exemple de Acceptare

Exemplu de acceptare:
Stare inițială: anunțul cu ID-ul A1 de pe Autovit are o observație de 10.000 EUR.
Acțiune: scraper-ul colectează din nou anunțul A1 și găsește prețul de 9.500 EUR.
Rezultat observabil: anunțul rămâne identificat prin `(autovit, A1)`, iar `snapshots` conține observațiile ambelor prețuri cu momentele colectării aferente.

Efectul schimbării unei cerințe:
Dacă beneficiarul cere notificări în timp real când apare un anunț nou în loc de actualizări periodice, arhitectura curentă periodica devine invalidă. Sistemul ar avea nevoie de monitorizare continuă a stream-urilor web și de o infrastructură complexă de proxy-uri pentru a evita blocarea imediată a IP-urilor de către platformele sursă.

# Cap 2. Modelarea Domeniului

## 2. Modelarea domeniului

* **Vehicul:** Entitatea fizică, distinctă conceptual de anunț. VIN-ul nu este expus în datele colectate, iar baza de date nu are o tabelă sau o cheie care să identifice sigur vehicule fizice. Nu se presupune că anunțurile de pe platforme diferite reprezintă aceeași mașină.
* **Anunț (Listing):** Înregistrarea unui anunț pe o platformă. În baza de date este identificat prin cheia compusă `(source, listing_id)`, unde `listing_id` este ID-ul furnizat de platforma respectivă.
* **Sursă de date:** Platforma de pe care se colectează anunțul, de exemplu **Autovit sau Auto.ro**.
* **Snapshot:** Observația unui anunț la o colectare, care păstrează prețul și datele de context observate atunci.

**Reguli coerente cu problema**

1. Identitatea stabilă gestionată de sistem este cea a anunțului în cadrul unei surse: `(source, listing_id)`.
2. Colectările adaugă observații în `snapshots`; istoricul existent nu este înlocuit când se colectează din nou anunțul.
3. Nu se poate concluziona din datele actuale că două anunțuri de pe surse diferite aparțin aceluiași vehicul fizic.

TODO: Trebuie adaugate datele in continuare conform cu modelul de date si cerintele proiectului