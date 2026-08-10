# UX-DIALOG-BUTTONS-STANDARD-1

## Jednotná pravidla potvrzovacích a ukládacích tlačítek v dialozích

Tento dokument je závazný pro **spodní lištu dialogů** (editory, výběrová okna,
potvrzení neuložených změn) v Manažeru BOZP.

Navazuje na:

- `UX_DIALOG_BUTTONS_AUDIT_1` (inventura variant; canvas / audit fáze)
- `UI_KOMPONENTY.md` (§ spodní lišta, validace Uložit / Uzavřít)
- `UX_NAZVOSLOVI.md`
- existující infrastrukturu `core/widgets/editor_dialog_controller.py`
  a `core/widgets/knowledge_editor_actions.py`

**Rozsah:** footer dialogů a editorů.  
**Neplatí** pro horní lištu seznamů (`UX_STANDARD_003.md`) ani pro akce
uvnitř formuláře (Přidat řádek, Odebrat, …).

**V této verzi standardu se nemění aplikační kód.**  
Zavádění probíhá později: jeden modul = jeden commit.

---

## 1. Nový záznam

| Tlačítka | Význam |
|---|---|
| **Uložit** | Uloží nový záznam a **zavře** dialog |
| **Zrušit** | Zavře dialog **bez** vytvoření záznamu |

```
[Uložit]  [Zrušit]
```

---

## 2. Editace existujícího záznamu

| Tlačítka | Význam |
|---|---|
| **Uložit** | Uloží změny |
| **Zavřít** | Zavře dialog |

```
[Uložit]  [Zavřít]
```

### Neuložené změny

Pokud jsou neuložené změny, **Zavřít**, **X** i **Escape** musí vyvolat
dirty prompt (§ 5).

Poznámka k chování **Uložit** u modalního editoru typu A:
po úspěšném uložení se dialog typicky zavře (stejně jako u nového záznamu).
Pokud editor zůstává otevřený, jde o typ D (§ 4), ne o typ A.

---

## 3. Výběrový dialog

| Tlačítka | Význam |
|---|---|
| **Použít** | Potvrdí výběr a zavře dialog |
| **Zavřít** | Zavře bez použití výběru |

```
[Použít]  [Zavřít]
```

Příklady:

- výběr šablony
- výběr položky
- výběr záznamu

### Nepoužívat pro stejný význam

Pokud není konkrétní důvod, nepoužívat:

- OK
- Vybrat
- Potvrdit výběr

Výjimka je přípustná jen tam, kde text musí přesněji popsat akci
(např. výběr fotografie: „Vybrat fotografii/e“) — Reject zůstává **Zavřít**
nebo **Zrušit** podle kontextu otevření.

---

## 4. Velký editor / stay-open editor

Použít **jen** tam, kde průběžné ukládání skutečně dává smysl
(uživatel pokračuje v práci v otevřeném editoru).

| Tlačítka | Význam |
|---|---|
| **Použít** | Uloží změny; editor **zůstane otevřený** |
| **Uložit a zavřít** | Uloží změny a editor **zavře** |
| **Zavřít** | Zavře editor; při neuložených změnách dirty prompt (§ 5) |

```
[Použít]  [Uložit a zavřít]  [Zavřít]
```

Tento vzor odpovídá footeru metodik (Audity / Prověrky) a obdobným
rozsáhlým editorům se stavem.

Nevynucovat u malých modalních formulářů typu A.

---

## 5. Dirty prompt

Při zavření editoru s neuloženými změnami:

| Tlačítka | Význam |
|---|---|
| **Uložit** | Uložit a zavřít |
| **Neukládat** | Zahodit změny a zavřít |
| **Zrušit** | Vrátit se do editoru (nezavírat) |

```
[Uložit]  [Neukládat]  [Zrušit]
```

Platí pro:

- **Zavřít**
- **X** (zavření okna)
- **Escape**

Text otázky: „Uložit změny před zavřením?“  
(shodně s `EDITOR_UNSAVED_PROMPT` / knowledge helper).

---

## 6. Lifecycle akce

**Nezaměňovat:**

| Pojem | Význam |
|---|---|
| **Zavřít** | Zavřít dialog / editor |
| **Uzavřít** | Změnit stav záznamu (lifecycle), např. uzavření spisu |

Tyto pojmy **nesjednocovat**.  
Lifecycle tlačítko může být na spodní liště vedle dialogových akcí
(viz `UI_KOMPONENTY.md`), ale musí mít vlastní jasný význam.

---

## 7. Co standard neznamená

Standard **neznamená**:

- že všechny dialogy musí mít stejná tlačítka
- že se mají upravit všechny dialogy najednou
- že se má měnit funkčnost modulů

Znamená:

- **stejný typ dialogu** = stejné labely a stejné chování
- úpravy jen skutečných nekonzistencí vůči tomuto typu

---

## 8. Zavádění

Aplikovat postupně:

**jeden modul = jeden commit**

Neprovádět globální hromadnou změnu.

Při každém modulu:

1. projít všechny jeho dialogy
2. určit typ podle tohoto standardu (A / B / C dirty / D / …)
3. upravit jen skutečné nekonzistence
4. doplnit dirty prompt tam, kde může dojít ke ztrátě změn
5. zachovat funkčnost

Preferovat existující helpery:

- `create_save_cancel_box` / `EditorDialogController` (typ A, dirty)
- `create_knowledge_editor_footer` (typ D)
- výběrový footer **Použít | Zavřít** (typ B)

---

## 9. Priorita zavádění

Začít velkými editory bez jednotné ochrany změn:

1. Audity
2. Prověrky BOZP
3. Kniha úrazů
4. Vyšetřování MU
5. Právní požadavky

Potom pokračovat ostatními moduly podle levého menu.

---

## 10. Rychlá mapa typů

| Typ | Tlačítka | Kdy |
|---|---|---|
| A – nový záznam | Uložit \| Zrušit | Vytvoření; Uložit zavře |
| A – editace | Uložit \| Zavřít | Úprava; dirty při Zavřít/X/Esc |
| B – výběr | Použít \| Zavřít | Výběr položky / šablony / záznamu |
| D – stay-open | Použít \| Uložit a zavřít \| Zavřít | Průběžné ukládání dává smysl |
| Dirty prompt | Uložit \| Neukládat \| Zrušit | Neuložené změny při zavírání |

---

## Související dokumenty

- `UI_KOMPONENTY.md` — spodní lišta, Náhled, Uzavřít (lifecycle)
- `UX_NAZVOSLOVI.md` — jednotné názvy
- `UX_STANDARD_003.md` — horní lišta seznamů (jiný rozsah)
- `ARCHITEKTURA_MODULU.md` — struktura modulů
