# Komponenty třetích stran

Tento soubor uvádí hlavní externí komponenty použité při vývoji a sestavení Manažera BOZP. Nekopíruje jejich úplná licenční znění a licence těchto komponent nevykládá. Licencí samotného Manažera BOZP je GPL-3.0-or-later, viz [LICENSE.txt](LICENSE.txt).

Údaje o licencích pocházejí z metadat nainstalovaných balíčků v ověřeném prostředí, z licenčního souboru interpretu Python 3.14.4, nebo z oficiálních metadat repozitáře linuxdeploy. Verze Pythonových balíčků odpovídají `requirements.txt` a `requirements-build.txt`.

## Python

Aplikace je napsaná v Pythonu. Ověřený vývojový interpret je CPython 3.14.4. Jeho instalace obsahuje soubor `LICENSE.txt`, ve kterém je uvedena Python Software Foundation License Version 2.

## PySide6 a Qt

PySide6 6.11.2 je vazba na aplikační framework Qt a slouží pro uživatelské rozhraní. Stejné licenční pole mají v metadatech instalace i balíčky PySide6_Essentials 6.11.2, PySide6_Addons 6.11.2 a shiboken6 6.11.2:

`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`

Domovská stránka projektu: <https://pyside.org>

Qt, jehož knihovny tyto balíčky používají, má vlastní licenční podmínky. V instalaci PySide6 nebyl nalezen samostatný licenční soubor Qt, proto zde není uvedena konkrétní licence knihoven Qt. Podmínky Qt zveřejňuje Qt Group na <https://www.qt.io/licensing>.

V repozitáři jsou také české překladové soubory Qt `zdroje/preklady/qtbase_cs.qm` a `zdroje/preklady/qt_filedialog_cs.qm`.

## SQLAlchemy

SQLAlchemy 2.0.52 zajišťuje přístup k databázi. Pole `License` v metadatech balíčku uvádí MIT. Úplný text je v souboru `LICENSE` distribuce balíčku. Projekt: <https://www.sqlalchemy.org>

## requests

requests 2.34.2 slouží pro HTTP požadavky. Pole `License` v metadatech balíčku uvádí Apache-2.0 a klasifikátor balíčku odkazuje na Apache Software License. Projekt: <https://github.com/psf/requests>

## Pillow

Pillow 12.3.0 slouží pro práci s obrázky. Pole `License-Expression` v metadatech balíčku uvádí MIT-CMU. Projekt: <https://python-pillow.github.io>

## PyInstaller

PyInstaller 6.22.3 se používá jen při sestavení aplikace, ne za jejího běhu ze zdrojových kódů. Pole `License` v metadatech balíčku uvádí:

`GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones)`

Soubor `COPYING.txt` v distribuci balíčku se jmenuje „The PyInstaller licensing terms“ a obsahuje text GNU GPL verze 2 nebo novější a oddíl Bootloader Exception. Tento soubor podmínky PyInstalleru nevykládá. Projekt: <https://pyinstaller.org>

## linuxdeploy

linuxdeploy je externí nástroj pro sestavení Linux AppImage. Do repository se neukládá. `build_release.sh` ho v případě potřeby stáhne z oficiálního continuous vydání a ověří SHA-256.

Oficiální metadata repozitáře <https://github.com/linuxdeploy/linuxdeploy> (GitHub License API) uvádějí MIT License a soubor `LICENSE.txt`. Sestavený AppImage může obsahovat další součásti; jejich licence zde nejsou posuzovány.
