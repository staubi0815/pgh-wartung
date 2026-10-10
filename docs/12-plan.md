# 12 – Arbeitsplan (Stand 10.10.2026)

Grundlage: Lückenliste `docs/11` Abschnitt 8, offene Punkte aus STATUS, Wünsche Patrick 10.10.2026 (Suche, Karte mit
Routen). Arbeitsweise: je Schritt ein eigener Zweig und Pull Request, Tests grün, Doku im selben PR, Patrick mergt,
danach DB sichern und `./deploy.sh`. Reihenfolge ist ein Vorschlag, Patrick kann umsortieren.

## Stufe 0 – Aufräumen (sofort)
1. PR #4 (Rollen wie Foxtag) und PR #5 (docs/11) mergen; DB sichern; Deploy (Migration 007).

## Stufe 1 – Betrieb absichern (K, ohne Foxtag-Bezug)
2. HTTPS (Zertifikat intern, Zugang weiter nur über WireGuard).
3. Sicherung der Anwendungsdaten aufs NAS (vorher mit Patrick abstimmen, NAS-Schreibzugriff).
4. Linter (ruff) in Test-Venv und CI.

## Stufe 2 – Bedienbarkeit und kleine Stammdaten-Lücken (Version 0.4)
5. **Globale Suche** (Feld in der Kopfzeile, wie Foxtag): findet Kunden, Objekte, Anlagen, Aufträge, Wohnungen und Melder
   (Nummer, Name, Ort, Seriennummer, Barcode); Ergebnisse nach Rechten des Nutzers gefiltert (Techniker sehen nur eigene
   Aufträge); Tastenkürzel, Treffer gruppiert. Foxtag-Verhalten der Trefferliste ist nicht erfasst (Suchfeld liefert
   per Skript keine sichtbare Liste) – wir bauen es nach eigenem Entwurf.
6. Stammtechniker je Anlage (Auswahl, Filter, Vorbelegung beim Planen).
7. Zulassungsnummer je Komponente; Link an der Wohnung (klärt Befund docs/03); Notizen mit Zeilenumbrüchen.
8. Anlage zu anderem Objekt verschieben; Typen zusammenführen; Kontakt an mehreren Kunden.
9. Labels (Name, Farbe) an Kunde, Objekt, Anlage, Auftrag, mit Filter.
10. Auftrag: Prüfumfang je Melder, Status „in Planung“ und „abgerechnet“, „extern beenden“ (Altprüfungen nachtragen).
11. Foxtag-Export um die neuen Felder erweitern (Zulassungsnummer, Standard-Techniker); Import entsprechend.

## Stufe 3 – Baustein 4: App (PWA)
12. Geräteverwaltung (höchstens 2 je Nutzer, koppeln/sperren), Offline-Speicher, Abgleich (docs/02).
13. Auftrag durchführen: Prüfliste, Ergebnis OK/Mangel, Tauschen, Nacharbeiten (docs/08).
14. Fotos und Dateien an Anlage/Auftrag/Mangel; Störung erfassen mit „Gemeldet von“.
15. Unterschriften, Auftrag beenden; Offline-Test mit Patrick; WireGuard je Tablet.

## Stufe 4 – Baustein 5: Material, Berichte, Versand
16. Artikelstamm und Artikelpositionen am Auftrag (Vorauswahl je Auftragsart), Import.
17. Berichte als PDF (Titel/Untertitel je Auftragsart, Logo), Berichtsempfänger an der Anlage, „Veröffentlicht“,
    Versandhistorie, Terminankündigung per E-Mail (Absender/Vorlagen unter Verwaltung).
18. Auswertungen: Material und Leistungen, Austauschliste (Excel), Jahresübersicht, Störungsliste je Anlage/global.

## Stufe 5 – Karte mit Routen (Wunsch Patrick; Foxtag hat nur Karte ohne Routen)
Foxtag zeigt Anlagen als Markierungen mit Filtern (Anwendung, Kunde, Prüf-/Austauschfälligkeit, Techniker); Routen
habe ich dort nicht gefunden. Wir können mehr: **Tagesroute je Techniker** aus den Terminen des Tages, Reihenfolge nach
Uhrzeit, Fahrzeit/Strecke je Etappe, Knopf „Navigation starten“ (Link an die Karten-App des Tablets).
Datenschutz-Entscheidung nötig (Kundenadressen sind Kundendaten):
- **Variante A (empfohlen, nur eigene Daten nach außen):** Koordinaten einmal je Objekt ermitteln und speichern; Karte
  mit Kacheln eines Kartendienstes (der Browser verrät nur den Kartenausschnitt, keine Adressen); Route über einen
  selbst betriebenen Routenserver (OSRM/Valhalla mit Bayern-/Sachsen-Kartendaten) im Container 192 oder eigenem
  Container; Koordinaten ermitteln per Adressdienst – hier gehen Adressen nach außen, daher einmalig und nur
  Straße/PLZ/Ort, oder von Hand per Kartenklick.
- **Variante B (einfach):** nur Markierungen und je Termin ein Link „Route in Karten-App öffnen“; keine eigenen Routen.
Entscheidung Patrick; Foxtag-Mapbox übernehmen wir nicht (fremder Dienst, Lizenz).
Schritte: 19 Koordinaten je Objekt (auto/eigen), 20 Kartenseite mit Filtern, 21 Tagesroute je Techniker.

## Stufe 6 – Türen
22. Konfigurationsmodell erweitern: Typ-Kategorien (Komponente/Sub-Komponente/Zentrale), Intervall je Typ, mehrere
    Checklisten mit Typzuordnung, Zusatzfelder, schaltbare Auftragsschritte. Danach Anlagenart „Türen“ nach Lehrgang.

## Stufe 7 – Später/Optional (S)
2FA (vor Zugang von außen vorziehen), iCal-Kalender, Zeitzone, Integrationen/API-Keys, Mehrfirma, Startseite anpassen,
Status je Techniker, Auftraggeberportal, unabhängige Prüfung von außen **vor Echtbetrieb**.

## Terminpunkte
- Foxtag-Testkonto läuft ca. 08.11.2026 aus: offene Beobachtungen (Offline-Test, Auftragsreiter mit Inhalt) davor erledigen;
  danach Regel `node /tmp/foxtag/*.js` löschen.
- Rauchwarnmelder-Konfiguration nach Lehrgang (KW 42/2026) gegenlesen und freigeben.
- GitHub-Token läuft ca. 2027-01-08 ab (Erinnerung).
