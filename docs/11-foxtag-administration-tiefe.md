# 11 – Foxtag in voller Tiefe: Administration, Anlagenseite, Auftragsseite ↔ pgh-wartung (Stand 10.10.2026)

Ergänzt `docs/10` (dort nur Überschriftenebene). Hier jeden Menüpunkt, jeden Reiter und jeden Dialog der Administration
einzeln durchgesehen, dazu die Anlagen-, Kunden-, Objekt- und Auftragsseite. Alles nur lesend im Testkonto erfasst,
nichts gespeichert, Rohdaten außerhalb des Repos. Erkenntnisse in eigenen Worten (Grundsatz 7).

Bewertung wie in `docs/10`: **K** Kern vor Echtbetrieb · **W** wichtig, bald · **S** später/optional · **=** gleichwertig ·
**+** bei uns besser/mehr.

**Nicht erfasst (Grenze der Methode):** Die Auftragsreiter Prüfungen, Artikelpositionen, Störungen, Fotos, Notizen
zeigen im Testkonto überall 0 Einträge; mit Inhalt sind sie nur durch Bedienen der App (Schreiben in Foxtag) zu sehen.
Aufbau und Bedienelemente der leeren Reiter sind erfasst, die Inhaltsdarstellung steht in `docs/08` (App). Die
Rollenbearbeitung ist im Testkonto nicht sichtbar (Pro-Funktion); Quelle ist die offizielle Rechtetabelle (`docs/06`).

## 1 Wartungsanwendung (Foxtag-Begriff für Anlagenart) – je Anwendung sieben Reiter

Bei Foxtag ist **alles konfigurierbar in der Oberfläche** und gehört einer Anwendung (Rauchwarnmelder, RWM-Einfamilienhaus,
Türen …). Bei uns steht dasselbe in einer Datei je Anlagenart im Repo (`konfig/anlagenarten/*.toml`), geprüft beim
Start. Das ist bewusst (Nachvollziehbarkeit, Version im Repo), aber Patrick kann nichts selbst ändern.

| Reiter | Foxtag | Wir | Bew. |
|---|---|---|---|
| Basisdaten | Name, Nummer; Anlagen haben Zentrale ja/nein; Aufträge mit Auftragsnummern; Fotos ja/nein; Lager-Funktion; Gruppen-Trenner (/ oder .); Kundenunterschrift je Gruppe; eigene Wörter für QR-Code/Komponente/Gruppe | `[allgemein]`: Name, Gruppe/Komponente (Einzahl/Mehrzahl), Trenner, Unterschrift je Gruppe, Fotos, Einzelnachweis | = ; **Zentrale** und **Lager** fehlen (S, erst für Türen/BMA) |
| Stammdaten | feste Felder an der Komponente + eigene Zusatzfelder (Name, Feldtyp, „im Bericht drucken“) | feste Felder; keine Zusatzfelder | W (Türen brauchen Zusatzfelder: Flügel, Brandschutzklasse) |
| Komponenten-Typen | Kategorien Komponente / Sub-Komponente / Zentrale; Typ = Name, Hersteller, Modell, Link; Liste mit Intervallen, Checklisten, Anzahl; Zusammenführen; Löschen nur wenn unbenutzt; Import/Export | Typ mit Hersteller, Modell, Funk, Batterie, Austauschjahre, Datenblatt; Kategorie komponente; kein Zusammenführen | W: **Typen zusammenführen** (Importe erzeugen Dubletten), **Sub-Komponente/Zentrale** (Türen) |
| Intervalle | Prüf- und Austauschintervall je Kategorie, **mit Typ-/Herstellerfilter**; „bald überfällig“ N Tage; Austausch ab Inbetriebnahme oder Baujahr; Neuberechnung nach Speichern | ein Intervall je Anlagenart (`[intervalle]`), Austausch ab Baujahr/Inbetriebnahme, Vorwarnung | W: Intervall **je Typ** (Türen: Obertürschließer ≠ Feststellanlage) |
| Checklisten | Komponenten-Checklisten (mit Zuordnung per Kategorie + Typfilter + Position) und allgemeine Auftrags-Checklisten; Zeile = Text, Zahl, Überschrift, Checkbox, Ja/Nein, Ja/Nein/n.v., i.O./n.i.O. (+n.v.), Einheit, vorausgefüllt, Pflicht; sortierbar; Import | **eine** Checkliste je Anlagenart: ja_nein, text, zahl, auswahl, Pflicht, Mangel bei „Nein“ | W: mehrere Checklisten, Typzuordnung, Überschrift, n.v.-Antwort, Einheit; **+** bei uns: Mangel entsteht automatisch aus der Antwort |
| Störungstypen | Name, Schweregrad, „Austausch vorschlagen“, im Auftraggeberportal sichtbar, aktiv, Standardbeschreibung, Position | `[[mangel]]`: Name, Schweregrad, Austausch vorschlagen; kein Portal, kein Standardtext | = (Portal S) |
| Auftragstypen | je Typ: Name, Nummer, aktiv, „für passive Anlagen“, Standard; **sieben schaltbare App-Schritte** (Inbetriebnahmen, Vorarbeiten + Checkliste, Prüfungen, Nacharbeiten + Checkliste, Material, Unterschrift Techniker, Kundenunterschrift); Bericht: Layout, Titel, Untertitel; Artikel-Vorauswahl aus Datei | `[[auftragsart]]` mit Schrittliste und Berichtstitel; 4 Arten (Wartung, Installation, Nachtermin, Ferninspektion) | = ; W: Untertitel, Vorauswahl von Artikeln je Auftragsart (mit Material); „für passive Anlagen“ S |

Weitere Befunde: Änderungen an Intervallen, Stammdaten, Checklisten wirken erst nach einigen Minuten (Neuberechnung im
Hintergrund) – bei uns sofort, weil die Fälligkeit beim Lesen berechnet wird (**+**). Foxtag lässt die Namen
„QR-Code/Komponente/Gruppe“ pro Anwendung umbenennen; wir ebenso über `[allgemein]`.

**Beispielbestand im Testkonto (nur Größenordnung):** RWM 1 Typ + Herstellertypen, 7 Störungstypen; Türen 10 Typen
(Tür-Arten als Komponente, Zubehör als Sub-Komponente), 20 Störungstypen, 6 Checklisten, 4 Auftragstypen. Das zeigt:
für Türen ist die Konfiguration mehrstufig – unsere Ein-Datei-Struktur reicht dafür **nicht** (K für den Türen-Baustein:
Kategorien, Intervall je Typ, mehrere Checklisten, Zusatzfelder).

## 2 Anwendungsverzeichnis (Vorlagen)

Foxtag liefert ein Verzeichnis fertiger Anwendungen (zehn Branchen: Brandschutz, Türen/Tore, Aufzüge, Sicherheitstechnik,
Elektro/Ladesäulen u. a.; Vorlagen z. B. BMA, RWA, Feuerlöscher, Sprinkler, Wandhydrant, Rauchwarnmelder, Türen mit
Feststellanlage) mit Demo-Anlage je Vorlage und „verwenden“-Knopf; „eigene Anwendung“ braucht nur einen Namen.
**Wir:** Anlagenarten sind Dateien, neue = neue Datei im Repo. **Bew. S** (PGH braucht RWM und Türen, keine Vorlagenwelt).
Wichtig bleibt: Vorlagen von Foxtag nicht übernehmen (Inhalte sind Foxtags).

## 3 Administrations-Menüs außerhalb der Wartungsanwendungen

| Menü | Foxtag (Felder/Dialoge) | Wir | Bew. |
|---|---|---|---|
| Firma/Niederlassung | Firmendaten, Rechnungsadresse; mehrere Niederlassungen/Firmen im Konto | `verwaltung.firma`, eine Firma | = (Mehrfirma S) |
| Berichte und Logo | Logo per Drag&Drop; Layouts: Standard-Layout duplizieren und anpassen | Berichte fehlen (Baustein 5) | K |
| Labels | Name, Beschreibung, Farbe, Vorschau, „in App zeigen“, „im Portal zeigen“ | fehlen | W |
| Artikel | Sortierung (Position im Bericht), Gruppe, Art.-Nr., Bezeichnung, Einheit, aktiv; Import | fehlen | K (Material) |
| Kontakte | Name, Firma, E-Mail, Telefon, Mobil, Fax, Notiz; an Kunde **und** Anlage wählbar | je Kunde, ohne Firma/Fax | W |
| Auftragsnummern | Präfix/Startwert je Anwendung | `nummernkreis` | = |
| Vorlagen für Anlagen | s. Abschnitt 2 | – | S |
| Datenimport | 9 Arten, je eine Seite (Vorlage laden, hochladen, Vorschau) | 7 Arten + Probelauf, alles-oder-nichts | = ; fehlt: Artikel, Artikelpositionen, Labels |
| Mitarbeiter | Einladen: E-Mail, Name, Nummer, vier Rollen-Kästchen; je Person eigener Nutzer; Kundenservice-Zugang; Geräte abmelden | Einladung per Einmal-Link, Einzelrechte, kombinierbare Rollen | + ; Gerätelimit fehlt (K Baustein 4) |
| E-Mails | Absender, Antwortadresse, Vorlagen, automatische Terminankündigung | fehlt (Feld `angekuendigt_am`, kein Versand) | W (Baustein 5) |
| Kalender | iCal-Abo je Nutzer, Outlook-Anbindung, Einstellungen firmenweit | fehlt | S |
| Smartphone-App | sieben firmenweite Schalter | Einzelrechte je Rolle | + |
| Integrationen | CLSS, IRAS, SQL-Handel, ERP/API, Outlook, OneDrive, SMTP, **API-Keys mit Recht je Ressource** (Lesen/Schreiben/Löschen für Artikel, Labels, Kunden, Objekte, Anlagen, Kontakte, Aufträge; Nutzer/Anwendungen nur lesen), Event-Logs | Voll-Export, Änderungsprotokoll | S |
| Auswertungen | siehe Abschnitt 5 | Ampel + Cockpit | W |
| Startseite anpassen, Glocke | Kacheln wählbar; Benachrichtigungen | Start-Cockpit fest | S |
| Profil | Daten, Sicherheit (Passwort, **2FA**), Benachrichtigungen, **Geräte (max. 2)**, Kalender-Abo | Konto: Passwort | 2FA W, Geräte K (Baustein 4), Rest S |

## 4 Anlagenseite (Reiter) und Kunde/Objekt

| Stelle | Foxtag | Wir | Bew. |
|---|---|---|---|
| Kopf | Nächster Auftrag, Fälligkeiten (Prüfung/Austausch), Kunde und Objekt als Karte | Nächster Auftrag, Ampel | = |
| Reiter Anlage | Nummer, Name, **Techniker (Stammtechniker)**, Hinweise; **Ansprechpartner vor Ort** (aus Kontakten); Zusatzfunktionen: Integrationen (Zugangsdaten, Eigentümercode), **passiv schalten**, **verschieben** (neues Objekt wählen, Alt-Objekt optional löschen), löschen | Hinweise, Ansprechpartner mit Rolle, passiv; kein Stammtechniker, kein Verschieben | W |
| Komponenten | je Wohnung: Nummer, Name; Zeilen mit Typ, Standort, Barcode, S/N, Baujahr, Fälligkeit; Melder/Wohnung hinzufügen; Import/Export der Komponenten; Seitenaufteilung | Wohnungen/Melder, Austausch, Ausbau, Kopieren, Import/Export | + |
| Komponenten-Dialog | Labels, Typ, Seriennummer, Baujahr, **Zulassungsnummer** | ohne Zulassungsnummer an der Komponente | W |
| Wohnung-Dialog | Nummer, Name, **Link** | Wohnung mit Bewohner, Zugang, Notiz; kein Link | W: Link (offener Befund `docs/10` Abschnitt 7) |
| Aufträge | Liste der Aufträge der Anlage, „Auftrag planen“ mit Hinweis auf **historische Prüfergebnisse als externer Auftrag** einpflegen | Abschnitt Aufträge in der Anlage | W: Altprüfungen nachtragen (Umstieg von Papier/Foxtag) |
| Störungen | Liste mit Filter gemeldet/offen, Schweregrad, Zielauftrag, Label; „Störung erfassen“: Komponente, Störungstyp, Status, Datum/Uhrzeit, Schweregrad, **Gemeldet von (Kunde)**, Beschreibung | Mängel entstehen in der App-Prüfung, keine freie Erfassung im Web | K (Baustein 4/5), **Gemeldet von** übernehmen |
| Notizen, Dateien | Notizen je Anlage; Dateien (Pläne, Handbücher) mit Zugriff für Techniker vor Ort | keine Tabellen | K |
| Freigaben | Berichtsempfänger per E-Mail ohne Portalzugang (aus Kontakten) | fehlt | K (Baustein 5) |
| Auswertungen (Anlage) | Jahresbericht (für jährlich geprüfte Anlagen), Störungsliste, Material und Leistungen über alle Aufträge | fehlt | W |
| Kunde | Nummer, Name, Link, Adresse (2 Zeilen), PLZ/Ort/Land, **Koordinaten** auto/eigen, interne Notiz (nicht aufs Smartphone), Reiter Kontakte (mit Funktion, Notiz, Zähler) | wie `docs/10`; Koordinaten fehlen | = |
| Objekt | Kunde (wechselbar), Nummer, Name, Zeitzone, Adresse wie Kunde/eigen, Koordinaten; Löschen nur ohne Anlagen | vergleichbar | = |
| Karte | Filter Anwendung, Kunde, Prüf-/Austauschfälligkeit, Techniker | fehlt | S |
| Störungsliste (global) | Filter Zeitraum, Anwendung, Kunde, Objekt, Status, Schweregrad, Zielauftrag, Label; Export | fehlt | K mit Störungen |

## 5 Auswertungen (Parameter einzeln)

| Auswertung | Parameter bei Foxtag | Wir | Bew. |
|---|---|---|---|
| Jahresfortschritt | Anwendung, Jahr, PDF/CSV | Cockpit (heute/Woche/überfällig/fällig) | W |
| Material und Leistungen | Jahr, Excel/CSV | fehlt (Material fehlt) | K mit Material |
| Austauschfälligkeiten | fällig bis, Anwendung, **Stammtechniker**, Objekt/Adresse, PLZ, Label, Excel/CSV | Ampel in Liste | W: als Liste/Excel (Kundenschreiben „Melder tauschen“) |
| Komponenten-Typen finden | Anwendung, bis 5 Typen, Excel/CSV | Suche im Typenkatalog | S |

## 6 Auftragsseite im Detail

| Punkt | Foxtag | Wir | Bew. |
|---|---|---|---|
| Status | in Planung → geplant → Auftrag läuft → erledigt → abgerechnet; Menü: zurück in Planung, auf „läuft“ setzen, entfällt, **als extern beenden**, löschen | geplant → läuft → abgeschlossen, storniert, Verschieben mit Grund, Verlauf | W: „in Planung“ (unfertige Planung), „abgerechnet“, **extern beenden** |
| Kopf | Nummer, Datum+Uhrzeit (Datum/Zeit/ganztägig getrennt bearbeitbar), mehrere Techniker, Hinweise (eigener Dialog), Kunde/Objekt/Anlage, **Verlauf mit Zeitstempel und Nutzer**, iCal-Download, Chips „+Link“ und „+Label“ | wie links, ohne Link/Label/iCal | = ; W Label/Link |
| **Prüfumfang** | „Ganze Anlage (n Komponenten)“ oder **detaillierte Planung**: je Komponente ein Schalter „eingeplant“ (Nummer, Typ, Standort, Barcode, S/N, Baujahr, Fälligkeit, Labels), zusätzlich eingeplante Störungen | Auswahl der Wohnungen im Auftrag (`auftrag_gruppe`), nicht je Melder | W: je Melder (Nachtermin einzelner Melder) |
| Neuer Auftrag | Auftragsnummer automatisch oder eigene, Anlage, Typ, Datum/Uhrzeit/bis/ganztägig, Techniker (mehrere, „Jeder (Pool)“), Prüfumfang, Hinweise | wie links; Bis-Zeit statt Dauer | = |
| Veröffentlicht | Schalter Ja/Nein; Berichtsempfänger (E-Mail mit Download-Link); Versandhistorie | fehlt | K (Baustein 5) |
| Berichte und Dateien | Kennzahlen: geprüfte Komponenten n von m (%), bestätigte Prüfungen, Mängel, Unterschriften; Liste aktualisieren, Bericht laden | fehlt | K |
| Reiter | In-/Außerbetriebnahmen · Prüfungen (auch allgemeine Checklisten) · Artikelpositionen (im Web editierbar: Artikel, Anzahl, Kommentar; Position hinzufügen, Liste importieren/löschen) · Störungen · Fotos (Filter nach Auftrag/Komponente/Störung, hinzufügen) · Notizen | fehlen (Bausteine 4/5) | K |

## 7 Neue Erkenntnisse, die das Datenmodell betreffen

1. **Stammtechniker je Anlage** (Feld an der Anlage) wird in Foxtag für Filter und Austauschlisten benutzt → bei uns nachziehen (W).
2. **Auftrag hat Prüfumfang** (Teilmenge der Komponenten) → Auftrag–Komponente statt nur Auftrag–Wohnung (W, vor Baustein 4, weil die App danach arbeitet).
3. **Auftragsschritte schaltbar, Checklisten mehrfach und typgebunden, Intervalle je Typ** → Konfigurationsmodell der Anlagenart muss für Türen erweitert werden (K Türen).
4. **Kategorie Sub-Komponente/Zentrale** und Zusatzfelder → Türen (K Türen).
5. Berichtsempfänger an der Anlage, **Veröffentlichen** am Auftrag, **Gemeldet von** an der Störung → Baustein 5.
6. Wohnungs-**Link**, Komponenten-**Zulassungsnummer**, Typen **zusammenführen**, Anlage **verschieben**, **extern beenden** → kleine Erweiterungen (W).
7. Korrektur: Rolle „Planen und Daten pflegen“ darf **keine Nutzer verwalten** (`docs/06` berichtigt).

## 8 Lückenliste in empfohlener Reihenfolge

1. **K, ohne Foxtag-Bezug:** HTTPS, NAS-Sicherung (unverändert aus `docs/10`).
2. **W, kleine Stammdaten-Erweiterungen (jetzt):** Stammtechniker, Zulassungsnummer, Wohnung-Link, Label, Anlage verschieben, Typen zusammenführen, Prüfumfang je Melder, „extern beenden“.
3. **K, Baustein 4 (App):** Geräte (max. 2 je Nutzer), Fotos/Dateien, Prüfung, Mängel („Gemeldet von“), Unterschrift.
4. **K, Baustein 5:** Artikel/Material mit Vorauswahl je Auftragsart, Berichte (Titel/Untertitel), Berichtsempfänger, Veröffentlichen, Auswertungen (Material, Austauschliste, Jahresübersicht), Terminankündigung.
5. **K vor Türen:** Konfigurationsmodell erweitern (Kategorien, Intervall je Typ, mehrere Checklisten mit Zuordnung, Zusatzfelder).
6. **S:** 2FA (vor Zugang von außen eher W), iCal, Karte, Integrationen/API-Keys, Mehrfirma, Vorlagenverzeichnis, Startseite anpassen.

## 9 Offene Nachprüfung

- Auftragsreiter mit Inhalt, Rollenbearbeitung: nur über App-Bedienung bzw. Pro-Konto prüfbar (Testkonto läuft ca. 08.11.2026 aus).
- Ob Foxtag beim Löschen eines Kunden mit Objekten sperrt, nicht geprüft (nur lesend).
