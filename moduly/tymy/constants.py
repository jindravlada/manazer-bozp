MODULE_KEY = "tymy"

TEAM_TYPES_CATALOG_PATH = "tymy/typy_tymu.json"
TEAM_ROLES_CATALOG_PATH = "tymy/role_v_tymu.json"

DEFAULT_TEAM_TYPES: tuple[dict, ...] = (
    {
        "id": "proverkova_komise",
        "nazev": "Prověrková komise",
        "popis": "Tým pro provádění prověrek BOZP.",
        "poradi": 10,
        "aktivni": True,
    },
    {
        "id": "audit",
        "nazev": "Audit",
        "popis": "Tým pro interní nebo externí audit.",
        "poradi": 20,
        "aktivni": True,
    },
    {
        "id": "vysetrovaci_tym",
        "nazev": "Vyšetřovací tým",
        "popis": "Tým pro šetření pracovních úrazů a mimořádných událostí.",
        "poradi": 30,
        "aktivni": True,
    },
    {
        "id": "havarijni_tym",
        "nazev": "Havarijní tým",
        "popis": "Tým pro řešení havarijních a mimořádných situací.",
        "poradi": 40,
        "aktivni": True,
    },
)

DEFAULT_TEAM_ROLES: tuple[dict, ...] = (
    {
        "id": "vedouci_tymu",
        "nazev": "Vedoucí týmu",
        "popis": "Odpovědný vedoucí týmu.",
        "poradi": 10,
        "aktivni": True,
    },
    {
        "id": "clen",
        "nazev": "Člen",
        "popis": "Řádný člen týmu.",
        "poradi": 20,
        "aktivni": True,
    },
    {
        "id": "zapisovatel",
        "nazev": "Zapisovatel",
        "popis": "Osoba vedoucí záznam z činnosti týmu.",
        "poradi": 30,
        "aktivni": True,
    },
    {
        "id": "prizvany_odbornik",
        "nazev": "Přizvaný odborník",
        "popis": "Externí nebo interní odborník přizvaný k činnosti týmu.",
        "poradi": 40,
        "aktivni": True,
    },
    {
        "id": "pozorovatel",
        "nazev": "Pozorovatel",
        "popis": "Osoba bez rozhodovací pravomoci, účastní se jako pozorovatel.",
        "poradi": 50,
        "aktivni": True,
    },
)
