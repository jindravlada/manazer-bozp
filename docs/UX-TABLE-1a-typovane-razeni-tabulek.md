# UX-TABLE-1a – Společné typované řazení tabulek

Stav k 2026-07-18. Infrastruktura bez migrace modulů.

## Umístění

| Soubor | Účel |
|--------|------|
| `core/widgets/typed_table_sort.py` | Typovaný klíč, položka tabulky, zapnutí řazení |
| `core/utils/czech_sort.py` | Existující české porovnání textů (reuse, bez duplicity) |

## Jak nastavit typovaný klíč

```python
from datetime import date
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    typed_bool,
    typed_date,
    typed_float,
    typed_int,
    typed_status,
    typed_text,
)

enable_typed_sorting(table)
table.setSortingEnabled(False)  # při plnění
table.setItem(row, col, create_typed_item("12. 7. 2026", typed_date(date(2026, 7, 12)), stable_id=row))
table.setItem(row, col, create_typed_item("1 250,50", typed_float(1250.5), stable_id=row))
table.setItem(row, col, create_typed_item("Ano", typed_bool(True), stable_id=row))
table.setItem(row, col, create_typed_item("Kritické", typed_status(0), stable_id=row))
table.setItem(row, col, create_typed_item("Chalupa", typed_text("Chalupa"), stable_id=row))
table.setSortingEnabled(True)
```

- Zobrazený text ≠ řadicí klíč (`TYPED_SORT_ROLE`).
- `stable_id` zajistí předvídatelné pořadí při shodě klíčů.
- Prázdné (`None`, `""`, jen mezery, `typed_empty()`) jsou **vždy poslední**.

## Zapojení do běžné tabulky (pozdější migrace)

1. `enable_typed_sorting(table)` jednou po vytvoření tabulky.
2. Při `refresh` vypnout sorting, plnit jen přes `create_typed_item(...)`, znovu zapnout.
3. Neměnit DisplayRole kvůli řazení – typovat klíč zvlášť.
4. Persistenci sloupce/směru UX-TABLE-1a neřeší.
