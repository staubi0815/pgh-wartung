# Status

## 2026-10-08
- Repo angelegt (Patrick), Deploy-Key `~/.ssh/id_deploy_pgh-wartung` (Schreibrecht), Alias `github.com-pgh-wartung`.
- Stufe 1 Grobstruktur (`docs/01-grobstruktur.md`, aus dem Büro-Repo übernommen) und Stufe 1b Sync/Zugang
  (`docs/02-sync-und-zugang.md`) fertig.
- Vorgaben Patrick: mehrere Nutzer gleichzeitig, offline im Keller mit automatischem Abgleich, Daten zu Hause,
  keine offenen Ports, später Türen.

## Offen
1. Verbindungsweg: **WireGuard über die FritzBox** (Patrick, 08.10.2026), Patrick richtet je Tablet eine Verbindung ein.
   Geräte (Patrick 08.10.): Android-Tablet zum Erfassen, Laptop (Windows, WireGuard schon eingerichtet) zum Funk-Auslesen. Nutzerzahl offen.
   „Ohne VPN über Webseite“ besprochen → bleibt bei WireGuard (Patrick bestätigt 08.10.).
2. Stufe 2 fertig: Datenmodell (`docs/03`), Konfig Rauchwarnmelder (Entwurf, nach Lehrgang gegenlesen), Masken Web (`docs/04`).
3. Stufe 3: Server **LXC 192 `pgh-wartung` angelegt** (08.10.2026, Freigabe Patrick; `ssh pgh-wartung`, DHCP 192.168.178.31,
   Doku homelab-infra `infra/lxc-192-pgh-wartung.md`). Technik: Python (FastAPI) + SQLite, Oberfläche als PWA, PDF über Chromium.
   **Grundgerüst Web läuft** (08.10.2026): http://192.168.178.31:8000 – Anmeldung (Argon2, Sperre nach 5 Fehlversuchen,
   CSRF, Sicherheitsköpfe), Einmal-Links zum Passwort-Setzen, Nutzer/Rollen, Firma, Änderungsprotokoll (nur anhängen).
   12 Tests grün. Deploy: `./deploy.sh`. Admin-Einladung für Patrick in Drive `pgh-wartung-einrichten.txt` (48 h).
   Feste IP eingetragen (Patrick, 10.10.2026). Offen: HTTPS, Sicherung der Anwendungsdaten; nächster Baustein Kunden/Objekte/Anlagen/Wohnungen/Melder + Import.
4. Analyse Foxtag-Rollen und -App (`docs/06`, 08.10.2026). **Einzelrechte + kombinierbare Rollen umgesetzt**
   (Migration 002, `rechte.py`, Masken Verwaltung → Rollen und Rechte; 29 Tests grün; DB vorher gesichert unter
   `/var/lib/pgh-wartung/sicherung/wartung-vor-002-2026-10-08.db`). Dabei behoben: eine DB-Verbindung je Thread und
   Transaktionen mit BEGIN IMMEDIATE/SAVEPOINT (vorher teilten sich gleichzeitige Anfragen eine Verbindung).
   App-Zerlegung: Patrick hat Erlaubnis von Foxtag telefonisch eingeholt, Bestätigung per Mail liegt bei Patrick vor (abgeheftet, 10.10.2026).
   Analyse Foxtag 2 (111.0.6) fertig → `docs/07`; Patrick hat die Analyse-Werkzeuge per Berechtigungsregel
   freigegeben. Folge: Abgleich als **Befehlsprotokoll** + Server-Abgleichnummer (docs/02, docs/03 angepasst).
   Offen: Bildschirmfolge durch Bedienen im Testkonto (bis ca. 08.11.).
5. Baustein 2 Stammdaten (08.10.2026), in sechs Schritten: 1 Fundament ✓ (Migration 003, Abgleich-Nummer,
   Nummernkreise, Anlagenart-Lader, Web in Bereiche aufgeteilt), 2 Kunden + Kontakte ✓ (Liste/Suche/Filter,
   Detail, Anlegen/Ändern/Löschen-Markierung, Rückfrage beim Löschen), 3 Objekte + Anlagen ✓ (Anschrift eigen oder
   „wie Kunde“, Objekt kann Kunden wechseln, Anlagenart fest, Ansprechpartner mit Rolle, Anlagenliste mit Suche),
   4 Wohnungen + Melder ✓ (Typenkatalog unter Verwaltung, Wohnungen, Melder einzeln/mehrere, Austausch/Ausbau mit
   Maßnahme ⊕ und Verlauf, Wohnung kopieren, Fälligkeiten mit Ampel in Anlage/Liste/Startseite; Austausch vorsichtig
   ab 1. Januar des Baujahrs – Zugabe nach Lehrgang prüfen: `austausch_zugabe_monate` in der Anlagenart),
   5 Excel-Import ✓ (Verwaltung → Excel-Import, Foxtag-Vorlagenformat für Kunden, Kontakte, Objekte, Anlagen,
   Typen, Melder je Anlage; Vorschau als Probelauf, Übernehmen alles oder nichts, Vorhandenes bleibt unverändert;
   mit den echten Foxtag-Vorlagen getestet), 6 Export ✓ (09.10.2026, Verwaltung → Export: Vollexport JSON/CSV/Schema
   als ZIP und Foxtag-Format als nummerierte Excel-Dateien; Rundweg Export → Import getestet; Vollexport nur mit
   Nutzer- und Protokollrecht, Büro darf den Foxtag-Export; jeder Export im Änderungsprotokoll; 143 Tests grün;
   Details `docs/05` Abschnitt 6). **Baustein 2 Stammdaten damit fertig.**
   Probe-Import ins Foxtag-Testkonto ✓ (10.10.2026, siehe Punkt 9). Offen: Import fasst Zeilenumbrüche in Notizen zu Leerzeichen zusammen (prüfen, ob Notizen mehrzeilig bleiben sollen).
7. Baustein 3 Aufträge (09.10.2026), in sechs Schritten: 1 Fundament ✓ (Migration 006: auftrag, auftrag_techniker,
   auftrag_gruppe, auftrag_verlauf ⊕; `auftraege.py` mit Statusübergängen, Verschieben mit Grund, Pool ohne
   Techniker; Löschsperre für Anlagen mit Aufträgen und Wohnungen in offenen Aufträgen; Feldart Uhrzeit; Datum muss
   existieren), 2 Masken ✓ (Auftrag planen aus der Anlage mit Techniker-/Wohnungsauswahl, Auftragsseite mit
   Status-Knöpfen und Verlauf, Bearbeiten/Verschieben mit Grund, Abschnitt Aufträge in der Anlage, Datum deutsch
   mit Wochentag; im Browser geprüft), 3 Liste + Wochenansicht ✓ (Menü „Aufträge“; Filter Status/Zeitraum/
   Techniker/Pool/Art/Suche; Büro und Planende sehen alle, Techniker eigene + Pool, nur Webzugang nur eigene;
   interne Notiz nur fürs Büro; im Browser geprüft), 4 Sammelplanung ✓ (Anlagen in der Liste ankreuzen →
   gemeinsame Auftragsart/Techniker/Datum, je Anlage abweichender Termin, alles oder nichts; Spalte und Übersicht
   „Nächster Auftrag“, Filter „nur ohne offenen Auftrag“), 5 Start-Cockpit ✓ (heutige Termine, Rest der Woche,
   überfällige Aufträge, fällige Anlagen „davon ohne Auftrag“, abzurechnen; Techniker nur eigene + Pool),
   6 Foxtag-Format ✓ (offene Aufträge als `07_Auftraege.xlsx` im Foxtag-Export, Import als weitere Datenart, Rundweg
   getestet; docs/05 Abschnitt 6). **Baustein 3 Aufträge damit fertig** (182 Tests grün).
   Probe-Import ✓ (Punkt 9): Foxtag übernimmt nur den Tag, Uhrzeit jetzt zusätzlich in den Hinweisen.
6. App-Analyse Foxtag 2 durch Bedienen (09.10.2026, `docs/08`): Navigation, Auftragsseite, Schrittfolge, Prüfliste,
   Ergebnis OK/Rückgängig, Tauschen, Nacharbeiten, Material, Unterschriften, Berichtsvorschau erfasst. Offen: Scan,
   Fotos, Auftrag beenden, **Offline-Test** (Methode steht in `docs/08`, Termin mit Patrick), zwei Geräte.
8. Übersicht und Arbeitsweise (10.10.2026, Wunsch Patrick): `docs/00-ueberblick.md` mit Diagrammen (Datenmodell und
   Auftragsstatus automatisch aus dem Code, Test wacht), automatische Tests auf GitHub, `CHANGELOG.md` mit Versionen
   0.1–0.3 (Tags), Entscheidungsliste `docs/09`, PR-Vorlage. Ab jetzt Änderungen nur noch per Pull Request
   (CLAUDE.md „Arbeitsweise“). Offen: unabhängige Prüfung von außen vor dem Echtbetrieb; optional Schutz von `main`
   in den GitHub-Einstellungen (Merge nur mit grünen Tests).
9. Probe-Import ins Foxtag-Testkonto (10.10.2026, Patrick per Hand, Nachtest per Skript mit Patricks
   Berechtigungsregel für `node /tmp/foxtag/*.js`): alle Datenarten kommen an. Folgerungen umgesetzt: Dateinamen wie
   das Foxtag-Menü und Menüpunkt je Datei im LIESMICH, Typen vor Komponenten (sonst legt Foxtag Typen ohne
   Prüfintervall an), Uhrzeit zusätzlich in den Auftragshinweisen (Import liest sie zurück), Probe-Kontakt ohne
   E-Mail. Details `docs/05` Abschnitt 6. Probedaten „PT-“ bleiben im Testkonto (läuft ca. 08.11. aus).
10. Abgleich Foxtag ↔ pgh-wartung (10.10.2026): `docs/10-abgleich-foxtag.md` – Felder, Aufträge, Rollen, Verwaltung,
    Hintergrund, Selbst-Check; Lückenliste mit Reihenfolge.
