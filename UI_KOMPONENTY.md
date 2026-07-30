# Standardy uživatelského rozhraní Manažera BOZP

Tento dokument je závazný pro návrh všech nových obrazovek, editorů, dialogů a formulářů.

Pokud zde existuje standardní komponenta, musí být použita.
Nové způsoby ovládání se nevytvářejí bez závažného důvodu.

Názvosloví textů řídí dokument `UX_NAZVOSLOVI.md`.

---

## 1. Formulář

- Pole zarovnávat do logických skupin.
- Jedna skupina = jedno téma.
- Nepoužívat dlouhé „excelové“ formuláře.
- Více než 4 logické celky → použít podzáložky.

---

## 2. Dynamické seznamy

Každý dynamický seznam obsahuje:

```text
hlavička
řádek
řádek
...
tlačítko Přidat
```

Pravidla:

- hlavička není součástí prvního řádku
- tlačítko Přidat je vždy pod seznamem
- Odebrat je vždy v posledním sloupci
- poslední sloupec se jmenuje **Akce**
- stejné odsazení
- stejné výšky řádků
- stejné ikony

---

## 3. Tabulky

- jednotná výška řádku
- jednotná hlavička
- stejné kontextové menu
- dvojklik = otevřít
- Delete = odebrat pouze pokud je to bezpečné
- tabulky používající `ElideRight` musí automaticky zobrazovat celý obsah buňky pomocí tooltipu (jen pokud je text skutečně zkrácen; u krátkých textů tooltip nezobrazovat)

---

## 4. Fotografie

Používat pouze společnou komponentu:

`PhotoPickerDialog`

Pravidla:

- podpora více fotografií
- stejné dialogy
- stejné náhledy
- stejné odstranění
- stejné pořadí

---

## 5. Modální dialogy

Používat:

- WindowModal
- `exec()`
- Overlay

Pravidla:

- šedý overlay
- automatické odstranění overlay
- Escape zavírá dialog
- žádný vlastní pseudo-modál

---

## 6. Validace

Rozlišovat:

**ULOŽIT**

**UZAVŘÍT**

Uložit:

- vždy umožnit uložit rozpracovanou práci

Uzavřít:

- kompletní validace

---

## 7. Prázdné stavy

Nikdy nezobrazovat prázdnou plochu.

Používat:

- informační panel
- vysvětlení
- případně odkaz na jinou část

Nepoužívat:

- prázdné widgety

---

## 8. Dlouhé obrazovky

Pokud:

- více než 4 logické oblasti

nebo

- nutnost rozsáhlého rolování

→ použít podzáložky.

---

## 9. Textová pole

Výška podle významu.

| Typ | Výška |
|---|---|
| Krátké | 2–3 řádky |
| Běžné | 4–6 řádků |
| Rozsáhlé | 6–8 řádků |

Nikdy nezabírat polovinu obrazovky prázdným polem.

---

## 10. Tlačítka

Ve spodní liště:

```text
[Náhled]                         [Zavřít] [Uložit] [Uzavřít]
vlevo                            vpravo
```

Pokud není důvod jinak.

---

## 11. Kontrola spisu

Každá validační chyba musí umět:

- otevřít správnou obrazovku
- otevřít správnou podzáložku
- zaměřit konkrétní pole

---

## 12. Ikony

Stejná akce = stejná ikona.

Nikdy nepoužívat dvě různé ikony pro stejnou činnost.

---

## 13. Rozestupy

Jednotné:

- mezery mezi skupinami
- odsazení
- výška hlaviček
- okraje

---

## 14. Konzistence

Pokud existuje obdobná obrazovka:

zkopírovat její UX.

Nevymýšlet nový způsob ovládání.

---

## 15. UX redesign

Pokud se na jedné obrazovce nahromadí přibližně 5–10 UX připomínek:

- přestat opravovat jednotlivé widgety,
- připravit jeden větší UX redesign celé obrazovky.

---

## 16. Závaznost

Tento dokument je závazný pro všechny nové moduly i úpravy stávajících obrazovek.

Odchylka je možná pouze tehdy, pokud přináší prokazatelně lepší uživatelské řešení a je vědomě schválena.
