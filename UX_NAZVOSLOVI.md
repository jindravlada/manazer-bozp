# UX názvosloví Manažera BOZP

Závazný style guide pro uživatelské texty v celé aplikaci.
Platí pro hlavní okna, editory, dialogy, záložky, skupiny, tlačítka, menu,
informační a validační hlášky.

**Rozsah:** pouze texty v UI.  
**Neměnit:** databázi, JSON klíče, exporty, importy, workflow, vnitřní kódy stavů.

---

## 1. Obecná pravidla

1. Texty jsou **krátké**, **jednoznačné** a **odborně správné**.
2. Stejná činnost má **stejný název** v celé aplikaci.
3. Preferovat **podstatná jména** (oblasti, skupiny, záložky) a **krátká slovesa** (tlačítka).
4. Nepoužívat směs věty / otázky / podstatného jména ve stejné roli.
5. Nepoužívat duplicitní synonyma pro stejnou akci.

---

## 2. Skupiny formulářů

Skupiny pojmenovávat jako **témata** (podstatná jména / krátké nominální fráze).

### Správně

- Pracovní doba
- Platné předpisy
- Kontrola dodržování předpisů
- Revize a zjevné závady
- Porušení předpisů
- Osobní ochranné pracovní prostředky / OOPP
- Odborná způsobilost
- Další skutečnosti
- Školení
- Kvalifikace
- Přílohy

### Nesprávně

- Vyber rok
- Jak bylo stanoveno hodnocení?
- Předpisy pro činnost, při které došlo k mimořádné události *(příliš dlouhá věta)*
- Kontroly a revize zařízení / zjevné závady na pracovišti *(příliš dlouhé / směs)*

---

## 3. Záložky

Záložka = **oblast práce**, ne popisný odstavec.

### Správně

- Spis
- Oznámení
- Svědci
- Časová osa
- OOPP
- Odborná způsobilost
- Rizika
- Kontroly
- Zaměstnavatelé
- Účastníci
- Předání rizik
- Zdroje rizik
- Posouzení rizik
- Oponentura AI
- Fotodokumentace
- Přílohy

### Nesprávně

- Zapisovatel / zaměstnavatel
- Svědci / podpisy
- Zúčastnění zaměstnavatelé
- Předání rizik dodavatelů
- Zdroje rizik na pracovišti
- Oponentní posouzení AI *(zbytečně dlouhé)*

---

## 4. Tlačítka

Preferovat krátká slovesa.

| Akce | Použít | Nepoužívat |
|---|---|---|
| Přidání položky do seznamu | **Přidat** | Vybrat *(pokud nejde o výběr ze souboru)* |
| Odebrání položky ze seznamu | **Odebrat** | Odstranit |
| Trvalé smazání celého záznamu | **Smazat** | Odebrat *(pro celý záznam)* |
| Úprava | **Upravit** | Editovat |
| Uložení | **Uložit** | Save |
| Uzavření procesu / životního cyklu | **Uzavřít** | Dokončit *(u nových modulů s mapou stavů)* |
| Zavření okna dialogu | **Zavřít** | Uzavřít *(pro dismiss dialogu)* |
| Náhled obsahu | **Náhled** | Zobrazit *(pro preview)* |
| Tisk | **Tisk** | Vytisknout |
| Vrácení k úpravám | **Vrátit k dopracování** | Vrátit do konceptu |

### Filtry seznamů

Popisek **„Zobrazit:“** u filtru tabulky (Aktivní / Vše) **ponechat**.  
Nejde o náhled, ale o rozsah zobrazení seznamu.

### Zjištěné změny legislativy

Filtr **„Vyhodnocení:“** – Nevyhodnocené / Vyhodnocené / Vše.  
Výchozí pohled je **Nevyhodnocené**.

Akce odborného posouzení dopadu: **Vyhodnoceno**.  
Nepoužívat „Označit jako vyhodnocené“ ani „Uložit vyhodnocení“.

**Vyhodnoceno** a **Převzít nové znění** jsou dvě různé akce.

### Generování v Prověrkách

Použít **Generovat prověrky**, nikoli „Generovat kontroly“.

---

## 5. Dialogy

Název dialogu popisuje **činnost nebo entitu**.

### Správně

- Výběr zaměstnance
- Přidání fotografie
- Kontrola spisu
- Oponentní posouzení
- Správa kategorií
- Generovat prověrky
- Stanovení hodnocení
- Identifikace rizik

### Nesprávně

- Neurčité názvy bez kontextu (`Sankce`, `Úkol` jako jediné slovo v MessageBox bez kontextu)
- Otázky jako titul dialogu (`Jak bylo stanoveno hodnocení?`)

---

## 6. Stavy

### Preferované UI popisky

- Rozpracováno
- Probíhá
- Schváleno
- Uzavřeno
- Archivováno
- Vráceno k dopracování
- Plánováno

### Zakázané synonymní varianty (pro stejný význam)

| Nepoužívat | Místo toho |
|---|---|
| Koncept | Rozpracováno |
| Příprava | Rozpracováno |
| Dokončeno *(u modulů s anglickými kódy stavů)* | Uzavřeno |
| Uzavřený / Schválený *(přídavné jméno)* | Uzavřeno / Schváleno |

### Výjimka (do migrace dat)

U **Auditů**, **Prověrek** a **Vyšetřování MU** je český text stavu zároveň uloženou hodnotou
(`"Dokončeno"`, `"Probíhá"`, …).  
Tyto uložené hodnoty **neměnit** bez datové migrace.  
Nové moduly používají anglické kódy (`draft`, `closed`, …) + mapu UI popisků.

---

## 7. Terminologie – jednotný slovník

### Fotografie a přílohy

| Termín | Význam |
|---|---|
| **Fotodokumentace** | Sekce / soubor fotografií k případu |
| **Fotografie** | Jednotlivý obrazový záznam |
| **Referenční fotografie** | Metodický vzor (katalog znalostí) |
| **Příloha** | Obecný soubor (PDF, ODT, …), ne nutně fotografie |

### Kontrola × Prověrka × Audit × Revize

| Termín | Význam |
|---|---|
| **Prověrka** | Modul / záznam roční prověrky BOZP |
| **Audit** | Modul / záznam auditu |
| **Kontrola** | Kontrolní bod, kontrola dodržování, SD portál „Kontroly“, datum „Kontrola do“ |
| **Revize** | Revize zařízení / dokumentu (technická nebo dokumentová) |
| **Revize posouzení rizik** | Záznam v Řízení rizik (dříve Přezkoumání opatření); není totéž co Revize opatření |
| **Revize opatření** | Způsob řešení nevyhovující kontrolní otázky v revizi posouzení rizik |

Nesmí se zaměňovat (např. „Generovat kontroly“ v modulu Prověrky).

### Další konzistentní termíny

| Preferovat | Nepoužívat synonymně |
|---|---|
| Zaměstnanec | Pracovník *(v UI, pokud není specifický kontext THP)* |
| Pracoviště | Místo výkonu práce *(kromě explicitní záložky)* |
| Kontrolní otázky pro revizi rizik | Navazující opatření / potřebná opatření *(u položek `required_measures`)* |
| Kontrolní otázka | Navazující opatření *(jednotné číslo u `required_measures`)* |
| Kontrolní otázky | Navazující opatření *(krátký název sloupce)*; dříve také Checklist přezkoumání |
| Nová kontrolní otázka | Nové navazující opatření |
| Úprava kontrolní otázky | Úprava navazujícího opatření |
| Revize posouzení rizik | Přezkoumání opatření |
| Nová revize | Nové přezkoumání |
| Provést revizi | Provést přezkoumání |
| Vytisknout kontrolní otázky | Vytisknout checklist |
| Opatření | Nápravné opatření / úkol *(pokud jde o finding measure)* |
| Souhrnné sdělení | Poznámka auditora / Komentář *(u nového režimu okruhu Auditů a Prověrek)* |

---

## 8. Validační hlášky

Jednotný styl, stručné konstatování:

- „Není vyplněno povinné pole.“
- „Není vybrán koordinátor.“
- „Schůzku nelze uzavřít.“
- „Nelze uložit pracovní úraz.“

Preferovat:

- **Není …** pro chybějící údaj
- **Nelze …** pro blokující podmínku

---

## 9. Potvrzovací dialogy

| Typ | Vzor |
|---|---|
| Potvrzení destruktivní akce | „Opravdu chcete …?“ / „Opravdu odebrat …?“ |
| Soft volba (otevřít existující) | „Chcete jej otevřít?“ *(přípustné)* |
| Chyba operace | „Nepodařilo se …“ |
| Úspěch | „Akce byla úspěšně dokončena.“ / „Změny byly uloženy.“ |

---

## 10. Checklist pro nové UI

Před merge ověřit:

- [ ] Záložky jsou krátké oblasti (ne věty)
- [ ] Skupiny jsou podstatná jména / témata
- [ ] Tlačítka odpovídají tabulce v §4
- [ ] Stavy odpovídají §6 (nebo výjimce s uloženou hodnotou)
- [ ] Fotografie / přílohy / prověrka / audit / kontrola / revize dle §7
- [ ] Potvrzení a validace dle §8–9
- [ ] Žádná změna DB / JSON / exportů / workflow

---

## 11. Příklady správného použití

```text
Záložky:     Spis | Oznámení | OOPP | Další skutečnosti
Skupiny:     Platné předpisy | Revize a zjevné závady | Přílohy
Tlačítka:    Přidat | Odebrat | Uložit | Uzavřít | Náhled | Tisk
Stavy:       Rozpracováno → Uzavřeno → Archivováno
Potvrzení:   Opravdu odebrat vybrané opatření?
Validace:    Není vyplněno povinné pole.
```
