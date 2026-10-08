# pgh-wartung – Prüf- und Wartungssoftware für PGH-Brandschutz

Arbeitsanleitung für Claude-Code-Sitzungen. Antworten immer auf Deutsch. Zuerst diese Datei und `docs/` lesen.

Ziel: eigene Software nach Vorbild Foxtag – zuerst Webseite fürs Büro, dann App (PWA) für Tablet/Laptop vor Ort.
Start mit Rauchwarnmeldern (DIN 14676-1), später Brandschutztüren/Feststellanlagen (DIN 14677) als weitere Anlagenart.

## Grundsätze

1. **Keine Kunden- oder Mieterdaten in dieses Repo** (privat, liegt aber bei GitHub/USA). Nur Code, Konfiguration,
   Testdaten mit erfundenen Namen. Echte Daten nur auf dem eigenen Server/NAS.
2. **Kundendaten nicht in den Chat** (Entscheidung Patrick 08.10.2026, Claude-Privatabo ohne AV-Vertrag) –
   Werkzeuge/Tests gegen Testdaten; bei echten Daten nur Zählwerte ausgeben.
3. **Zugangsdaten** nur in `~/.config/pgh-brandschutz/` auf LXC 191 (chmod 600), nie im Repo oder Chat.
4. **Keine offenen Ports im Heimnetz.** Zugriff von außen nur über das gewählte VPN (siehe `docs/02-sync-und-zugang.md`).
5. **Offline zuerst:** Die App muss ohne Netz voll arbeiten und selbst abgleichen; Prüfungen/Mängel/Unterschriften
   nur anhängen, nie überschreiben (Prüfnachweise müssen nachvollziehbar bleiben).
6. Anlagenarten als Konfiguration (nicht fest verdrahtet), damit Türen später nur eine weitere Konfiguration sind.
7. Funktionen von Foxtag nachbauen ist ok – **keinen Foxtag-Code, keine Texte/Logos/Gestaltung 1:1** übernehmen.
   Checklisten eigenständig aus der Norm formulieren.
8. Änderungen an Proxmox/Containern: homelab-infra-Skill nutzen, `infra/*.md` aktualisieren und pushen.

## Dokumente

| Datei | Inhalt |
|---|---|
| `docs/01-grobstruktur.md` | Analyse Foxtag, Datenmodell grob, Webseite/App/Bericht, Umfang Eigenbau |
| `docs/02-sync-und-zugang.md` | Mehrbenutzer, Offline-Abgleich, Verbindungswege (Entscheidung: WireGuard FritzBox), Sicherheit |
| `docs/03-datenmodell.md` | Tabellen und Felder, Anlagenart-Konfiguration, Fälligkeiten, Abgleich |

Analyse-Werkzeuge und Rohdaten (nicht im Repo): `~/tools/foxtag-analyse/`, `~/.local/state/pgh-brandschutz/foxtag-analyse/`.
Foxtag-Testkonto bis ca. 08.11.2026 (Zugang `~/.config/pgh-brandschutz/foxtag.env`).

## Stand

Siehe `STATUS.md`.
