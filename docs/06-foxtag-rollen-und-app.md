# Foxtag: Nutzer-Rollen und App – Analyse (Stand 08.10.2026)

Quellen: eigenes Foxtag-Testkonto (nur gelesen, nichts gespeichert), öffentliche Leistungsbeschreibung
(Stand 01.09.2024), AGB (Stand 01.05.2021), Store-Einträge (App Store, Google Play).
Rohdaten lokal unter `~/.local/state/pgh-brandschutz/foxtag-analyse/` (nicht im Repo).
Texte sind sinngemäß wiedergegeben, nicht 1:1 übernommen (Grundsatz 7).

## 1. Nutzer und Rollen bei Foxtag

### Aufbau

- **Personen-Konto** (E-Mail, Name, Passwort) ist getrennt vom **Nutzer im Firmenkonto**. Eine Person kann in
  mehreren Firmenkonten (Niederlassungen) Nutzer sein, je mit eigenen Rechten.
- Einladung per E-Mail; Status in der Liste (eingeladen / angemeldet). E-Mail und Name pflegt der Nutzer selbst.
- Pro Nutzer: optionale Mitarbeiter-/Personalnummer, Zeitzone, **Liste der angemeldeten Geräte**
  (Gerät, angemeldet seit). Begrenzung: **2 Geräte gleichzeitig** je Nutzer.
- **Zwei-Faktor-Anmeldung (2FA)** als Richtlinie je Rolle einstellbar.
- **Kundenservice-Zugang:** Foxtag-Support kann per Code befristet ins Firmenkonto eingeladen werden.
- **Portal-Nutzer:** Kunden (z. B. Hausverwaltung) bekommen Lesezugriff auf freigegebene Anlagen/Berichte.
- Lizenz: jeder Nutzer kostet (Testphase: 5 Lizenzen frei, 30 Tage).

### Rollen = Bündel aus Einzelrechten, mehrere Rollen je Nutzer kombinierbar (Kontrollkästchen)

Eigene Rollen anlegen bzw. anpassen ist möglich (Pro). Standardrollen:

| Einzelrecht (sinngemäß) | Administration | Planen und Daten pflegen | Techniker | Techniker ohne Webzugang |
|---|:-:|:-:|:-:|:-:|
| Web-Bereich betreten | ✓ | ✓ | ✓ (nur eigene Aufträge) | – |
| Kunden / Objekte / Anlagen / Komponenten verwalten | ✓ | ✓ | – | – |
| Störungen (Mängel) verwalten | ✓ | ✓ | – | – |
| Aufträge planen und verwalten | ✓ | ✓ | – | – |
| Admin-Bereich: Artikel, Kontakte, Labels | ✓ | ✓ | – | – |
| Mitarbeiter einladen/löschen, Rollen bearbeiten, Geräte abmelden, Kundenservice-Zugang | ✓ | – | – | – |
| Berichtslayouts, Wartungsanwendungen, Integrationen, allgemeine Einstellungen | ✓ | – | – | – |
| Daten exportieren | ✓ | ✓ | – | – |
| Auswertungen erstellen | ✓ | – | – | – |
| Import (Kunden, Objekte, Anlagen, Komponenten, Aufträge, Artikel, Kontakte) | ✓ | ✓ | – | – |
| App: anmelden | ✓ | – | ✓ | ✓ |
| App: Aufträge starten und durchführen | ✓ | – | ✓ | ✓ |
| App: Ansprechpartner verwalten | ✓ | – | ✓ | ✓ |
| App: Dateien am Auftrag verwalten | ✓ | – | ✓ | ✓ |

Auffällig: „Planen und Daten pflegen“ darf **nicht** in die App. Nutzer verwalten darf sie laut offizieller Rechtetabelle (PDF 2021) **nicht** – das ist allein Administration (korrigiert 10.10.2026, vorher stand hier das Gegenteil). Im Administrationsbereich hat „Planen“ nur Artikel, Labels, Datenimport und Löschen von Anlagenvorlagen.

### Zusätzlich firmenweit: „App-Rechte“ (gelten für alle App-Nutzer)

Neue Aufträge in der App anlegen · Auftragsdatum verschieben (vor Beginn) · Fotos an Komponenten · Fotos an
Störungen · Fotos am Auftrag · fehlende Artikel anlegen · fehlende Komponenten-Typen anlegen.

### Vergleich mit unserem Grundgerüst

| Punkt | Foxtag | pgh-wartung heute | Bewertung |
|---|---|---|---|
| Rollen | 4 Standardrollen, frei anpassbar, kombinierbar | 3 feste Rollen (admin, buero, techniker), eine je Nutzer | gleiche Idee, unseres ist starrer |
| Rechteprüfung | Einzelrechte | Rollenname im Code | **umstellen auf Einzelrechte**, solange es nur wenige Seiten gibt |
| Techniker ohne Web | eigene Rolle | fehlt | als Rolle ergänzen |
| App-Rechte firmenweit | 7 Schalter | fehlt | mit der App (Stufe 4) als Firmeneinstellung |
| Geräteliste je Nutzer | ja, max. 2 | Tabelle `geraet` geplant (docs/03) | mit der App; Gerät sperren = Abmeldung |
| 2FA | je Rolle | nein | bei uns ersetzt WireGuard (nur mit Geräteschlüssel erreichbar) den zweiten Faktor; später optional TOTP für admin |
| Mehrere Firmenkonten | ja | nein (eine Firma) | nicht nötig |
| Portal für Kunden | ja | nein | später (Stufe 6), braucht Zugang von außen → eigene Entscheidung |
| Support-Zugang | ja | entfällt | – |

**Entscheidung (Patrick 08.10.2026, umgesetzt mit Migration 002):** Rechte als feste Liste im Code
(`server/wartung/rechte.py`), Rollen als benannte Bündel in der Datenbank, mehrere Rollen je Nutzer. Standardrollen
Administration (fest, alle Rechte), Planen und Daten pflegen, Techniker, Techniker ohne Webzugang (Namen und Rechte seit Migration 007 wie bei Foxtag; Patrick kann sie in der Maske ändern). Foxtags firmenweite App-Schalter sind bei uns
Einzelrechte je Rolle (feiner). Seiten prüfen nur noch Rechte, nie Rollennamen. Details: `docs/04` Abschnitt 9.

## 2. Die Foxtag-App

### Zwei Apps

| | Foxtag (alt) | Foxtag 2 (neu, aktuell) |
|---|---|---|
| Kennung | `co.foxtag.serviceapp` | `app.foxtag.service` |
| Stand | Vorgänger, Umstieg wird empfohlen | komplett neu entwickelt, Version 111 (Okt. 2026), Updates alle 1–3 Wochen |
| Plattform | Android, iOS | Android, iOS/iPadOS (ab iOS 15.5), ca. 47 MB |
| Verbreitung | – | Play Store „500+ Downloads“ |

Die Rolle hat getrennte Rechte für beide Apps (Übergangszeit).

### Arbeitsweise (öffentlich beschrieben)

- **Native App**, Verwaltung nur im Web; App ist für die Durchführung von Aufträgen.
- **Offline:** Auftrag vorab geladen, Arbeit ohne Netz (Keller), Abgleich automatisch, sobald Netz da ist.
- **Laufender Abgleich**, dadurch können **mehrere Techniker am selben Auftrag** arbeiten.
- Ablauf je Auftragstyp einstellbar (Schritte, Checklisten, Messwerte, Verbrauchsmengen) – siehe docs/01 Abschnitt 5.
- Identifikation per **QR-/Barcode-Scan** (Kamera), Scan auch als Nachweis „vor Ort gewesen“.
- Fotos (Komponente, Störung, Auftrag; Mehrfachauswahl aus Galerie, Komprimierung), Dateianhänge (auch CSV/TXT).
- Unterschrift Techniker und Kunde bzw. **Mieter je Wohnung**; Bericht wird danach automatisch erzeugt.
- Mangel → **direkter Austausch-Ablauf** (Melder tauschen im selben Auftrag).
- Pro-Funktionen: Aufträge/Kunden in der App anlegen, Termin verschieben, Störungsbehebung mit Historie, Karte.
- Lagerartikel/Material je Auftrag, Zähler, Kalender-Anbindung.

### Berechtigungen der Android-App (Play Store)

Kalender · Standort · Kamera · Sonstiges. Laut Datenschutzangabe erhoben: personenbezogene Daten, Fotos/Videos,
Geräte-IDs, Absturz-/Diagnosedaten, genauer Standort; Übertragung verschlüsselt.

### Was öffentlich nicht beschrieben ist (→ selbst ausprobieren)

Bildschirmfolge im Detail, Verhalten bei Konflikten (zwei Techniker ändern denselben Melder), wie der Auftrag
aufs Gerät kommt (automatisch/manuell), Anzeige „noch nicht abgeglichen“, Verhalten bei Abmeldung mit
ungesendeten Daten, Wohnungs-/Mieterunterschrift, Austausch-Ablauf, Bedienung mit Handschuhen/einhändig.

## 3. Wie wir die App analysieren

**Stand 08.10.2026:** Patrick hat nach eigener Aussage telefonisch mit Foxtag die Erlaubnis zum Zerlegen und
Analysieren vereinbart (schriftliche Bestätigung per Mail angekündigt; Risiko trägt Patrick ausdrücklich).
App-Paket Foxtag 2 Version 111.0.6 geladen (lokal, nicht im Repo). Erkannt aus der Paketliste: **Flutter/Dart**,
lokale **SQLite**, Barcode-Erkennung (ML Kit), PDF-Anzeige (pdfium), Kamera (CameraX), Android ab 10 (SDK 29).
Die Zerlegung wurde zunächst von der Sicherheitsprüfung der Claude-Umgebung gestoppt; Patrick hat die
Analyse-Werkzeuge danach ausdrücklich freigegeben. Ergebnis: `docs/07-foxtag-app-aufbau.md`. Grundsatz 7 gilt unverändert: kein Foxtag-Code, keine Texte, nur Erkenntnisse in eigenen Worten.

Ursprünglicher Plan (ohne Zerlegen):

**Nicht:** App-Datei (APK) zerlegen oder zurückübersetzen. Die AGB (Nr. 10.3) erlauben Dekompilieren nur im
Rahmen von § 69e UrhG – also nur für Kompatibilität, wenn die Infos nicht anders zu bekommen sind, und **nicht
zur Entwicklung eines ähnlichen Programms**. Für den Wechsel brauchen wir nur das Importformat, das ist
öffentlich (docs/05). Zerlegen wäre also unzulässig – und passt nicht zu Grundsatz 7.

**Sondern:** Foxtag 2 als normaler Nutzer im Testkonto bedienen (erlaubt: Nutzung auf eigenen Geräten).

1. Patrick installiert **Foxtag 2** aus dem Play Store auf dem Android-Tablet bzw. Handy und meldet sich mit dem
   Testkonto an. Nur Demodaten (kein echter Kunde im Testkonto).
2. Im Web lege ich einen Testauftrag für die Demo-Anlage an (Rauchwarnmelder, 2 Wohnungen, wenige Melder).
3. Durchgang Schritt für Schritt, jede Maske festhalten:
   - **Variante A (empfohlen):** Tablet per „Drahtloses Debugging“ (Entwickleroptionen) mit LXC 191 koppeln;
     Claude liest Bildschirm und Bildschirmaufbau (Bedienelemente, Texte) mit `adb` aus – das ist Beobachten
     der Oberfläche, kein Zerlegen. Danach Debugging wieder aus.
   - **Variante B:** Patrick macht Bildschirmfotos und legt sie in Drive ab.
4. Gezielte Tests: Flugmodus (offline) während des Auftrags, zwei Geräte gleichzeitig am selben Auftrag
   (Tablet + Handy, Foxtag erlaubt 2 Geräte), Mangel + Austausch, Mieterunterschrift, Bericht.
5. Ergebnis: Maskenfolge der App (docs/07) als Vorlage für unsere PWA, eigene Gestaltung.

Frist: Testkonto läuft bis ca. 08.11.2026.
