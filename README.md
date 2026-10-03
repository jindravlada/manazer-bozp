# Manažer BOZP 4.0.9

Aktuální verze: 4.0.9

## 📥 Stažení aplikace

Hotovou aplikaci není nutné sestavovat ze zdrojových kódů.

### Linux

**Manažer BOZP 4.0.9 – AppImage**

[⬇️ Stáhnout Manažer BOZP pro Linux](https://github.com/jindravlada/manazer-bozp/releases/download/v4.0.9/Manazer-BOZP-4.0.9-x86_64.AppImage)

Po stažení nastavte soubor jako spustitelný a spusťte jej.

### Windows

**Manažer BOZP 4.0.9 – instalační program**

[⬇️ Stáhnout Manažer BOZP pro Windows](https://github.com/jindravlada/manazer-bozp/releases/download/v4.0.9/Manazer_BOZP_4_0_9_Setup.exe)

Určeno pro Windows 10/11.

[Všechna vydání a soubory ke stažení](https://github.com/jindravlada/manazer-bozp/releases)

## O aplikaci

Manažer BOZP je lokální desktopová aplikace pro podporu evidence a řízení agendy bezpečnosti a ochrany zdraví při práci.

Aplikace v současné verzi pokrývá zejména tyto oblasti:

- pracovní plochu a agendu,
- audity systémů řízení,
- prověrky BOZP,
- právní požadavky,
- knihu úrazů a vyšetřování mimořádných událostí,
- řízení rizik,
- úkoly,
- kontroly,
- koordinaci BOZP,
- státní dozor v rámci agendy,
- události a jejich šablony,
- smlouvy odborně způsobilé osoby,
- správu dat a nastavení.

Aplikace pracuje lokálně na počítači uživatele. Nepotřebuje serverový backend. Uživatelská data nejsou součástí tohoto repository.

Samotné používání aplikace nezajišťuje splnění právních povinností.

## Stav projektu

Jde o aktivně vyvíjený projekt. Současná veřejná verze je 4.0.9.

## Spuštění ze zdrojových kódů – Linux

Ověřené vývojové prostředí používá Python 3.14.4. Projekt v repozitáři nestanovuje širší rozsah podporovaných verzí Pythonu.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Vytvoření AppImage

Do stejného virtuálního prostředí doinstalujte nástroje pro sestavení a spusťte build:

```bash
python -m pip install -r requirements-build.txt
./build_release.sh
```

Skript si v případě potřeby stáhne oficiální linuxdeploy a před použitím ověří jeho SHA-256. Výsledkem je soubor `ManagerBOZP.AppImage`.

## Windows

Sestavení na Windows předpokládá:

- Python a lokální virtuální prostředí `.venv`,
- závislosti z `requirements.txt`,
- nástroje z `requirements-build.txt`,
- Inno Setup 6.

Sestavení se spouští skriptem `build_windows.bat`. Skript hledá `ISCC.exe` na `PATH` nebo v běžném umístění Inno Setup 6.

Windows build nebyl v rámci této linuxové přípravy fyzicky ověřen na Windows.

## Data

Provozní databáze, přílohy a zálohy vznikají až při používání aplikace a nejsou součástí zdrojového repository.

## Licence

Copyright © 2026 Ing. Vladimír Jindra

Manažer BOZP je svobodný software distribuovaný podle podmínek GNU General Public License, version 3 or any later version (GPL-3.0-or-later).

Úplné znění licence je v souboru [LICENSE.txt](LICENSE.txt).

Informace o hlavních externích komponentách jsou v souboru [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Licence těchto komponent nejsou licencí Manažera BOZP.

## Použité technologie

- Python
- PySide6 / Qt
- SQLAlchemy
- requests
- Pillow
- PyInstaller
- linuxdeploy

## AI

Při vývoji byly využívány nástroje umělé inteligence, zejména ChatGPT a Cursor AI, jako pomoc při návrhu, programování, testování a dokumentaci. Autorem a držitelem copyrightu projektu je Ing. Vladimír Jindra.
