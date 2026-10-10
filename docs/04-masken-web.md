# Stufe 2b: Webseite (Büro) – Seiten und Masken (Entwurf, Stand 08.10.2026)

Grundlage: `03-datenmodell.md`, `server/wartung/konfig/anlagenarten/rauchwarnmelder.toml`. Ziel: so wenig Seiten wie nötig,
alles in höchstens zwei Klicks erreichbar. Gestaltung eigenständig (PGH-Farben der Website), nicht wie Foxtag.

## Menü

`Start · Kunden · Anlagen · Aufträge · Mängel · Auswertungen · Verwaltung` + Suche (Kunde, Adresse, Anlage,
Auftrag, Seriennummer, Funk-ID) + Anzeige „Abgleich: Tablet 1 vor 5 min“.

## 1. Start (Cockpit)

| Kachel | Inhalt |
|---|---|
| Heute / diese Woche | geplante Aufträge mit Adresse, Techniker, Status |
| Fällig | Anlagen mit Ampel rot/gelb (Prüfung), Melder mit Austausch in den nächsten 6 Monaten |
| Offene Mängel | Anzahl je Schweregrad, Klick → Mängelliste |
| Nachtermine | Wohnungen „nicht angetroffen“ ohne neuen Termin |
| Abzurechnen | abgeschlossene Aufträge ohne Rechnung |
| Konflikte | Abgleich-Konflikte, die das Büro entscheiden muss |

## 2. Kunden

**Liste:** Nummer, Name, Art, Ort, Anzahl Anlagen, nächste Fälligkeit. Filter: Art, Label. Knopf „Kunde anlegen“.

**Kunde (Detail, Reiter):**
- *Daten:* Art, Name, Zusatz, Anschrift, Telefon, E-Mail, Rechnungs-E-Mail, Lieferantennummer, interne Notiz, Labels.
- *Kontakte:* Liste + „Kontakt anlegen“ (Name, Funktion, Telefon, Mobil, E-Mail).
- *Objekte und Anlagen:* Baum Objekt → Anlagen mit Ampel; „Objekt anlegen“.
- *Aufträge / Rechnungen:* Verlauf.

## 3. Objekt (Maske, aus Kunde heraus)

Bezeichnung, Anschrift (oder „wie Kunde“), Zugangshinweise, Notiz; Karte mit Position (Klick setzt Punkt).
Darunter Anlagen des Objekts + „Anlage anlegen“ (Anlagenart wählen: Rauchwarnmelder; später Türen).

## 4. Anlagen

**Liste:** Nummer, Objekt/Adresse, Kunde, Anlagenart, Anzahl Melder, nächste Prüfung (Ampel), nächster Austausch,
nächster Auftrag. Filter: Fälligkeit (überfällig / 30 Tage / Zeitraum), Austausch fällig, Techniker, Label.
Mehrfachauswahl → „Aufträge planen“.

**Anlage (Detail, Reiter):**
- *Übersicht:* Kopf mit Kunde, Objekt, Ampel, nächstem Auftrag; Hinweise für den Techniker; Ansprechpartner vor Ort,
  Berichtsempfänger, Terminankündigung (Kontakte zuordnen); Verfahren A/B/C; Einzelnachweis ja/nein; passiv.
- *Wohnungen und Melder* (Hauptarbeitsfläche):
  - je Wohnung ein aufklappbarer Block: „Whg 43 · 1. OG links · Bewohner“ · Anzahl Melder · letzter Besuch.
  - Tabelle je Wohnung: Nr. (43/1), Raum, Typ, Seriennummer, Funk-ID, Baujahr, nächste Prüfung, Austausch, Status.
  - Knöpfe: „Wohnung anlegen“, „Melder anlegen“, „Mehrere Melder anlegen“ (z. B. 3 Stück: Flur, Schlafen, Kind),
    „Wohnung kopieren“ (gleicher Grundriss), Import/Export Excel.
  - Melder-Maske (Dialog): Typ (Katalog, Suche nach Hersteller/Modell), Raum (Liste + frei), Raumart (vorbelegt
    aus Raum), Seriennummer, Funk-ID, Barcode, Baujahr, Inbetriebnahme; Reiter „Verlauf“ (Prüfungen, Mängel,
    Maßnahmen, Änderungen); Aktion „Austauschen“, „Ausbauen“.
- *Aufträge:* Liste aller Aufträge der Anlage, „Auftrag planen“.
- *Mängel:* offene/erledigte Mängel der Anlage.
- *Dateien und Notizen:* Pläne, Fotos, Übergabeprotokolle.
- *Verlauf:* Prüfverlauf je Jahr (für Nachweis gegenüber Verwaltung/Versicherung).

## 5. Aufträge

**Umgesetzt 09.10.2026 (Baustein 3):** Auftrag planen aus der Anlage (Techniker mehrfach oder Pool, Umfang ganze
Anlage oder Wohnungen), Auftragsseite mit Status-Knöpfen, Verlauf und Verschieben mit Grund, Liste mit Filtern und
Wochenansicht, Sammelplanung aus der Anlagenliste, Start-Cockpit. Techniker sehen eigene und Pool-Aufträge. Noch
offen (mit den Prüfungen, Baustein 4/5): Fortschritt je Wohnung, Material, Bericht, Terminankündigung, Rechnung,
Mängel einplanen. Ursprüngliche Planung:

**Liste/Kalender:** Umschalter Liste ↔ Wochenkalender. Filter: Zeitraum, Status, Techniker, Auftragsart.

**Auftrag planen (Dialog):** Anlage, Auftragsart, Datum/Uhrzeit (ganztägig), Techniker (einer/mehrere) oder Pool,
Umfang (ganze Anlage / Auswahl Wohnungen), offene Mängel einplanen (Liste zum Anhaken), Hinweise.
Rechts: Kurzinfo Anlage (Adresse, Melderzahl, Fälligkeit, letzte Aufträge).

**Auftrag (Detail):**
- Status mit Knöpfen (planen → angekündigt → aktiv → abgeschlossen → abgerechnet; stornieren/verschieben).
- *Terminankündigung:* Vorschau Mail an Verwaltung + Aushang für das Treppenhaus (PDF zum Drucken).
- *Fortschritt:* je Wohnung erledigt / nicht angetroffen / offen, je Melder Ergebnis (live, sobald Tablets abgleichen).
- *Material und Leistungen:* Positionen (Artikel, Menge) – vorbelegt aus Maßnahmen (z. B. Austausch → Melder + Arbeit).
- *Bericht:* Vorschau, „Bericht erzeugen“ (PDF aufs NAS), Versand an Berichtsempfänger (nur nach Freigabe Patrick).
- *Rechnung:* „Rechnungsentwurf erzeugen“ → übergibt Positionen an `dokument.py` im Büro-Repo (Entwurf, Freigabe wie
  bisher); Rechnungsnummer wird zurückgeschrieben.

## 6. Mängel

Liste: Anlage, Wohnung/Melder, Mangeltyp, Schweregrad, Status, seit, Zielauftrag. Filter: Status, Schweregrad,
Kunde. Aktionen: Status ändern (mit Begründung), in Auftrag einplanen, als „kein Mangel“ schließen.

## 7. Auswertungen

- Prüffortschritt je Jahr (geprüft / offen / nicht angetroffen), je Kunde.
- Austauschvorschau (Melder je Jahr bis 10 Jahre voraus – Umsatzplanung).
- Material und Leistungen je Zeitraum.
- Meldertypen im Bestand (z. B. „alle Ei650 mit Baujahr 2016“ – für Rückrufe).

## 8. Verwaltung

Firma (Name, Logo, Nummernkreise, Berichtsfußzeile) · Nutzer und Rollen · Geräte (freischalten/sperren, letzter
Abgleich) · Meldertypen (Katalog) · Artikel und Preise · Kontakte · Labels · Vorlagen (Ankündigung, Aushang, Mail-
Texte) · Import (Excel: Kunden, Objekte, Anlagen, Wohnungen/Melder) · Export (Vollexport, Foxtag-Format; siehe
docs/05 Abschnitt 6) · Abgleich-Konflikte · Protokoll (Änderungen).

## 9. Berechtigungen

Umgesetzt 08.10.2026 (Migration 002): **Einzelrechte** (feste Liste in `server/wartung/rechte.py`, 23 Rechte in den
Bereichen Webseite, Daten, Verwaltung, App) und **Rollen als Bündel**; ein Nutzer kann mehrere Rollen haben.
Seiten prüfen nur Rechte. Übersicht als Matrix unter Verwaltung → Rollen und Rechte.

| Standardrolle | darf |
|---|---|
| Administration | alles, auch künftige Rechte; fest, nicht änderbar |
| Planen und Daten pflegen (Kennung buero) | Stammdaten, Aufträge, Mängel, Berichte, Rechnungsentwürfe, Katalog, Nutzer verwalten, Import, Export im Foxtag-Format; nicht in die App, keine Auswertungen |
| Techniker | App (Aufträge, Melder vor Ort, Fotos); Webseite nur eigene Aufträge |
| Techniker ohne Webzugang | wie Techniker, ohne Webseite |

Schutzregeln: Rollen/Rechte nur vergeben oder entziehen, die man selbst hat; Administration nur durch
Administratoren; Nutzer mit mehr Rechten als man selbst nicht bearbeitbar; eigenes Konto nicht deaktivierbar, eigene
Administration nicht entfernbar; immer mindestens ein aktiver Administrator. Rechteänderungen wirken sofort.
Notfall: `python -m wartung admin-einladen` auf dem Server. Vergleich mit Foxtag: `docs/06`.

## 10. Reihenfolge der Umsetzung

1. Grundgerüst + Anmeldung + Verwaltung Nutzer/Firma
2. Kunden, Objekte, Anlagen, Wohnungen/Melder inkl. Excel-Import (damit Bestand erfasst werden kann)
3. Aufträge planen + Fälligkeiten/Ampel + Start-Cockpit
4. App (Prüfablauf offline) + Abgleich
5. Bericht-PDF, Terminankündigung/Aushang, Rechnungsübergabe
6. Mängel, Auswertungen, Ferninspektion
