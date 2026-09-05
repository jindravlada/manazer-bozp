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

### 2026-09-05 – UX-RISK-4

**Co se povedlo:** Převzetí více zdrojů z katalogu je jedna akce, bez změny datového modelu a bez „Vybrat vše“.

**Co už bychom dnes udělali jinak:** Dialog převzetí hned stavět na zaškrtávání místo jednoduchého výběru řádku.

**Co bylo zbytečně složité:** Nic – stačilo opakovat existující převzetí jednoho zdroje.

**Jaké nové pravidlo z toho vzniklo:** Změna filtru v dialogu nesmí zahodit již provedené označení položek.

---

### 2026-09-04 – RISK-REVIEW-TERMINOLOGY-2

**Co se povedlo:** Uživatel vidí Revizi posouzení rizik místo Přezkoumání opatření, bez zásahu do dat.

**Co už bychom dnes udělali jinak:** Záložku pojmenovat podle účelu (revize posouzení) hned při vzniku.

**Co bylo zbytečně složité:** Slovo checklist vedle kontrolních otázek.

**Jaké nové pravidlo z toho vzniklo:** Revize posouzení rizik není totéž co Revize opatření. Technické názvy a historické výsledky se kvůli přejmenování nemění.

---

### 2026-09-04 – RISK-CONTROL-QUESTIONS-1

**Co se povedlo:** Uživatel vidí kontrolní otázky, interní model zůstal kompatibilní.

**Co už bychom dnes udělali jinak:** Význam `required_measures` pojmenovat jako otázky hned při vzniku checklistu.

**Co bylo zbytečně složité:** Dvojí jazyk opatření vs. otázky v AI instrukcích.

**Jaké nové pravidlo z toho vzniklo:** Technické názvy polí se kvůli kompatibilitě nemění; mění se jen uživatelský význam.

---

### 2026-09-04 – RISK-AI-MEASURE-RECOMMENDATION-EDIT-1

**Co se povedlo:** Doporučení k opatřením jde upravit před zapracováním, aniž by se otevíral editor balíku události.

**Co už bychom dnes udělali jinak:** Fronta by od začátku rozlišovala editor podle typu návrhu.

**Co bylo zbytečně složité:** Informační blokace místo editoru.

**Jaké nové pravidlo z toho vzniklo:** Identita a cíl AI návrhu se při úpravě ve frontě nemění.

---

### 2026-09-04 – RISK-AI-SINGLE-FILE-EXPORT-1

**Co se povedlo:** Katalogový export je jeden JSON, který Copilot zpracuje bez doprovodných souborů.

**Co už bychom dnes udělali jinak:** Režimy starter/review zbytečně štěpily UI; stačí univerzální instrukce podle `source_data`.

**Co bylo zbytečně složité:** ZIP s pěti soubory, z toho dva duplicitní výpisy.

**Jaké nové pravidlo z toho vzniklo:** Podklady pro AI jdou jako jeden UTF-8 JSON. Interní ID a mapa exportu zůstávají v DB.

---

### 2026-09-04 – AUDIT-PROGRAM-STATEMENTS-ODT-1

**Co se povedlo:** Tisk tvrzení vybrané návštěvy bez zahájení Auditu. Zahájený audit tiskne zmrazený snapshot.

**Co už bychom dnes udělali jinak:** Stejný režim otevření jako u plánu (dočasný ODT) hned, ne přes Uložit jako.

**Co bylo zbytečně složité:** Nic.

**Jaké nové pravidlo z toho vzniklo:** Rozsah tisku bere kanonická služba snapshotu / editoru. Otevření ani tisk nesmí založit Audit.

---

### 2026-09-04 – AUDIT-PROGRAM-ODT-DETAIL-4

**Co se povedlo:** Harmonogram ukazuje u každé návštěvy její auditované procesy. Schvalovaný plán už nemíchá souhrn za celý program.

**Co už bychom dnes udělali jinak:** Procesy dát do sloupce návštěvy hned, ne do samostatné agregace.

**Co bylo zbytečně složité:** Nic.

**Jaké nové pravidlo z toho vzniklo:** Řádek plánu popisuje jednu návštěvu. Chybějící přiřazení se píše do buňky návštěvy, ne do souhrnné sekce.

---

### 2026-09-04 – AUDIT-PROGRAM-ODT-PREVIEW-3

**Co se povedlo:** Tlačítko Exportovat plán rovnou otevře dočasný ODT. Uživatel si v LibreOffice uloží nebo vyexportuje PDF sám.

**Co už bychom dnes udělali jinak:** Náhled z dočasného souboru místo dialogu Uložit jako.

**Co bylo zbytečně složité:** Nic.

**Jaké nové pravidlo z toho vzniklo:** Dočasný ODT se po spuštění LibreOffice nesmaže. Chyba otevření musí ukázat cestu k souboru.

---

### 2026-09-04 – AUDIT-PROGRAM-ODT-EXPORT-2

**Co se povedlo:** Po úspěšném exportu plánu se ODT otevře ve výchozí aplikaci. Chyba otevření soubor nenechá zmizet.

**Co už bychom dnes udělali jinak:** Otevření hned napojit na `open_local_file`, ne přes obálku exportu.

**Co bylo zbytečně složité:** Nic.

**Jaké nové pravidlo z toho vzniklo:** Selhání otevření nesmí vypadat jako selhání exportu. Cesta k hotovému souboru musí zůstat v hlášce.

---

### 2026-09-04 – AUDIT-PROGRAM-ODT-EXPORT-1

**Co se povedlo:** Manažer auditů umí předložit představenstvu plán programu jako ODT. Harmonogram bere skutečné návštěvy, souhrn procesů skutečná přiřazení, bez zakládání Auditů.

**Co už bychom dnes udělali jinak:** Tabulky plánu rovnou jako ODF fragment se `table:header-rows`, ne jako textový seznam.

**Co bylo zbytečně složité:** Nic. Stačil stávající ODT engine a samostatná šablona.

**Jaké nové pravidlo z toho vzniklo:** Schvalovaný plán programu nesmí obsahovat provozní stav Auditů. Chybějící přiřazení procesů je upozornění, ne důvod k pádu exportu.

---

### 2026-09-04 – DATA-SUMMARY-PREIMPORT-BACKUP-2

**Co se povedlo:** Chybějící předimportní záloha po úspěšném importu RPP už nesnižuje stav dat, pokud existuje novější ověřená úplná záloha a diagnostika je v pořádku.

**Co už bychom dnes udělali jinak:** Předimportní ZIP je pojistka k jednomu importu. Po pozdější úplné záloze už její soubor nemusí existovat.

**Co bylo zbytečně složité:** Stejná hláška pro chybějící soubor u aktuální úplné zálohy i u historické předimportní zálohy.

**Jaké nové pravidlo z toho vzniklo:** Chybějící bezpečnostní záloha před úspěšným importem RPP nesmí sama způsobit „Vyžaduje pozornost“, pokud je k dispozici ověřená úplná záloha novější než import. Na kartě importu může zůstat jako historie.

---

### 2026-09-04 – DATA-SUMMARY-OPTIONAL-EXPORTS-1

**Co se povedlo:** Chybějící soubor dříve úspěšného přenosového exportu už nesnižuje celkový stav dat. Souhrn rozlišuje informační stav na kartě od skutečné chyby zálohy, obnovy, importu nebo diagnostiky.

**Co už bychom dnes udělali jinak:** Hlavní důvody nahoře držet jen u databáze a úplné zálohy. Přenosový export je volitelný výstup, soubor se po úspěchu smí přesunout.

**Co bylo zbytečně složité:** Stejná hláška „soubor nenalezen“ pro zálohu i export. U zálohy je to problém, u exportu jen informace na kartě.

**Jaké nové pravidlo z toho vzniklo:** Chybějící soubor ověřeného exportu (RPP, číselníky i jiný přenos) nesmí sám způsobit „Vyžaduje pozornost“. INCOMPLETE záloha a neověřená/poškozená záloha ano. VALID_WITH_WARNINGS se neznačí jako poškození.

---

### 2026-09-04 – FULL-BACKUP-SNAPSHOT-PHOTOS-1

**Co se povedlo:** Zmrazené fotografie metodické podpory (`snapshot_support_photos/`) jsou v defaultní úplné záloze. Neznámý datový kořen už nemůže zůstat tiše mimo balíček.

**Co už bychom dnes udělali jinak:** Seznam kořenů držet na jednom místě od začátku. Pevný include bez kontroly první úrovně workspace nový adresář přehlédne.

**Co bylo zbytečně složité:** Completeness porovnávala jen známé kořeny, takže chybějící snapshot fotky hlásila jako COMPLETE_WITH_LIMITATIONS.

**Jaké nové pravidlo z toho vzniklo:** Každý kořen první úrovně workspace je buď v úplné záloze, nebo výslovně vyloučený. Jinak INCOMPLETE a názvy v logu/metadatech. Starší balíček bez deklarace `snapshot_support_photos` se obnoví, ale neoznačí se jako bezvýhradně úplný.

---

### 2026-09-03 – AUDIT-START-DEFERRED-SAVE-1

**Co se povedlo:** Zahájení Auditu z plánované návštěvy je až při úspěšném Uložit. Otevření editoru je read-only; `started_at` zůstane prázdné, dokud ho uživatel nezadá.

**Co už bychom dnes udělali jinak:** Nevolat `create_audit_from_visit` z dvojkliku / Zahájit. Editor musí umět `audit_id=None` s pracovními daty z návštěvy.

**Co bylo zbytečně složité:** Skryté auto-doplnění dnešního data. Stejný výsledek dává povinné pole a běžná validace.

**Jaké nové pravidlo z toho vzniklo:** Nový Audit z návštěvy vzniká v jedné transakci (řádek, číslo, snapshot, vazba). Bez `started_at` se nezapisuje. Chyba kteréhokoli kroku rollbackne celek.

---

### 2026-09-03 – STATE-SUPERVISION-AUTHORITY-WEB-COVERAGE-NAMESPACE-9A4

**Co se povedlo:** Territorial coverage může omezit unmatched místní záznamy prefixem `external_key`. Ústecký rozsah tak neuvidí 42 cizích ÚP jen proto, že mají `office_kind=territorial`.

**Co už bychom dnes udělali jinak:** Hranici jmenného prostoru držet v prefixu zakončeném dvojtečkou. `khs:ustecky-kraj` není dítětem `khs:ustecky-kraj:`.

**Co bylo zbytečně složité:** Prefix slouží hlavně unmatched local a remote kontraktu. Přesná shoda klíče se dál porovnává stejně; possible_duplicate smí hledat v celém orgánu, ale nesmí nic slučovat.

**Jaké nové pravidlo z toho vzniklo:** Neprázdné `covered_external_key_prefixes` zužují missing_remote i povolené remote/expected klíče. Prázdná množina zachová dosavadní chování podle `office_kind`. Apply nesmí přijmout výběr mimo vybraný rozsah.

---

### 2026-09-03 – STATE-SUPERVISION-AUTHORITY-WEB-MULTI-COVERAGE-9A3

**Co se povedlo:** Registr webových adapterů je klíčovaný `coverage_id`. `check_authority_web("khs")` dál spouští jen `khs-regional`; další rozsah stejného orgánu půjde přidat bez změny UI.

**Co už bychom dnes udělali jinak:** ČBÚ nechat s `coverage_id=cbu-regional`, i když pokrývá territorial. Přejmenování by rozbilo 9A1.

**Co bylo zbytečně složité:** Dvě nezávislé implementace kontroly podle kódu orgánu a podle rozsahu. Stačí jedna cesta a primární coverage jako vstupní bod.

**Jaké nové pravidlo z toho vzniklo:** Každý orgán má právě jeden primární adapter. Další coverage se kontrolují jen podle `coverage_id` a nesmí se slučovat do jednoho complete výsledku.

---

### 2026-09-03 – STATE-SUPERVISION-KHS-TERRITORIAL-SEED-9A2

**Co se povedlo:** Bundled katalog KHS má 48 ověřených územních pracovišť z aktuálních oficiálních webů; čistá instalace má 5 orgánů a 94 pracovišť. Krajský webový check dál vidí jen 14 regional klíčů.

**Co už bychom dnes udělali jinak:** Čtyři kraje (Karlovarský, Královéhradecký, Jihomoravský, Olomoucký) zůstanou mimo seed, dokud nebude jednoznačný živý oficiální seznam.

**Co bylo zbytečně složité:** Ruční duplicita bez external_key se musí přesně shodovat v názvu i adrese; samotný název nestačí a klíč se k ručnímu řádku nepřipojuje.

**Jaké nové pravidlo z toho vzniklo:** Územní pracoviště KHS se přidávají jen z ověřeného oficiálního HTTPS zdroje. Sídlo kraje, druhá budova, podatelna ani ukončené pracoviště se do seedu neukládají. Více ÚP může sdílet `display_order` rodiče + 1.

---

### 2026-09-03 – STATE-SUPERVISION-AUTHORITY-WEB-COVERAGE-9A1

**Co se povedlo:** Webové adaptery teď mají explicitní rozsah (coverage_id + office_kind + přesná množina klíčů). Úplný krajský výsledek KHS/HZS/SÚIP nenabídne deaktivaci územního pracoviště.

**Co už bychom dnes udělali jinak:** ČBÚ má `coverage_id=cbu-regional`, ale seed i adapter používají `office_kind=territorial`; rozsah proto pokrývá territorial, ne regional.

**Co bylo zbytečně složité:** Neúplný nebo záměnou klíčů poškozený remote výsledek se musí odmítnout dřív, než comparator vytvoří missing_remote.

**Jaké nové pravidlo z toho vzniklo:** Úplnost adapteru se posuzuje podle přesné množiny expected_external_keys daného rozsahu, ne podle celého orgánu. Neznámý office_kind se do missing_remote nezařazuje.

---

**Co se povedlo:** Tabulky průběhu a zjištění vyplní viewport; poslední sloupec je Stretch, první Interactive se základními šířkami.

**Co už bychom dnes udělali jinak:** Profil v `configure_table_columns` založit ve stejném sprintu jako tabulku. Chybějící větev nechá `setStretchLastSection(False)` a Qt výchozí ~100 px, takže tabulka zůstane úzký blok vlevo.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Každý `configure_table_columns(profile)` musí mít větev. Bez ní se jen vypne stretch posledního sloupce.

**Aktualizované dokumenty:** —

### 2026-09-02 – STATE-SUPERVISION-EDITOR-LAYOUT-7B1

**Co se povedlo:** První záložka je dvousloupcová bez splitteru; tabulka dokladů dostala zbývající výšku (294 px při 1600×900, 474 px při 1920×1080). Starší `initial_information` se slučuje do předmětu až při skutečném uložení.

**Co už bychom dnes udělali jinak:** Nenechat tři roztažené textové skupiny na stejné záložce s tabulkou. Jejich `sizeHint` vytlačí viewport tabulky pod lištu tlačítek, takže poslední řádek nejde vybrat a scrollbar se neobjeví.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Záložka s tabulkou pod formulářem: textové bloky `stretch 0`, tabulka `stretch 1` a `SizeAdjustPolicy.AdjustIgnored`. Výšku tabulky neodvozovat od počtu řádků. Legacy sloupec se nesmí mazat migrací; sloučit ho do kanonického pole až při uložení záznamu.

**Aktualizované dokumenty:** —

### 2026-08-30 – AUDIT-METHOD-LONG-OPERATION-4B

**Co se povedlo:** Použít, Uložit a zavřít i zavírací Uložit jdou jedním persistovacím tokem mimo GUI vlákno; dávkový zápis druhů z 4A zůstal.

**Co už bychom dnes udělali jinak:** Snapshot pending změn sbírat jako čistá data od začátku, ať GUI nemusí stashovat těsně před workerem.

**Co bylo zbytečně složité:** Tři synchronní ukládací cesty se lišily epilogem i tím, co se zapisuje.

**Nové pravidlo:** Persistence editoru metodiky patří do `persist_audit_method_save`. GUI jen snapshot, blokování a epilog. Po úspěšném zápisu se selhání obnovy editoru nesmí tvářit jako neuložená data.

**Aktualizované dokumenty:** —

### 2026-08-30 – AUDIT-METHOD-SAVE-BATCH-4A

**Co se povedlo:** Změny druhů otázek se ukládají po souborech, ne po tvrzeních; 100 změn v jednom JSON je jeden zápis.

**Co už bychom dnes udělali jinak:** Pending druhy od začátku sbírat jako dávku, ne jako mapu „ulož po jednom“.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Opakovaný zápis téhož knowledge JSON v jednom uložení editoru je chyba. Nejdřív dávková persistence, teprve potom LongOperationRunner.

**Aktualizované dokumenty:** —

### 2026-08-30 – SIMILARITY-LOCATION-DISPLAY-3

**Co se povedlo:** Nad tabulkou jsou názvy porovnávaných oblastí ze snapshotu; v buňkách Umístění zůstane konec cesty (`ElideLeft`) a tooltip drží úplnou původní cestu.

**Co už bychom dnes udělali jinak:** Kořen cesty (`MODULE_NAME`) oddělit od popisku comboboxu (`domain_label`) hned při sběru kandidátů, ať heading i ořez používají stejný zdroj bez fallbacku.

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Viditelný text sloupce Umístění smí zkrátit jen přesný počáteční kořen + oddělovač. Identita otázky a `location_label` v DTO se nemění.

**Aktualizované dokumenty:** —

### 2026-08-30 – SIMILARITY-LONG-OPERATION-2

**Co se povedlo:** Analýza podobností běží přes `LongOperationRunner` a výsledky se plní `ChunkedUiPump`; dialog průběhu zůstane mezi výpočtem a tabulkou, takže 100 % výpočtu už nezamrazí GUI.

**Co už bychom dnes udělali jinak:** Follow-up režim (`close_on_success=False`) hned v jádru dialogu, ať napojení modulu nemusí bojovat se zavřením po `succeeded`.

**Co bylo zbytečně složité:** Globální `refresh_elided_cell_tooltips` po tisících řádcích. Tooltipy se teď připraví v dávce.

**Nové pravidlo:** Dlouhá operace s následným plněním tabulky je jeden dialog: worker → pumpa → `complete()`. 100 % workeru není konec zobrazení.

**Aktualizované dokumenty:** —

### 2026-08-30 – LONG-OPERATION-CORE-1

**Co se povedlo:** Společný runner/dialog/pumpa bez napojení na produkční moduly; QThread lifecycle s generací signálů a zpožděným zobrazením dialogu.

**Co už bychom dnes udělali jinak:** Testy hned stavět na vlastním čekání na signál, ne na `QSignalSpy[]` (v aktuálním PySide není indexovatelný).

**Co bylo zbytečně složité:** —

**Nové pravidlo:** Dlouhá operace: worker `QObject.moveToThread`, ne podtřída `QThread`. Dialog se `exec()` nezobrazuje kvůli zpožděnému show. Mezi UI dávkami `QTimer.singleShot`, ne `processEvents`.

**Aktualizované dokumenty:** —

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
