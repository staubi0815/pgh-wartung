"""Fälligkeitsregeln (Prüfung, Austausch, Ampel) und Katalog der Komponententypen."""
from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient

from wartung import __main__ as befehle
from wartung import anlagen, anlagenart, db, faelligkeit, kunden, objekte, typen

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

RWM = anlagenart.holen("rauchwarnmelder")
TYP = {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "hersteller": "Ei Electronics",
       "kategorie": "komponente", "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}


# ---------- Regeln ----------

@pytest.mark.parametrize("tag, monate, ergebnis", [
    (date(2026, 1, 31), 1, date(2026, 2, 28)),
    (date(2028, 1, 31), 1, date(2028, 2, 29)),     # Schaltjahr
    (date(2026, 10, 8), 12, date(2027, 10, 8)),
    (date(2026, 11, 30), 3, date(2027, 2, 28)),
    (date(2016, 6, 15), 120, date(2026, 6, 15)),
])
def test_monate_addieren(tag, monate, ergebnis):
    assert faelligkeit.monate_addieren(tag, monate) == ergebnis


def test_naechste_pruefung_gleitend_sonst_ab_inbetriebnahme():
    assert faelligkeit.naechste_pruefung(RWM, "2026-03-10", "2020-01-01") == date(2027, 3, 10)
    assert faelligkeit.naechste_pruefung(RWM, None, "2026-05-02") == date(2027, 5, 2)
    assert faelligkeit.naechste_pruefung(RWM, None, None) is None


def test_austausch_ab_baujahr_vorsichtig_ab_1_januar():
    assert faelligkeit.austausch_faellig(RWM, 2016, "2017-08-01") == date(2026, 1, 1)
    assert faelligkeit.austausch_faellig(RWM, None, "2017-08-01") == date(2027, 8, 1)  # ohne Baujahr
    assert faelligkeit.austausch_faellig(RWM, None, None) is None
    assert faelligkeit.austausch_faellig(RWM, 2016, None, typ_jahre=8) == date(2024, 1, 1)  # Typ hat Vorrang
    mit_zugabe = replace(RWM, austausch_zugabe_monate=6)
    assert faelligkeit.austausch_faellig(mit_zugabe, 2016) == date(2026, 7, 1)
    ab_inbetriebnahme = replace(RWM, austausch_ab="inbetriebnahme")
    assert faelligkeit.austausch_faellig(ab_inbetriebnahme, 2016, "2017-08-01") == date(2027, 8, 1)


def test_ampel():
    heute = date(2026, 10, 8)
    assert faelligkeit.ampel("2026-10-07", heute, 30) == "rot"
    assert faelligkeit.ampel("2026-10-08", heute, 30) == "gelb"
    assert faelligkeit.ampel("2026-11-07", heute, 30) == "gelb"
    assert faelligkeit.ampel("2026-11-08", heute, 30) == "gruen"
    assert faelligkeit.ampel(None, heute, 30) == "grau"


# ---------- in der Datenbank ----------

@pytest.fixture
def anlage_mit_wohnung(umgebung):
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "privat", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "adresse_wie_kunde": "1"}, None)
    a = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    g = db.anlegen(con, "gruppe", {"anlage_id": a, "nummer": 1}, None)
    return c, con, a, g


def test_komponente_berechnen_und_typ_aenderung(anlage_mit_wohnung):
    c, con, a, g = anlage_mit_wohnung
    t = typen.anlegen(con, TYP, None)
    m = db.anlegen(con, "komponente", {"anlage_id": a, "gruppe_id": g, "nummer": 1, "komponententyp_id": t,
                                       "baujahr": 2020, "inbetriebnahme_am": "2020-06-01"}, None)
    assert faelligkeit.komponente_berechnen(con, m) == 1
    zeile = con.execute("SELECT naechste_pruefung_am, austausch_faellig_am FROM komponente WHERE id = ?", (m,)).fetchone()
    assert tuple(zeile) == ("2021-06-01", "2030-01-01")
    assert faelligkeit.komponente_berechnen(con, m) == 0  # nichts zu tun
    typen.aendern(con, t, {**TYP, "austausch_jahre": "8"}, None)
    assert con.execute("SELECT austausch_faellig_am FROM komponente WHERE id = ?", (m,)).fetchone()[0] == "2028-01-01"


def test_migrieren_rechnet_alle_neu(anlage_mit_wohnung, monkeypatch, tmp_path, capsys):
    _, con, a, g = anlage_mit_wohnung
    t = typen.anlegen(con, TYP, None)
    m = db.anlegen(con, "komponente", {"anlage_id": a, "gruppe_id": g, "nummer": 1, "komponententyp_id": t,
                                       "baujahr": 2019}, None)
    monkeypatch.setenv("WARTUNG_DATEN", str(tmp_path))
    assert befehle.main(["migrieren"]) == 0
    assert "Fälligkeiten neu berechnet: 1" in capsys.readouterr().out
    assert con.execute("SELECT austausch_faellig_am FROM komponente WHERE id = ?", (m,)).fetchone()[0] == "2029-01-01"


# ---------- Typenkatalog ----------

def test_typ_anlegen_pruefen_deaktivieren(umgebung):
    c, con = umgebung
    anmelden(c)
    seite = c.get("/verwaltung/typen/neu").text
    t = csrf_aus(seite)
    assert c.post("/verwaltung/typen/neu", data={**TYP, "csrf_token": t}, follow_redirects=False).status_code == 303
    r = c.post("/verwaltung/typen/neu", data={**TYP, "bezeichnung": "ei650", "csrf_token": t})
    assert r.status_code == 400 and "gibt es schon" in r.text
    r = c.post("/verwaltung/typen/neu", data={**TYP, "bezeichnung": "X", "datenblatt_link": "javascript:alert(1)",
                                              "austausch_jahre": "50", "csrf_token": t})
    assert r.status_code == 400 and "https://" in r.text and "1 bis 30" in r.text
    tid = con.execute("SELECT id FROM komponententyp").fetchone()[0]
    assert typen.auswahl(con, "rauchwarnmelder") == ((tid, "Ei650 (Ei Electronics)"),)
    c.post(f"/verwaltung/typen/{tid}", data={**TYP, "aktiv": "", "csrf_token": t})
    assert typen.auswahl(con, "rauchwarnmelder") == ()                         # inaktiv: nicht mehr wählbar …
    assert typen.auswahl(con, "rauchwarnmelder", auch_id=tid)[0][0] == tid     # … außer für Melder, die ihn haben
    assert "inaktiv" in c.get("/verwaltung/typen").text


def test_typen_recht_katalog(umgebung):
    c, con = umgebung
    nutzer_mit_passwort(con, "Bea", "bea@example.org", [rolle_id(con, "buero")])
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    buero, techniker = TestClient(c.app), TestClient(c.app)
    anmelden(buero, "bea@example.org")
    anmelden(techniker, "tom@example.org")
    start = buero.get("/").text
    assert 'href="/verwaltung"' in start  # Büro hat nur den Katalog in der Verwaltung …
    assert buero.get("/verwaltung", follow_redirects=False).headers["location"] == "/verwaltung/typen"
    assert "keine_berechtigung" in buero.get("/verwaltung/nutzer", follow_redirects=False).headers["location"]
    assert "keine_berechtigung" in techniker.get("/verwaltung/typen", follow_redirects=False).headers["location"]
