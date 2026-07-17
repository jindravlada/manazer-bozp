# UX-SAVE-1a – Analýza současného ukládání editorů

Stav k 2026-07-17. Pouze podklad pro UX-SAVE-1b. Bez změny chování.

## Shrnutí

| Modul | Současný stav | Riziko při skutečném Uložit/Zrušit | Doporučení pro UX-SAVE-1b |
|-------|---------------|-----------------------------------|---------------------------|
| Registr rizik | Hybrid: Uložit = jen základní údaje (dialog zůstane otevřený). Zrušit = zavře bez rollbacku. Záložky (zdroje, události, posouzení, opatření, fotky) ukládají okamžitě při Accept / Aktivovat. Pracovní kopie není. Revize/historie není. | Zrušit dnes neodvolá už zapsaný obsah. Požadavek na ID před editací záložek. | Nejdřív oddělit staging obsahu od základů; Cancel musí mít transakční/worker copy. |
| Katalog zdrojů rizik | Hybrid: Uložit = jen základní údaje. Obsah (události, posouzení, opatření, právní vazby) okamžitě do DB. Zrušit/Zavřít při dirty obsahu **zvýší revizi** (+ historie `manual_edit`), ale obsah nevrací. Pracovní kopie obsahu není. | Zrušit ≠ revert. Revize se pečetí při zavření, obsah už je živý. Historie bez delta. | True Save/Cancel vyžaduje working copy celého stromu MASTER; zrušit finalize-on-close. |
| Audity | Hybrid: Uložit = Spis + komise + závěr. Zrušit = reject bez rollbacku. Výsledky tvrzení, fotky, zjištění, úkoly, Dokončit = okamžitý zápis (sdílený `ControlResultSelectorWidget`). Revize entity není. Historie = odvozené čtení `control_results`. | Cancel neodvolá výsledky/fotky/zjištění. Nový audit bez ID nemůže hodnotit. Dokončit commitne uprostřed session. | Staging výsledků/zjištění do Accept; nebo explicitní „pracovní spis“. |
| Prověrky | Stejný hybrid jako Audity (`BozpInspectionDialog` + okamžité výsledky/zjištění). Revize entity není. | Stejná rizika jako Audity. | Stejný přístup jako Audity (sdílená vrstva control results). |
| Kniha úrazů | Nejbližší deferred režimu: formulář + administrativa až při Accept. Zrušit = reject. Přílohy a export závěrečné zprávy ukládají okamžitě. „Otevřít Vyšetřování MU“ volá `accept()` (= vynucené uložení). Revize/historie není (jen `updated_at`). | Cancel neodvolá přílohy/export. Vynucený save před MU. Žádný dirty prompt. | Oddělit přílohy od Accept; zrušit auto-`accept` před MU nebo nabídnout potvrzení. |

## Doplňující poznámky

### Okamžité ukládání (společné)

- `ControlResultSelectorWidget._save_current_state` → Audity i Prověrky.
- Child dialogy s `accept()` → create/update service → `session.commit`.
- Aktivovat/Deaktivovat na toolbarech.
- `AttachmentWidget` (Kniha úrazů, podobně jinde).

### Pracovní kopie (omezeně)

- Jen odložené základní/spisové formuláře v paměti widgetů do Accept.
- Žádný draft/clone/snapshot entity.
- Editory znalostí (Audity/Prověrky) mají in-memory drafty sekcí — oddělený tok od spisu.

### Revize

| Modul | Kde |
|-------|-----|
| Katalog zdrojů | `version_number` + `HazardLibraryTemplateRevision` při zavření editoru (`_finalize_content_version`) a při AI/import zapracování |
| Ostatní | Ne |

### Historie

| Modul | Kde |
|-------|-----|
| Katalog zdrojů | Metadata revize (reason), bez field-level delta |
| Audity | Čtení historie kontrolních bodů z `control_results`; maturity snapshot při roční zprávě |
| Prověrky | Čtení z `control_results` |
| Registr rizik / Kniha úrazů | Ne |

### Nejvyšší priorita blokátorů pro UX-SAVE-1b

1. Katalog: Zrušit dnes pečetí revizi a nevrací obsah.
2. Registr / Audity / Prověrky: nested immediate writes vs. footer Cancel.
3. Kniha úrazů: přílohy + vynucený Accept před MU.
