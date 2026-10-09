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
   Offen: feste IP (Patrick), HTTPS, Sicherung der Anwendungsdaten; nächster Baustein Kunden/Objekte/Anlagen/Wohnungen/Melder + Import.
4. Analyse Foxtag-Rollen und -App (`docs/06`, 08.10.2026). **Einzelrechte + kombinierbare Rollen umgesetzt**
   (Migration 002, `rechte.py`, Masken Verwaltung → Rollen und Rechte; 29 Tests grün; DB vorher gesichert unter
   `/var/lib/pgh-wartung/sicherung/wartung-vor-002-2026-10-08.db`). Dabei behoben: eine DB-Verbindung je Thread und
   Transaktionen mit BEGIN IMMEDIATE/SAVEPOINT (vorher teilten sich gleichzeitige Anfragen eine Verbindung).
   App-Zerlegung: Patrick hat Erlaubnis von Foxtag telefonisch eingeholt (Mail folgt, dann hier vermerken).
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
   Offen: Probe-Import des Exports ins Foxtag-Testkonto (bis ca. 08.11., erfundene Daten); Import fasst
   Zeilenumbrüche in Notizen zu Leerzeichen zusammen (prüfen, ob Notizen mehrzeilig bleiben sollen).
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
   überfällige Aufträge, fällige Anlagen „davon ohne Auftrag“, abzurechnen; Techniker nur eigene + Pool), 6 Export/Import Foxtag-Format.
6. App-Analyse Foxtag 2 durch Bedienen (09.10.2026, `docs/08`): Navigation, Auftragsseite, Schrittfolge, Prüfliste,
   Ergebnis OK/Rückgängig, Tauschen, Nacharbeiten, Material, Unterschriften, Berichtsvorschau erfasst. Offen: Scan,
   Fotos, Auftrag beenden, **Offline-Test** (Methode steht in `docs/08`, Termin mit Patrick), zwei Geräte.
