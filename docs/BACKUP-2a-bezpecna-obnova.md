# BACKUP-2a – Bezpečná obnova `*.mbbackup`

Cíl: obnovit celou instance Manažera BOZP z balíčku `*.mbbackup` tak, aby
aplikace **nikdy** nezůstala v napůl obnoveném stavu.

**Bez dialogů, menu, automatických záloh a bez rollbacku po přepnutí (BACKUP-2b).**

Moduly: `core/backup/package_restore.py`, `package_extract.py`.

---

## 1. API

```python
from core.backup import restore_instance_backup

result = restore_instance_backup(
    "/cesta/zaloha.mbbackup",
    workspace_root=None,   # výchozí StorageService.base
    settings_path=None,    # výchozí SettingsManager
)
# result.workspace_root, result.database_path, result.database_integrity
```

Výjimka: `InstanceRestoreError` s polem `code` (viz níže).

---

## 2. Postup obnovy

1. Otevření balíčku a kontrola přípony `.mbbackup`
2. Kompletní kontrola integrity (`inspect_backup_integrity` – BACKUP-1c)
3. Preflight volného místa na disku
4. Bezpečné rozbalení do dočasného adresáře (**bez** `extractall`)
5. Ověření povinných komponent v extractu
6. Sestavení **nové** instance vedle stávajícího workspace
7. Atomická výměna adresářů (`os.rename`)
8. Atomický zápis `settings.json` (pokud je v balíčku)
9. Post-check (DB existuje, `integrity_check=ok`, velikost dle metadat)
10. Úklid temp / předchozí instance

`zalohy/` se z balíčku neobnovuje – při obnově se **přenesou** z původního
workspace (prevence ztráty historických záloh).

---

## 3. Atomická výměna

```text
workspace/          →  .workspace.mbrestore-prev-<token>/
.workspace.mbrestore-new-<token>/  →  workspace/
```

- Nová instance se sestaví **celá** před jakýmkoli přejmenováním.
- Původní data se nemažou, dokud není nová instance hotová.
- Pokud selže druhý `rename`, provede se best-effort návrat `prev` → `workspace`.
- Plný rollback po úspěšném přepnutí = BACKUP-2b.

---

## 4. Bezpečnost cest

- Žádné `ZipFile.extractall` / `extract`
- Každý člen přes `normalize_archive_path` + `resolve` pod kořenem extractu
- Absolutní cesty, `..` a útěk z kořene → `RESTORE_ERR_UNSAFE_PATH`

---

## 5. Diagnostické kódy

| Kód | Význam |
|-----|--------|
| `bad_archive` | Poškozený / nečitelný ZIP nebo špatná přípona |
| `invalid_metadata` | Neplatná / nekompletní metadata |
| `invalid_database` | DB chybí nebo neprojde integrity_check |
| `missing_component` | Chybí povinná komponenta |
| `disk_full` | Nedostatek místa |
| `write_error` | Chyba zápisu / výměny |
| `interrupted` | Přerušená obnova |
| `integrity_failed` | Obecná chyba integrity balíčku |
| `post_restore_check_failed` | Selhání ověření po obnově |
| `unsafe_path` | Nebezpečná cesta v archivu |

---

## 6. Testy

`tests/test_backup_2a_restore_instance_backup.py`

---

## 7. Co záměrně chybí

- UI / dialogy / menu
- automatické a generační zálohy
- rollback původní instance po úspěšném přepnutí (BACKUP-2b)
- legacy ZIP obnova (stávající `BackupService` beze změny)
