# Änderungen je Version

In Alltagssprache: was neu ist und worauf man achten muss. Technische Einzelheiten stehen in den Commits und in
`docs/`. Versionen: **0.x** = Aufbau vor dem Echtbetrieb; die mittlere Zahl steigt mit jedem fertigen Baustein, die
letzte bei Korrekturen. Jede Version ist in Git als Markierung (Tag `v0.3.0` usw.) festgehalten; was gerade auf dem
Server läuft, steht dort in `/opt/pgh-wartung/app/STAND`.

## Noch ohne Version

- **Übersicht:** `docs/00-ueberblick.md` mit Bildern (Systemaufbau, Datenmodell, Lebenslauf eines Auftrags, Stand der
  Bausteine). Datenmodell und Auftragsstatus werden aus dem Code erzeugt; ein Test meldet, wenn sie veraltet sind.
- **Automatische Prüfung auf GitHub:** Bei jedem Hochladen laufen alle Tests auf einem fremden Rechner. Ergebnis ist
  ein grüner oder roter Haken am Commit und am Pull Request.
- **Arbeitsweise:** Änderungen kommen als Pull Request mit Zusammenfassung in Alltagssprache (Vorlage
  `.github/pull_request_template.md`); dazu dieses CHANGELOG und die Entscheidungsliste `docs/09-entscheidungen.md`.
- Am Programm selbst ändert sich nichts.

## 0.3.0 – Aufträge (09.10.2026)

- Aufträge planen, direkt aus der Anlage oder für viele Anlagen auf einmal (Ankreuzen in der Anlagenliste).
  Mit Auftragsart, Techniker (oder Pool ohne Techniker), Datum, Uhrzeit und Auswahl der Wohnungen.
- Ablauf: geplant → in Arbeit → abgeschlossen → abgerechnet oder ohne Rechnung; stornieren möglich. Rückschritte und
  Stornieren nur mit Grund. Jeder Schritt und jedes Verschieben steht im Verlauf des Auftrags.
- Menü „Aufträge“: Liste mit Filtern und Wochenansicht. Büro und Planende sehen alles, Techniker nur ihre eigenen
  Aufträge und den Pool.
- Startseite als Cockpit: Termine heute und in dieser Woche, überfällige Aufträge, fällige Anlagen ohne Auftrag,
  Aufträge zum Abrechnen.
- Anlagen mit (nicht stornierten) Aufträgen und Wohnungen in offenen Aufträgen lassen sich nicht mehr löschen.
- Foxtag-Format: offene Aufträge werden mit exportiert und lassen sich auch importieren.
- Kopfzeilen des Foxtag-Exports stimmen jetzt exakt mit den Foxtag-Vorlagen überein.
- **Beim Einspielen:** Datenbank-Umbau Nr. 6 (vorher gesichert).

## 0.2.0 – Stammdaten (09.10.2026)

- Kunden mit Kontakten, Objekte (Anschrift eigen oder wie beim Kunden), Anlagen mit Ansprechpartnern, Wohnungen und
  Melder. Gelöscht wird nur als Markierung, mit Rückfrage.
- Typenkatalog der Melder; Austausch und Ausbau mit Verlauf je Melder; Wohnung kopieren.
- Fälligkeiten mit Ampel in der Anlagenliste, in der Anlage und auf der Startseite.
- Excel-Import im Format der Foxtag-Vorlagen: erst Probelauf mit Vorschau, dann alles oder nichts übernehmen.
  Vorhandenes bleibt unverändert.
- Export: Vollexport aller Daten (JSON/CSV) und Export im Foxtag-Format, damit ein Wechsel jederzeit möglich bleibt.
  Jeder Export wird protokolliert.
- **Beim Einspielen:** Datenbank-Umbauten Nr. 3–5.

## 0.1.0 – Grundgerüst (08.10.2026)

- Server auf LXC 192, Webseite im Heimnetz.
- Anmeldung mit Sperre nach 5 Fehlversuchen; neue Nutzer bekommen einen Einladungslink zum Passwort-Setzen.
- Nutzer, Rollen und Einzelrechte (Rollen sind kombinierbar), Firmendaten, Änderungsprotokoll (nur anhängen).
