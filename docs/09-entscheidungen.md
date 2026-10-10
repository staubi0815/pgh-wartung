# Entscheidungen – warum etwas so gebaut ist

Kurze Einträge: worum es ging, was entschieden wurde, warum und mit welchen Folgen. Neue Einträge kommen **unten** dazu.
Ein Eintrag wird nicht umgeschrieben, wenn sich etwas ändert. Stattdessen kommt ein neuer Eintrag dazu, und der alte
bekommt den Vermerk „ersetzt durch Nr. …“. So bleibt nachvollziehbar, was wann warum galt.

Format: **Nr. – Titel** (Datum, wer) · Frage · Entscheidung · Begründung · Folgen · ausführlich in …

---

### 1 – Eigene Software statt Foxtag-Abo (08.10.2026, Patrick)
- **Frage:** Foxtag weiter nutzen oder selbst bauen?
- **Entscheidung:** Selbst bauen, Funktionen nach Vorbild Foxtag, aber kein Foxtag-Code und keine Texte, Logos oder
  Gestaltung 1:1.
- **Begründung:** Daten bleiben im Haus, keine laufenden Kosten, Abläufe passen zum eigenen Betrieb.
- **Folgen:** Jedes Modul bringt einen Export im Foxtag-Format mit, damit ein Rückweg jederzeit möglich bleibt (Nr. 7).
- **Ausführlich:** `docs/01-grobstruktur.md`.

### 2 – Python (FastAPI) und SQLite auf eigenem Container (08.10.2026)
- **Frage:** Womit und wo läuft der Server?
- **Entscheidung:** Eigener LXC 192 auf Proxmox, Python mit FastAPI, Datenbank SQLite.
- **Begründung:** Passt zu den vorhandenen Python-Werkzeugen im Büro; SQLite ist eine einzige Datei, braucht keine
  Wartung und reicht für wenige gleichzeitige Nutzer locker aus.
- **Folgen:** Schreibzugriffe laufen nacheinander (BEGIN IMMEDIATE). Sollte es je eng werden, wäre ein Wechsel auf
  PostgreSQL möglich; die Datenbankzugriffe liegen überwiegend in den Fachmodulen (Ausnahme: Teile der Verwaltung).
- **Ausführlich:** `docs/01-grobstruktur.md` Abschnitt 8.

### 3 – Zugang von außen nur über WireGuard der FritzBox (08.10.2026, Patrick)
- **Frage:** Wie kommen Tablets unterwegs an den Server?
- **Entscheidung:** WireGuard-VPN der FritzBox, je Gerät eine eigene Verbindung; keine Webseite im Internet.
- **Begründung:** Kostenlos, kein Fremdanbieter, keine offenen Ports für die Anwendung.
- **Folgen:** Abgleich nur mit aktivem VPN; ein verlorenes Gerät muss sofort aus der FritzBox gelöscht werden. Wechsel
  auf NetBird wäre später möglich, die App bleibt gleich.
- **Ausführlich:** `docs/02-sync-und-zugang.md` Abschnitt 3.

### 4 – Prüfnachweise nur anhängen, Löschen nur als Markierung (08.10.2026)
- **Frage:** Dürfen Prüfungen, Maßnahmen und Verläufe nachträglich geändert oder gelöscht werden?
- **Entscheidung:** Nein. Diese Tabellen erlauben nur das Anhängen; das sichern Regeln in der Datenbank selbst ab
  (Trigger), nicht nur das Programm. Stammdaten werden beim Löschen nur markiert.
- **Begründung:** Prüfnachweise müssen auch Jahre später nachvollziehbar sein (Haftung, DIN 14676-1). Für den
  Offline-Abgleich ist Anhängen außerdem viel robuster als Überschreiben.
- **Folgen:** Korrekturen sind neue Einträge, die auf den alten verweisen. Die Datenbank wächst nur, was bei der
  Datenmenge unkritisch ist.

### 5 – Einzelrechte und kombinierbare Rollen (08.10.2026)
- **Frage:** Feste Rollen (Büro, Techniker, Admin) oder feiner?
- **Entscheidung:** Einzelrechte (z. B. `auftraege.planen`, `export`), die zu Rollen gebündelt werden; ein Nutzer kann
  mehrere Rollen haben.
- **Begründung:** Im Kleinbetrieb macht oft eine Person mehreres; Foxtag arbeitet ähnlich.
- **Folgen:** Jede Seite prüft ein konkretes Recht. Neue Funktionen bekommen ein eigenes Recht oder nutzen ein
  passendes vorhandenes.
- **Ausführlich:** `docs/06-foxtag-rollen-und-app.md`.

### 6 – Abgleich der App als Befehlsprotokoll (08.10.2026)
- **Frage:** Wie gleicht die Offline-App ihre Änderungen mit dem Server ab?
- **Entscheidung:** Die App schickt Befehle („Melder 3 geprüft, Ergebnis OK“) mit eindeutiger Befehls-ID. Der Server
  führt sie der Reihe nach aus, doppelt gesendete Befehle ignoriert er. Jeder Datensatz trägt eine fortlaufende
  Abgleichnummer vom Server statt eines Zeitstempels.
- **Begründung:** Robust bei Funklöchern mitten im Senden, passt zu Nr. 4, und die Geräte-Uhrzeit spielt keine Rolle.
  Foxtag macht es dem Prinzip nach ähnlich (eigene Umsetzung).
- **Folgen:** Widersprüche (z. B. ein Befehl auf einen inzwischen ausgebauten Melder) landen in einer Konfliktliste
  fürs Büro, statt still überschrieben zu werden.
- **Ausführlich:** `docs/07-foxtag-app-aufbau.md`, `docs/02-sync-und-zugang.md`.

### 7 – Export in zwei Formen: Vollexport und Foxtag-Format (08.10.2026)
- **Frage:** Wie bleibt ein Wechsel weg von der eigenen Software möglich?
- **Entscheidung:** Vollexport aller Tabellen (JSON/CSV mit Schema) sowie Export als Excel-Dateien im Format der
  Foxtag-Importvorlagen, Kopfzeilen exakt wie dort.
- **Begründung:** Keine Abhängigkeit von der eigenen Software; ein Test vergleicht die Kopfzeilen mit den Vorlagen.
- **Folgen:** Der Vollexport ist nur mit Nutzer- und Protokollrecht erlaubt, weil er alles enthält. Exporte mit echten
  Daten liegen nur auf dem NAS.
- **Ausführlich:** `docs/05-export-und-wechsel.md`.

### 8 – Anlagenarten als Konfiguration (08.10.2026)
- **Frage:** Wie kommen später Brandschutztüren und Feststellanlagen dazu?
- **Entscheidung:** Anlagenarten (Felder, Fälligkeitsregeln, Prüflisten) stehen in Konfigurationsdateien
  (`server/wartung/konfig/anlagenarten/`), nicht im Code.
- **Begründung:** Eine neue Anlagenart ist dann vor allem eine neue Konfiguration.
- **Folgen:** Allgemeine Begriffe im Code: „Gruppe“ statt Wohnung, „Komponente“ statt Melder.

### 9 – HTTPS vor dem App-Baustein (10.10.2026)
- **Frage:** Kann die App ohne HTTPS gebaut werden?
- **Entscheidung:** Nein, HTTPS wird vor Baustein 4 eingerichtet.
- **Begründung:** Browser erlauben den Offline-Speicher (Service Worker) nur über HTTPS. Das gilt auch für den
  Silk-Browser des Fire-Testtablets.
- **Folgen:** Es braucht ein Zertifikat für das Heimnetz (Let's-Encrypt-DNS-Nachweis oder eigene
  Zertifizierungsstelle); offen laut `docs/02` Abschnitt 3.

### 10 – Arbeitsweise mit Pull Request, automatischer Prüfung und Übersicht (10.10.2026, Patrick)
- **Frage:** Wie behält ein Mensch den Überblick, wenn der Code fast vollständig von Claude geschrieben wird?
- **Entscheidung:** Änderungen kommen als Pull Request mit Zusammenfassung in Alltagssprache; GitHub lässt bei jedem
  Hochladen alle Tests laufen; `docs/00-ueberblick.md` zeigt das Ganze in Bildern; dazu `CHANGELOG.md` mit Versionen und
  diese Entscheidungsliste. Vor dem Echtbetrieb mit Kundendaten folgt eine unabhängige Prüfung von außen.
- **Begründung:** Patrick muss den Code nicht lesen, um zu verstehen und freizugeben, was sich ändert. Die Tests
  laufen dann unabhängig von der Aussage „alles grün“.
- **Folgen:** Kein direktes Hochladen auf `main` mehr; Freigabe durch Patrick per Merge.
