# Manažer BOZP 4.2.1

Verze 4.2.1 navazuje na veřejné vydání 4.2.0. Datum vydání se doplní při zveřejnění. Linuxový AppImage a instalační program pro Windows se k tomuto textu připojí až jako soubory vydání.

### 🎬 Videonávody a ukázky programu

Na oficiálním YouTube kanálu najdete představení Manažera BOZP, ukázky jednotlivých modulů, návody k jejich používání i přehledy novinek.

**▶️ [Navštívit YouTube kanál Manažer BOZP](https://www.youtube.com/@ManazerBOZP)**

## Novinky

Změny od veřejné verze 4.2.0.

Koordinace BOZP

- Splněný úkol předání rizik se při dalším uložení plánovaného stavu bere jako existující vazba. Druhý úkol se nezaloží.
- Následné převzetí rizik má vlastní záznam, historii oprav a dialog. Původní dohoda o předání se nemění.
- Převzetí se promítne do úkolu a do stavu předání.
- Stejnou činnost dodavatele lze zapsat ve více oddělených termínech. Duplicita se odmítne jen při shodném zaměstnavateli, místě, názvu a obou datech.
- Dokument z katalogu rizik dodavatelů lze ke koordinaci připojit odkazem, bez kopie souboru. Příloha B ho vypíše spolu s následným převzetím.
- Příloha předaná při koordinaci a příloha následného převzetí se zapíší do katalogu odkazem na už uložený soubor. Oprava data u stejné přílohy se promítne jen do odpovídajícího dokumentu katalogu.

Řízení rizik

- Rizika dodavatelů jsou samostatná evidence firem a převzatých dokumentů. Název firmy lze doplnit z ARES.
- Seznam ukazuje jednu firmu na řádek. Dokumenty se spravují v detailu. Datum zpracování zůstává nezávislé na datu převzetí.
- Firmu v katalogu lze vyhledat podle IČO. Uložené IČO se při hledání nemění a nejednoznačná shoda firmu nepřiřadí.

Kniha úrazů

- Aktualizace záznamu po DPN se nezobrazí, pokud DPN nevznikla. Historicky vyplněné řádky zůstanou uložené a sekce se vrátí až po ukončení dodatečně vzniklé DPN.

Audity

- Text zjištění z předchozích auditů zůstává celý. Do přehledu se už nebere jen první řádek oříznutý na 120 znaků.
- Plánovaný audit se sám ukáže v Agendě. Jde o audit s datem, který ještě nebyl zahájen ani ukončen.
- Stejný plán je na pracovní ploše v Nadcházejících a v kalendáři v den auditu.
- Prošlý nezahájený audit se objeví v Připomínkách.
- Tyto plány se nepočítají do souhrnného počtu položek Po termínu.

Vyšetřování mimořádných událostí

- Spis má datum a čas vzniku události. U úrazu se při prvním uložení převezmou ze zdrojového záznamu. Starší spis se při otevření nepřepisuje a prázdný čas se nedoplňuje na půlnoc.
- Běžný čas se ukládá jako hodiny a minuty, čas zařízení včetně sekund. Neúplný nebo historický text zůstane beze změny a neblokuje uložení, dokud ho uživatel sám neupraví do neplatné podoby.
- Datum a čas téže události jsou na jednom řádku v oznámení, zajištění důkazů, milníku časové osy i u lékařské prohlídky.
- Záložka Přílohy na konci spisu ukazuje všechny přílohy vyšetřování jen ke čtení. Zařazení se bere z existující vazby nebo z předpony názvu. Soubory se nekopírují a záznamy příloh se nemění.
- U školení lze vyplnit platnost do. Prázdná hodnota zůstane prázdná. U zkoušek platnost beze změny znamená platnost bez časového omezení; rok 2999 se nepřepisuje.

Testy

- Po úspěšném uložení odpovědí papírového testu se sám otevře detail zkoušky.
- Výsledek Vyhověl(a) nebo Nevyhověl(a) je zvýrazněný.
- Detail vypíše chybně zodpovězené a nezodpovězené otázky. Když žádné nejsou, prázdný seznam se neukáže.
- Zrušené nebo neúspěšné uložení detail neotevře. Zkouška zůstane v původním stavu.

Ochrana databáze

- Před změnou databáze na verzi 4.2.1 se automaticky vytvoří záloha a ověří se její integrita.
- Když se zálohu nepodaří vytvořit nebo ověřit, migrace se nespustí a původní databáze zůstane beze změny.
