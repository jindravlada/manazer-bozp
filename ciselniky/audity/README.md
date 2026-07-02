# Znalostní databáze interních auditů

Každý řídicí proces je samostatný JSON soubor. Struktura je stabilní — doplňujte pouze obsah.

## Pracovní postup

1. Zkopírujte `_sablona_rizeni_procesu.json` na `{id_procesu}.json`.
2. Vyplňte kostru (id, názvy oblastí, prázdná pole).
3. Pošlete celý JSON k odbornému doplnění.
4. Vraťte doplněný JSON zpět beze změny struktury a názvů polí.
5. Zaregistrujte proces v `procesy.json`.
6. Spusťte validaci: `python tools/validate_audity_knowledge.py`

## Soubory

| Soubor | Účel |
|--------|------|
| `procesy.json` | Registr řídicích procesů |
| `{id}.json` | Kompletní znalostní báze jednoho procesu |
| `_sablona_rizeni_procesu.json` | Prázdná kostra — nepoužívat v aplikaci |

## Struktura procesu (`{id}.json`)

Pole udržujte v tomto pořadí:

```
verze
id
nazev
popis
ucel_procesu
proc_je_dulezity
ocekavany_vystup
poradi
aktivni
vazby_procesy
pozadavky_norem
sekce
```

## Struktura oblasti ověření (`sekce[]`)

```
id
nazev
popis
cil_overeni
poradi
aktivni
sekce

postup_kontroly
auditni_tvrzeni
kontrolni_body
navodne_otazky

objektivni_dukazy
doporucene_rozhovory
pozorovani_v_provozu
typicke_neshody
typicke_zavady
pkz
pozorovani
doporucene_postupy
legislativa
pozadavky_normy

vazby_procesy
poznamky_auditora
referencni_fotografie
historie
```

Prázdné sekce ponechte jako `[]`. Pole `navodne_otazky` a `kontrolni_body` ponechte prázdná — používejte `auditni_tvrzeni`.

## Auditní tvrzení (`auditni_tvrzeni[]`)

Každé tvrzení:

```
id          — stabilní identifikátor (snake_case, neměnit po nasazení)
text        — ověřitelné tvrzení (ne otázka)
popis       — metodický popis pro auditora
poradi      — pořadí zobrazení (10, 20, 30, …)
aktivni     — true / false
zavaznost   — kriticka | vysoka | stredni | nizka
```

Příklad tvaru textu: „Všechny pracovní úrazy jsou evidovány.“

## Seznamové položky (důkazy, neshody, PKZ, …)

```
id
nazev
popis       — volitelné
poradi
aktivni
```

## Registrace nového procesu (`procesy.json`)

```json
{
  "id": "rizeni_rizik",
  "nazev": "Řízení rizik",
  "popis": "",
  "ucel_procesu": "",
  "poradi": 20,
  "aktivni": true,
  "soubor_znalosti": "rizeni_rizik.json"
}
```

`id` v registru musí odpovídat `id` v souboru znalostí. Název souboru = `{id}.json`.

## Pravidla pro úpravy obsahu

- Neměňte názvy polí ani strukturu bez domluvy.
- Neměňte `id` existujících tvrzení a oblastí po nasazení (stable key).
- Každý JSON musí být validní (spusťte validátor).
- Odborný text doplňujte do prázdných polí; nevymýšlejte nová pole.
