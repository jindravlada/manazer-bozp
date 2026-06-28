# Opatření - vyžaduje kontrolu účinnosti

Nové pole:
- requires_verification (ANO/NE)

Výchozí hodnoty:
- Ruční opatření: NE
- Úraz: ANO
- Audit: ANO
- Prověrka: ANO
- Kontrola: ANO

Logika:
- NE -> po splnění je stav rovnou Ukončeno.
- ANO -> po splnění vznikne 'Splněno - čeká na kontrolu', nastaví se Kontrola do = +15 dní.
- Ukončeno až po vyplnění:
    - Datum kontroly
    - Kontroloval
