# Manažer BOZP 3.0

Architektura projektu a pravidla pro další vývoj.

---

## Single Source of Truth

Každá informace má v systému jednoho vlastníka.

Ostatní moduly ji nekopírují, ale odkazují se na ni přes `EntityLink`.

Příklady:

- právní předpisy, požadavky a sankce vlastní **Registr právních požadavků**
- úkoly vlastní modul **Úkoly**
- audity vlastní modul **Audity**
- prověrky vlastní modul **Prověrky**
- pracovní úrazy vlastní **Kniha úrazů**

---

## EntityLink bez obchodní logiky

`EntityLink` je pouze obecná vazba mezi objekty.

Nesmí obsahovat obchodní logiku konkrétních modulů.

Například vazba na úkol neřeší:

- stav úkolu
- termín
- odpovědnou osobu

To řeší modul **Úkoly**.

---

## Žádné přímé FK mezi moduly

Mezi samostatnými moduly nevytvářej přímé cizí klíče.

Vazby mezi moduly řeš přes `EntityLink`.

**Výjimka:** interní vztahy uvnitř jednoho modulu (např. požadavek → sankce, požadavek → ověření plnění).

---

## Malé commity

Jeden commit = jedna dokončená funkční změna.

Každý commit musí být:

- funkční
- otestovaný
- samostatně pochopitelný

---

## Odpovědnost podle funkce / role (budoucí směr)

Funkce a role jsou samostatná entita organizační struktury.

V budoucnu budou osoby vykonávat jednu nebo více funkcí/rolí.

Procesní požadavky budou primárně navázány na funkce/role, nikoliv na konkrétní osoby.

Současná implementace (fáze 33) je prvním krokem k tomuto modelu.

Zatím nepředělávat THP ani organizační strukturu.
