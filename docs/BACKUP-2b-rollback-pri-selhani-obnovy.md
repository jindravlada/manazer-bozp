# BACKUP-2b – Rollback při selhání obnovy

Doplňuje [BACKUP-2a](BACKUP-2a-bezpecna-obnova.md) o automatický návrat původní
instance při chybě **po** atomickém přepnutí.

**Bez UI a bez automatického řešení recovery markeru při startu aplikace.**

---

## 1. Rollback postup

1. Před swapy se vytvoří rollback kopie (`…mbrestore-prev-…`) přesunem původního workspace.
2. Zároveň se zkopírují původní settings do `settings.json.mbrestore-bak`.
3. Po swapy se obnoví settings a provede post-check.
4. Teprve po úspěchu se maže rollback kopie a settings backup.

Při chybě po přepnutí:

1. neúspěšně obnovená data → `…mbrestore-failed-…`
2. rollback kopie → zpět na `workspace/`
3. návrat settings ze `.mbrestore-bak`
4. ověření `integrity_check` původní DB
5. úklid failed dat + markeru
6. výjimka `failed_after_swap_rolled_back` (původní data jsou zpět)

---

## 2. Recovery marker

Soubor mimo workspace:

`.mbrestore-in-progress-<token>.json`

Příklad polí:

| Pole | Význam |
|------|--------|
| `marker_format_version` | Verze formátu markeru |
| `kind` | `instance_restore` |
| `phase` | např. `before_swap`, `after_swap`, `rolling_back` |
| `started_at` / `updated_at` | ISO čas |
| `backup_format_version` | Verze formátu zálohy |
| `package_path` | Cesta k `*.mbbackup` |
| `workspace_root` | Cílový workspace |
| `new_workspace` | Staging nové instance |
| `rollback_workspace` | Kopie původních dat |
| `settings_path` / `settings_backup` | Settings transakce |

Marker se maže po úspěšné obnově nebo úspěšném rollbacku.
Při nevyřešeném stavu (selhání rollbacku) **zůstává** pro budoucí/ruční opravu.

---

## 3. Chybové stavy (fázové kódy)

| Kód | Význam |
|-----|--------|
| `failed_before_swap` | Selhání před přepnutím; původní data beze změny (`cause_code` = detail) |
| `failed_after_swap_rolled_back` | Selhání po přepnutí; rollback uspěl; původní data obnovena |
| `rollback_failed` | Rollback selhal; pracovní adresáře + marker zůstávají |

`InstanceRestoreError` má také:

- `phase`, `cause_code`, `rolled_back`
- `marker_path`, `preserved_paths` (zejména při `rollback_failed`)

---

## 4. Zbytkové adresáře po kritickém selhání

Při `rollback_failed` mohou zůstat:

- `.mbrestore-in-progress-<token>.json`
- `.workspace.mbrestore-prev-<token>/`
- `.workspace.mbrestore-failed-<token>/`
- `settings.json.mbrestore-bak`

Tyto artefakty se **automaticky nemažou** – slouží k ruční nebo budoucí automatické opravě.

Při úspěšné obnově a chybě úklidu rollback kopie:

- obnova zůstává platná,
- výsledek má `rollback_copy_removed=False` a varování v `warnings`.

---

## 5. Výsledek úspěšné obnovy

`RestoreInstanceBackupResult` (rozšíření 2a):

- `restored=True`
- `post_check_ok=True`
- `rollback_copy_removed`
- `recovery_marker_removed`
- `warnings` (+ zpětně kompatibilní `notes`)

---

## 6. Testy

`tests/test_backup_2b_restore_rollback.py`
