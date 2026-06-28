# StorageService

Od verze 054 jsou všechna uživatelská data směrována do:

~/.local/share/manazer-bozp/

Struktura:

~/.local/share/manazer-bozp/
├── databaze/
│   └── manager_bozp.db
├── prilohy/
├── zalohy/
├── export/
├── import/
└── logy/

Důležité:
- databáze už nemá být v adresáři projektu,
- přílohy už nemají být v adresáři projektu,
- další moduly mají používat výhradně StorageService.
