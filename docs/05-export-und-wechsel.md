# Export und Wechsel zu einem anderen Dienst (Stand 08.10.2026)

Vorgabe Patrick (08.10.2026): Ein späterer Wechsel z. B. zu Foxtag soll leicht möglich sein. Daher von Anfang an:
**jede Datenart lässt sich vollständig exportieren**, und es gibt einen Export **genau im Importformat von Foxtag**.

## 1. Foxtag-Importformate (aus dem Testkonto, Vorlagen `foxtag.io/import_templates/…xlsx`)

Reihenfolge beim Import in Foxtag: Kunden → Kontakte → Objekte → Anlagen → Komponenten (je Anlage) → Typen → Artikel
→ Aufträge → Artikelpositionen. `*` = Pflicht. Nummern müssen in Foxtag eindeutig sein und vorher existieren
(z. B. Objekt-Nummer beim Anlagenimport).

| Foxtag-Datei | Spalten | Quelle bei uns |
|---|---|---|
| Kunden | KUNDEN.NUMMER*, KUNDE.NAME*, ADRESSZEILE 1, ADRESSZEILE 2, PLZ, ORT, LAND, NOTIZ | kunde.nummer, name, strasse, zusatz, plz, ort, land, notiz_intern |
| Kontakte | NAME*, FIRMA, EMAIL, TELEFON, MOBIL, FAX, NOTIZ, KUNDE (Kundennummer) | kontakt.* |
| Objekte | KUNDE.NUMMER, OBJEKT.NAME, OBJEKT.NUMMER, ADRESSZEILE 1, ADRESSZEILE 2, PLZ, ORT, LAND | objekt.* |
| Anlagen | OBJEKT.NUMMER*, WARTUNGSANWENDUNG.NUMMER*, ANLAGE.NUMMER*, ANLAGE.NAME, TECHNIKER.NUMMER | anlage.*, Anlagenart → Nummer der Foxtag-Wartungsanwendung (vorher dort vergeben), nutzer.personalnummer |
| Komponenten Rauchwarnmelder | GRUPPE.NUMMER, GRUPPE.NAME, NUMMER*, SUB-NUMMER, TYP.NAME*, TYP.HERSTELLER, TYP.MODELL, STANDORT, SERIENNUMMER, QR-CODE, BAUJAHR, LABEL, LABEL2, LETZTE PRÜFUNG, INBETRIEBNAHME AM | gruppe.nummer, gruppe.bezeichnung (+ Bewohner), komponente.nummer, 0, komponententyp.*, raum, seriennummer, barcode, baujahr, Labels, letzte Prüfung, inbetriebnahme_am |
| Komponenten Türen mit FSA | wie RWM + ZULASSUNGSNUMMER | dto. + zulassungsnummer, SUB-NUMMER = Sub-Komponente |
| Komponenten-Typen | TYP.NAME*, TYP.HERSTELLER, TYP.MODELL, TYP.KATEGORIE* (Komponente/Sub-Komponente), TYP.LINK | komponententyp.* |
| Artikel | ARTIKEL.NUMMER*, BEZEICHNUNG*, GRUPPE, EINHEIT, SORTIERUNG | artikel.* |
| Aufträge | AUFTRAG.NUMMER, ANLAGE.NUMMER*, DATUM*, AUFTRAGSTYP.NUMMER*, TECHNIKER.NUMMER* (bis 3), AUFTRAG.HINWEISE | nur geplante/offene Aufträge |
| Artikelpositionen | ARTIKEL.NUMMER*, ANZAHL*, KOMMENTAR | position.* |

**Grenze:** Foxtag übernimmt je Melder nur das Datum der **letzten Prüfung**, nicht den ganzen Verlauf. Der Verlauf
(Prüfungen, Mängel, Unterschriften) wird daher zusätzlich als **PDF-Berichte je Auftrag** mitgegeben (in Foxtag als
Dateien an die Anlage hängbar) und bleibt bei uns im Archiv auf dem NAS (Aufbewahrung).

Alternativ zur Excel-Datei: Foxtag-REST-API (`api.foxtag.io/api/v1/public`, OpenAPI 1.6.0) mit Endpunkten für
Kunden, Kontakte, Objekte, Anlagen, Artikel, Aufträge, Labels – Komponenten dort nur über Inventar lesbar, Anlegen
per Excel-Import.

## 2. Folgen für unser Datenmodell (eingearbeitet in `03-datenmodell.md`)

- `komponente.sub_nummer` (0 = Hauptkomponente; bei Türen 1, 2 … für Feststellanlage, Magnet usw.).
- `komponente.labels` (beliebig viele; Export nimmt die ersten zwei).
- `nutzer.personalnummer` (Foxtag: TECHNIKER.NUMMER).
- Nummern für Kunde, Objekt, Anlage, Auftrag, Artikel sind **Pflicht und eindeutig** (Foxtag braucht sie als Schlüssel).
- `anlage.bezeichnung` und `gruppe.bezeichnung` getrennt von Bewohnername halten; Foxtag kennt nur GRUPPE.NAME →
  Export setzt „Bewohner, Lage“ zusammen (wie im Foxtag-Beispiel „Friedrich, 1.OG Mitte“).

## 3. Eigene Exporte (unabhängig von Foxtag)

- **Vollexport** (Verwaltung → Export): alle Tabellen als CSV (UTF-8, Semikolon) + JSON + alle Dateien (Fotos,
  Unterschriften, Berichte) als ZIP. Damit kann jeder andere Dienst oder ein Programmierer die Daten übernehmen.
- **Foxtag-Export:** je Datenart eine `.xlsx` genau in den Spalten oben, in Import-Reihenfolge nummeriert
  (`01_Kunden.xlsx` … `09_Artikelpositionen.xlsx`), Komponenten je Anlage eine Datei.
- Export enthält Kunden-/Mieterdaten → nur auf dem NAS ablegen, nicht per Mail/Chat; Datenübergabe an einen neuen
  Dienst erst nach AV-Vertrag mit diesem.

## 4. Umsetzung

Bausteine werden mit dem jeweiligen Modul gebaut (Kunden-Modul bringt seinen Export mit usw.). Test: Export in das
Foxtag-Testkonto importieren, solange es läuft (bis ca. 08.11.2026) – nur mit erfundenen Testdaten.
