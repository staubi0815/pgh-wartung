"""Fälligkeiten in Anlagenliste, Anlagenseite und Startseite (Ampel, Filter, passive Anlagen)."""
from datetime import date, timedelta

import pytest

from wartung import anlagen, anlagenart, auftraege, db, gruppen, komponenten, kunden, objekte, typen

from hilfen import anmelden

RWM = anlagenart.holen("rauchwarnmelder")
HEUTE = date.today()
TYP = {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "kategorie": "komponente", "funk": "keine",
       "batterie": "fest_10j", "aktiv": "1"}


def tage(n):
    return date.fromordinal(HEUTE.toordinal() + n).isoformat()


@pytest.fixture
def drei_anlagen(umgebung):
    """ANL-0001: Prüfung überfällig; ANL-0002: Prüfung in 10 Tagen; ANL-0003: alles in Ordnung, Austausch überfällig."""
    c, con = umgebung
    anmelden(c)
    typ = typen.anlegen(con, TYP, None)
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    ids = []
    for nr, letzte, baujahr in ((1, tage(-400), None), (2, tage(-355), None), (3, tage(-30), 2010)):
        o = objekte.anlegen(con, k, {"bezeichnung": f"Haus {nr}", "adresse_wie_kunde": "1"}, None)
        a = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
        g = gruppen.holen(con, gruppen.anlegen(con, RWM, a, {"zugang": "frei"}, None))
        komponenten.anlegen(con, RWM, g, {"komponententyp_id": typ, "letzte_pruefung_am": letzte,
                                          "baujahr": str(baujahr) if baujahr else ""}, None)
        # zweiter Melder mit späterer Fälligkeit: die Anlage zeigt die früheste
        komponenten.anlegen(con, RWM, g, {"komponententyp_id": typ, "letzte_pruefung_am": tage(-1)}, None)
        ids.append(a)
    return c, con, ids


def test_anlage_zeigt_frueheste_faelligkeit(drei_anlagen):
    _, con, (a1, a2, a3) = drei_anlagen
    d1, d2, d3 = (anlagen.bewerten(anlagen.holen(con, a)) for a in (a1, a2, a3))
    assert (d1["pruefung_ampel"], d2["pruefung_ampel"], d3["pruefung_ampel"]) == ("rot", "gelb", "gruen")
    assert d3["austausch_ampel"] == "rot" and d3["naechster_austausch_am"] == "2020-01-01"


def test_filter_und_startseite(drei_anlagen):
    c, con, (a1, a2, a3) = drei_anlagen
    nummern = lambda f: [a["nummer"] for a in anlagen.liste(con, faellig=f)]  # noqa: E731
    assert nummern("pruefung_ueberfaellig") == ["ANL-0001"]
    assert nummern("pruefung_bald") == ["ANL-0001", "ANL-0002"]
    assert nummern("austausch_bald") == ["ANL-0003"]
    assert len(anlagen.liste(con, faellig="unsinn")) == 3  # unbekannter Filter = alle
    assert anlagen.faellig_zaehlen(con) == {"pruefung_ueberfaellig": 1, "pruefung_bald": 2, "austausch_bald": 1,
                                            "pruefung_bald_ohne_auftrag": 2}
    # sobald eine fällige Anlage einen offenen Auftrag hat, zählt sie nicht mehr als „ohne Auftrag“
    auftraege.anlegen(con, anlagen.holen(con, a1), {"auftragsart": "wartung",
                                                    "datum": (date.today() + timedelta(days=3)).isoformat()}, None)
    assert anlagen.faellig_zaehlen(con)["pruefung_bald_ohne_auftrag"] == 1
    seite = c.get("/anlagen?faellig=pruefung_ueberfaellig").text
    assert "ANL-0001" in seite and "ANL-0002" not in seite and "ampel-rot" in seite
    start = c.get("/").text
    assert 'href="/anlagen?faellig=pruefung_ueberfaellig"' in start and "Prüfung überfällig" in start


def test_passive_anlage_ruht(drei_anlagen):
    c, con, (a1, a2, a3) = drei_anlagen
    db.aendern(con, "anlage", a1, {"passiv": 1}, None)
    assert [a["nummer"] for a in anlagen.liste(con, faellig="pruefung_bald")] == ["ANL-0002"]
    assert anlagen.faellig_zaehlen(con)["pruefung_ueberfaellig"] == 0
    assert "ruht (passiv)" in c.get(f"/anlagen/{a1}").text
