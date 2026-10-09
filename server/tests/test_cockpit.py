"""Start-Cockpit: heutige Termine, Rest der Woche, überfällige und abzurechnende Aufträge; Sicht je Rolle."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, auftraege, kunden, objekte

from hilfen import anmelden, nutzer_mit_passwort, rolle_id

HEUTE = date.today()


@pytest.fixture
def lage(umgebung):
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "strasse": "Lindenweg 3", "plz": "90402",
                                 "ort": "Nürnberg"}, None)
    a = anlagen.holen(con, anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None))
    tom = nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    ute = nutzer_mit_passwort(con, "Ute", "ute@example.org", [rolle_id(con, "techniker")])

    def plan(tage, **f):
        return auftraege.anlegen(con, a, {"auftragsart": "wartung", "datum": (HEUTE + timedelta(days=tage)).isoformat(),
                                          **f}, None)
    ids = {"heute_tom": plan(0, uhrzeit="09:00", techniker=[tom]), "heute_ute": plan(0, techniker=[ute]),
           "vergessen": plan(1, techniker=[tom]), "fertig": plan(2)}
    gestern = (HEUTE - timedelta(days=1)).isoformat()
    auftraege.aendern(con, ids["vergessen"], {"auftragsart": "wartung", "datum": gestern, "techniker": [tom],
                                              "grund": "nachgetragen"}, None)
    auftraege.status_setzen(con, ids["fertig"], "abgeschlossen", None)
    return {"c": c, "con": con, "tom": tom, "ids": ids}


def test_cockpit_zahlen(lage):
    con, ids = lage["con"], lage["ids"]
    k = auftraege.cockpit(con)
    assert [x["id"] for x in k["heute"]] == [ids["heute_ute"], ids["heute_tom"]]  # ganztägig zuerst
    assert (k["ueberfaellig"], k["abzurechnen"]) == (1, 1)
    sonntag = auftraege.montag(HEUTE) + timedelta(days=6)
    if HEUTE < sonntag:
        auftraege.anlegen(con, anlagen.holen(con, con.execute("SELECT id FROM anlage").fetchone()[0]),
                          {"auftragsart": "wartung", "datum": sonntag.isoformat()}, None)
        assert auftraege.cockpit(con)["rest_woche"] == 1
    # Techniker: eigene + Pool
    k = auftraege.cockpit(con, (lage["tom"], True))
    assert [x["id"] for x in k["heute"]] == [ids["heute_tom"]] and k["ueberfaellig"] == 1


def test_startseite_buero(lage):
    c, ids = lage["c"], lage["ids"]
    anmelden(c)
    s = c.get("/").text
    assert "Heute" in s and f'href="/auftraege/{ids["heute_tom"]}"' in s and "Lindenweg 3" in s
    assert "Überfällige Aufträge" in s and "Termin vorbei, aber nicht abgeschlossen" in s
    assert 'href="/auftraege?status=abzurechnen"' in s and "1</strong> abgeschlossene Auftrag" in s
    assert "davon noch ohne Auftrag" in s
    gestern = (HEUTE - timedelta(days=1)).isoformat()
    ueberfaellig = c.get(f"/auftraege?status=offen&bis={gestern}").text
    assert f'href="/auftraege/{ids["vergessen"]}"' in ueberfaellig and ueberfaellig.count('href="/auftraege/') == 1


def test_startseite_techniker(lage):
    c, ids = lage["c"], lage["ids"]
    tom = TestClient(c.app)
    anmelden(tom, "tom@example.org")
    s = tom.get("/").text
    assert "(meine und Pool)" in s and f'href="/auftraege/{ids["heute_tom"]}"' in s
    assert f'href="/auftraege/{ids["heute_ute"]}"' not in s
    assert "Abzurechnen" not in s and "Fällig" not in s and "Überfällige Aufträge" in s


def test_cockpit_zaehlt_ohne_listengrenze(lage, monkeypatch):
    """Die Liste ist für die Anzeige begrenzt, die Zahlen im Cockpit dürfen es nicht sein."""
    con = lage["con"]
    a = anlagen.holen(con, con.execute("SELECT id FROM anlage").fetchone()[0])
    for _ in range(3):
        aid = auftraege.anlegen(con, a, {"auftragsart": "wartung", "datum": HEUTE.isoformat()}, None)
        auftraege.status_setzen(con, aid, "abgeschlossen", None)
    monkeypatch.setattr(auftraege, "MAX_LISTE", 1)
    assert len(auftraege.liste(con, "abzurechnen")) == 2  # Anzeige: 1 + 1 („es gibt mehr“)
    assert auftraege.cockpit(con)["abzurechnen"] == 4
