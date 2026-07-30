# Standardní architektura modulů Manažera BOZP

Tento dokument definuje společnou architekturu všech modulů Manažera BOZP.

Nové moduly se navrhují podle tohoto dokumentu.

Odchylky jsou možné pouze tehdy, pokud mají jednoznačný přínos.

Související závazné dokumenty:

- `UX_NAZVOSLOVI.md`
- `UI_KOMPONENTY.md`
- `.cursor/rules/vyvojove-standardy.mdc`

---

## 1. Struktura modulu

Každý modul by měl pokud možno obsahovat:

```text
Seznam
  ↓
Editor
  ↓
Číselníky
  ↓
Reporty / Tisk
  ↓
AI funkce (pokud dávají smysl)
  ↓
Nastavení
```

---

## 2. Seznam

Seznam je vstupní obrazovka.

Obsahuje:

- hledání
- filtry
- třídění
- počitadla
- hlavní akce
- kontextové menu

Dvojklik vždy otevírá editor.

---

## 3. Editor

Editor obsahuje pouze práci s jedním záznamem.

Nepřidává seznam dalších záznamů.

Editor se dělí na logické skupiny.

Více než čtyři logické oblasti → podzáložky.

---

## 4. Číselníky

Každý modul má vlastní správu číselníků pouze tehdy, pokud:

- číselník používá více záznamů

nebo

- je editovatelný uživatelem.

---

## 5. Vazby

Vazby jsou samostatná záložka.

Každá vazba musí umět:

- otevřít cílový objekt
- zobrazit typ vazby
- odstranit vazbu

---

## 6. Fotografie

Používat jednotný `PhotoPickerDialog`.

---

## 7. Dokumenty

Používat společnou komponentu.

Stejné ovládání ve všech modulech.

---

## 8. Kontrola spisu

Každý větší modul obsahuje **Kontrolu spisu**, která:

- najde chyby
- otevře správné místo
- umožní jejich opravu

---

## 9. Tisk

Pokud modul vytváří dokumenty, obsahuje podle potřeby:

- Náhled
- Tisk
- Export PDF
- Export ODT

---

## 10. AI

Pokud je AI použita:

- musí být vždy oddělena od ruční práce
- AI pouze navrhuje
- nikdy automaticky nemění data

---

## 11. Historie

Významné změny mají historii.

Historie je pouze pro čtení.

---

## 12. Stav objektu

Objekt má jednoznačný životní cyklus.

Například:

```text
Rozpracováno
  ↓
Uzavřeno
  ↓
Archivováno
```

Nepoužívat více různých workflow bez důvodu.

---

## 13. Mazání

Mazání významných záznamů se pokud možno nepoužívá.

Preferovat:

- Archivaci

nebo

- Deaktivaci

---

## 14. UX

Každý modul dodržuje:

- `UX_NAZVOSLOVI.md`
- `UI_KOMPONENTY.md`
- vývojové standardy

---

## 15. Architektonická konzistence

Při návrhu nového modulu je první otázka:

„Existuje již podobný modul?“

Pokud ano:

použít stejnou architekturu.

Nevytvářet nový způsob práce.

---

## 16. Rozšiřitelnost

Každý modul má být navržen tak, aby bylo možné později bez zásahu do architektury doplnit:

- fotografie
- dokumenty
- AI oponenturu
- vazby
- historii
- tisk
- reporty

---

## 17. Sdílené komponenty

Pokud se stejná funkcionalita objeví alespoň ve třech modulech:

musí být vytvořena společná komponenta.

Nevznikají tři různé implementace stejné funkce.

---

## 18. Textová podobnost (SIMILARITY-1)

Centrální služba: `core/services/text_similarity_service.py`.

Účel:

- najít možné duplicity a textově podobné záznamy,
- pouze upozornit uživatele (bez slučování, mazání a vazeb).

Normalizace před porovnáním:

- trim, malá písmena, sjednocení mezer a zalomení řádků,
- odstranění běžné koncové interpunkce,
- diakritika zůstává.

Prahy (konstanty služby):

- 100 % → Přesná shoda,
- 90–99 % → Velmi podobné,
- 80–89 % → Možná podobnost,
- pod 80 % → nezobrazovat.

Rozšíření na další typy záznamů:

1. Připravit kolekci `SimilarityCandidate(id, text)`.
2. Zavolat `find_similar_texts(...)` / `text_similarity_service.find_similar(...)`.
3. Zobrazit výsledky ve vlastním UI (jako u kontrolních otázek prověrek).

První nasazení: metodika Prověrky BOZP → kontrolní body (`Najít podobné otázky`).

Hromadná údržba kvality dat: nabídka **Nástroje → Analýza podobností...**
(`core/ui/similarity_analysis_dialog.py`, SIMILARITY-2). Porovnává párově
všechny vybrané záznamy; v tomto sprintu pouze kontrolní otázky prověrek.

---

## 19. Cíl

Každý nový modul má působit dojmem, že byl vytvořen ve stejný den stejným autorem, bez ohledu na dobu svého vzniku.
