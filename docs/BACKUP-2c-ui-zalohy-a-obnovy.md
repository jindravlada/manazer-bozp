"""BACKUP-2c / 2e – Uživatelské rozhraní zálohy a obnovy

Napojení infrastruktury BACKUP-1a…2b do Správy dat a Dashboardu.

**Bez automatických / generačních záloh.**

---

## 1. Kde v aplikaci

**Správa dat → Zálohování a obnova**

Jediná karta pro běžného uživatele:

**Úplná záloha Manažera BOZP (`*.mbbackup`)**

- Vytvořit zálohu  
- Ověřit zálohu  
- Obnovit ze zálohy  
- Diagnostika obnovy  

Popis: záloha obsahuje databázi, přílohy, fotografie, číselníky, šablony,
konfiguraci a uživatelská nastavení.

**Dashboard** (tlačítka Záloha / Obnova) používá stejný `*.mbbackup` workflow.

### Starý ZIP formát

Od BACKUP-2e **není** v běžném UI. Zůstává jen jako interní kompatibilita:

- `BackupService` / `full_backup_workflow_service` (API, testy, diagnostika),
- bezpečnostní ZIP před importem číselníků / registru,
- případná obnova starých ZIP souborů přes servisní nástroje.

Po přechodu z 3.1.0 má uživatel vytvořit novou `*.mbbackup`
(viz [MIGRATION-0](MIGRATION-0-overeni-prechodu-3.1.0-na-3.2.0.md)).

---

## 2. Vytvoření zálohy

1. Dialog uložení s výchozím názvem `manazer-bozp-instance-YYYY-MM-DD_HHMMSS.mbbackup`
2. Volání `create_instance_backup()`
3. Souhrn: cesta, datum, verze aplikace, počet souborů, integrita DB
4. Technické detaily v „Podrobnosti“

---

## 3. Ověření zálohy

1. Výběr `*.mbbackup`
2. `inspect_backup_integrity()` – **nemění data**
3. Stav: Platná / Platná s upozorněními / Neplatná + seznam problémů

---

## 4. Obnova

1. Výběr souboru + kontrola integrity (neplatná ⇒ zákaz)
2. Potvrzovací dialog s datem, verzí aplikace, varováním o nahrazení dat a informací o rollbacku
3. Uzavření DB session (`dispose_database_engine`)
4. `restore_instance_backup()` s progress dialogem (nelze zavřít)
5. Po úspěchu: potvrzení + ukončení aplikace (restart)

### Chybové stavy (česky)

| Situace | Zpráva |
|---------|--------|
| Před přepnutím | Původní data nebyla změněna |
| Po přepnutí + rollback | Původní data byla úspěšně vrácena |
| Selhání rollbacku | Kritická chyba + cesta markeru + zákaz mazání |

---

## 5. Recovery marker při startu

`main.py` před `MainWindow` volá `check_recovery_markers_at_startup()`.

Při existenci `.mbrestore-in-progress-*.json`:

- výrazné upozornění,
- zákaz další obnovy,
- diagnostika v UI,
- **žádné** automatické mazání / oprava.

---

## 6. Technické soubory

| Soubor | Role |
|--------|------|
| `moduly/sprava_dat/sluzby/instance_backup_workflow_service.py` | UI workflow `*.mbbackup` |
| `moduly/sprava_dat/ui/instance_backup_dialogs.py` | Dialogy |
| `moduly/sprava_dat/ui/backup_tab.py` | Záložka (jen `*.mbbackup`) |
| `moduly/sprava_dat/sluzby/full_backup_workflow_service.py` | Legacy ZIP API (bez běžného UI) |
| `core/database/session.py` | `dispose_database_engine()` |
| `tests/test_backup_2c_ui.py` | UI testy mbbackup |
| `tests/test_backup_2e_ui.py` | Odstranění ZIP z UI |
