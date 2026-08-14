# Retrospektiva modulu

Šablona pro krátkou retrospektivu po dokončení významnějšího modulu nebo většího UX sprintu.

Cíl: zachytit zkušenosti z reálného používání a případně aktualizovat závazné dokumenty.

---

## Záznam

**Modul:**  
**Datum:**  

### Co se povedlo



### Co už bychom dnes udělali jinak



### Co bylo zbytečně složité



### Jaké nové pravidlo z toho vzniklo



---

## Aktualizace dokumentů

Patří některé zjištění do:

- [ ] Vývojových standardů (`.cursor/rules/vyvojove-standardy.mdc`)
- [ ] Architektury modulů (`ARCHITEKTURA_MODULU.md`)
- [ ] UI komponent (`UI_KOMPONENTY.md`)
- [ ] UX názvosloví (`UX_NAZVOSLOVI.md`)
- [ ] UX standardů (`UX_STANDARD_001.md`)

Pokud ano, aktualizovat příslušný dokument ve stejném sprintu nebo ihned poté.

---

## Historie retrospektiv

Nové záznamy přidávat níže (nejnovější nahoře).

### 2026-08-14 – AUDIT-EXTRAORDINARY-3

**Co se povedlo:** Typ ověření Dokumentace/Terén u mimořádných otázek se znovupoužil ze stávajících konstant; snapshot zmrazuje typ; výstupy (checklist, protokol, podrobná, roční, závěrečná) čtou jen snapshot a legacy bez typu nerozbíjí staré audity.

**Co už bychom dnes udělali jinak:** Povinný Typ ověření zavést už v EXTRAORDINARY-1, aby nevznikaly pending záznamy bez typu.

**Co bylo zbytečně složité:** Oddělit umístění v AuditDialogu (vše v „Mimořádné ověření“) od zařazení do terénního checklistu podle zmrazeného typu.

**Nové pravidlo:** Pending mimořádná otázka bez platného typu nesmí vstoupit do nového auditu (rollback + konkrétní zpráva); staré snapshoty se nedoplňují.

**Aktualizované dokumenty:** —

### 2026-08-06 – UX STANDARD č. 001 / ACCIDENT-UX-3

**Co se povedlo:** V Knize úrazů sjednocena aktivace lišty podle výběru; z chování vznikl závazný UX STANDARD č. 001 pro všechny seznamové moduly.

**Co už bychom dnes udělali jinak:** Standard zavést dříve – dříve než první modulové UX sprinty.

**Co bylo zbytečně složité:** Různé moduly řešily aktivaci tlačítek ad hoc (někde jen část akcí, jinde hlášky „Vyberte…“).

**Nové pravidlo:** Aktivace akcí podle výběru záznamu (`UX_STANDARD_001.md`); bez hlášek „Vyberte záznam.“, pokud stačí deaktivovat tlačítko; zavádění po modulech.

**Aktualizované dokumenty:** `UX_STANDARD_001.md`, `UI_KOMPONENTY.md`, `ARCHITEKTURA_MODULU.md`, `.cursor/rules/*`.

<!--
### YYYY-MM-DD – Název modulu / sprintu

**Co se povedlo:** …

**Co už bychom dnes udělali jinak:** …

**Co bylo zbytečně složité:** …

**Nové pravidlo:** …

**Aktualizované dokumenty:** …
-->
