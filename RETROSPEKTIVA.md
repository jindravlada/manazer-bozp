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

### 2026-08-17 – METHODOLOGY-PDF-1

**Co se povedlo:** Přímý PDF přehled živé metodiky (QPdfWriter) z editorů Auditů a Prověrek, včetně pracovní neuložené podoby bez stash/zápisu.

**Co už bychom dnes udělali jinak:** Sjednotit `ensure=False` u stromu metodiky prověrek hned při AUDIT-HANG-FIX, ať export nemusí dohánět jednorázové načtení.

**Co bylo zbytečně složité:** Nic zásadního — stačil existující QPdfWriter vzor a stromy editorů.

**Nové pravidlo:** Přehled živé metodiky se tiskne přímo do PDF, ne přes ODT; export čte pracovní stav editoru a metodiku nejvýše jednou.

**Aktualizované dokumenty:** —

### 2026-08-14 – AUDIT-METHOD-SUPPORT-SNAPSHOT-1-PERF

**Co se povedlo:** Rychlý DB-only integrity guard (~60 ms) místo domnělé úplné kontroly; odstraněn opakovaný `get_knowledge_tree` ve snapshot backfill fast-path.

**Co už bychom dnes udělali jinak:** Hned při zavádění support snapshotů oddělit fast/full kontrolu a early-exit completed migrací.

**Co bylo zbytečně složité:** Skutečná ~0,3 s režie byla ve snapshot-1a inventuře, ne v method-support payload hashi.

**Nové pravidlo:** Completed migration guard smí na startu jen levné agregované SQL; JSON/SHA souborů jen při migraci, create nebo zjištěném nesouladu.

**Aktualizované dokumenty:** —

### 2026-08-14 – AUDIT-METHOD-SUPPORT-SNAPSHOT-1

**Co se povedlo:** Samostatná 1:1 tabulka `audit_question_support_snapshots` zmrazí statickou metodickou podporu bez zásahu do `snapshot_integrity_hash` a bez živého JSON fallbacku v AuditDialogu; batch načtení + jedno `get_knowledge_tree` při backfillu.

**Co už bychom dnes udělali jinak:** Support payload zahrnout už do prvního snapshotového sprintu spolu s textem otázky.

**Co bylo zbytečně složité:** Oddělení content-addressed referenčních fotografií od živých cest při zachování historie/sdílených zkušeností dynamicky.

**Nové pravidlo:** Statická metodická podpora patří do support snapshotu; dynamická historie provozu a sdílené zkušenosti zůstávají DB službami. Snapshotový audit nesmí číst živý JSON metodiky.

**Aktualizované dokumenty:** —

### 2026-08-14 – AUDIT-CONCLUSION-1

**Co se povedlo:** Povinný uživatelský závěr při business dokončení; podmíněné silné stránky v ODT bez prázdných nadpisů; validace na servisní vrstvě.

**Co už bychom dnes udělali jinak:** Oddělit generovaný `zaver_text` od uživatelského `conclusion_text` dříve, aby nevznikala kolize názvů.

**Co bylo zbytečně složité:** Statický nadpis Silné stránky v ODT vs. podmíněné zobrazení — řešeno OdtRichContent se zabudovaným nadpisem.

**Nové pravidlo:** Závěr je povinný jen při přechodu do dokončeného stavu; historické dokončené audity bez závěru se neblokují.

**Aktualizované dokumenty:** —

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
