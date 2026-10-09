"""Mehrere Anlagen auf einmal planen; nächster Auftrag und Filter „ohne offenen Auftrag“ in der Anlagenliste."""
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, auftraege, kunden, objekte, rechte
from wartung.felder import Ungueltig, datum_de

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id


def tag(n):
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture
def drei(umgebung):
    """Drei Anlagen (eine passiv) und ein Techniker."""
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    ids = []
    for i, passiv in ((1, ""), (2, ""), (3, "1")):
        o = objekte.anlegen(con, k, {"bezeichnung": f"Haus {i}", "strasse": f"Weg {i}", "plz": "90402",
                                     "ort": "Nürnberg"}, None)
        ids.append(anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A", "passiv": passiv},
                                   None))
    tom = nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    return {"c": c, "con": con, "ids": ids, "tom": tom}


def zeilen(con, ids):
    return [anlagen.holen(con, i) for i in ids]


def test_mehrere_anlegen(drei):
    con, (a1, a2, _) = drei["con"], drei["ids"]
    neu = auftraege.mehrere_anlegen(con, zeilen(con, [a1, a2]),
                                    {"auftragsart": "wartung", "techniker": [drei["tom"]], "hinweise": "Sammeltermin"},
                                    {a1: (tag(3), "08:00"), a2: (tag(4), "")}, None)
    u1, u2 = (auftraege.holen(con, x) for x in neu)
    assert (u1["nummer"], u1["datum"], u1["uhrzeit"], u1["umfang"], u1["hinweise"]) == \
        ("A-1001", tag(3), "08:00", "ganze_anlage", "Sammeltermin")
    assert (u2["nummer"], u2["datum"], u2["uhrzeit"]) == ("A-1002", tag(4), None)
    assert [t["name"] for t in auftraege.techniker(con, u2["id"])] == ["Tom"]


def test_mehrere_alles_oder_nichts(drei):
    con, (a1, a2, a3) = drei["con"], drei["ids"]
    with pytest.raises(Ungueltig) as e:
        auftraege.mehrere_anlegen(con, zeilen(con, [a1, a2, a3]), {"auftragsart": "wartung"},
                                  {a1: (tag(3), ""), a2: ("", ""), a3: (tag(3), "")}, None)
    assert set(e.value.fehler) == {a2, a3}
    assert "Pflicht" in e.value.fehler[a2] and "passiv" in e.value.fehler[a3]
    assert con.execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM auftrag_verlauf").fetchone()[0] == 0
    # keine Nummer verbraucht: der nächste Auftrag bekommt A-1001
    aid = auftraege.anlegen(con, anlagen.holen(con, a1), {"auftragsart": "wartung", "datum": tag(3)}, None)
    assert auftraege.holen(con, aid)["nummer"] == "A-1001"
    with pytest.raises(Ungueltig, match="mindestens eine Anlage"):
        auftraege.mehrere_anlegen(con, [], {}, {}, None)
    with pytest.raises(Ungueltig, match="Höchstens"):
        auftraege.mehrere_anlegen(con, zeilen(con, [a1]) * (auftraege.MAX_MEHRERE + 1), {}, {}, None)


def test_naechster_auftrag_und_filter(drei):
    con, (a1, a2, _) = drei["con"], drei["ids"]
    spaet = auftraege.anlegen(con, anlagen.holen(con, a1), {"auftragsart": "wartung", "datum": tag(10)}, None)
    frueh = auftraege.anlegen(con, anlagen.holen(con, a1), {"auftragsart": "wartung", "datum": tag(5)}, None)
    a = anlagen.holen(con, a1)
    assert (a["naechster_auftrag_id"], a["naechster_auftrag_datum"]) == (frueh, tag(5))
    auftraege.status_setzen(con, frueh, "storniert", None, grund="x")
    assert anlagen.holen(con, a1)["naechster_auftrag_id"] == spaet  # stornierte zählen nicht
    assert anlagen.holen(con, a2)["naechster_auftrag_id"] is None
    ohne = [x["id"] for x in anlagen.liste(con, ohne_auftrag=True)]
    assert a1 not in ohne and a2 in ohne


def test_seiten(drei):
    c, con, (a1, a2, a3) = drei["c"], drei["con"], drei["ids"]
    anmelden(c)
    liste = c.get("/anlagen").text
    assert f'name="anlage" value="{a1}"' in liste and f'name="anlage" value="{a3}"' not in liste  # passiv: kein Haken
    assert "Aufträge für ausgewählte Anlagen planen" in liste
    assert c.get("/auftraege/mehrere", follow_redirects=False).headers["location"].endswith("hinweis=keine_auswahl")
    form = c.get("/auftraege/mehrere", params=[("anlage", a1), ("anlage", a2)])
    assert form.status_code == 200 and "2 Aufträge planen" in form.text
    t = csrf_aus(form.text)
    # Fehler: kein Datum für a2 -> nichts gespeichert, Eingaben bleiben
    r = c.post("/auftraege/mehrere", data={"csrf_token": t, "anlage": [a1, a2], "auftragsart": "wartung",
                                          f"datum_{a1}": tag(2), "hinweise": "bleibt"})
    assert r.status_code == 400 and "Nichts gespeichert" in r.text and "bleibt" in r.text
    assert con.execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 0
    # gemeinsames Datum, eine Zeile mit eigenem Datum
    r = c.post("/auftraege/mehrere", data={"csrf_token": t, "anlage": [a1, a2], "auftragsart": "wartung",
                                          "datum_alle": tag(6), "uhrzeit_alle": "09:00", f"datum_{a2}": tag(7),
                                          "techniker": [drei["tom"]]}, follow_redirects=False)
    assert r.headers["location"].endswith("hinweis=mehrere_angelegt&anzahl=2")
    assert "2 Aufträge geplant." in c.get(r.headers["location"]).text
    termine = {x["anlage_id"]: (x["datum"], x["uhrzeit"]) for x in con.execute("SELECT * FROM auftrag")}
    assert termine == {a1: (tag(6), "09:00"), a2: (tag(7), "09:00")}
    liste = c.get("/anlagen").text
    assert datum_de(tag(6)) in liste
    assert "keiner geplant" not in c.get(f"/anlagen/{a1}").text and "keiner geplant" in c.get(f"/anlagen/{a3}").text
    assert re.search(r"A-100[12]</a> am ", c.get(f"/anlagen/{a1}").text)


def test_rechte(drei):
    c, con, (a1, _, _) = drei["c"], drei["con"], drei["ids"]
    buero_ohne_planen = TestClient(c.app)
    rid = rechte.rolle_anlegen(con, "Lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea", "lea@example.org", [rid])
    anmelden(buero_ohne_planen, "lea@example.org")
    liste = buero_ohne_planen.get("/anlagen").text
    assert 'name="anlage"' not in liste and "Aufträge für ausgewählte" not in liste
    r = buero_ohne_planen.get("/auftraege/mehrere", params={"anlage": a1}, follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]
    r = buero_ohne_planen.post("/auftraege/mehrere", data={"csrf_token": csrf_aus(liste), "anlage": a1,
                                                           "datum_alle": tag(3)}, follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]
    assert con.execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 0
