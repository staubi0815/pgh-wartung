# Stufe 2a: Datenmodell im Detail (Entwurf, Stand 08.10.2026)

Grundlage: `01-grobstruktur.md` (Foxtag-Analyse), `02-sync-und-zugang.md` (offline, mehrere Nutzer).
Server: SQLite (später PostgreSQL möglich), Geräte: IndexedDB mit denselben Feldern.

## Allgemeine Regeln

- Alles muss vollständig exportierbar sein, u. a. im Importformat von Foxtag (siehe `05-export-und-wechsel.md`);
  Nummern von Kunde, Objekt, Anlage, Auftrag, Artikel sind Pflicht und eindeutig.

- Jede Tabelle hat `id` (UUID, auf dem Gerät erzeugt), `erstellt_am`, `erstellt_von` (Nutzer), `erstellt_auf` (Gerät),
  `geaendert_am`, `geaendert_von`, `version` (Zähler für den Abgleich) und `geloescht` (nur Kennzeichen –
  **nichts wird physisch gelöscht**, Prüfnachweise bleiben nachvollziehbar).
- Feldänderungen an Stammdaten landen zusätzlich im `aenderungsprotokoll` (wer, wann, Gerät, Feld, alt → neu).
- Tabellen mit „nur anhängen“ (⊕): Datensätze werden nach dem Speichern nicht mehr geändert; Korrektur = neuer
  Datensatz mit Verweis `ersetzt_id` (wie Storno in der Buchhaltung).
- Nummern (`nummer`): auf dem Gerät vorläufig (`vorlaeufig = ja`), endgültig vom Server beim Abgleich.

## 1. Stammdaten

### firma (eine Zeile)
name, anschrift, telefon, email, logo (Datei), auftragsnummer_praefix (`A-`), naechste_auftragsnummer,
kundennummer_praefix (`K`), anlagennummer_praefix (`ANL-`), berichtsfusszeile.

### nutzer
name, kuerzel, personalnummer (Foxtag: TECHNIKER.NUMMER), email, rolle (`buero` | `techniker` | `admin`), qualifikation (Text, z. B. „Fachkraft für
Rauchwarnmelder nach DIN 14676 seit …“ – erst nach Lehrgang), qualifikation_nachweis (Datei), aktiv, unterschrift
(Bild, optional als Vorlage), anmeldung (Passwort-Hash / Passkey, nur Server).

### geraet (Tablet/Laptop)
name („Tablet 1“), nutzer_id, freigeschaltet_am, gesperrt_am, letzter_abgleich_am, letzter_checkpoint.

### kunde
nummer (K0001), art (`hausverwaltung` | `eigentuemer` | `weg` | `vermieter` | `privat` | `sonstig`), name,
zusatz, strasse, plz, ort, land (DE), telefon, email, rechnungs_email, lieferantennummer (die der Kunde uns gibt),
notiz_intern, labels.

### kontakt
kunde_id (optional), name, firma, funktion („Hausmeister“, „Verwalter“), telefon, mobil, email, notiz.
Rollen über Verknüpfung `anlage_kontakt`: `vor_ort` | `berichtsempfaenger` | `terminankuendigung`.

### objekt (Gebäude)
nummer, kunde_id, bezeichnung („Musterstraße 12“), strasse, plz, ort, adresse_wie_kunde (ja/nein),
lage (Breite/Länge, für Karte und Fahrten), zugangshinweise („Schlüssel bei Hausmeister“), notiz.

### anlage
nummer (ANL-0001), objekt_id, anlagenart (`rauchwarnmelder`, später `tueren`), bezeichnung, hinweise_techniker,
verfahren (`A` | `B` | `C` – Art der Inspektion: vor Ort / teilweise Fern / Ferninspektion), passiv (ja/nein),
einzelnachweis_je_wohnung (ja/nein, Standard nein – z. B. bei Eigentümergemeinschaften einschaltbar), labels, notiz.
Melder werden nur verkauft (Patrick 08.10.2026) – kein Mietmodell, Melder gehören dem Kunden.
Verknüpfungen: anlage_kontakt (siehe oben), dateien.

### gruppe (= Wohnung bzw. bei Türen Geschoss/Bauteil)
anlage_id, nummer (43), bezeichnung („1. OG links“), bewohner (Name am Klingelschild – personenbezogen!),
bewohner_telefon (optional), zugang (`frei` | `nur_termin` | `schluessel`), notiz, link.

### komponente (= Melder bzw. Tür)
anlage_id, gruppe_id, nummer (laufend in der Gruppe → angezeigt „43/1“), sub_nummer (0 = Hauptkomponente,
bei Türen 1, 2 … für Teile), komponententyp_id, raum („Flur“,
Auswahlliste je Anlagenart + frei), raumart (`schlafraum` | `kinderzimmer` | `flur_rettungsweg` | `sonstiger`),
seriennummer, funk_id (wM-Bus-Adresse, für Ferninspektion), barcode (eigener Aufkleber), baujahr (Jahr bzw.
Herstellungsdatum), inbetriebnahme_am, austausch_faellig_am (berechnet, änderbar), naechste_pruefung_am (berechnet),
status (`aktiv` | `ausgebaut` | `ersetzt`), ersetzt_durch_id, labels, notiz.
Bei Türen zusätzlich `eltern_id` (Sub-Komponenten: Feststellanlage, Haftmagnet, Rauchschalter …).

### komponententyp (Katalog, je Anlagenart)
anlagenart, hersteller, modell, bezeichnung, kategorie (`komponente` | `sub_komponente`), zulassungsnummer,
funk (`keine` | `wmbus` | `lorawan`), batterie (`fest_10j` | `wechselbar`), austausch_jahre (Standard 10),
datenblatt_link, aktiv.

## 2. Aufträge und Arbeit vor Ort

### auftrag
nummer (A-1001), anlage_id, auftragsart (`wartung` | `installation` | `nachtermin` | `reparatur` | `ferninspektion`),
status (`ungeplant` | `geplant` | `aktiv` | `abgeschlossen` | `storniert` | `verschoben` | `abgerechnet` | `kostenlos`),
beginn, ende, ganztaegig, techniker (Liste nutzer_id) oder `pool`, umfang (`ganze_anlage` | Liste gruppe_id /
komponente_id), einzuplanende_maengel (Liste mangel_id), hinweise, angekuendigt_am (Terminankündigung),
abgeschlossen_am, bericht_datei, rechnung_nummer (Verweis ins Büro-Repo-Werkzeug).
Statusverlauf in `auftrag_status` ⊕ (zeit, alt, neu, nutzer).

### besuch ⊕ (je Gruppe/Wohnung und Auftrag)
auftrag_id, gruppe_id, ergebnis (`erledigt` | `nicht_angetroffen` | `zutritt_verweigert` | `teilweise`),
zeitpunkt, techniker_id, geraet_id, unterschrift_name, unterschrift_bild, unterschrift_zeit, anmerkung.
→ „nicht angetroffen“ erzeugt automatisch einen Vorschlag für einen Nachtermin.

### pruefung ⊕ (je Komponente und Auftrag)
auftrag_id, komponente_id, besuch_id, zeitpunkt, techniker_id, geraet_id, verfahren (`vor_ort` | `fern`),
ergebnis (`ok` | `mangel` | `nicht_geprueft`), grund_nicht_geprueft, checkliste_werte (Feld → Wert),
fern_daten (bei Ferninspektion: Rohtelegramm-Auszug, Zeitstempel, Statusbits), foto_ids, ersetzt_id.

### mangel ⊕ + Status (Mangel selbst bleibt, Status ändert sich über `mangel_status` ⊕)
komponente_id oder gruppe_id oder anlage_id, pruefung_id, mangeltyp (aus Anlagenart), schweregrad
(`hinweis` | `normal` | `schwer`), beschreibung, foto_ids, status (`offen` | `in_arbeit` | `behoben` |
`kein_mangel`), zielauftrag_id, behoben_durch_auftrag_id.

### massnahme ⊕ (Ein-/Ausbau, Austausch)
auftrag_id, art (`inbetriebnahme` | `ausbau` | `austausch` | `batteriewechsel` | `reinigung` | `versetzt`),
komponente_alt_id, komponente_neu_id, grund, zeitpunkt, techniker_id.

### position (Material und Leistungen)
auftrag_id, artikel_id, menge, einheit, kommentar. → Grundlage für die Rechnung.

### artikel
nummer, name, gruppe, einheit, preis_netto (nur Büro), art (`material` | `arbeit` | `fahrt` – wie in
`dokument.py`, Arbeit/Fahrt = § 35a-Anteil), aktiv.

### foto / datei
Besitzer (Tabelle + id), datei (auf dem Server unter NAS-Pfad, auf dem Gerät nur bis zum Abgleich), aufgenommen_am,
beschreibung, sha256.

### auftrag_unterschrift ⊕
auftrag_id, art (`techniker` | `kunde`), name, bild, zeit.

## 3. Ferninspektion (Laptop, später)

### funk_lauf ⊕
auftrag_id oder anlage_id, geraet_id (Laptop), beginn, ende, empfaenger („iM871A“), anzahl_empfangen.
### funk_telegramm ⊕
funk_lauf_id, funk_id, zeit, rssi, auswertung (Statusfelder aus wmbusmeters), roh (hex, gekürzt).
→ Abgleich: Telegramm passt zu `komponente.funk_id` → `pruefung` mit verfahren `fern`; nicht empfangene
Melder → Liste „vor Ort prüfen“.

## 4. Anlagenart-Konfiguration (Datei im Repo, nicht in der Datenbank)

`server/wartung/konfig/anlagenarten/rauchwarnmelder.toml`, später `tueren.toml`. Inhalt: Bezeichnungen (Gruppe = „Wohnung“,
Komponente = „Melder“, Trenner „/“), Unterschrift pro Gruppe (ja), Raumliste, Prüfintervall (12 Monate, Vorwarnung
30 Tage), Austauschregel (10 Jahre ab Baujahr/Inbetriebnahme), Checkliste je Komponente, Mängeltypen mit
Schweregrad und „Austausch vorschlagen“, Auftragsarten mit Ablaufschritten, Berichtstexte.
Die Checklisten-Punkte formuliere ich eigenständig nach den Prüfkriterien der DIN 14676-1 und lasse sie nach
Patricks Lehrgang (KW 42) von ihm gegenlesen.

## 5. Fälligkeiten (Regeln)

- `naechste_pruefung_am` = letzte Prüfung mit Ergebnis `ok`/`mangel` + 12 Monate (gleitend); ohne Prüfung =
  Inbetriebnahme + 12 Monate. Ampel: grün > 30 Tage, gelb ≤ 30 Tage, rot überfällig.
- `austausch_faellig_am` = Baujahr + 10 Jahre (Typ-Einstellung vor Anlagenart), sonst Inbetriebnahme + 10 Jahre.
  Vom Baujahr ist nur das Jahr bekannt → vorsichtig ab 1. Januar; Zugabe (`austausch_zugabe_monate`) nach Lehrgang
  gegen DIN 14676-1 prüfen. Umgesetzt in `server/wartung/faelligkeit.py` (08.10.2026).
- `letzte_pruefung_am` je Komponente (Migration 004): bis zu den Aufträgen von Hand/Import, danach aus der Prüfung.
- Anlage zeigt die früheste Fälligkeit ihrer aktiven Komponenten.

## 6. Abgleich (Kurzform, Details folgen in Stufe 3)

- Gerät bekommt nur die Daten seiner Aufträge (Anlage, Gruppen, Komponenten, offene Mängel, Kontakte vor Ort).
- Push: **Befehle** (Tabelle `befehl` ⊕ auf dem Server: befehl_id, geraet_id, nutzer_id, art, datensatz, auftrag_id,
  zeitpunkt, daten, empfangen_am, ergebnis). Idempotent über befehl_id; ⊕-Vorgänge (Prüfung, Mangel, Unterschrift)
  immer übernehmen, Stammdaten feldweise mit Vergleich gegen den mitgeschickten bisherigen Wert; Widersprüche
  → Tabelle `konflikt` (Büro entscheidet). Siehe `docs/07` Abschnitt 4–5.
- Pull: je Tabelle alles seit der letzten Abgleich-Nummer (Spalte `abgleich_nr`, vom Server fortlaufend vergeben).
- Umfang je Gerät über Abo je Anlage (eigene Aufträge), Nachholen bei neuem Abo, „Gerät zurücksetzen“.
- Komponenten-Lebenslauf: Lager → verbaut → ersetzt/entfernt; Austausch als eigener Vorgang. Scan-Nachweis speichern.
- Nach Abschluss und Abgleich: Bewohnernamen/Unterschriften auf dem Gerät löschen.

## Geklärt (Patrick 08.10.2026)

1. Melder werden nur verkauft, nicht vermietet.
2. Einzelnachweis je Wohnung vorerst nicht; als Schalter je Anlage vorgesehen (z. B. Eigentümer-Objekte).
