"""Globale Suche: Treffer je Gruppe, Mindestlänge, LIKE-Sonderzeichen, Sicht je Rolle."""
from datetime import date

import pytest

from wartung import anlagen, anlagenart, auftraege, gruppen, komponenten, kunden, objekte, suche, typen

from hilfen import anmelden, nutzer_mit_passwort, rolle_id

ALLE = {"stammdaten.lesen", "auftraege.planen"}


@pytest.fixture
def lage(umgebung):
    c, con = umgebung
    rwm = anlagenart.holen("rauchwarnmelder")
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Zebra Verwaltung", "ort": "Zwickau"}, None)
    kunden.kontakt_anlegen(con, k, {"name": "Hanna Hausmeister", "telefon": "0123 4567"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Wohnpark Quelle", "strasse": "Lindenweg 3", "plz": "90402",
                                 "ort": "Nürnberg"}, None)
    a = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A", "bezeichnung": "Haus Nord"}, None)
    t = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "kategorie": "komponente",
                            "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)
    g = gruppen.anlegen(con, rwm, a, {"nummer": "7", "bezeichnung": "EG links", "bewohner": "Familie Quirin",
                                      "zugang": "frei"}, None)
    komponenten.anlegen(con, rwm, gruppen.holen(con, g),
                        {"nummer": "1", "komponententyp_id": t, "raum": "Flur", "seriennummer": "SN-4711-X",
                         "baujahr": "2021", "barcode": "BC-0815"}, None)
    tom = nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    eigener = auftraege.anlegen(con, anlagen.holen(con, a), {"auftragsart": "wartung", "nummer": "AUF-MEINS",
                                                              "datum": date.today().isoformat(), "techniker": [tom]},
                                None)
    fremder = auftraege.anlegen(con, anlagen.holen(con, a), {"auftragsart": "wartung", "nummer": "AUF-ZWEI",
                                                              "datum": date.today().isoformat(), "techniker": []},
                                None)
    return {"c": c, "con": con, "tom": tom, "a": a, "eigener": eigener, "fremder": fremder}


def test_treffer_je_gruppe(lage):
    con = lage["con"]
    s = lambda b: suche.suchen(con, b, ALLE, 1)  # noqa: E731
    assert "kunden" in s("Zebra") and "kontakte" in s("Hanna")
    assert "objekte" in s("Wohnpark")
    assert "anlagen" in s("Haus Nord")
    assert "wohnungen" in s("Quirin")
    assert "melder" in s("4711") and "melder" in s("BC-0815")
    assert "auftraege" in s("AUF-MEINS")


def test_zu_kurz_und_nichts(lage):
    con = lage["con"]
    assert suche.suchen(con, "Z", ALLE, 1) == {}
    assert suche.suchen(con, "   ", ALLE, 1) == {}
    assert suche.suchen(con, "gibtesnicht", ALLE, 1) == {}


def test_like_sonderzeichen_sind_woertlich(lage):
    con = lage["con"]
    assert suche.suchen(con, "%%", ALLE, 1) == {}
    assert suche.suchen(con, "__", ALLE, 1) == {}


def test_mehr_als_zehn(umgebung):
    c, con = umgebung
    for i in range(12):
        kunden.anlegen(con, {"art": "privat", "name": f"Serie {i:02d}"}, None)
    kunden_treffer, mehr = suche.suchen(con, "Serie", ALLE, 1)["kunden"]
    assert len(kunden_treffer) == suche.PRO_GRUPPE and mehr


def test_techniker_sieht_eigene_und_pool_auftraege_keine_stammdaten(lage):
    con = lage["con"]
    ute = nutzer_mit_passwort(con, "Ute", "ute@example.org", [rolle_id(con, "techniker")])
    auftraege.anlegen(con, anlagen.holen(con, lage["a"]), {"auftragsart": "wartung", "nummer": "AUF-UTE",
                                                            "datum": date.today().isoformat(), "techniker": [ute]}, None)
    r = suche.suchen(con, "AUF-", {auftraege.TECHNIKER_RECHT}, lage["tom"])
    assert set(r) == {"auftraege"}
    assert {z["nummer"] for z in r["auftraege"][0]} == {"AUF-MEINS", "AUF-ZWEI"}  # eigener + Pool, nicht Ute
    assert set(suche.suchen(con, "Zebra", {auftraege.TECHNIKER_RECHT}, lage["tom"])) <= {"auftraege"}
    assert suche.suchen(con, "4711", {auftraege.TECHNIKER_RECHT}, lage["tom"]) == {}


def test_seite(lage):
    c = lage["c"]
    anmelden(c)
    r = c.get("/suche", params={"q": "Zebra"})
    assert r.status_code == 200 and "Zebra Verwaltung" in r.text
    assert "mindestens 2" in c.get("/suche", params={"q": "Z"}).text
    assert "Nichts gefunden" in c.get("/suche", params={"q": "gibtesnicht"}).text
    assert c.get("/suche").status_code == 200


def test_seite_verlangt_anmeldung(lage):
    r = lage["c"].get("/suche", follow_redirects=False)
    assert r.status_code in (302, 303, 401)
