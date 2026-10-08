# Stufe 1b: Mehrere Nutzer, Offline-Betrieb und sicherer Zugang (Stand 08.10.2026)

Anforderungen (Patrick, 08.10.2026):
- Mehrere Techniker tragen **gleichzeitig** Melder ein und bearbeiten sie (z. B. zwei Personen in einem Haus).
- **Kein Empfang** (Keller) darf die Arbeit nicht stoppen; sobald wieder Netz da ist, wird **automatisch synchronisiert**.
- Server und Daten bleiben **zu Hause** (Proxmox/NAS), **keine offenen Ports** im Heimnetz, alles sicher.

Befund Anschluss (08.10.2026): Telekom mit öffentlicher, dynamischer IPv4 und IPv6 (kein DS-Lite). Technisch wäre
also jede Variante möglich – die Vorgabe „keine offenen Ports“ schränkt ein.

## 1. Offline und gleichzeitiges Arbeiten (unabhängig vom Verbindungsweg)

**Prinzip „offline zuerst“:** Die App arbeitet immer gegen eine eigene Datenbank auf dem Tablet. Netz wird nur zum
Abgleichen gebraucht. Der Server zu Hause ist die maßgebliche Stelle („Wahrheit“) und verteilt die Änderungen.

| Baustein | Lösung |
|---|---|
| Speicher auf dem Gerät | IndexedDB im Browser (PWA), Speicher als „dauerhaft“ anfordern (`navigator.storage.persist()`), damit der Browser nichts löscht |
| Abgleich | **Befehlsprotokoll** (seit 08.10.2026, nach Analyse der Foxtag-App, `docs/07`): Gerät wendet jede Änderung sofort lokal an und legt sie als Befehl mit eindeutiger Befehls-ID in eine Ausgangs-Warteschlange (Push, in Reihenfolge, idempotent); Server führt aus und ist maßgeblich. Holen (Pull) je Tabelle alles seit der letzten **vom Server vergebenen Abgleich-Nummer**. Eigene schlanke Umsetzung statt RxDB |
| Auslöser | sofort bei Änderung, wenn online; beim Wiederkehren des Netzes (`online`-Ereignis) und alle 30 s Wiederholung, solange die App offen ist; Android zusätzlich Background Sync |
| Kennungen | jedes Gerät erzeugt eindeutige IDs (UUID) – keine Doppelvergabe, auch offline |
| Prüfungen, Mängel, Fotos, Unterschriften | werden nur **angehängt**, nie überschrieben → zwei Techniker können sich nicht gegenseitig etwas zerstören; ergibt zugleich einen lückenlosen Prüfverlauf |
| Stammdaten (Melder, Wohnung) | Änderungsbefehl enthält nur die geänderten Felder **mit dem bisherigen Wert**. Server übernimmt je Feld (A ändert Standort, B Seriennummer → beides bleibt); weicht der aktuelle Wert vom mitgeschickten bisherigen ab (zwei ändern dasselbe Feld) → **Konfliktliste** im Büro statt stillem Überschreiben |
| Nummern (Melder 43/4, Auftrag A-1001) | auf dem Gerät vorläufig, endgültig vergibt der Server; Doppel (zwei legen offline 43/4 an) werden beim Abgleich erkannt und gemeldet |
| Absprache vor Ort | Auftrag kann auf Techniker/Wohnungen aufgeteilt werden; online zeigt die App „Wohnung 43 in Arbeit bei X“ (weiche Sperre) |
| Bericht | entsteht erst auf dem Server, wenn alle Geräte des Auftrags abgeglichen haben und der Auftrag abgeschlossen ist |

**Geräte:** Am besten **Android-Tablets mit Chrome**. Dort gibt es Background Sync (Abgleich auch bei geschlossener App),
den eingebauten Barcode-/QR-Scanner (BarcodeDetector) und dauerhaften Speicher für installierte Apps. iPad geht auch,
gleicht aber nur bei geöffneter App ab, braucht einen Scanner per JavaScript, und iOS löscht Daten nicht
installierter Web-Apps nach ca. 7 Tagen ohne Nutzung. Windows-Laptop mit Chrome/Edge geht wie Android.

## 2. Verbindungswege – Vergleich

| | A) Mesh-VPN (NetBird oder Tailscale) | B) Eigener Knoten bei Hetzner (Cloud-Server) | C) WireGuard in der FritzBox | D) „Über die Webseite“ (Webhosting S) | E) Cloudflare Tunnel |
|---|---|---|---|---|---|
| Offene Ports zu Hause | **keine** (nur ausgehende Verbindungen) | **keine** (Heimserver baut Tunnel nach außen auf) | 1 UDP-Port an der FritzBox (antwortet Fremden nicht, aber offen) | – | keine |
| Funktioniert technisch | ja | ja | ja (öffentliche IPv4 vorhanden) | **nein** als Tunnel: geteilter Webspace ohne eigene Dienste/feste IP; ginge nur als verschlüsselter „Briefkasten“ mit Eigenbau-Verschlüsselung | ja |
| Wer sieht Inhalte | niemand außer Gerät + Server (Ende-zu-Ende WireGuard) | niemand (Ende-zu-Ende) | niemand | Hetzner nur verschlüsselte Pakete – aber eigene Krypto = Fehlerrisiko | **Cloudflare entschlüsselt** (sieht Mieterdaten) |
| Wer sieht Metadaten | Anbieter (Geräteliste, IPs) | nur Patrick | nur Patrick | Hetzner | Cloudflare |
| Zugriff begrenzbar | ja: Regel „Tablets nur auf Wartungsserver, Port 443“ | ja (Firewall auf dem Knoten) | eingeschränkt (Zugriff ins Heimnetz) | – | ja |
| Gerät verloren | Gerät in der Konsole sperren | Schlüssel entfernen | Verbindung löschen | Token sperren | Nutzer sperren |
| HTTPS für die App | Tailscale: automatisch (`*.ts.net`); NetBird: eigenes Zertifikat (Domain + DNS-Nachweis) | eigenes Zertifikat | eigenes Zertifikat | Zertifikat vom Webhosting | automatisch |
| Kosten | NetBird: kostenlos bis 5 Nutzer/100 Geräte (gewerbliche Nutzung dort nicht ausdrücklich geregelt), Team 6 €/Nutzer/Monat. Tailscale: kostenlos **nur privat**, gewerblich 8 $/Nutzer/Monat | ca. 6 €/Monat (CX23 5,49 € + IPv4 0,50 €), Software kostenlos (NetBird selbst gehostet oder Headscale) | 0 € | 0 € (aber viel Eigenbau) | 0 € |
| Aufwand/Pflege | gering | mittel: öffentlicher Server muss gepflegt werden (Updates) – aber außerhalb des Heimnetzes | gering | hoch | gering |
| Anbieter | NetBird: Berlin, Open Source; Tailscale: Kanada/USA | Hetzner, Deutschland | – | Hetzner | USA |

Ausgeschlossen: **D** (kein Tunnel möglich; „Briefkasten“ nur mit
selbstgebauter Verschlüsselung – zu riskant für Mieterdaten), **E** (Cloudflare liest mit).

## 3. Entscheidung Patrick (08.10.2026): WireGuard in der FritzBox (Variante C)

Kostenlos, ohne Fremdanbieter. Der eine UDP-Port an der FritzBox wird bewusst in Kauf genommen (WireGuard antwortet
Unbekannten nicht, ist also von außen nicht sichtbar). Patrick richtet je Tablet eine eigene Verbindung ein
(FritzBox: Internet → Freigaben → VPN (WireGuard) → Einzelgerät, QR-Code mit der WireGuard-App scannen).

Folgen und Ausgleich:
- Abgleich nur bei aktiver VPN-Verbindung → Empfehlung: in Android „Durchgehend aktives VPN“ für WireGuard
  einschalten, sonst warten Änderungen auf dem Tablet, bis das VPN wieder an ist (gehen aber nicht verloren).
- FritzBox-VPN öffnet das ganze Heimnetz (keine Regel „nur Wartungsserver“) → je Tablet eigene Verbindung, bei Verlust
  sofort löschen; NAS/FritzBox/Proxmox nur mit starken Passwörtern; Wartungsserver selbst mit Anmeldung.
- Dynamische IP: über die MyFRITZ-Adresse der FritzBox (aktualisiert sich selbst).
- HTTPS für die App im Heimnetz: eigenes Zertifikat nötig (z. B. `wartung.pgh-brandschutz.de` mit Let's-Encrypt-
  DNS-Nachweis oder eigene Zertifizierungsstelle auf den Tablets) – wird beim Aufsetzen des Servers gelöst.
- Später jederzeit auf NetBird wechselbar, die App bleibt gleich.

## 3a. Ursprüngliche Empfehlung (zurückgestellt)

1. **Start: NetBird (Variante A).** Auf jedem Tablet die NetBird-App als „immer aktives VPN“. Zu Hause ein
   NetBird-Client auf dem Wartungsserver (eigener LXC). Zugriffsregel: Tablets dürfen **nur** den Wartungsserver auf
   Port 443 erreichen, nichts anderes im Heimnetz (NAS, FritzBox, Familie). Keine Portfreigabe in der FritzBox.
   Vor dem Start bei NetBird klären, ob der kostenlose Tarif gewerblich genutzt werden darf, sonst Team (6 €/Nutzer).
2. **Später bei Bedarf: NetBird selbst betreiben (Variante B)** auf einem kleinen Hetzner-Server in Deutschland –
   dann hängt nichts mehr an einem Fremdanbieter (gleiche Apps, nur andere Serveradresse).
3. Tailscale ist technisch gleichwertig und einfacher bei HTTPS, kostet gewerblich aber 8 $/Nutzer und ist ein
   US-Anbieter.

## 4. Sicherheitsmaßnahmen (gelten für jede Variante)

- Tablets: Geräteverschlüsselung (Android Standard), Bildschirmsperre mit PIN, automatische Updates.
- App: persönliche Anmeldung je Techniker (Passkey oder Passwort + zweiter Faktor), Gerät wird einmalig zu Hause
  freigeschaltet; Sitzung je Gerät sperrbar; Rollen (Techniker sieht nur zugewiesene Aufträge).
- Datensparsam auf dem Gerät: nur Aufträge der nächsten Tage; nach erfolgreichem Abgleich und Abschluss werden
  Mieterdaten vom Tablet entfernt (auf dem Server bleiben sie).
- Server: eigener LXC nur für die Wartungssoftware, nur Port 443 im VPN, tägliche Sicherung auf NAS + verschlüsselt
  zu Hetzner (wie die Belege), Protokoll jeder Änderung (wer, wann, welches Gerät).
- Keine Kundendaten im Repo und nicht im Claude-Chat (Grundsatz 6 Büro-Repo).

## 5. Offene Punkte für Patrick

- ~~Verbindungsweg wählen~~ → WireGuard FritzBox (08.10.2026).
- Welche Geräte (Android-Tablet / iPad / Windows-Laptop) und wie viele Nutzer ungefähr?

Quellen: tailscale.com/pricing, tailscale.com/kb/1153/enabling-https, netbird.io/pricing,
docs.netbird.io/selfhosted/selfhosted-quickstart, rxdb.info/replication.html, web.dev/learn/pwa/offline-data,
whatpwacando.today (Background Sync, Barcode), Hetzner-Cloud-Preise 2026 (costgoat.com/pricing/hetzner).
