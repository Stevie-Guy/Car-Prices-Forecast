# Cap 1. Formularea problemei și cerințe

## Beneficiari

| Tip de Beneficiar | Use Case |
|-------------------|----------|
| Cumpărători de autoturisme | Analizează evoluția prețurilor în timp pentru a stabili prețul corect pe piață asociat specificațiilor unui anumit model de mașină, în vederea achiziției. |
| Dealeri auto și persoane fizice| Estimează și adaptează prețul propriilor autovehicule supuse la vânzare în funcție de tendințele curente și concurența de pe piață. |
| Analiști și pasionați de economie | Urmăresc evoluția temporală a pieței pentru a identifica comportamente economice, cum ar fi ratele de depreciere ale modelelor sau fluctuațiile generale de preț (ex: corelația cu inflația). |

## Obiective

Sistemul urmărește îndeplinirea următoarelor obiective:

- Crearea unei platforme care reunește informații despre anunțurile de pe piața auto din România (ex: Autovit, Auto.ro, Țiriac Auto) pentru a permite o analiză centralizată a pieței.

- Păstrarea unui istoric al anunțurilor pe parcursul timpului pentru a surprinde fluctuațiile de preț și dinamica ofertelor.

- Oferirea unei modalități obiective de a prezice prețul unei mașini pe baza specificațiilor sale tehnice și a contextului actual al pieței.

- Punerea la dispoziția utilizatorilor a unui panou interactiv care transpune datele brute în informații ușor de înțeles privind deprecierea, cererea și inflația modelelor auto.

## Limite

Sistemul are urmatoarele limite:

- Sistemul monitorizează și analizează exclusiv piața auto din România, deci nu se vor prelua date de pe platforme internaționale.

- Aplicația are un rol strict de observare și analiză (read-only); Nu facilitează tranzacții financiare, rezervări de autovehicule și nu oferă un canal de comunicare directă între cumpărător și proprietarul anunțului.

- Autenticitatea anunțurilor nu este validată fizic; sistemul depinde de acuratețea datelor furnizate de site-urile sursă și analizează informațiile exact așa cum au fost expuse public.

- Limitarile de trafic impuse de site-urile sursa impiedica actualizarile in timp real ale datelor. Acestea vor fi realizate periodic la un interval de tip prestablit.

## Cerinte Verificabile

- Când scraperul identifică un anunț cu un ID / URL deja existent în sistem, dar care are un preț diferit față de ultima extragere, sistemul nu suprascrie valoarea, ci adaugă o nouă înregistrare în istoricul de preț al acelui vehicul, marcată cu data curentă. 

- Când utilizatorul solicită o predicție de preț prin dashboard, dacă nu furnizează atributele obligatorii, sistemul respinge cererea, nu apelează modelul ML și afișează un mesaj care indică exact câmpul lipsă.

- Când o platformă sursă blochează accesul (eroare timeout sau rate-limit), sistemul întrerupe extragerea doar pentru acea sursă și salvează datele parțiale obținute, fără a bloca funcționarea dashboard-ului pentru utilizatori.

## Ipoteze 

- ID-ul unui anunț furnizat de platforma sursă rămâne constant pe toată durata valabilității acelui anunț.

- Modificările de preț operate de vânzător nu generează un URL nou pe platforma sursă.

## Intrebari Deschise

- Cum gestionăm situația în care exact aceeași mașină este postată de același proprietar pe platforme diferite (ex: Autovit și Auto.ro)? Le unificăm sub același vehicul sau le tratăm ca entități separate?

- Ce strategie aplicăm atunci când o platformă își schimbă brusc structura codului HTML?

## Exemple de Acceptare

Exemplu de acceptare: 
Stare inițială: vehiculul V1 are un preț înregistrat de 10.000 EUR. 
Acțiune: scraper-ul rulează și detectează pentru acelasi ID prețul de 9.500 EUR. 
Rezultat observabil: sistemul păstrează un singur vehicul V1, iar istoricul său conține acum ambele prețuri cu datele aferente.

Efectul schimbării unei cerințe: 
Dacă beneficiarul cere notificări în timp real când apare un anunț nou în loc de actualizări periodice, arhitectura curentă periodica devine invalidă. Sistemul ar avea nevoie de monitorizare continuă a stream-urilor web și de o infrastructură complexă de proxy-uri pentru a evita blocarea imediată a IP-urilor de către platformele sursă.