"""Export: Foxtag-Format (Inhalt, Formate, Rundweg Export -> Import) und Vollexport (vollständig, ohne Geheimnisse)."""
import csv
import io
import json
import re
import zipfile
from datetime import datetime

import openpyxl
import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, export, gruppen, komponenten, kunden, lebenslauf, objekte, rechte, typen
from wartung import excel_import as imp
from wartung.app import erzeuge_app

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

RWM = anlagenart.holen("rauchwarnmelder")


def entpacken(inhalt):
    with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
        return {n: z.read(n) for n in z.namelist()}


def blatt(inhalt):
    """Erstes Blatt einer Excel-Datei als (Kopf, [Zeilen]) mit den rohen Zellwerten."""
    zeilen = list(openpyxl.load_workbook(io.BytesIO(inhalt)).active.iter_rows(values_only=True))
    return list(zeilen[0]), [list(z) for z in zeilen[1:]]


@pytest.fixture
def bestand(umgebung):
    """Erfundener Bestand: zwei Kunden (einer gelöscht), Kontakte, zwei Objekte, eine Anlage mit zwei Wohnungen."""
    _, con = umgebung
    k1 = kunden.anlegen(con, {"nummer": "K-7", "art": "hausverwaltung", "name": "Muster Hausverwaltung GmbH",
                              "zusatz": "z. Hd. Technik", "strasse": "Hauptstr. 5", "plz": "01067", "ort": "Dresden",
                              "land": "DE", "telefon": "+49 351 1234", "notiz_intern": "=SUMME(1;2)"}, None)
    weg = kunden.anlegen(con, {"nummer": "K-8", "art": "privat", "name": "Gelöscht"}, None)
    kunden.loeschen(con, weg, None)
    kunden.kontakt_anlegen(con, k1, {"name": "Herr Beispiel", "funktion": "Hausmeister", "telefon": "0351 99",
                                     "notiz": "Schlüssel im Büro"}, None)
    o1 = objekte.anlegen(con, k1, {"nummer": "O-1", "bezeichnung": "Wohnanlage Süd", "adresse_wie_kunde": "1"}, None)
    objekte.anlegen(con, k1, {"nummer": "O-2", "bezeichnung": "Haus Nord", "strasse": "Nordweg 1", "plz": "90402",
                              "ort": "Nürnberg", "land": "DE"}, None)
    a = anlagen.anlegen(con, o1, {"nummer": "ANL/1", "anlagenart": "rauchwarnmelder", "verfahren": "A",
                                  "bezeichnung": "Haus A"}, None)
    typ = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "hersteller": "Ei Electronics",
                              "modell": "Ei650", "kategorie": "komponente", "funk": "keine", "batterie": "fest_10j",
                              "datenblatt_link": "https://example.org/ei650", "aktiv": "1"}, None)
    g1 = gruppen.holen(con, gruppen.anlegen(con, RWM, a, {"nummer": "36", "bezeichnung": "1.OG Mitte",
                                                           "bewohner": "Friedrich", "zugang": "frei"}, None))
    g2 = gruppen.holen(con, gruppen.anlegen(con, RWM, a, {"nummer": "43", "bezeichnung": "2.OG links",
                                                           "zugang": "frei"}, None))
    komponenten.anlegen(con, RWM, g1, {"nummer": "1", "komponententyp_id": typ, "raum": "Flur",
                                       "seriennummer": "90024-1", "barcode": "QR-36-1", "baujahr": "2020",
                                       "inbetriebnahme_am": "2020-03-01", "letzte_pruefung_am": "2025-11-17"}, None)
    komponenten.anlegen(con, RWM, g1, {"nummer": "2", "komponententyp_id": typ, "raum": "Kinderzimmer",
                                       "baujahr": "2020"}, None)
    alt = komponenten.holen(con, komponenten.anlegen(con, RWM, g2, {"nummer": "1", "komponententyp_id": typ,
                                                                    "raum": "Flur", "baujahr": "2019"}, None))
    lebenslauf.ausbauen(con, alt, {"grund": lebenslauf.AUSBAU_GRUENDE[0][0], "zeitpunkt": "2025-01-10"}, None)
    return con


# ---------- Foxtag-Format ----------

def test_foxtag_dateien_und_kopf(bestand):
    inhalt, anzahl = export.foxtag(bestand)
    dateien = entpacken(inhalt)
    assert list(dateien) == ["LIESMICH.txt", "01_Kunden.xlsx", "02_Kontakte.xlsx", "03_Objekte.xlsx",
                             "04_Anlagen.xlsx", "05_Komponenten-Typen_Rauchwarnmelder.xlsx",
                             "06_Komponenten_ANL_1.xlsx", "07_Auftraege.xlsx"]
    assert anzahl == {"01_Kunden.xlsx": 1, "02_Kontakte.xlsx": 1, "03_Objekte.xlsx": 2, "04_Anlagen.xlsx": 1,
                      "05_Komponenten-Typen_Rauchwarnmelder.xlsx": 1, "06_Komponenten_ANL_1.xlsx": 2,
                      "07_Auftraege.xlsx": 0}
    # Kopfzeilen genau wie die Foxtag-Vorlagen (Pflichtspalten mit *)
    assert blatt(dateien["01_Kunden.xlsx"])[0] == ["KUNDEN.NUMMER*", "KUNDE.NAME*", "ADRESSZEILE 1", "ADRESSZEILE 2",
                                                   "PLZ", "ORT", "LAND", "NOTIZ"]
    assert blatt(dateien["04_Anlagen.xlsx"])[0] == ["OBJEKT.NUMMER*", "WARTUNGSANWENDUNG.NUMMER*", "ANLAGE.NUMMER*",
                                                    "ANLAGE.NAME", "TECHNIKER.NUMMER"]
    assert blatt(dateien["06_Komponenten_ANL_1.xlsx"])[0] == [
        "GRUPPE.NUMMER", "GRUPPE.NAME", "NUMMER*", "SUB-NUMMER", "TYP.NAME*", "TYP.HERSTELLER", "TYP.MODELL",
        "STANDORT", "SERIENNUMMER", "QR-CODE", "BAUJAHR", "LABEL", "LABEL2", "LETZTE PRÜFUNG", "INBETRIEBNAHME AM"]
    liesmich = dateien["LIESMICH.txt"].decode("utf-8")
    assert "„RWM“" in liesmich and "06_Komponenten_ANL_1.xlsx  (2 Zeilen)" in liesmich and "Mieterdaten" in liesmich
    assert "01_Kunden.xlsx  (1 Zeile)" in liesmich
    # je Datei der passende Punkt im Foxtag-Menü „Datenimport“
    assert "05_Komponenten-Typen_Rauchwarnmelder.xlsx  (1 Zeile)\n      -> Datenimport -> Komponenten-Typen, dort " \
           "Wartungsanwendung „Rauchwarnmelder“ auswählen" in liesmich
    assert "06_Komponenten_ANL_1.xlsx  (2 Zeilen)\n      -> Datenimport -> Komponenten, dort Anlage „ANL/1“ " \
           "auswählen" in liesmich


# Kopfzeilen der Foxtag-Importvorlagen (Stand Testkonto 10/2026, ohne Hinweis-/Hilfespalten)
FOXTAG_KOEPFE = {
    "01_Kunden.xlsx": ["KUNDEN.NUMMER*", "KUNDE.NAME*", "ADRESSZEILE 1", "ADRESSZEILE 2", "PLZ", "ORT", "LAND",
                       "NOTIZ"],
    "02_Kontakte.xlsx": ["NAME*", "FIRMA", "EMAIL", "TELEFON", "MOBIL", "FAX", "NOTIZ", "KUNDE"],
    "03_Objekte.xlsx": ["KUNDE.NUMMER", "OBJEKT.NAME", "OBJEKT.NUMMER", "ADRESSZEILE 1", "ADRESSZEILE 2", "PLZ", "ORT",
                        "LAND"],
    "04_Anlagen.xlsx": ["OBJEKT.NUMMER*", "WARTUNGSANWENDUNG.NUMMER*", "ANLAGE.NUMMER*", "ANLAGE.NAME",
                        "TECHNIKER.NUMMER"],
    "05_Komponenten-Typen_Rauchwarnmelder.xlsx": ["TYP.NAME*", "TYP.HERSTELLER", "TYP.MODELL", "TYP.KATEGORIE*",
                                                  "TYP.LINK"],
    "06_Komponenten_ANL_1.xlsx": ["GRUPPE.NUMMER", "GRUPPE.NAME", "NUMMER*", "SUB-NUMMER", "TYP.NAME*",
                                  "TYP.HERSTELLER", "TYP.MODELL", "STANDORT", "SERIENNUMMER", "QR-CODE", "BAUJAHR",
                                  "LABEL", "LABEL2", "LETZTE PRÜFUNG", "INBETRIEBNAHME AM"],
    "07_Auftraege.xlsx": ["AUFTRAG.NUMMER", "ANLAGE.NUMMER*", "DATUM*", "AUFTRAGSTYP.NUMMER*", "TECHNIKER.NUMMER*",
                          "TECHNIKER.NUMMER2", "TECHNIKER.NUMMER3", "AUFTRAG.HINWEISE"],
}


def test_alle_koepfe_wie_foxtag_vorlagen(bestand):
    """Jede Datei hat genau die Kopfzeile der Foxtag-Vorlage – auch die Sternchen (Foxtag liest die Namen wörtlich)."""
    dateien = entpacken(export.foxtag(bestand)[0])
    assert {n for n in dateien if n.endswith(".xlsx")} == set(FOXTAG_KOEPFE)
    for name, kopf in FOXTAG_KOEPFE.items():
        assert blatt(dateien[name])[0] == kopf, name


def test_foxtag_werte(bestand):
    dateien = entpacken(export.foxtag(bestand)[0])
    _, kunden_zeilen = blatt(dateien["01_Kunden.xlsx"])
    # gelöschter Kunde fehlt; PLZ bleibt Text mit führender Null; „=…“ bleibt Text, keine Formel
    assert kunden_zeilen == [["K-7", "Muster Hausverwaltung GmbH", "Hauptstr. 5", "z. Hd. Technik", "01067", "Dresden",
                              "DE", "=SUMME(1;2)"]]
    zelle = openpyxl.load_workbook(io.BytesIO(dateien["01_Kunden.xlsx"])).active["H2"]
    assert zelle.data_type == "s"
    assert blatt(dateien["02_Kontakte.xlsx"])[1] == [["Herr Beispiel", None, None, "0351 99", None, None,
                                                      "Funktion: Hausmeister\nSchlüssel im Büro", "K-7"]]
    # „wie Kunde“: wirksame Anschrift des Kunden
    assert blatt(dateien["03_Objekte.xlsx"])[1] == [
        ["K-7", "Wohnanlage Süd", "O-1", "Hauptstr. 5", None, "01067", "Dresden", "DE"],
        ["K-7", "Haus Nord", "O-2", "Nordweg 1", None, "90402", "Nürnberg", "DE"]]
    assert blatt(dateien["04_Anlagen.xlsx"])[1] == [["O-1", "RWM", "ANL/1", "Haus A", None]]
    assert blatt(dateien["05_Komponenten-Typen_Rauchwarnmelder.xlsx"])[1] == [
        ["Ei650", "Ei Electronics", "Ei650", "Komponente", "https://example.org/ei650"]]
    _, melder = blatt(dateien["06_Komponenten_ANL_1.xlsx"])
    # ausgebauter Melder (Wohnung 43) fehlt; Zahlen als Zahl, Datum als Excel-Datum
    assert melder == [
        [36, "Friedrich, 1.OG Mitte", 1, 0, "Ei650", "Ei Electronics", "Ei650", "Flur", "90024-1", "QR-36-1", 2020,
         None, None, datetime(2025, 11, 17), datetime(2020, 3, 1)],
        [36, "Friedrich, 1.OG Mitte", 2, 0, "Ei650", "Ei Electronics", "Ei650", "Kinderzimmer", None, None, 2020,
         None, None, None, None]]
    datumszelle = openpyxl.load_workbook(io.BytesIO(dateien["06_Komponenten_ANL_1.xlsx"])).active["N2"]
    assert datumszelle.number_format == export.DATUMSFORMAT


def test_foxtag_leerer_bestand(umgebung):
    dateien = entpacken(export.foxtag(umgebung[1])[0])
    assert list(dateien) == ["LIESMICH.txt", "01_Kunden.xlsx", "02_Kontakte.xlsx", "03_Objekte.xlsx",
                             "04_Anlagen.xlsx", "07_Auftraege.xlsx"]
    assert blatt(dateien["01_Kunden.xlsx"])[1] == []


def test_gleiche_dateinamen_und_steuerzeichen(bestand):
    """„ANL/1“ und „ANL_1“ ergeben denselben Dateinamen – keiner darf den anderen im ZIP überdecken.
    Steuerzeichen sind in Excel nicht erlaubt und werden weggelassen, statt den Export abbrechen zu lassen."""
    con = bestand
    o = con.execute("SELECT id FROM objekt WHERE nummer = 'O-2'").fetchone()["id"]
    a2 = anlagen.anlegen(con, o, {"nummer": "ANL_1", "anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    typ = con.execute("SELECT id FROM komponententyp").fetchone()["id"]
    g = gruppen.holen(con, gruppen.anlegen(con, RWM, a2, {"nummer": "1", "zugang": "frei"}, None))
    komponenten.anlegen(con, RWM, g, {"nummer": "1", "komponententyp_id": typ, "raum": "Flur"}, None)
    con.execute("UPDATE kunde SET name = 'Muster\x07 GmbH' WHERE nummer = 'K-7'")
    inhalt, anzahl = export.foxtag(con)
    dateien = entpacken(inhalt)
    assert "06_Komponenten_ANL_1.xlsx" in dateien and "06_Komponenten_ANL_1_2.xlsx" in dateien
    # nach Anlagennummer sortiert: „ANL/1“ (2 Melder) vor „ANL_1“ (1 Melder)
    assert anzahl["06_Komponenten_ANL_1.xlsx"] == 2 and anzahl["06_Komponenten_ANL_1_2.xlsx"] == 1
    assert blatt(dateien["01_Kunden.xlsx"])[1][0][1] == "Muster GmbH"
    with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
        assert len(z.namelist()) == len(set(z.namelist()))


def test_gruppenname_und_dateiname():
    assert export.gruppenname("Friedrich", "1.OG Mitte") == "Friedrich, 1.OG Mitte"
    assert export.gruppenname("", "EG links") == "EG links"
    assert imp.wohnungsname(export.gruppenname("Friedrich", "1.OG Mitte")) == ("Friedrich", "1.OG Mitte")
    assert export.dateiname_sicher("ANL/1 Süd") == "ANL_1_S_d" and export.dateiname_sicher("../") == "ohne_nummer"


def test_rundweg_export_dann_import(bestand, tmp_path):
    """Der Foxtag-Export lässt sich mit dem eigenen Import vollständig wieder einlesen (gleiche Stammdaten)."""
    dateien = entpacken(export.foxtag(bestand)[0])
    ziel = erzeuge_app(tmp_path / "ziel").state.con
    for name, art in (("01_Kunden.xlsx", "kunden"), ("02_Kontakte.xlsx", "kontakte"), ("03_Objekte.xlsx", "objekte"),
                      ("04_Anlagen.xlsx", "anlagen")):
        e = imp.uebernehmen(ziel, art, dateien[name], None)
        assert e.gespeichert and e.anzahl("neu") == len(e.zeilen), (name, [z.meldungen for z in e.zeilen])
    assert imp.uebernehmen(ziel, "typen", dateien["05_Komponenten-Typen_Rauchwarnmelder.xlsx"], None,
                           {"anlagenart": "rauchwarnmelder"}).gespeichert
    anlage = anlagen.holen(ziel, ziel.execute("SELECT id FROM anlage WHERE nummer = 'ANL/1'").fetchone()["id"])
    e = imp.uebernehmen(ziel, "komponenten", dateien["06_Komponenten_ANL_1.xlsx"], None, {"anlage": anlage})
    assert e.gespeichert and e.anzahl("neu") == 2

    def stand(con):
        return {
            "kunden": con.execute("SELECT nummer, name, zusatz, strasse, plz, ort, land, notiz_intern FROM kunde "
                                  "WHERE geloescht = 0").fetchall(),
            "objekte": con.execute(f"SELECT o.nummer, o.bezeichnung, {objekte.ADRESSE_SQL} FROM objekt o "
                                   "JOIN kunde k ON k.id = o.kunde_id ORDER BY o.nummer").fetchall(),
            "anlagen": con.execute("SELECT nummer, anlagenart, bezeichnung FROM anlage").fetchall(),
            "wohnungen": con.execute("SELECT nummer, bezeichnung, bewohner FROM gruppe g WHERE EXISTS (SELECT 1 FROM "
                                     "komponente k WHERE k.gruppe_id = g.id AND k.status = 'verbaut') "
                                     "ORDER BY nummer").fetchall(),
            "melder": con.execute("SELECT g.nummer, k.nummer, k.raum, k.seriennummer, k.barcode, k.baujahr, "
                                  "k.inbetriebnahme_am, k.letzte_pruefung_am, k.naechste_pruefung_am, "
                                  "k.austausch_faellig_am, t.hersteller, t.modell FROM komponente k "
                                  "JOIN gruppe g ON g.id = k.gruppe_id JOIN komponententyp t ON t.id = "
                                  "k.komponententyp_id WHERE k.status = 'verbaut' ORDER BY 1, 2").fetchall(),
        }
    vorher, nachher = stand(bestand), stand(ziel)
    for teil in vorher:
        assert [tuple(z) for z in vorher[teil]] == [tuple(z) for z in nachher[teil]], teil
    # bekannte Abweichungen: die Funktion des Kontakts steht in Foxtag in der Notiz, und der Import fasst
    # Zeilenumbrüche zu Leerzeichen zusammen
    assert ziel.execute("SELECT notiz FROM kontakt").fetchone()[0] == "Funktion: Hausmeister\nSchlüssel im Büro"


# ---------- Vollexport ----------

ERWARTETE_TABELLEN = {"abgleich_zaehler", "aenderungsprotokoll", "anlage", "anlage_kontakt", "auftrag",
                      "auftrag_gruppe", "auftrag_techniker", "auftrag_verlauf", "firma", "gruppe",
                      "komponente", "komponententyp", "kontakt", "kunde", "kunde_kontakt", "label", "label_zuordnung", "massnahme", "nummernkreis", "nutzer",
                      "nutzer_rolle", "objekt", "rolle", "rolle_recht", "schema_version"}


def test_vollexport_tabellen_bewusst_eingeordnet(umgebung):
    """Kommt eine neue Tabelle dazu, muss sie hier bewusst als exportiert oder ausgenommen eingetragen werden."""
    con = umgebung[1]
    alle = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                           "AND name NOT LIKE 'sqlite_%'")}
    assert alle == ERWARTETE_TABELLEN | set(export.AUSGENOMMEN_TABELLEN)
    assert {t for t, _, _ in export.tabellen(con)} == ERWARTETE_TABELLEN


def test_vollexport_inhalt(bestand):
    inhalt, anzahl = export.voll(bestand)
    dateien = entpacken(inhalt)
    assert {"LIESMICH.txt", "daten.json", "schema.sql"} <= set(dateien)
    assert {n for n in dateien if n.startswith("tabellen/")} == {f"tabellen/{t}.csv" for t in ERWARTETE_TABELLEN}
    daten = json.loads(dateien["daten.json"])["tabellen"]
    assert set(daten) == ERWARTETE_TABELLEN and {t: len(z) for t, z in daten.items()} == anzahl
    # vollständig: auch gelöschte Kunden, ausgebaute Melder und Maßnahmen
    assert {(k["nummer"], k["geloescht"]) for k in daten["kunde"]} == {("K-7", 0), ("K-8", 1)}
    assert sorted(k["status"] for k in daten["komponente"]) == ["ausgebaut", "verbaut", "verbaut"]
    assert [m["art"] for m in daten["massnahme"]] == ["ausbau"] and daten["aenderungsprotokoll"]
    # keine Anmeldegeheimnisse, kein Anmeldeprotokoll
    assert "anmeldeversuch" not in daten
    nutzer = daten["nutzer"][0]
    assert nutzer["email"] == "admin@example.org"
    assert not {"passwort_hash", "einladung_hash", "einladung_bis", "sitzung_zaehler"} & set(nutzer)
    assert not re.search(r"argon2|\$argon", dateien["daten.json"].decode("utf-8"))
    liesmich = dateien["LIESMICH.txt"].decode("utf-8")
    assert "kunde: 2" in liesmich and "anmeldeversuch" in liesmich


def test_vollexport_csv(bestand):
    dateien = entpacken(export.voll(bestand)[0])
    roh = dateien["tabellen/kunde.csv"]
    assert roh.startswith("﻿".encode("utf-8"))  # BOM: Excel erkennt UTF-8 (Umlaute)
    zeilen = list(csv.DictReader(io.StringIO(roh.decode("utf-8-sig")), delimiter=";"))
    k7 = next(z for z in zeilen if z["nummer"] == "K-7")
    daten = {k["nummer"]: k for k in json.loads(dateien["daten.json"])["tabellen"]["kunde"]}
    assert k7["notiz_intern"] == "'=SUMME(1;2)" and daten["K-7"]["notiz_intern"] == "=SUMME(1;2)"
    assert k7["telefon"] == "+49 351 1234" and k7["plz"] == "01067"
    assert len(zeilen) == 2


def test_csv_zelle():
    assert export._csv_zelle(None) == "" and export._csv_zelle(5) == 5
    assert export._csv_zelle("=1+1") == "'=1+1" and export._csv_zelle("@x") == "'@x"
    assert export._csv_zelle("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert export._csv_zelle("-2+3") == "'-2+3"
    assert export._csv_zelle("+49 (0)911 / 123-4") == "+49 (0)911 / 123-4" and export._csv_zelle("-5") == "-5"


# ---------- Webseite ----------

def test_export_seite_und_download(umgebung, bestand):
    c, con = umgebung
    anmelden(c)
    seite = c.get("/verwaltung/export")
    assert seite.status_code == 200 and "Vollexport herunterladen" in seite.text
    assert 'href="/verwaltung/export"' in seite.text  # im Verwaltungsmenü
    t = csrf_aus(seite.text)
    r = c.post("/verwaltung/export/voll", data={"csrf_token": t})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert re.fullmatch(r'attachment; filename="pgh-wartung-vollexport-\d{4}-\d{2}-\d{2}\.zip"',
                        r.headers["content-disposition"])
    assert r.headers["cache-control"] == "no-store" and "daten.json" in entpacken(r.content)
    r = c.post("/verwaltung/export/foxtag", data={"csrf_token": t})
    assert "01_Kunden.xlsx" in entpacken(r.content)
    eintraege = con.execute("SELECT feld, neu FROM aenderungsprotokoll WHERE aktion = 'export' ORDER BY id").fetchall()
    assert [e["feld"] for e in eintraege] == ["vollexport", "foxtag"] and "Datensätze" in eintraege[0]["neu"]
    seite = c.get("/verwaltung/export").text
    assert "Letzte Exporte" in seite and "Foxtag-Format" in seite and "Test Admin" in seite


def test_export_ohne_csrf(umgebung):
    c, con = umgebung
    anmelden(c)
    r = c.post("/verwaltung/export/voll", data={"csrf_token": "falsch"}, follow_redirects=False)
    assert r.status_code == 303 and "sitzung_abgelaufen" in r.headers["location"]
    assert not con.execute("SELECT 1 FROM aenderungsprotokoll WHERE aktion = 'export'").fetchone()


def test_export_rechte(umgebung):
    c, con = umgebung
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    nutzer_mit_passwort(con, "Bea", "bea@example.org", [rolle_id(con, "buero")])
    techniker, buero = TestClient(c.app), TestClient(c.app)
    anmelden(techniker, "tom@example.org")
    anmelden(buero, "bea@example.org")
    assert "keine_berechtigung" in techniker.get("/verwaltung/export", follow_redirects=False).headers["location"]
    t = csrf_aus(techniker.get("/").text)
    r = techniker.post("/verwaltung/export/voll", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and "keine_berechtigung" in r.headers["location"]
    # Büro: Foxtag-Export ja, Vollexport nein (enthält Nutzer und Änderungsprotokoll, die das Büro nicht sehen darf)
    seite = buero.get("/verwaltung/export")
    assert seite.status_code == 200 and "Foxtag-Export herunterladen" in seite.text
    assert "Vollexport herunterladen" not in seite.text and "in der Regel die Administration" in seite.text
    t = csrf_aus(seite.text)
    r = buero.post("/verwaltung/export/voll", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and "keine_berechtigung" in r.headers["location"]
    assert buero.post("/verwaltung/export/foxtag", data={"csrf_token": t}).headers["content-type"] == "application/zip"
    # nur „export“ ohne Stammdaten-Leserecht: keiner der beiden Exporte
    rid = rechte.rolle_anlegen(con, "Nur Export", "", ["web.zugang", "export"], None)
    nutzer_mit_passwort(con, "Eva", "eva@example.org", [rid])
    nur_export = TestClient(c.app)
    anmelden(nur_export, "eva@example.org")
    seite = nur_export.get("/verwaltung/export").text
    assert "herunterladen" not in seite and "Recht zum Ansehen der Stammdaten" in seite
    r = nur_export.post("/verwaltung/export/foxtag", data={"csrf_token": csrf_aus(seite)}, follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]
    assert [e["feld"] for e in con.execute("SELECT feld FROM aenderungsprotokoll WHERE aktion = 'export'")] == \
        ["foxtag"]
