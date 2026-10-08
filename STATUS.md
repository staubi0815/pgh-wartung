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
2. Stufe 2: Datenmodell (`docs/03-datenmodell.md`) + Konfig Rauchwarnmelder (`konfig/anlagenarten/rauchwarnmelder.toml`, Entwurf, nach Lehrgang gegenlesen). Weiter: (Tabellen/Felder), Anlagenart-Konfiguration Rauchwarnmelder, Masken der Webseite,
   Fälligkeitsregeln, Prüfbericht nach DIN 14676-1.
3. Danach: Wartungsserver (eigener LXC), Grundgerüst Web, dann App.
