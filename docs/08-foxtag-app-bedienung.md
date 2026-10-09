# Foxtag 2 – Bedienung der App (Beobachtungen aus dem Testkonto)

Stand: 09.10.2026. Quelle: Foxtag 2, Version 111.0.6, Pixel-Handy, **normales Bedienen** der App mit dem Testkonto
(erfundene Demo-Daten, ein Testauftrag). Bildschirmfotos liegen nur lokal (nicht im Repo, Grundsatz 7). Hier
steht der **Ablauf in eigenen Worten** als Vorlage für unsere PWA – Gestaltung und Texte machen wir selbst.

Ergänzt `docs/07` (technischer Aufbau). Noch offen: Scan, Ergebnis-Buchung, Tauschen, Unterschriften, Bericht,
Flugmodus, zwei Geräte (siehe unten „Noch zu prüfen“).

## 1. Navigation

- Hauptmenü (Seitenleiste): Aufträge · Karte · Daten synchronisieren · Einstellungen · Firma wechseln · Abmelden.
  Kopf: Name des Nutzers, Firma, App-Version.
- Einstellungen: verbundener Server, **Anzahl lokaler Datensätze + Meldung „alle synchronisiert“**,
  „Lokale Daten löschen und neu synchronisieren“, Diagnosedaten senden, Darstellung hell/dunkel/automatisch.
- Auftragsliste: drei Reiter **Heute / Demnächst / Erledigt**, Suche, „+“ (nur Auftrag für bestehenden oder neuen
  Kunden – Kunden, Objekte, Anlagen legt man im Web an). Karte: Datum, Uhrzeit, Status-Plakette, Auftragsart + Nr.,
  Kunde, Adresse, Anlagenart, Karten-Knopf.

## 2. Auftragsseite

Kopf: Auftragsart, Kunde, Nummer, Statusplakette (geplant / Auftrag läuft / erledigt).
Kacheln: Termin (+ „13 Melder geplant (Ganze Anlage)“) · Anlage · Standort (mit Karten-Knopf) · Ansprechpartner vor
Ort (Telefon, Handy) · Hinweise (Freitext fürs Team, getrennt von „allgemeinen Hinweisen“ der Anlage) · Dateien.
Unten ein großer Hauptknopf, der zum Status passt (hier „Auftrag fortsetzen“; bei erledigten „Auftrag wieder
öffnen“). Dreipunkt-Menü: Label, Datum bearbeiten, Auftrag kopieren, im Kalender speichern, Kontakte bearbeiten,
Datei hochladen. Seitenmenü: Anlage ansehen, Störungen (Zähler), interne Notizen (Zähler), Dateien (Zähler), Berichte.

## 3. Der Auftrag als Schrittfolge (Kernidee)

Nummerierte Karten mit Fortschrittsbalken und Zähler „x / n“:

1. Vorarbeiten (Aufgaben vor der Prüfung, z. B. Mieter benachrichtigen)
2. **Prüfungen dokumentieren** (13 Melder) – Knöpfe **Prüfliste** und **Scan**
3. Nacharbeiten (Aufgaben, die aus Mängeln entstehen; hier 0 / 4)
4. Material und Leistungen (Artikelpositionen erfassen)
5. Fotos
6. Auftragsdatum überprüfen (mit „bearbeiten“)
7. Unterschrift Techniker
8. Kundenunterschrift
Darunter: **Berichtsvorschau laden** und **Auftrag beenden**.

→ Für uns: dieselbe Reihenfolge ist sinnvoll; wir hängen die Mieter-Unterschrift **je Wohnung** (Grundsatz 5/8 in
docs/07) in den Prüfschritt statt einer einzigen Kundenunterschrift am Ende.

## 4. Prüfliste

- Reiter **Offen n / Erledigt n**, Filter „Geplant“ und „Alle Gruppen“, Suche.
- Melder **nach Gruppe (Wohnung) gegliedert**; jede Karte: Platz („1/1 Flur EG“), Typ, **Ampelpunkt**,
  Seriennummer, Label (z. B. A/B), Dreipunkt-Menü, Knöpfe **Mängel**, **Prüfdaten**, und breit **Ergebnis OK**.
- **Prüfdaten erfassen** (Checkliste je Melder, Anlagenart Rauchwarnmelder): Montageort geprüft ·
  Eintrittsöffnungen geprüft · Beschädigungen geprüft · Farb-Übermalungen geprüft · Testknopf gedrückt ·
  Alarmton geprüft · Freitext „geänderte Raumnutzung“. (Abgleich mit unserer `rauchwarnmelder.toml`: deckt sich
  im Kern mit DIN 14676-1 – Abnahme der Liste durch Patrick nach dem Lehrgang.)
- **Mängel**: Liste von 12 Störungstypen mit Filterfeld – Alarmton löst nicht aus · Bauliche Veränderungen ·
  Beschriftung fehlt · Eintrittsöffnungen fehlerhaft · Farb-Übermalungen fehlerhaft · Melder defekt · Melder nicht
  auffindbar · Melder verschmutzt · Melder wurde ausgetauscht · Sonstiger Mangel · Testknopf fehlerhaft · Wurde in
  anderen Raum verlegt. Danach „Störung anlegen“: Typ (Pflicht), Schweregrad (niedrig / normal / schwerwiegend /
  Hinweis), Status (offen / geschlossen), Foto, Beschreibung.
- **Melder-Menü**: Details ansehen · Bearbeiten · **Tauschen** · **Außer Betrieb nehmen** · Sub-Komponente
  hinzufügen · Foxtag-ID (Funketikett) hinzufügen · Störungen anzeigen.
- Formulare fragen beim Verlassen **„Änderungen speichern? – Nein, verwerfen / Ja, speichern“**.

## 5. Was wir übernehmen / anders machen

- Übernehmen: Schrittfolge mit Zählern; Prüfliste je Wohnung; Ergebnis mit **einem** Tipp (OK) und Ausnahmen über
  „Mängel“; Mangeltyp-Liste mit Filter; Schweregrad; Verwerfen-Rückfrage; Sync-Stand sichtbar in den Einstellungen.
- Anders: Mangeltypen und Checkpunkte kommen aus unserer Anlagenart-Konfiguration (`rauchwarnmelder.toml`), nicht
  aus einer Datenbank-Einstellung; Austausch/Außerbetriebnahme sind bei uns Vorgänge im Lebenslauf (docs/05).

## 6. Noch zu prüfen (nächste Schritte)

Ergebnis OK buchen (was ändert sich, Rückgängig?) · Scan · Tauschen-Dialog · Nacharbeiten · Fotos · Unterschriften ·
Bericht · **Flugmodus** (Verhalten offline, Anzeige wartender Daten) · **zwei Geräte** am selben Auftrag
(Handy + Browser/Tablet) · Konflikte.
