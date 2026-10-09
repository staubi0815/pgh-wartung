# Foxtag 2 – Bedienung der App (Beobachtungen aus dem Testkonto)

Stand: 09.10.2026. Quelle: Foxtag 2, Version 111.0.6, Pixel-Handy, **normales Bedienen** der App mit dem Testkonto
(erfundene Demo-Daten, ein Testauftrag). Bildschirmfotos liegen nur lokal (nicht im Repo, Grundsatz 7). Hier
steht der **Ablauf in eigenen Worten** als Vorlage für unsere PWA – Gestaltung und Texte machen wir selbst.

Ergänzt `docs/07` (technischer Aufbau). Noch offen: Scan, Fotos, Auftrag beenden,
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

## 4a. Weitere Beobachtungen (Stand 09.10.2026, Testauftrag)

- **Ergebnis OK** bucht mit **einem Tipp sofort**: keine Rückfrage, auch ohne ausgefüllte Prüfdaten. Der Melder wandert
  in den Reiter „Erledigt“ (Zeitstempel mit Sekunden, Ergebnis, Knopf **Rückgängig**, Sortierknopf). Rückgängig
  wirkt ebenfalls sofort ohne Rückfrage; der Melder steht wieder unter „Offen“.
- **Tauschen** (Melder-Menü): Hinweis „tauscht aus und schließt alle offenen Störungen“. Zwei Abschnitte:
  Außerbetriebnahme (Grund, optional) und Inbetriebnahme des neuen Melders (Typ*, Seriennummer mit Scan,
  Funketikett-ID mit Scan, Baujahr, Zulassungsnummer). Knöpfe „Tauschen“ / „Abbrechen“.
- **Nacharbeiten** ist ein Abschlussformular: Prüfbescheinigung (zwei Haken: Überprüfung nach DIN 14676 /
  durch ausgebildete Fachkraft nach DIN 14676), „Mängel wurden vor Ort behoben“ (Ja / Nein / n. v.),
  Freitext „Weitere Arbeiten“. Zurück ohne Speichern kam ohne Rückfrage.
- **Material und Leistungen**: Artikelkatalog aus dem Web (Nummer, Kategorie wie Anfahrt/Arbeitszeit, Ersatzteile,
  Verbrauchsmaterial, Einheit), Filter, Mehrfachauswahl, neuer Artikel direkt anlegbar.
- **Unterschriften** (Techniker, Kunde): Zeichenfläche mit „Löschen“, Datum, Name vorbefüllt (Techniker = Nutzer,
  Kunde = Ansprechpartner), Haken zum Übernehmen. Eine Unterschrift je Auftrag.
- **Berichtsvorschau**: PDF „Wartungsbericht <Anlagenart>“ mit Berichtsdatum, Auftrags- und Kundennummer, Kasten
  Kunde / Standort / Durchgeführt von, Wasserzeichen „Vorschau“, Teilen-Knopf.
- Fotos: Kamerafläche je Auftrag (nicht ausprobiert).

Folgerungen für uns: (1) Prüfergebnis „OK“ mit einem Tipp **und** Rückgängig sind für die Praxis gut, wir buchen
aber trotzdem die Pflicht-Checkpunkte der Anlagenart mit (nicht optional wie hier). (2) Die Haken „Fachkraft nach
DIN 14676“ setzen wir erst nach dem Lehrgang (KW 42) frei. (3) Mieter-Unterschrift je Wohnung bleibt unser
Mehrwert gegenüber Foxtag (eine Unterschrift je Auftrag).

## 5. Was wir übernehmen / anders machen

- Übernehmen: Schrittfolge mit Zählern; Prüfliste je Wohnung; Ergebnis mit **einem** Tipp (OK) und Ausnahmen über
  „Mängel“; Mangeltyp-Liste mit Filter; Schweregrad; Verwerfen-Rückfrage; Sync-Stand sichtbar in den Einstellungen.
- Anders: Mangeltypen und Checkpunkte kommen aus unserer Anlagenart-Konfiguration (`rauchwarnmelder.toml`), nicht
  aus einer Datenbank-Einstellung; Austausch/Außerbetriebnahme sind bei uns Vorgänge im Lebenslauf (docs/05).

## 6. Noch zu prüfen (nächste Schritte)

**Offline-Test, Methode (erprobt 09.10.2026, Test selbst verschoben):** Android-eigene Netzsperre nur für die App,
per adb: `cmd connectivity set-chain3-enabled true` und `cmd connectivity set-package-networking-enabled false
app.foxtag.service`; zurück mit `… enabled true app.foxtag.service` und `set-chain3-enabled false`. Wirkt auf WLAN
und Mobilfunk, andere Apps und adb bleiben online, kein Eingriff in FritzBox/AdGuard/Proxmox. (AdGuard-Sperre wäre
hausweit und würde durch Umschalten auf Mobilfunk umgangen; die Proxmox-Firewall sieht den WLAN-Verkehr nicht.)


Scan · Fotos · Auftrag beenden (und Bericht danach) · **Flugmodus** (Verhalten offline, Anzeige wartender Daten) · **zwei Geräte** am selben Auftrag
(Handy + Browser/Tablet) · Konflikte.
