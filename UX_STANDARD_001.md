# UX STANDARD č. 001

## Aktivace akcí podle výběru záznamu

Tento dokument je závazný pro všechny seznamové moduly Manažera BOZP.

Od této chvíle se všechny nové i upravované moduly řídí tímto standardem.

Související dokumenty:

- `UI_KOMPONENTY.md`
- `UX_NAZVOSLOVI.md`
- `ARCHITEKTURA_MODULU.md`

---

## 1. Akce nezávislé na výběru

Tyto akce nepracují s konkrétním záznamem.

Jsou vždy aktivní.

Příklady:

- Nový...
- Import...
- Export všeho...
- Nastavení...
- Šablony...
- Správa...
- Analýza...
- Synchronizace...
- Aktualizovat...

---

## 2. Akce nad jedním záznamem

Tyto akce vyžadují právě jeden vybraný záznam.

| Stav výběru | Stav tlačítka |
|---|---|
| Bez výběru | neaktivní |
| Právě jeden výběr | aktivní |
| Více výběrů | neaktivní |

Příklady:

- Upravit
- Historie
- Dokumenty
- Ohláška OO
- Vyšetřování MU
- Výpis
- Závěrečná zpráva
- Detail

(Otevřít pouze pokud modul skutečně rozlišuje prohlížení a editaci – viz § 6a.)

---

## 3. Hromadné akce

Akce podporující více záznamů.

| Stav výběru | Stav tlačítka |
|---|---|
| Bez výběru | neaktivní |
| Právě jeden výběr | aktivní |
| Více výběrů | aktivní |

Příklady:

- Archivovat
- Změnit stav
- Export vybraných
- Tisk vybraných
- Označit jako...

---

## 4. Zákaz informačních dialogů

Nepoužívat hlášky typu:

```text
Vyberte záznam.
```

pokud lze stejného výsledku dosáhnout deaktivací tlačítka.

Dialog použít pouze tehdy, pokud stav nelze poznat předem.

---

## 5. Vícenásobný výběr

Pokud modul podporuje více výběrů, musí být u každé akce jednoznačně určeno:

- podporuje více výběrů,
- nepodporuje více výběrů.

Tlačítka tomu musí odpovídat.

---

## 6. Dvojklik

Pokud modul obsahuje **Upravit** (nebo výjimečně **Otevřít** v režimu pouze prohlížení), musí dvojklik provést stejnou výchozí akci.

---

## 6a. Otevřít vs. Upravit

Nepoužívat současně **Otevřít** a **Upravit**, pokud obě akce vedou na stejný editor.

Pokud neexistuje rozdíl mezi prohlížením a editací, ponechat pouze **Upravit**.

Obě akce jsou přípustné jen tehdy, když modul skutečně rozlišuje:

- pouze prohlížení,
- editaci.

---

## 7. Výjimky

Výjimka musí být zdůvodněna.

Není dovoleno vytvářet odlišné UX bez důvodu.

---

## 8. Zavádění

Standard se zavádí postupně.

Každý modul bude upraven samostatným sprintem.

Jeden sprint = jeden commit.

Bez hromadných změn napříč celou aplikací.

---

## Verze

**UX STANDARD č. 001**  
Aktivace akcí podle výběru záznamu
