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
