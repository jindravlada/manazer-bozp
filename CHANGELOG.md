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

# Verze 4.1.0

Datum vydání:

9. 10. 2026

Nové funkce

- Modul Testy: evidence zkoušených a oprávnění ke zkoušení, banka písemných otázek, ústní okruhy, definice testů, příprava zkoušky s neměnným zadáním, elektronické i papírové provedení, vyhodnocení, protokol, příloha podepsaného protokolu, sledování platnosti, souhrn na nástěnce a tisk studijních otázek se správnými odpověďmi.
- Přehledy vypořádání zjištění z auditů, včetně historie stavů, uložených snímků a exportu do ODT.
- Přehled vypořádání zjištění z dokončených prověrek.
- Tisk změn od posledního auditu v podrobné zprávě i v protokolu.

Vylepšení

- Horní lišta Auditů je dvouřádková.
- Přehled vypořádání má srozumitelnější souhrn, novější přehled je první a neobsahuje kumulativní statistiky.
- Uložení auditu a prověrky se potvrdí.
- Přehled auditů má upravené sloupce a krátké popisky. Oba tiskové dokumenty auditu ponechávají název programu. V dialogu úkolu je pracoviště za odpovědným.
- Elektronický test, ústní část, tištěný test a protokol jsou čitelnější. Evidence pohlaví v protokolu není.

Opravy

- Zapracování návrhu katalogu rizik už neselže, když se opatření přiřazuje k hodnocení.
- Uložení zjištění a úkolů auditu a prověrky proběhne celé, nebo se neuloží vůbec.
- Opravený tisk papírového testu, zadání papírových odpovědí a zobrazení vyhodnocení.
- U zkoušek je chráněný časový limit, ukládání protokolů, velikost PDF, cesty a integrita obrázků a vyhodnocení se ukládá v jedné transakci. Zkoušku lze zablokovat a technicky ukončit.

---

# Verze 4.0.10

Datum vydání:

4. 10. 2026

Audity: při plánování programu se auditované procesy střídají mezi provozy, aby se stejná skladba neopakovala na všech pracovištích stejně. Kontrola změn právních předpisů běží spolehlivěji na pozadí a při chybě zapíše podrobnosti do diagnostického logu. U zaměstnavatele se Hlavní CZ-NACE zobrazuje jako kód a název činnosti. Má-li subjekt v ARES více činností, hlavní se vybere ručně a první položka seznamu se už nepovažuje za převažující. Uložení údajů zaměstnavatele se potvrdí. Při odchodu s neuloženými změnami se aplikace zeptá, zda je uložit.

---

# Verze 4.0.9

Datum vydání:

2. 10. 2026

Audity: sjednocení názvu protokolu a úprava tisku auditních tvrzení. Výsledný dokument interního auditu je terminologicky sjednocen na „Protokol z interního auditu“. Označení „Protokol z interního auditu“ je použito v hlavním nadpisu i v zápatí dokumentu. V tisku auditních tvrzení byl mírně rozšířen sloupec „Způsob ověření“, aby se hodnota „Dokumentace“ zobrazovala na jednom řádku.

---

# Verze 4.0.8

Datum vydání:

1. 10. 2026

Audity: podpora vícedenních auditů a sjednocení pořadí auditních tvrzení. Do Spisu auditu bylo doplněno nepovinné Předpokládané datum ukončení. U zahájeného vícedenního auditu používá Agenda toto datum pro hlídání termínu; pokud není vyplněné, zachovává se dosavadní chování podle Data zahájení. Význam Plánovaného data, Data zahájení a skutečného dokončení auditu se nemění. Tisk Auditních tvrzení u připraveného auditu používá stejné pořadí řídicích procesů, oblastí a tvrzení jako samotné provádění auditu. Mimořádná ověření zůstávají při tisku za běžnými tvrzeními.

---

# Verze 4.0.7

Datum vydání:

25. 9. 2026

Audity: dokončení nového životního cyklu plánování, přípravy a provádění auditů. Ručně založený audit používá vědomý postup Založit → Připravit → Zahájit. U ručního auditu lze před přípravou určit rozsah auditu výběrem řídicích procesů; bez zvoleného rozsahu jej nelze připravit. Program auditů považuje návštěvu za splněnou až po skutečném dokončení navázaného auditu. Samotné založení nebo probíhající audit se jako dokončený nezapočítává. Dokončení auditu, návštěvy programu, jejích procesů a mimořádných ověření probíhá atomicky. Při chybě se přechod do stavu Dokončeno neuloží částečně.

---

# Verze 4.0.6

Datum vydání:

25. 9. 2026

Audity: oddělení plánování, přípravy a skutečného zahájení auditu. Plánovaný audit lze založit bez data zahájení, snapshot vzniká až vědomou funkcí Připravit audit a skutečné provádění vyžaduje Datum zahájení.

---

# Verze 4.0.5

Datum vydání:

24. 9. 2026

RPP a rizika: Open Data import, nevyřešené právní odkazy AI a úprava výběru Platí pro

---

# Verze 4.0.4

Datum vydání:

22. 9. 2026

Rizika: oddělení lokálních úprav provozu a bezpečná aktualizace z Masteru

---

# Verze 4.0.3

Datum vydání:

22. 9. 2026

Rizika: relevance zásad bezpečné práce podle ohrožených skupin

---

# Verze 4.0.2

Datum vydání:

21. 9. 2026

Agenda: ukončené úkoly ve filtrech Splněné a Vše

---

# Verze 4.0.1

Datum vydání:

15. 9. 2026

Zvýšení verze aplikace. Program, dialog O programu a balicí metadata se identifikují jako Manažer BOZP 4.0.1.

---

# Verze 4.0.0

Datum vydání:

14. 9. 2026

Před vydáním 4.0.0 prošel Manažer BOZP systematickým interním bezpečnostním review produkčního kódu. Nalezené potvrzené problémy byly opraveny a pokryty regresními testy. Nešlo o nezávislý profesionální penetrační test ani bezpečnostní certifikaci.

## Bezpečnost a ochrana dat

- omezení cest souboru znalosti, příloh a referenčních fotografií na určená úložiště
- bezpečnější práce s importy, přílohami a ODT, včetně odstranění aktivního obsahu z exportních šablon
- zpevnění HTTPS komunikace ARES a e-Sbírky (pouze HTTPS, allowlist hostů, ruční redirecty, limit velikosti odpovědi)
- ochrana lokálních dat a dočasných souborů
- atomická migrace unikátního omezení ročních zpráv auditů
- sjednocení automatických safety záloh na formát mbbackup
- připnutí přímých runtime závislostí, PyInstalleru a linuxdeploy

## Další změny od 3.4.5

- evidence změn právních požadavků a práce s novelizací bez přepisu používaného znění
- záložka Po ukončení DPN a související povinnosti v Knize úrazů
- nesblokování okna při tvorbě a obnově zálohy
- export plánu interních auditů do ODT a další úpravy přehledů auditů a prověrek

---

# Verze 3.4.5

Datum vydání:

27. 8. 2026

Zvýšení verze aplikace. Program, dialog O programu a balicí metadata se identifikují jako Manažer BOZP 3.4.5.

---

# Verze 3.4.0

Datum vydání:

7. 8. 2026

Významné rozšíření práce s agendou, událostmi a šablonami, sjednocení UX a úpravy Knihy úrazů.

---

## Hlavní novinky

### Agenda

- společný přehled úkolů a událostí
- sjednocený vstup k zakládání a úpravám
- zjednodušená práce se šablonami událostí (Nová událost ze šablony, správa šablon bez zavírání výběru)

### Události

- ergonomie editoru a výběru osob
- priority událostí
- našeptávání místa z pracovišť
- externí účastníci
- kontrola minulého termínu a časových konfliktů

### Šablony událostí

- zakládání události ze šablony
- samostatná správa šablon
- sjednocení lišty editoru šablon
- automatická synchronizace dialogu výběru při změnách ve správě

### Kalendář

- zobrazení událostí v kalendáři
- delší a stabilní tooltipy

### Kniha úrazů

- přesun akcí ohlášení do přehledu úrazů
- Ohláška odborové organizaci
- sjednocení aktivace tlačítek

### UX standardy

- jednotné názvosloví a standardní komponenty
- sjednocení akcí Otevřít / Upravit
- jednotná horní lišta modulů
- sjednocení aktivace tlačítek napříč moduly
- výraznější zvýraznění aktivního modulu v levém menu

### Podobnosti a správa dat

- analýza podobností mezi oblastmi
- správa zkontrolovaných dvojic a možnost jejich vrácení do analýzy

---

## Podporované platformy

- Linux
- Windows

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
