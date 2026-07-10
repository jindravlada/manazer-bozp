# Manažer BOZP

## Motto projektu

> Manažer BOZP není pouze software pro evidenci.
>
> Jeho cílem je pomáhat odborně způsobilým osobám řídit systém bezpečnosti a ochrany zdraví při práci, prokazovat plnění právních požadavků, podporovat prevenci rizik a vytvářet podklady pro neustálé zlepšování systému řízení BOZP.
>
> Projekt vzniká jako otevřený nástroj postavený na praktických zkušenostech z výkonu prevence rizik a interních auditů.

---

# Historie verzí

---

# Verze 3.1.0

Datum vydání:

10. 7. 2026

První stabilní vydání nové generace Manažera BOZP.

---

## Hlavní novinky

### Registr právních požadavků

Nový modul pro správu právních požadavků organizace.

Obsahuje:

- evidenci právních předpisů
- evidenci jednotlivých ustanovení
- registr řídicích procesů
- správu sankcí
- kontroly změn legislativy
- evidenci zjištěných změn
- právní podklady procesů
- vazby mezi procesy
- slučování procesů
- diagnostiku registru
- import právních předpisů
- import a export registru

---

### Řídicí procesy

Nově podporují:

- hierarchii procesů
- vlastníka procesu
- vstupy procesu
- výstupy procesu
- způsob plnění
- stav plnění
- periodické ověřování
- automatický výpočet dalšího ověření
- právní podklady
- sankce
- automatické použití v auditních metodikách
- ruční vazby
- globální vyhledávání
- import a export

---

### Globální vyhledávání

Nová centrální navigace programu.

Vyhledává:

- řídicí procesy
- právní předpisy
- úkoly

Architektura je připravena pro postupné zapojení všech ostatních modulů.

---

### Správa dat

Nový servisní modul.

Obsahuje:

- Souhrn stavu dat
- Kompletní zálohu programu
- Kompletní obnovu programu
- Přenos registru právních požadavků
- Správu číselníků
- Diagnostiku

---

## Bezpečnost dat

Významně přepracován systém zálohování.

Nově:

- kompletní záloha programu
- ověřování integrity záloh
- automatická bezpečnostní záloha před obnovou
- přehled obsahu záloh
- otevření umístění záloh
- centrální Správa dat

---

## Audit systému řízení

Rozšířena integrace s řídicími procesy.

Editor metodiky nyní podporuje:

- vazby na řídicí procesy
- automatickou normalizaci starších metodik
- vyšší kompatibilitu mezi verzemi JSON

---

## Uživatelské prostředí

Vylepšeno:

- Dashboard
- Globální vyhledávání
- Přehled řídicích procesů
- Filtry
- Dialogy
- Modální okna
- Správa záloh
- Správa číselníků

---

## Architektura

Projekt byl sjednocen.

Vznikly společné služby pro:

- zálohování
- obnovu
- export
- import
- správu registru
- správu číselníků
- globální vyhledávání

Byly odstraněny duplicitní implementace.

---

## Podporované platformy

- Linux
- Windows

---

## Směr dalšího vývoje

Další rozvoj bude zaměřen zejména na:

- Registr rizik
- Prověrky BOZP
- Audity systému řízení
- Vyšetřování mimořádných událostí
- Knihu úrazů
- Rozšíření globálního vyhledávání
- Další propojení jednotlivých modulů

---

## Poděkování

Manažer BOZP vzniká jako otevřený projekt založený na dlouholetých praktických zkušenostech z oblasti BOZP, interních auditů a prevence rizik.

Na návrhu architektury, analýze problémů a tvorbě návrhů se významně podílejí moderní nástroje umělé inteligence, zejména ChatGPT společnosti OpenAI a Cursor AI.

Velké poděkování patří všem vývojářům těchto nástrojů. Jejich práce umožňuje věnovat více času řešení odborných problémů BOZP a méně času rutinním programátorským činnostem.

---

## Licence

Projekt je připravován jako open-source software pod licencí GNU GPL v3.
