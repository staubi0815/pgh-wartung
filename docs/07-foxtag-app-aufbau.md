# Foxtag 2 (Android) – Aufbau, Offline-Speicher, Abgleich (Analyse 08.10.2026)

Grundlage: App-Paket Foxtag 2, Version 111.0.6 (Android, Stand Okt. 2026). Zerlegung mit Erlaubnis von Foxtag
(telefonisch durch Patrick, schriftliche Bestätigung angekündigt). Ausgewertet wurden nur Paketbeschreibung,
Dateinamen und im Programm enthaltene Texte – **kein Programmcode übernommen**, alles in eigenen Worten
(Grundsatz 7). Rohdaten und Werkzeuge nur lokal (`~/.local/state/pgh-brandschutz/foxtag-apk/`,
`~/tools/apk-analyse/`), nicht im Repo. Keine Anfragen an Foxtag-Server gestellt.

## 1. Technik

| Bereich | Foxtag 2 | Bedeutung für uns |
|---|---|---|
| Rahmen | Flutter (Dart), eine Codebasis für Android und iOS; ab Android 10 | wir: PWA (eine Codebasis für Tablet und Laptop, ohne Store) |
| Offline-Speicher | SQLite auf dem Gerät (WAL), 32 Tabellen | wir: IndexedDB im Browser – gleiches Prinzip |
| Anmeldung | OpenID Connect (AppAuth), Schlüssel im sicheren Gerätespeicher | wir: Geräte-Anmeldung mit widerrufbarem Geräteschlüssel (Tabelle `geraet`) |
| Server | REST unter `/api/v1/`, Fotos/Dateien direkt in einen Objektspeicher (vorab signierte Upload-Adressen) | wir: eigener Server, Dateien auf LXC 192 |
| Anstoß zum Abgleich | Push-Nachricht über Firebase (Google), zusätzlich regelmäßig und von Hand | wir: **kein** Google-Dienst (Daten bleiben zu Hause) → regelmäßig, beim Öffnen, bei Netz-Rückkehr, nach Auftragsende |
| Scannen | Google ML Kit (Barcode/QR) über die Kamera; jeder Scan wird lokal festgehalten | wir: Barcode-Erkennung im Browser; Scan-Zeitpunkt als Nachweis speichern |
| Weiteres | Karten (OpenStreetMap/Mapbox), Kalender, Standort, Unterschrift von Hand, PDF-Anzeige, Vorlesen (Text-to-Speech), Absturz-/Nutzungsstatistik an Google | Statistik an Dritte: bei uns nicht |

Programmaufbau (nach Ordnern): Schnittstelle (42 Teile, je Datenart einer), Datenbankzugriff (35), Abgleich (29),
Befehle (40 Befehlsarten), Dienste, Oberfläche (~300 Dateien), Hilfsfunktionen (u. a. „Zusammenfassen“ von Befehlen).

## 2. Begriffe (Foxtag → wir)

| Foxtag intern | Foxtag Oberfläche | pgh-wartung (docs/03) |
|---|---|---|
| installation_type | Wartungsanwendung | Anlagenart (`konfig/anlagenarten/*.toml`) |
| installation | Anlage | anlage |
| location | Objekt | objekt |
| group | Gruppe (bei RWM: Wohnung) | gruppe |
| thing | Komponente (Melder) | komponente |
| thing_type | Komponenten-Typ | komponententyp |
| job / job_type | Auftrag / Auftragstyp | auftrag / Auftragsart |
| job_thing | Umfang des Auftrags | (Auftrag ↔ Komponenten) |
| event (Art „check“, „installation“) | Prüfung / Einbau | pruefung ⊕ |
| incident / incident_status | Störung / Status-Verlauf | mangel ⊕ / mangel_status ⊕ |
| signature (mit Gruppe) | Unterschrift (je Wohnung) | auftrag_unterschrift ⊕ |
| stocked_thing | Lagerbestand (noch nicht verbaut) | – (neu, s. u.) |
| scan_event | Scan-Nachweis | – (neu, s. u.) |
| command | (unsichtbar) wartende Änderung | – (neu: Befehlsprotokoll, s. Abschnitt 4) |

## 3. Datenhaltung auf dem Gerät (Prinzip)

- Jede Tabelle ist eine **Kopie** des Server-Stands: eigene ID (Text/UUID), `updated_at`, Löschmarke statt
  Löschen, und eine **vom Server vergebene laufende Abgleich-Nummer** je Datensatz. Das Gerät fragt je Tabelle
  „alles nach Nummer X“ ab – keine Zeitstempel-Vergleiche, dadurch keine Probleme mit falsch gehenden Uhren.
- **Was aufs Gerät kommt**, steuert ein „Abo“ je Anlage: Das Gerät meldet, welche Anlagen es braucht (z. B. die
  der eigenen Aufträge); für neu abonnierte Anlagen gibt es einen Nachhol-Abruf. Ein Rücksetzen („alles löschen und
  neu laden“) ist vorgesehen.
- **Fälligkeiten rechnet der Server** und schickt sie als fertige Felder mit (nächste Prüfung, Vorwarnung,
  Austausch fällig, „ungeprüft seit“). Die App rechnet nicht selbst.
- **Prüfungen sind Ereignisse** (nur anhängen): Zeitpunkt, Art (Prüfung/Einbau/vorläufig), Ergebnis, Bemerkung,
  Checklisten-Werte als Datenpaket, Techniker, Auftrag. Ergebniswerte u. a.: in Ordnung, Mangel, ignoriert,
  keine Info.
- **Komponenten haben einen Lebenslauf**: im Lager → verbaut → ersetzt/entfernt. Austausch ist ein eigener Vorgang
  (alter Melder raus, neuer rein, Verweis auf den Auftrag), nicht „Felder überschreiben“.
- **Anlagenart** trägt die Bezeichnungen und Schalter: wie Gruppen/Komponenten heißen („Wohnung“, „Melder“),
  Trennzeichen für Nummern, ob es Unterschriften je Gruppe gibt, Fotos, Lager, Zentrale, eigene Zusatzfelder.
- **Auftragstyp** schaltet die Schritte: Erfassen/Installation, Prüfungen, Material, Unterschrift Techniker,
  Unterschrift Kunde, Material je Komponente, Checkliste vorher/nachher.
- **Mängel** haben eine eigene Status-Historie (nur anhängen) mit Bezug auf Auftrag und Prüfung; Mängelart
  mit Vorgabe-Schweregrad und „Austausch vorschlagen“.
- Fotos hängen an Komponente, Mangel oder Auftrag; werden getrennt hochgeladen.

## 4. Abgleich (Kern)

**Hochladen = Befehle, nicht Datensätze.** Jede Änderung in der App wird
1. sofort lokal angewendet (die Oberfläche zeigt sie gleich) und
2. als **Befehl** in eine Warteschlange geschrieben: eindeutige Befehls-ID, Art (z. B. „Melder geprüft“,
   „Melder ersetzt“, „Mangel angelegt“, „Unterschrift hinzugefügt“, „Prüfung verwerfen“), betroffener Datensatz,
   Zeitpunkt, Auftrag, Nutzdaten, Status „noch nicht gesendet“.

Beim Abgleich werden die wartenden Befehle **in Reihenfolge, in Paketen** an den Server geschickt. Der Server
führt sie aus und ist **maßgeblich**; das Ergebnis kommt beim nächsten Herunterladen als normaler Datenstand zurück.
Aufeinanderfolgende Änderungen am selben Datensatz werden vor dem Senden **zusammengefasst**. Rund 40 Befehlsarten,
u. a.: Komponente prüfen / Prüfung verwerfen / einbauen / ersetzen / entfernen / ändern / duplizieren, Lager-
komponente anlegen und einbauen, Gruppe anlegen/ändern/verwerfen, Notiz, Kontakt, Mangel und Mangel-Status,
Material, Anhang, Foto, Unterschrift, Auftragsstatus, -termin, -checkliste, -labels, Komponententyp anlegen.

**Herunterladen = Zustand.** Je Tabelle die Änderungen seit der letzten Abgleich-Nummer.

**Sichtbar für den Techniker:** Zähler „X Datensätze warten auf Abgleich“ / „alles abgeglichen“, Knopf
„Jetzt abgleichen“, automatischer Abgleich in regelmäßigen Abständen, beim Beenden eines Auftrags die Frage
„jetzt abgleichen?“, **Warnung beim Abmelden**, wenn noch nicht gesendete Daten da sind; ist die Anmeldung
abgelaufen, Aufforderung zum erneuten Anmelden, „damit kein Datenverlust entsteht“. Diagnose-Datei kann zum
Support hochgeladen werden.

Folge: Es gibt auf dem Gerät **keine Konfliktauflösung** – zwei Techniker erzeugen einfach zwei Befehle; der
Server entscheidet. Prüfungen kollidieren nie (beide werden gespeichert).

## 5. Folgerungen für pgh-wartung

Übernehmen (als Idee, eigene Umsetzung):

1. **Befehlsprotokoll statt Datensatz-Abgleich** (ändert docs/02 Abschnitt Abgleich, siehe dort): App schreibt
   Befehle in eine Ausgangs-Warteschlange (IndexedDB), Server nimmt sie **idempotent** an (Befehls-ID doppelt =
   ignorieren, wichtig bei Funkloch mitten im Senden), führt sie in Reihenfolge aus, protokolliert sie im
   Änderungsprotokoll. Passt genau zu Grundsatz 5 (nur anhängen) und ist einfacher und robuster als
   feldweises Zusammenführen auf dem Gerät. Widersprüche (z. B. Befehl auf inzwischen gelöschten Melder) landen
   serverseitig in der Konfliktliste fürs Büro.
2. **Server-Abgleichnummer** je Datensatz (fortlaufend, vom Server vergeben) statt Zeitstempel.
3. **Abo je Anlage** für den Geräte-Umfang + Nachholen + „Gerät zurücksetzen“.
4. **Fälligkeiten nur auf dem Server rechnen**, als Felder mitschicken.
5. **Lebenslauf der Melder** (Lager → verbaut → ersetzt/entfernt) und **Austausch als eigener Vorgang** – deckt
   Patricks Ablauf „Mangel → sofort tauschen“ ab; Lagerbestand ist für den Melderverkauf nützlich.
6. **Scan-Nachweis** speichern (wann welcher Melder gescannt wurde).
7. **Anzeige wartender Datensätze**, Abmelde-Warnung, Abgleich bei Auftragsende – genau das braucht der Keller.
8. Unterschrift mit Bezug auf die Wohnung (für den späteren Einzelnachweis je Wohnung).

Bewusst anders:

- Keine Google-Dienste (Push, Statistik, Absturzberichte) – Abgleich-Anstoß ohne Push (s. Abschnitt 1).
- Kein App-Store-Zwang: PWA. Dafür prüfen: Kamera-Scan und Speicher-Dauerhaftigkeit (`navigator.storage.persist()`)
  auf dem Android-Tablet.
- Zusatzfelder und Bezeichnungen über unsere Anlagenart-Konfiguration statt Datenbank-Einstellung.

Offen (nur durch Bedienen der App im Testkonto zu klären, Variante B aus docs/06): Bildschirmfolge im Detail,
Bedienung beim Prüfen vieler Melder, Austausch-Dialog, Mieter-Unterschrift, Bericht.
