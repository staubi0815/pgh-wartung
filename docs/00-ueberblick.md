# Überblick – pgh-wartung auf einen Blick

Einstieg für Menschen: was es gibt, wie es zusammenhängt, wo wir stehen. Details stehen in den anderen `docs/`-Dateien.
Die Diagramme zeigt GitHub direkt als Bild an. Datenmodell und Auftragsstatus werden **automatisch aus dem Code
erzeugt** (`server/werkzeuge/diagramme.py`) und von den Tests geprüft – sie können also nicht veralten.

## 1. Wie die Teile zusammenhängen

```mermaid
flowchart LR
    subgraph aussen["Unterwegs"]
        tablet["Tablet / Laptop<br>App (PWA, offline)<br><i>Baustein 4 – geplant</i>"]
    end
    subgraph heim["Heimnetz"]
        fritz["FritzBox<br>WireGuard-VPN"]
        subgraph pve["Proxmox"]
            server["LXC 192 pgh-wartung<br>Python FastAPI<br>Webseite + Abgleich"]
            db[("SQLite<br>wartung.db")]
        end
        nas[("NAS (QNAP)<br>Sicherungen,<br>Exporte")]
    end
    buero["Büro-Browser<br>Webseite"]
    foxtag["Foxtag<br>(Wechsel möglich)"]
    github["GitHub<br>Code + Doku,<br>keine Kundendaten"]

    buero -- "HTTP, später HTTPS" --> server
    tablet -- "VPN" --> fritz --> server
    server --- db
    db -- "Proxmox-Sicherung täglich" --> nas
    server -. "Export Foxtag-Format / Vollexport" .-> nas
    nas -. "Import von Hand" .-> foxtag
    github -- "deploy.sh" --> server
```

Grundsätze, die überall gelten (Langfassung in `CLAUDE.md`): keine offenen Ports, Zugang nur über VPN; Kundendaten
nie im Repo oder Chat; Prüfnachweise werden nur angehängt, nie überschrieben; Löschen ist eine Markierung; jedes
Modul kann exportieren (eigener Vollexport und Foxtag-Format).

## 2. Stand der Bausteine

| # | Baustein | Stand | Version |
|---|---|---|---|
| 1 | Grundgerüst: Anmeldung, Nutzer, Rollen und Einzelrechte, Firma, Änderungsprotokoll | ✅ fertig | 0.1 |
| 2 | Stammdaten: Kunden, Objekte, Anlagen, Wohnungen, Melder, Fälligkeiten, Excel-Import, Export | ✅ fertig | 0.2 |
| 3 | Aufträge: planen, Liste und Woche, Sammelplanung, Start-Cockpit, Foxtag-Format | ✅ fertig | 0.3 |
| 4 | App (PWA) für Tablet/Laptop mit Offline-Abgleich – vorher HTTPS | ⏳ als Nächstes | – |
| 5 | Bericht als PDF, Terminankündigung/Aushang, Rechnungsübergabe | geplant | – |
| 6 | Mängel, Auswertungen, Ferninspektion; später Brandschutztüren als weitere Anlagenart | geplant | – |

Was sich je Version geändert hat: `CHANGELOG.md`. Tagesaktueller Stand und offene Punkte: `STATUS.md`.
Warum etwas so gebaut ist: `docs/09-entscheidungen.md`.

## 3. Datenmodell

Linien: eine Zeile auf der Seite mit dem Doppelstrich gehört zu vielen Zeilen auf der Seite mit dem Kreis und der Gabel
(z. B. ein Kunde hat viele Objekte). Sind zwei Tabellen mehrfach verknüpft, steht die Spalte an der Linie. Im Alltag: **Kunde → Objekt → Anlage → Wohnung (gruppe) → Melder (komponente)**;
Aufträge hängen an der Anlage. Feldbeschreibungen: `docs/03-datenmodell.md`.

<!-- AUTO:datenmodell -->
```mermaid
erDiagram
    objekt ||--o{ anlage : ""
    anlage ||--o{ anlage_kontakt : ""
    kontakt ||--o{ anlage_kontakt : ""
    anlage ||--o{ auftrag : ""
    auftrag ||--o{ auftrag_gruppe : ""
    gruppe ||--o{ auftrag_gruppe : ""
    auftrag ||--o{ auftrag_techniker : ""
    nutzer ||--o{ auftrag_techniker : ""
    auftrag ||--o{ auftrag_verlauf : ""
    anlage ||--o{ gruppe : ""
    anlage ||--o{ komponente : ""
    komponente ||--o{ komponente : "eltern_id"
    komponente ||--o{ komponente : "ersetzt_durch_id"
    gruppe ||--o{ komponente : ""
    komponententyp ||--o{ komponente : ""
    kunde ||--o{ kontakt : ""
    komponente ||--o{ massnahme : "komponente_alt_id"
    komponente ||--o{ massnahme : "komponente_neu_id"
    nutzer ||--o{ nutzer_rolle : ""
    rolle ||--o{ nutzer_rolle : ""
    kunde ||--o{ objekt : ""
    rolle ||--o{ rolle_recht : ""
```

Ohne Verknüpfung (Verwaltung und Technik): `abgleich_zaehler`, `aenderungsprotokoll`, `anmeldeversuch`, `firma`, `nummernkreis`, `schema_version`.
<!-- /AUTO:datenmodell -->

## 4. Lebenslauf eines Auftrags

„Mit Grund“: Der Schritt ist nur mit einer Begründung möglich, die im Verlauf des Auftrags stehen bleibt.

<!-- AUTO:auftragsstatus -->
```mermaid
stateDiagram-v2
    direction LR
    state "Geplant" as geplant
    state "In Arbeit" as aktiv
    state "Abgeschlossen" as abgeschlossen
    state "Abgerechnet" as abgerechnet
    state "Abgeschlossen ohne Rechnung" as kostenlos
    state "Storniert" as storniert
    [*] --> geplant
    geplant --> aktiv
    geplant --> abgeschlossen
    geplant --> storniert : mit Grund
    aktiv --> abgeschlossen
    aktiv --> geplant : mit Grund
    abgeschlossen --> abgerechnet
    abgeschlossen --> kostenlos
    abgeschlossen --> aktiv : mit Grund
    abgerechnet --> abgeschlossen : mit Grund
    kostenlos --> abgeschlossen : mit Grund
    storniert --> geplant : mit Grund
```
<!-- /AUTO:auftragsstatus -->

## 5. Wo was im Code liegt

| Ort | Inhalt |
|---|---|
| `server/wartung/` | Fachlogik je Thema: `kunden.py`, `objekte.py`, `anlagen.py`, `gruppen.py`, `komponenten.py`, `auftraege.py`, `export.py`, `excel_import.py`, `rechte.py` |
| `server/wartung/web/` | Webseiten je Bereich (Anzeige und Formulare; die Regeln stehen in der Fachlogik) |
| `server/wartung/templates/`, `static/` | Seitenvorlagen und Gestaltung |
| `server/wartung/migrationen/` | Datenbankschema, nummeriert; jede Änderung ist eine neue Datei |
| `server/wartung/konfig/` | Konfiguration je Anlagenart (Rauchwarnmelder; später Türen) |
| `server/tests/` | automatische Tests – laufen bei jedem Hochladen auf GitHub |
| `server/werkzeuge/` | Hilfsskripte (Diagramme, Probe-Import) |
| `deploy.sh` | spielt den Stand auf den Server ein (vorher laufen die Tests) |

## 6. So entsteht eine Änderung

```mermaid
flowchart LR
    a["Zweig anlegen"] --> b["Code + Tests + Doku"] --> c["Pull Request<br>Zusammenfassung in<br>Alltagssprache"]
    c --> d{"GitHub prüft:<br>alle Tests grün?"}
    d -- nein --> b
    d -- ja --> e["Patrick liest und<br>gibt frei (Merge)"] --> f["deploy.sh<br>auf LXC 192"]
```
