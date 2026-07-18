# BACKUP-1a – Formát záložního balíčku a metadata

Cíl této fáze: společný, verzovaný a testovaný základ pro úplné zálohy Manažera BOZP
ve formátu `*.mbbackup`. **Bez UI, bez tvorby obsahu a bez obnovy** – ty přijdou
v BACKUP-1b a dalších fázích.

Modul: `core/backup/` (nezávislý na konkrétním business modulu aplikace).

---

## 1. Přípona a technický formát

| Vlastnost | Hodnota |
|-----------|---------|
| Přípona souboru | `.mbbackup` (`BACKUP_EXTENSION`) |
| Technický kontejner | ZIP (kompatibilní s běžnými ZIP nástroji) |
| Verze formátu | `BACKUP_FORMAT_VERSION = 1` |
| Typ balíčku (v1) | `instance_backup` |
| Metadata v archivu | `metadata.json` (kořen archivu) |

Přípona `.mbbackup` a povinná pole v `metadata.json` (zejména `package_kind` a
`format_version`) oddělují úplnou zálohu instance od běžného ZIP importu/exportu
workspace a od budoucích knowledge exportů.

Současný `BackupService` (ZIP + `VERSION.json`) se v této fázi **nemění**.

---

## 2. Struktura archivu

Minimální povinná struktura formátu v1:

```text
archive.mbbackup          # ZIP s příponou .mbbackup
├── metadata.json         # povinné metadata + manifest
├── database/             # DB snapshot (soubory doplní BACKUP-1b)
├── workspace/            # workspace mimo DB (soubory doplní BACKUP-1b)
└── settings/             # nastavení / konfigurační stopy (BACKUP-1b)
```

Konstanty kořenů: `REQUIRED_ARCHIVE_ROOTS` =
`("database", "workspace", "settings")`.

Struktura je **rozšiřitelná**: nové adresáře nebo soubory lze přidat v nové
verzi formátu nebo jako volitelné položky v manifestu (`required: false`) bez
porušení čtení starších platných balíčků, pokud validátor podporuje danou
`format_version`.

---

## 3. Metadata (`metadata.json`)

### Povinná pole

| Pole | Význam |
|------|--------|
| `format_version` | Verze formátu balíčku (int) |
| `created_at` | ISO 8601 datum/čas včetně časové zóny |
| `app_version` | Verze aplikace (`APP_VERSION`) |
| `platform` | Platforma vytvoření (např. `linux/x86_64`) |
| `package_kind` | Typ balíčku (`instance_backup`) |
| `included_components` | Seznam zahrnutých komponent |
| `files` | Manifest souborů |
| `total_content_size` | Součet velikostí položek v `files` |
| `package_status` | Stav dokončení (`creating` / `complete`) |

### Doporučená / volitelná pole

| Pole | Význam |
|------|--------|
| `schema_version` | Verze DB schématu, pokud ji aplikace umí zjistit; jinak `null` |
| `database_integrity` | Výsledek kontroly integrity DB (např. `ok`, `failed`, `skipped`) |

### Co se **neukládá**

- názvy zaměstnavatele,
- osobní údaje,
- absolutní cesty workspace / DB na disku uživatele,
- hesla a tokeny.

---

## 4. Manifest souborů

Každá položka v `files` obsahuje minimálně:

| Pole | Povinné | Popis |
|------|---------|--------|
| `path` | ano | Relativní POSIX cesta v archivu |
| `component` | ano | Komponenta (`database`, `workspace`, `settings`, …) |
| `size` | ano | Velikost v bajtech (≥ 0) |
| `sha256` | ano | Hex SHA-256 (64 znaků) |
| `required` | ne | Výchozí `true` |

Pravidla cest:

- vždy relativní a normalizované (`/` jako oddělovač),
- bez absolutních cest,
- bez `..`,
- bez Windows drive / UNC,
- bez duplicit v rámci jednoho manifestu.

Normalizace: `core.backup.paths.normalize_archive_path`.

---

## 5. Bezpečnost cest

Společná validace (`normalize_archive_path` / `is_safe_archive_path`) odmítá:

- absolutní cesty (`/etc/passwd`, `/tmp/...`),
- `..` a pokusy o útěk z kořene,
- prázdnou cestu,
- Windows cesty mimo kořen (`C:\...`, `\\server\share`, `C:/...`),
- nebezpečné rozdíly oddělovačů (`workspace\..\database` → zamítnuto kvůli `..`).

Samotné rozbalování archivu v této fázi **není** implementováno – pouze
validační infrastruktura pro budoucí bezpečný extract.

---

## 6. Kontrolní součty

Algoritmus: **SHA-256**.

Pomocné funkce v `core.backup.hashing`:

- `sha256_file(path)` – čtení po blocích (výchozí 1 MiB),
- `sha256_bytes(data)` – hash bytů,
- `sha256_stream(stream)` – hash z otevřeného streamu,
- `hashes_equal(expected, actual)` – porovnání (case-insensitive).

Velké soubory se **nesmí** načítat celé do paměti.

---

## 7. Stav dokončení balíčku

| Stav | Význam |
|------|--------|
| `creating` | Balíček se ještě sestavuje; **není** platná záloha |
| `complete` | Balíček je dokončený a připravený k validaci jako platná záloha |

`validate_backup_metadata(..., require_complete=True)` (výchozí) přijme pouze
`package_status == "complete"`.

Doporučený postup tvorby (BACKUP-1b):

1. vytvořit dočasný soubor (např. `*.mbbackup.partial`),
2. zapsat obsah a metadata se stavem `creating`,
3. přepsat metadata na `complete`,
4. atomicky přejmenovat na finální `*.mbbackup`.

---

## 8. Verzování a kompatibilita

- Konstanta `BACKUP_FORMAT_VERSION` určuje aktuální verzi zápisu.
- `SUPPORTED_BACKUP_FORMAT_VERSIONS` určuje, které verze smí čtenář přijmout.
- Zvýšení verze formátu musí být zdokumentované; starší čtenáři odmítnou
  nepodporovanou verzi jasnou chybou (`BackupMetadataError`).
- Nová volitelná pole v JSON jsou přípustná, pokud neporuší povinná pole v1.
- Odstranění nebo významová změna povinného pole vyžaduje novou `format_version`.

---

## 9. Záloha instance vs. budoucí export znalostí

| | Úplná záloha instance | Budoucí knowledge export |
|--|------------------------|---------------------------|
| Přípona | `.mbbackup` | např. `.mbcatalog` (zatím ne) |
| `package_kind` | `instance_backup` | např. `risk_catalog_export` |
| Obsah | DB + workspace + settings instance | katalog / znalosti bez plné instance |
| Obnova | obnova celé instance | import znalostí do běžící instance |

V BACKUP-1a je podporován **pouze** `instance_backup`. Konstanta
`PACKAGE_KIND_RISK_CATALOG_EXPORT` je rezervovaná, formát `*.mbcatalog`
**nevzniká**.

---

## 10. API (přehled)

```python
from core.backup import (
    BACKUP_FORMAT_VERSION,
    PACKAGE_STATUS_COMPLETE,
    create_backup_metadata,
    mark_package_complete,
    validate_backup_metadata,
    build_file_entry,
    normalize_archive_path,
    sha256_file,
    sha256_bytes,
)
```

---

## 11. Co tato fáze záměrně neřeší

- uživatelské UI a ruční spuštění zálohy,
- zápis obsahu do ZIP / atomické přejmenování,
- obnovu dat,
- změnu stávajícího ZIP workspace exportu / `BackupService`,
- `extractall` / `_replace_item`,
- automatické zálohy.
