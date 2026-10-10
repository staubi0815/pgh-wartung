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
| Kontakte | NAME*, FIRMA, EMAIL, TELEFON, MOBIL, FAX, NOTIZ, KUNDE (Kundennummer) | kontakt.*; gehört ein Kontakt zu mehreren Kunden, steht er je Kunde in einer eigenen Zeile (die Vorlage kennt nur einen Kunden je Zeile; im Foxtag entstehen dadurch Einträge je Kunde). Der Import verknüpft einen Kontakt mit identischen Angaben (Name, Firma, E-Mail, Telefon, Mobil, Fax) mit dem Kunden, statt ihn zu verdoppeln |
| Objekte | KUNDE.NUMMER, OBJEKT.NAME, OBJEKT.NUMMER, ADRESSZEILE 1, ADRESSZEILE 2, PLZ, ORT, LAND | objekt.* |
| Anlagen | OBJEKT.NUMMER*, WARTUNGSANWENDUNG.NUMMER*, ANLAGE.NUMMER*, ANLAGE.NAME, TECHNIKER.NUMMER | anlage.*, Anlagenart → Nummer der Foxtag-Wartungsanwendung (vorher dort vergeben), nutzer.personalnummer; TECHNIKER.NUMMER = Personalnummer des Stammtechnikers der Anlage (Export; Import setzt den Stammtechniker, wenn es einen Techniker mit dieser Personalnummer gibt, sonst Hinweis in der Vorschau) |
| Komponenten Rauchwarnmelder | GRUPPE.NUMMER, GRUPPE.NAME, NUMMER*, SUB-NUMMER, TYP.NAME*, TYP.HERSTELLER, TYP.MODELL, STANDORT, SERIENNUMMER, QR-CODE, BAUJAHR, LABEL, LABEL2, LETZTE PRÜFUNG, INBETRIEBNAHME AM | gruppe.nummer, gruppe.bezeichnung (+ Bewohner), komponente.nummer, 0, komponententyp.*, raum, seriennummer, barcode, baujahr, Labels, letzte Prüfung, inbetriebnahme_am. Hat mindestens ein Melder einer Anlage eine Zulassungsnummer, hängt der Export dieser Datei als letzte Spalte ZULASSUNGSNUMMER an (LIESMICH weist darauf hin; nicht in der RWM-Vorlage – lehnt Foxtag sie ab, Spalte löschen), sonst bleibt die Datei exakt wie die Vorlage |
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

## 5. Import (umgesetzt 09.10.2026)

Verwaltung → Excel-Import liest dieselben Vorlagen (`server/wartung/excel_import.py`): Kunden, Kontakte, Objekte,
Anlagen (WARTUNGSANWENDUNG.NUMMER = Importname der Anlagenart, z. B. „RWM“), Melder-Typen, Melder je Anlage.
Regeln: Vorschau = Probelauf mit vollständigem Zurückrollen; Übernehmen nur, wenn keine Zeile fehlerhaft ist;
vorhandene Nummern/Plätze werden übersprungen (nie überschrieben); GRUPPE.NAME „Bewohner, Lage“ wird getrennt;
Typen werden über Hersteller + Modell gefunden oder einmal angelegt. Noch nicht übernommen: Labels (die Foxtag-Vorlagen haben nur an Komponenten Label-Spalten, und die Komponenten-Labels gibt es bei uns noch nicht), Techniker-Nummer,
Sub-Komponenten (Türen). Getestet mit den Original-Vorlagen aus dem Foxtag-Testkonto (nur lokal, nicht im Repo).

## 6. Export (umgesetzt 09.10.2026)

Verwaltung → Export (`server/wartung/export.py`, Seite `server/wartung/web/export.py`), jeweils als ZIP:

- **Foxtag-Format:** `01_Kunden`, `02_Kontakte`, `03_Objekte`, `04_Anlagen`, `05_Komponenten-Typen_<Anlagenart>`,
  `06_Komponenten_<Anlagennummer>` und `07_Auftraege` als `.xlsx` (Namen wie die Punkte im Foxtag-Menü
  „Datenimport“, seit 10.10.2026), dazu `LIESMICH.txt` mit Reihenfolge, Menüpunkt je Datei und Hinweisen. Spalten kommen aus
  denselben Definitionen wie der Import (`excel_import.ARTEN`), Kopfzeilen sind identisch mit den Foxtag-Vorlagen.
  Nur gültiger Bestand (nicht gelöscht, Melder nur verbaut). Formate wie in den Vorlagen: Nummern als Zahl, Datum als
  Excel-Datum, LAND als Code; PLZ als Text (führende Null bleibt). WARTUNGSANWENDUNG.NUMMER = erster `import_namen`-
  Eintrag der Anlagenart („RWM“) – in Foxtag muss die Wartungsanwendung diese Nummer haben. Objekt-Anschrift = wirksame
  Anschrift; Kontakt-Funktion steht in der Notiz; GRUPPE.NAME = „Bewohner, Lage“. Text mit „=“ bleibt Text (keine
  Formel), Steuerzeichen werden weggelassen, gleiche Dateinamen bekommen einen Zusatz `_2`.
- **Vollexport:** `daten.json` (maßgeblich, alle Tabellen, auch gelöschte/ersetzte Datensätze und Änderungsprotokoll),
  `tabellen/<tabelle>.csv` (UTF-8 mit BOM, Semikolon; Formel-Text mit vorangestelltem `'`), `schema.sql`,
  `LIESMICH.txt`. Nicht enthalten: Tabelle `anmeldeversuch`, Spalten `*_hash`, `einladung_bis`, `sitzung_zaehler`.
  Eine neue Tabelle muss im Test bewusst als exportiert oder ausgenommen eingetragen werden.
- **Rechte:** Foxtag-Export braucht `export` + `stammdaten.lesen`; Vollexport zusätzlich `verwaltung.nutzer` +
  `verwaltung.protokoll` (enthält Nutzer und Protokoll) – Büro darf also den Foxtag-Export, den Vollexport nur die
  Administration. Kein Export zeigt mehr, als der Nutzer in der Oberfläche sehen darf.
- Jeder Export steht im Änderungsprotokoll (wer, wann, Umfang); Download nur per Formular mit CSRF-Merkmal.
- **Rundweg getestet:** Foxtag-Export → eigener Import in eine leere Datenbank ergibt dieselben Stammdaten.
  Bekannte Abweichungen: Typ-Bezeichnung wird beim Import aus dem Modell gebildet; einzeilige Felder fassen Zeilenumbrüche
  zu Leerzeichen zusammen; Notizen (Kunde, Kontakt, Auftragshinweise) behalten sie seit Migration 009/Schritt 7.
  Die Spalte ZULASSUNGSNUMMER (nur in der Türen-Vorlage) wird beim Import gelesen, falls vorhanden. Der RWM-Export hängt sie
  als letzte Spalte an, wenn mindestens ein Melder der Anlage eine Zulassungsnummer hat; sonst bleibt er im Format der
  RWM-Vorlage. **Probe-Import im Testkonto (10.10.2026):** Foxtag bietet „Zulassungsnummer“ in der Feldzuordnung an,
  übernimmt beide Probe-Melder und zeigt den Wert am Melder als „Zul.Nr.“.
- **Aufträge (09.10.2026):** `07_Auftraege.xlsx` mit den offenen Aufträgen (geplant/in Arbeit). AUFTRAGSTYP.NUMMER
  = Schlüssel der Auftragsart in Großbuchstaben (WARTUNG, INSTALLATION, NACHTERMIN, FERNINSPEKTION – in Foxtag so
  anlegen), TECHNIKER.NUMMER = Personalnummer (Verwaltung → Nutzer), höchstens drei; Uhrzeit steht als Datum mit
  Zeit in DATUM und zusätzlich als erste Zeile „Uhrzeit HH:MM Uhr“ in AUFTRAG.HINWEISE (Foxtag übernimmt aus DATUM
  nur den Tag, s. Probe-Import). Foxtag verlangt einen Techniker: Pool-Aufträge
  und fehlende Personalnummern meldet LIESMICH.txt. Umfang „ausgewählte Wohnungen“ ist in Foxtag nicht abbildbar.
  **Import** (Verwaltung → Excel-Import → Aufträge): gleiche Spalten; Auftragstyp als Nummer oder Name; leerer
  Techniker = Pool; Datum in der Vergangenheit erlaubt (Hinweis), damit offene Aufträge aus Foxtag übernommen
  werden können; Hilfespalte der Foxtag-Vorlage wird übergangen. Rundweg Export → Import getestet.
  Eine Hinweiszeile „Uhrzeit HH:MM Uhr“ am Anfang wird wieder zur Uhrzeit (Zeit im DATUM hat Vorrang).
- **Korrektur 09.10.2026:** Kontakte (`KUNDE`) und Objekte (`KUNDE.NUMMER`, `OBJEKT.NAME`) hatten Sternchen, die
  die Foxtag-Vorlage nicht hat (unser Import verlangt die Spalten, Foxtag nicht). Jetzt trennt `Importart` „Pflicht
  bei uns“ von „Pflicht laut Foxtag“; ein Test vergleicht alle Kopfzeilen mit den Vorlagen.
- **Probe-Import:** `server/werkzeuge/foxtag_probe.py` legt erfundene Daten (Präfix „PT-“) in einer leeren Datenbank
  an und schreibt den Export. Im Testkonto vorher Nummern vergeben: Wartungsanwendung Rauchwarnmelder „RWM“,
  Auftragstypen Wartungstermin „WARTUNG“, Installationstermin „INSTALLATION“, eigener Nutzer Personalnummer
  „PT-TECH-1“ (Stand 09.10.: dort alle ohne Nummer).
- **Probe-Import im Testkonto (10.10.2026, Patrick per Hand, Nachtest per Skript):** Kunden 2/2, Objekte 2/2,
  Anlagen 2/2, Melder 5 + 2, Aufträge 2/2 übernommen. Erkenntnisse (stehen jetzt im LIESMICH):
  - Bezeichnungen waren unklar („05_Typen“ statt „Komponenten-Typen“) → Dateinamen wie das Foxtag-Menü, je Datei
    der Menüpunkt im LIESMICH. Komponenten-Typen fragen nach der Wartungsanwendung, Komponenten nach der Anlage.
  - Typen: Die Melder wurden vor den Typen eingelesen. Foxtag legte die fehlenden Typen dabei selbst an (Name aus
    TYP.NAME, **ohne Prüfintervall**); der Typen-Import danach meldete „nicht eindeutig“ (harmlos). Also 05 vor 06
    und nach dem Import die Prüfintervalle der neuen Typen in Foxtag eintragen.
  - Kontakt mit `@example.org` abgelehnt („E-Mail ist keine valide E-Mail Adresse“); ohne E-Mail nachimportiert:
    angekommen, mit Kunde verknüpft. Probe-Skript legt den Kontakt jetzt ohne E-Mail an.
  - Aufträge: Foxtag liest DATUM als UTC-Zeit, speichert aber nur den Tag als ganztägigen Auftrag (planned_at
    00:00, `all_day`). Der Tag stimmt. Nachtest PT-A-3: Hinweis „Uhrzeit 08:30 Uhr“ kommt mit Zeilenumbruch an.
  - Abgebrochene oder liegengebliebene Uploads bleiben in der Importliste als „in Vorbereitung“ stehen (harmlos).
  - Probedaten (Präfix PT-) bleiben im Testkonto; es läuft ca. 08.11.2026 aus.
- **Offen:** Dateien (Fotos, Unterschriften, Berichte) und Artikel kommen mit den jeweiligen Modulen.
