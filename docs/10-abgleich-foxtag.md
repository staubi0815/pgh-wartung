# 10 – Abgleich Foxtag ↔ pgh-wartung (Stand 10.10.2026)

Zweck: Feldaufbau, Abhängigkeiten im Hintergrund, Rollen und Nutzer von Foxtag (Web, API v1.6.0, Importvorlagen,
Testkonto) mit unserem Stand (Version 0.3, Migrationen bis 006) vergleichen. Alles nur lesend erfasst; Foxtag-Texte
und -Code sind nicht übernommen, nur Erkenntnisse in eigenen Worten (Grundsatz 7).

Bewertung: **K** = Kern, vor Echtbetrieb nötig · **W** = wichtig, bald · **S** = später/optional · **=** gleichwertig ·
**+** bei uns besser/mehr.

## 1 Stammdaten

| Bereich | Foxtag | Wir | Bew. |
|---|---|---|---|
| Kunde | Nummer, Name, Adresse (2 Zeilen), PLZ/Ort/Land, Link, Koordinaten (auto/eigen), interne Notiz, Labels | zusätzlich Art, Zusatz, Telefon, E-Mail, Rechnungs-E-Mail, Lieferantennummer; kein Link, keine Koordinaten, keine Labels | = / W (Labels) |
| Kontakt | eigenes Adressbuch, über Kunde **und** Anlage verknüpfbar (n:m); Name, Firma, E-Mail, Telefon, Mobil, Fax, Notiz | Kontakt gehört genau einem Kunden, Verknüpfung zur Anlage mit Rolle (`anlage_kontakt`) | W: Kontakt über mehrere Kunden (z. B. Hausmeisterdienst) |
| Objekt | Nummer, Name, **Zeitzone**, Adresse „wie Kunde“ oder eigen | Nummer, Bezeichnung, Adresse wie Kunde/eigen, Koordinaten, Zugangshinweise | = (Zeitzone S, wir arbeiten nur in einer) |
| Anlage | Nummer, Name, **Standard-Techniker**, Hinweise, Ansprechpartner, passiv schalten, verschieben, Labels, Berichtsempfänger | Hinweise für Techniker, Verfahren A/B/C, passiv, Einzelnachweis je Wohnung; **kein Standard-Techniker, kein Verschieben der Anlage zu anderem Objekt, keine Berichtsempfänger** | K: Berichtsempfänger (Baustein 5), W: Standard-Techniker, Anlage verschieben |
| Wohnung/Gruppe | nur Nummer, Name, Link | zusätzlich Bewohner, Telefon, Zugang, Notiz | + |
| Komponente (Melder) | Etiketten, Typ, Seriennummer, Baujahr, Zulassungsnummer, QR-Code, Standort, letzte Prüfung, Inbetriebnahme | zusätzlich Raumart, Funk-ID, Status, Ersatzkette, Austausch-/Prüffälligkeit; **keine Zulassungsnummer je Komponente** (nur am Typ) | W (Zulassungsnr. bei Türen/Brandschutz) |
| Typ | Hersteller, Modell, Kategorie | zusätzlich Funk, Batterie, Austauschjahre, Datenblatt | + |
| Dateien/Fotos/Notizen | an Kunde, Anlage, Auftrag, Störung | **keine Tabellen** (nur interne Notiz-Felder) | K (Fotos mit Baustein 4) |
| Labels | frei benennbar, Farbe, in App/Portal sichtbar, an fast allem | fehlen | W |

## 2 Aufträge

| Punkt | Foxtag | Wir | Bew. |
|---|---|---|---|
| Status | in Planung, geplant, läuft, erledigt, abgerechnet; API zusätzlich storniert, verschoben, kostenfrei | geplant → läuft → abgeschlossen (+ storniert, Verschieben mit Grund, Verlauf) | W: „abgerechnet/kostenfrei“ (Rechnungsnummer-Feld vorhanden) |
| Techniker | mehrere, **Status je Techniker** | mehrere (`auftrag_techniker`), ein gemeinsamer Status; Pool ohne Techniker | S |
| Zeit | Datum+Uhrzeit, Enddatum, ganztägig | Datum, Uhrzeit, Dauer | = |
| Terminankündigung | Kontakte, Vorlaufzeit, Hinweistext, E-Mail | Feld `angekuendigt_am`, kein Versand | W (Baustein 5) |
| Kalender | iCal-Download, Outlook-Anbindung | keine | S |
| Material/Leistungen | Artikelpositionen am Auftrag, Artikelstamm mit Gruppe/Einheit/Sortierung | fehlt (Baustein 5) | K |
| Prüfung, Mängel, Störungen, Unterschriften, Bericht | vollständig, Berichtslayouts, Veröffentlichen mit Download-Link | fehlt (Bausteine 4/5) | K |
| Listenfilter | Zeitraum, Anwendung, Techniker, Objekt, Status, Labels | Status, Zeitraum, Techniker, Pool, Art, Suche, Wochenansicht, Sammelplanung | = / + |

## 3 Nutzer, Rollen, Rechte, Geräte

- Foxtag: 4 feste Rollen (Administration, Planen und Daten pflegen, Techniker, Techniker ohne Webzugang) als
  Kontrollkästchen; Einstellungen der App firmenweit; je Nutzer bis zu 2 aktive Geräte; 2FA-Richtlinie und
  Kundenservice-Zugang.
- Wir: **Einzelrechte** (23 Stück in fünf Bereichen) in kombinierbaren Rollen, `admin` hat immer alles; App-Rechte
  (Zugang, Aufträge, Stammdaten, Fotos, Auftrag anlegen, Termin verschieben, Ferninspektion) je Rolle statt firmenweit.
  Personalnummer/Kürzel/Qualifikation am Nutzer, Einladung per Einmal-Link, Sperre nach 5 Fehlversuchen. → **+**
- Fehlt: Geräteverwaltung (Gerät koppeln/sperren, Obergrenze) → K für Baustein 4 (`docs/02`); 2FA → W vor Zugang über
  HTTPS von außen; Kundenportal → S.
- Prüfung der Durchsetzung (Quelltext, Stand heute): Jede Route der Webseite ruft `web.nutzer(request, Recht)` mit
  Modulrecht (`stammdaten.lesen/bearbeiten`, `auftraege.planen`, `import`, `export`, `verwaltung.*`). Ausnahmen mit
  Absicht: Auftragsliste und -detail (Sicht je Nutzer über `auftraege.sicht`/`darf_sehen`: Büro alles, Techniker eigene +
  Pool, nur Webzugang nur eigene), Anmeldung/Konto. Vollexport verlangt zusätzlich Nutzer- und Protokollrecht.
  **Keine Route ohne Prüfung gefunden.**

## 4 Verwaltung/Einstellungen

| Foxtag-Einstellung | Wir | Bew. |
|---|---|---|
| Firmendaten | `verwaltung.firma` | = |
| Wartungsanwendungen (Anlagenarten) | Anlagenart-Dateien (Rauchwarnmelder, Entwurf bis nach Lehrgang) | = |
| Artikel | fehlt | K (mit Material) |
| Kontakte-Verzeichnis, Labels | fehlen | W |
| Auftragsnummern (Präfix, Startwert) | `nummernkreis` | = |
| Berichte/Logo/Layout | fehlt | K (Baustein 5) |
| E-Mail (Absender, Vorlagen, Unzustellbares) | fehlt | W |
| Kalender, Integrationen, API-Keys, Event-Logs | fehlen; wir bieten stattdessen Voll-Export und Änderungsprotokoll | S |
| Datenimport/-export | Excel-Import in Foxtag-Vorlagenformat, Foxtag-Export als ZIP, Vollexport | + |
| Auswertungen (Jahresfortschritt, Material, Austauschfälligkeit, Typ-Suche) | Fälligkeits-Ampel, Start-Cockpit | W (Austauschliste als Ausdruck) |

## 5 Abhängigkeiten im Hintergrund

- **Löschen:** Foxtag löscht Objekte nur ohne Anlagen. Wir: Löschen ist eine Markierung mit Rückfrage; Anlagen mit
  Aufträgen und Wohnungen in offenen Aufträgen sind gesperrt. Zu klären: Kunde/Objekt mit aktiven Unterelementen
  (Test ergänzen, falls nicht vorhanden). =
- **Nummern:** Foxtag automatische oder eigene Nummern je Anwendung abschaltbar; bei uns Nummernkreise, eigene Nummern
  beim Import erlaubt. =
- **Fälligkeit:** beide leiten „Nächster Auftrag“/Prüf- und Austauschfälligkeit aus Komponenten ab. =
- **Zeitzone/Koordinaten:** nur Foxtag; bei uns ohne Bedeutung, solange ein Standort.
- **Ereignisse nach außen:** Foxtag hat `/ingestion` und `/trigger_events`; für uns nicht geplant (S).
- **Ersatzkette:** bei uns Komponente ersetzt Komponente, Maßnahmen mit Verlauf; in Foxtag nur „Tauschen“ in der App
  ohne sichtbare Kette. +

## 6 Datenaustausch

- Import (Excel, Foxtag-Format): Kunden, Kontakte, Objekte, Anlagen, Typen, Melder, Aufträge. Probelauf, alles oder nichts. =
- Export: Foxtag-Format (nummerierte Excel-Dateien, mit Probe-Import im Testkonto verifiziert) und Vollexport. +
- Foxtag-seitig bekannt: Zulassungsnummer, zweites Label, Standard-Techniker, Artikelpositionen sind Spalten, die wir
  noch nicht liefern (hängt an den Lücken oben).

## 7 Selbst-Check unseres Codes (10.10.2026)

- 186 Tests grün (61 s), CI auf GitHub aktiv.
- Jede schreibende Route prüft CSRF (`web.formular`/`web.csrf`); Anmeldung mit Argon2, Sperre, Sicherheitsköpfe.
- Rechte je Route belegt (Abschnitt 3). Ein erster Skriptlauf meldete „ohne Prüfung“ für Austausch/Ausbau und
  Export; das war ein Fehlalarm (Rechte stehen in Hilfsfunktionen), im Quelltext nachgelesen.
- Linter nicht installiert (ruff fehlt im Test-Venv) → W: in CI/Venv aufnehmen.
- **Offene Befunde:**
  1. `docs/03` nennt ein Link-Feld an der Wohnung; im Schema gibt es keins → Doku oder Schema angleichen.
  2. Keine Sicherung der Anwendungsdaten auf das NAS, kein HTTPS (K vor Echtbetrieb).
  3. Notizen: Zeilenumbrüche gehen beim Import verloren.
  4. Unabhängige Prüfung von außen vor Echtbetrieb (STATUS Punkt 8).

## 8 Empfohlene Reihenfolge

1. **K, ohne Foxtag-Bezug:** HTTPS, Sicherung aufs NAS.
2. **K, Baustein 4 (App):** Geräteverwaltung, Fotos/Dateien, Prüfung, Mängel, Unterschrift.
3. **K, Baustein 5:** Artikel/Material, Berichte, Berichtsempfänger, Terminankündigung per E-Mail.
4. **W, kleine Stammdaten-Erweiterungen:** Labels, Standard-Techniker je Anlage, Zulassungsnummer je Komponente,
   Kontakt an mehreren Kunden, Anlage verschieben, Doku/Schema Link-Feld.
5. **S:** Status je Techniker, iCal, Zeitzone, Integrationen.
