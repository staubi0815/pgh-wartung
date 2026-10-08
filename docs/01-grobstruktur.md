# Nachbau Foxtag – Stufe 1: Analyse und Grobstruktur (Stand 08.10.2026)

Ziel (Patrick): Foxtag (foxtag.de) als eigene Lösung nachbauen – zuerst die Webseite (Büro), danach die App
(vor Ort beim Kunden). Schrittweise: erst grob, dann immer detaillierter.

Grundlage: Testkonto „Pro“ (info@-Adresse, läuft bis ca. 08.11.2026), nur lesend durchsucht (54 Seiten), dazu die
öffentliche API-Beschreibung (OpenAPI 1.6.0, `api.foxtag.io/openapi.json`) und das Support-Forum. Im Testkonto
angelegt: Vorlagen „Rauchwarnmelder“ und „Rauchwarnmelder (EFH)“ aus dem Verzeichnis, je mit Demo-Anlage.
Zugang: `~/.config/pgh-brandschutz/foxtag.env` (600), Analyse-Skripte: `~/tools/foxtag-analyse/` (LXC 191).

## 1. Ergebnis vorab

**Machbar – und deutlich kleiner als Foxtag.** Foxtag ist eine Plattform für viele Gewerke (Brandmeldeanlagen,
Türen, Feuerlöscher, Aufzüge …) mit Mandanten, Lizenzen und Verzeichnis. Für PGH-Brandschutz wird nur eine
„Wartungsanwendung“ gebraucht: Rauchwarnmelder. Der Kern ist ein überschaubares Datenmodell (Kunde → Objekt →
Anlage → Wohnung → Melder) plus Aufträge, Prüfungen, Mängel und ein PDF-Prüfbericht.

Was Foxtag **nicht** kann und ein Eigenbau kann: Ferninspektion/Funkauslesung (im Forum nur als Wunsch gefragt),
Anbindung an die eigenen Rechnungen/Bücher (`tools/dokument.py`), Daten nur im eigenen Haus (keine Auftrags-
verarbeitung mit Dritten für Mieterdaten und Unterschriften).

Kostenvergleich: Foxtag Basic 39 €, Pro 69 € je Nutzer/Monat (netto, jährlich) → 468–828 €/Jahr für Patrick allein.

## 2. Technik von Foxtag (was man sehen kann)

| Teil | Befund |
|---|---|
| Webseite | Ruby on Rails (Anmeldung über Devise), Oberfläche Vue.js, Daten als JSON nachgeladen |
| App | Native Apps iOS + Android, arbeitet **offline**, Abgleich mit Server, mehrere Techniker parallel |
| Karte | Mapbox (Objekte mit Adresse auf der Karte) |
| Schnittstelle | REST-API mit API-Schlüssel (Kunden, Kontakte, Objekte, Anlagen, Aufträge, Artikel, Labels, Inventar) |
| Berichte | PDF, frei wählbares Layout mit Logo, revisionssicher archiviert, per E-Mail an Empfänger |

## 3. Datenmodell (grob)

```
Firma (Niederlassung, Logo, Absender-Mail, Auftragsnummernkreis)
 └─ Mitarbeiter (Techniker, Rollen)
Kunde (Nr. K0001, Name, Adresse, Kontakte, Labels, interne Notiz)       ← z. B. Hausverwaltung, Eigentümer
 └─ Objekt (Nr., Name, Adresse – eigene oder die des Kunden)              ← Gebäude
     └─ Anlage (Nr., Name, Wartungsanwendung, Ansprechpartner vor Ort,  ← „Rauchwarnmelder Haus 12“
        Berichtsempfänger, Hinweise für Techniker, Notizen, Dateien, passiv j/n)
         └─ Gruppe = Wohnung (Nr. 43, Name „Mieter, 1.OG links“, Link)
             └─ Komponente = Melder (Nr. 43/1, Typ/Hersteller/Modell, Seriennummer, Baujahr,
                Zulassungsnr., Barcode/QR, Standort „Flur“, Labels, nächste Prüfung, Austausch fällig,
                Prüfhistorie)
Auftrag (Nr. A-1001, Anlage, Auftragstyp, Datum/Uhrzeit, Techniker oder „Pool“, Umfang: ganze Anlage
         oder Auswahl, einzuplanende Mängel, Hinweise, Status, Material, Anhänge, Statusverlauf)
   Status: ungeplant · geplant · aktiv · abgeschlossen · storniert · verschoben · abgerechnet · kostenlos
Prüfung (je Melder und Auftrag: Datum, Ergebnis OK/Mangel/ignoriert/keine Info, Techniker, Checklistenwerte)
Mangel/Störung (Typ, Schweregrad, Status, Beschreibung, Melder, Zielauftrag, im Kundenportal sichtbar)
Artikel (Nr., Name, Gruppe, Einheit) – für Material und Leistungen im Auftrag
Kontakt (Name, Firma, Mail, Telefon, Mobil, Notiz) – Ansprechpartner, Berichtsempfänger, Terminankündigung
Label (Name, Farbe, sichtbar in App/Portal)
```

**Konfiguration („Wartungsanwendung“)** – bei Foxtag frei einstellbar, bei uns fest für Rauchwarnmelder:

| Bereich | Foxtag-Vorlage „Rauchwarnmelder“ (MFH) |
|---|---|
| Bezeichnungen | Gruppe = „Wohnung“, Komponente = „Melder“, Code = „Barcode“, Trenner „/“ (43/1) |
| Unterschrift | **pro Wohnung** (Mieter unterschreibt je Wohnung, Techniker einmal am Ende) |
| Typen | 24 Meldertypen (Ei 605/650, Hekatron Genius, Gira, Pyrexx, Telenot, ELRO, FireAngel …) |
| Intervalle | Prüfung 1 Jahr (gleitend, Vorwarnung 30 Tage), Austausch 10 Jahre ab Baujahr |
| Checkliste je Melder (EFH-Vorlage) | Montageort · Eintrittsöffnungen · Beschädigungen · Farb-Übermalungen · Testknopf · Alarmton (je Haken) · geänderte Raumnutzung (Text) |
| Checkliste Nacharbeiten (MFH) | Prüfbescheinigung „gem. DIN 14676“ / „durch ausgebildete Fachkraft“, ausgeführte Prüfungen, Anmerkungen |
| Mängeltypen | Alarmton löst nicht aus · Bauliche Veränderungen · Beschriftung fehlt · Eintrittsöffnungen fehlerhaft · Farb-Übermalungen · Melder defekt · nicht auffindbar · verschmutzt · ausgetauscht · Testknopf fehlerhaft · in anderen Raum verlegt · Sonstiges |
| Auftragstypen | Wartungstermin (Standard), Installationstermin |

## 4. Webseite (Büro) – Bereiche

| Menü | Inhalt |
|---|---|
| Start | Anpassbares Cockpit: „meine Aufträge heute“, Fälligkeiten |
| Karte | Objekte/Aufträge auf Karte |
| Kunden | Liste, Detail mit Kundendaten, Kontakten, Anlagen, interner Notiz |
| Anlagen | Liste mit Filtern (Prüffälligkeit, Austauschfälligkeit, Techniker, Labels), Ampel; Detail mit Reitern Anlage · Komponenten (nach Wohnungen) · Aufträge · Störungen · Notizen · Dateien · Freigaben · Auswertungen |
| Aufträge | Liste mit Zeitraum/Status/Techniker-Filter, „Auftrag planen“ |
| Störungen | Mängelliste mit Schweregrad, Status, Zielauftrag |
| Auswertungen | Jahresfortschritt, Material und Leistungen, Austauschfälligkeiten, Melder-Typen suchen |
| Verwaltung | Firmendaten, Artikel, Kontakte, Labels, Auftragsnummern, Berichtslayouts + Logo, Datenimport (Excel für Kunden, Objekte, Anlagen, Melder, Typen, Aufträge, Artikel), Mitarbeiter, E-Mail (Absender, Antwort-Adresse, **Terminankündigung**), Kalender (Outlook/Google/Apple), App-Rechte, API-Schlüssel |
| Kundenportal | Hausverwaltung erhält Berichte per Mail oder sieht Anlagen, Berichte und Mängel online, kann Störungen melden |

## 5. App (vor Ort) – Ablauf eines Auftrags

Der Auftragstyp legt fest, welche Schritte die App führt (jeder Schritt abschaltbar):

1. **Inbetriebnahmen** – neue Melder erfassen (Typ, Standort, S/N, Barcode scannen)
2. **Vorarbeiten** – allgemeine Checkliste
3. **Prüfungen** – Wohnung für Wohnung, Melder für Melder: OK oder Mangel, Checkliste, Foto, Mangel erfassen,
   Melder tauschen/außer Betrieb nehmen; Melder per Barcode/QR finden
4. **Nacharbeiten** – Checkliste (Prüfbescheinigung)
5. **Material und Leistungen** – Artikelpositionen
6. **Unterschrift Techniker**
7. **Kundenunterschrift** – bei Rauchwarnmeldern je Wohnung (Mieter)

Danach automatisch: PDF-Bericht, Versand an Berichtsempfänger, neue Fälligkeiten berechnet.
Zusatz (Pro): **Einzelnachweise** – je Wohnung ein eigenes PDF (z. B. für den Mieter), bis 200 je Auftrag.

## 6. Prüfbericht (PDF) – Aufbau

1. Kopf: Titel/Untertitel, Datum, Auftrags-, Kunden-, Anlagennummer; Kunde · Standort · durchgeführt von
2. Allgemeine Checklisten (Vor-/Nacharbeiten)
3. Material und Leistungen
4. In-/Außerbetriebnahmen und Austausch (je Wohnung)
5. Prüfergebnisse je Wohnung und Melder (OK/Mangel, Stammdaten, Checklistenwerte, Mängel mit Status)
6. Unterschriften (Techniker, Kunde bzw. je Wohnung)
7. Fotos
8. Fußzeile (Firmenname, Seite x/y)

## 7. Eigenbau – Vorschlag Umfang

**Anlagenarten statt fest verdrahtet (Patrick 08.10.2026: später kommen Türen/Feststellanlagen dazu):**
Wie Foxtags „Wartungsanwendung“, aber schlanker – je Anlagenart eine Konfigurationsdatei im Repo statt eines
Editors in der Oberfläche: Bezeichnungen (Gruppe = Wohnung bzw. Geschoss/Bauteil, Komponente = Melder bzw. Tür),
Komponententypen mit Sub-Komponenten (Tür → Feststellanlage, Haftmagnet, Rauchschalter, Auslösetaster),
Prüf-/Austauschintervalle, Checklisten, Mängeltypen, Auftragstypen/Ablauf, Unterschrift pro Gruppe j/n,
Berichtstexte (DIN 14676-1 bzw. DIN 14677). Start mit „Rauchwarnmelder“; „Türen/Feststellanlagen“ ist dann eine
weitere Datei plus ggf. Zusatzfelder (z. B. Zulassungsnummer DIBt, Feuerwiderstandsklasse).

**Übernehmen (Kern):** Datenmodell aus Abschnitt 3, Fälligkeiten mit Ampel,
Auftragsplanung, Prüfablauf mit Checkliste nach DIN 14676-1, Mängel, Unterschrift je Wohnung, PDF-Prüfbericht,
Einzelnachweis je Wohnung, Excel-Import, Terminankündigung per Mail.

**Weglassen:** frei konfigurierbare Wartungsanwendungen und Verzeichnis, andere Gewerke, Lager, Mandanten/
Lizenzen, Fremdschnittstellen (Honeywell CLSS, IRAS), große Mitarbeiterverwaltung.

**Zusätzlich (Mehrwert gegenüber Foxtag):**
- Ferninspektion: Funkdaten (wmbusmeters, siehe `docs/recherche-ferninspektion-2026-10-08.md`) als Prüfergebnis
  übernehmen
- „Wohnung nicht angetroffen“ → automatisch Nachtermin, Aushang/Brief für Mieter-Ankündigung
- Aus abgeschlossenem Auftrag direkt Rechnung über `tools/dokument.py` (Bücher bleiben unberührt bis Freigabe)
- Fahrten aus Aufträgen für `tools/fahrten.py`

## 8. Machbarkeit und Technik (Vorschlag)

| Baustein | Vorschlag | Begründung |
|---|---|---|
| Server | eigener LXC auf Proxmox, Python (FastAPI) + SQLite, Backup über NAS/Hetzner-Kette | passt zu den vorhandenen Python-Werkzeugen, wenig Wartung |
| Webseite | im Heimnetz, später per VPN (FritzBox) erreichbar – **nicht öffentlich** | Mieterdaten/Unterschriften bleiben im Haus |
| App | **PWA** (Web-App zum Installieren) für Tablet und Laptop: offline (Service Worker + IndexedDB), Kamera-Scan für Barcode/QR, Unterschriftsfeld | eine Codebasis, kein App-Store, läuft auf Android-Tablet und Windows-Laptop |
| Abgleich | Auftrag vor dem Termin aufs Gerät laden, vor Ort offline arbeiten, danach daheim (WLAN) oder per VPN hochladen | kein Netz im Keller nötig |
| PDF | HTML → PDF mit Chromium wie `tools/dokument.py` | bewährt, gleiches Erscheinungsbild wie Rechnungen |
| Ablage | Berichte als PDF auf das NAS (`PGH-Brandschutz`), unveränderbar archiviert | Aufbewahrung wie bei Rechnungen |

Risiken: Offline-Abgleich (Konflikte, wenn zwei Geräte dieselbe Anlage bearbeiten) – bei einem Techniker gering;
Kamera-Scan im Browser braucht HTTPS (lokales Zertifikat oder VPN mit Domain); Unterschrift-Beweiskraft wie bei
Foxtag (Bild + Zeitstempel + Name).

Rechtlich: Funktionen und Abläufe nachbauen ist erlaubt. Nicht übernehmen: Foxtag-Code, Logo, Gestaltung 1:1,
Texte und Vorlagen wörtlich. Checklisten eigenständig aus DIN 14676-1 formulieren.

**Code:** dieses Repo (`staubi0815/pgh-wartung`, privat), Klon `~/repos/pgh-wartung` auf LXC 191, Deploy-Key
`~/.ssh/id_deploy_pgh-wartung` (Alias `github.com-pgh-wartung`). Das Büro-Repo `pgh-brandschutz-buero` bleibt fürs Büro.
Kunden-/Mieterdaten nie ins Repo (nur Code,
Konfiguration, Testdaten mit erfundenen Namen).

## 9. Nächste Stufen

- **Stufe 2 (Web, detailliert):** Tabellen und Felder des Datenmodells, Bildschirmliste mit Feldern je Maske,
  Fälligkeitsregeln, Nummernkreise, Berichtsinhalt nach DIN 14676-1 (Prüfnachweis je Wohnung).
- **Stufe 3:** Server aufsetzen (LXC), Grundgerüst Web (Kunden/Objekte/Anlagen/Wohnungen/Melder, Import).
- **Stufe 4:** Aufträge, Fälligkeiten, Prüfbericht-PDF.
- **Stufe 5 (App):** PWA mit Offline-Prüfablauf, Scan, Unterschrift, Abgleich.
- **Stufe 6:** Ferninspektion, Rechnungsanbindung, Kundenportal (optional).
