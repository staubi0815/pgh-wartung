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
   Offen: feste IP in der FritzBox (Patrick), dann Grundgerüst Web (Reihenfolge `docs/04` Abschnitt 10).
