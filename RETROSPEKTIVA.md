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

### 2026-08-26 – AUDIT-SNAPSHOT-REGRESSION-CHECK-1

**Co se povedlo:** Fast-path completed backfillu znovu pozná smazaný snapshotový řádek levným SQL count/hash, bez živé metodiky a bez přepisu dat.

**Co už bychom dnes udělali jinak:** U completed migrace hned přidat levnou integritní kontrolu, nejen detekci pristine auditů.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Completed snapshot guard smí přeskočit `get_knowledge_tree`, ale ne kontrolu `snapshot_question_count` / `snapshot_integrity_hash` vůči uloženým řádkům. Poškozený snapshot se nesmí označit jako validní.

**Aktualizované dokumenty:** —

### 2026-08-26 – AUDIT-LEAD-RECOMMENDATION-1

**Co se povedlo:** Doporučení vedoucího auditora je vidět a editovatelné na záložce Závěr; novému dokončení předchází kontrola textu a podpisu výsledků.

**Co už bychom dnes udělali jinak:** Generátor doporučení hned oddělit od exportního kontextu, ať UI i tisk sdílí jednu službu.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Automatický návrh se potvrzuje vůči deterministickému podpisu výsledků. Ruční text se bez potvrzení nepřepisuje. Staré dokončené audity bez uloženého doporučení exportují fallback a neoznačují se jako neplatné.

**Aktualizované dokumenty:** —

### 2026-08-26 – AUDIT-DETAILED-INTRO-PUNCTUATION-UX1

**Co se povedlo:** V Podrobné zprávě mají mezititulky Úvodu dvojtečku; záložka Úvod a Protokol beze změny.

**Co už bychom dnes udělali jinak:** Exportní mezititulky hned odlišit od popisků QGroupBox.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Dvojtečka u mezititulků Podrobné zprávy patří do exportního textu, ne do konstant záložky Úvod.

**Aktualizované dokumenty:** —

### 2026-08-26 – AUDIT-HISTORY-AS-OF-FIX1

**Co se povedlo:** Historie provozu bere jen audity se `started_at` přísně před časovým bodem aktuálního auditu; plán 1/2028 už není „předchozí audit“ roku 2026.

**Co už bychom dnes udělali jinak:** Časový filtr historie zavést hned v AUDIT-INTRO-1, ne jen vyloučení aktuálního ID.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Historie = stejný provoz, skutečně zahájeno, `started_at` < as-of (`started_at` aktuálního, jinak plán návštěvy). Bez as-of raději prázdná historie než všechny ostatní audity.

**Aktualizované dokumenty:** —

### 2026-08-26 – PROVERKY-CONCLUSION-SAVE-FIX1

**Co se povedlo:** Refresh souhrnu na záložce Závěr už nepřepisuje doporučení vedoucího; Uložit zapíše text do DB a nechá ho v poli.

**Co už bychom dnes udělali jinak:** Stejné oddělení load/refresh jako u AuditConclusionWidget zavést hned při stay-open ukládání Prověrek.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** `refresh()` souhrnu nesmí přepisovat editovatelná pole; načtení z modelu jen v `load_*`.

**Aktualizované dokumenty:** —

### 2026-08-26 – PROVERKY-DETAILED-STRONG-SIDES-UX1

**Co se povedlo:** Prázdná sekce Silné stránky zmizí z Podrobné zprávy i Protokolu Prověrky (nadpis, pomlčka i prázdný odstavec); vyplněná sekce zůstává stejná.

**Co už bychom dnes udělali jinak:** Nadpis Silné stránky v šabloně Prověrek nechat hned v `OdtRichContent`, stejně jako u Auditů.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Podmíněná exportní sekce má nadpis v `OdtRichContent` (`omit_when_empty`), ne natvrdo v ODT šabloně.

**Aktualizované dokumenty:** —

### 2026-08-26 – PROVERKY-PLANNED-SECTION-SUMMARY-MIGRATION-1

**Co se povedlo:** Čisté plánované Prověrky s `notes_mode IS NULL` šlo převést hromadnou inventurou bez N+1, bez backfillu textů a bez zásahu do Auditů.

**Co už bychom dnes udělali jinak:** Režim poznámek u vygenerovaných plánovaných Prověrek nastavit hned při vzniku záznamu, ať pozdější datová migrace není nutná.

**Co bylo zbytečně složité:** Rozlišení technických řádků `nekontrolovano` od skutečné práce — stačilo ignorovat samotné `recorded_at` a brát jako práci až výsledek, komentář, fotografii, sdílenou zkušenost nebo jméno zapisovatele.

**Nové pravidlo:** Převod do Souhrnného sdělení jen u čistě plánovaných Prověrek; jakákoli pochybnost = legacy režim.

**Aktualizované dokumenty:** —

### 2026-08-26 – PROVERKY-SECTION-SUMMARY-UX1

**Co se povedlo:** Kontrolovaná oblast má 70/30 sloupce, Souhrnné sdělení je ukotvené (~110 px) a terénní checklist se zapíná až po uložení, pokud existují terénní body.

**Co už bychom dnes udělali jinak:** Tlačítko checklistu od začátku vázat na uloženou prověrku i na přítomnost terénních bodů, ne jen na `inspection_id`.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Referenční fotografie a Souhrnné sdělení zůstávají mimo scroll Kontrolních bodů; prázdné fotografie jsou kompaktní.

**Aktualizované dokumenty:** —

### 2026-08-26 – AUDIT-SECTION-SUMMARY-UX1

**Co se povedlo:** V Dokumentaci a Terénu je Souhrnné sdělení ukotvené nahoře (~110 px s vlastním rolováním) a karty otázek se rolují samostatně pod nadpisem Auditní tvrzení.

**Co už bychom dnes udělali jinak:** Společný scroll celé pracovní plochy od začátku rozdělit na pevnou hlavičku a seznam karet.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Souhrnné sdělení a nadpis Auditní tvrzení zůstávají viditelné; rolují se jen karty otázek.

**Aktualizované dokumenty:** —

### 2026-08-26 – AUDIT-PROVERKY-SECTION-NOTE-1

**Co se povedlo:** Nové Audity a Prověrky mají jedno Souhrnné sdělení za okruh (společné pro Dokumentaci i Terén), stávající záznamy zůstaly v legacy režimu `notes_mode IS NULL`.

**Co už bychom dnes udělali jinak:** Režim poznámek zavést jako explicitní sloupec hned při prvním modelu poznámek u otázek, ať později není nutný paralelní legacy/nový výstup.

**Co bylo zbytečně složité:** Nic zásadního — stačila aditivní tabulka sdělení a sdílený deferred buffer.

**Nové pravidlo:** Nový režim jen při vytvoření záznamu; existující Audity/Prověrky se nepřepínají ani neslučují.

**Aktualizované dokumenty:** `UX_NAZVOSLOVI.md` (Souhrnné sdělení)

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
