"""Auftragsliste und Wochenansicht: Filter, Sortierung, Sichtbarkeit (Büro / Techniker / nur eigene), Seiten."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, auftraege, kunden, objekte, rechte
from wartung.felder import datum_de

from hilfen import anmelden, nutzer_mit_passwort, rolle_id

RWM = anlagenart.holen("rauchwarnmelder")
HEUTE = date.today()


def tag(n):
    return (HEUTE + timedelta(days=n)).isoformat()


@pytest.fixture
def bestand(umgebung):
    """Zwei Anlagen (Nürnberg, Fürth); Aufträge für Tom, für Ute, im Pool, abgeschlossen und storniert."""
    c, con = umgebung
    k1 = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Alpha Verwaltung"}, None)
    k2 = kunden.anlegen(con, {"art": "privat", "name": "Beta Privat"}, None)
    o1 = objekte.anlegen(con, k1, {"bezeichnung": "Haus 1", "strasse": "Ahornweg 1", "plz": "90402",
                                   "ort": "Nürnberg"}, None)
    o2 = objekte.anlegen(con, k2, {"bezeichnung": "Haus 2", "strasse": "Birkenweg 2", "plz": "90762",
                                   "ort": "Fürth"}, None)
    a1 = anlagen.holen(con, anlagen.anlegen(con, o1, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None))
    a2 = anlagen.holen(con, anlagen.anlegen(con, o2, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None))
    tom = nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    ute = nutzer_mit_passwort(con, "Ute", "ute@example.org", [rolle_id(con, "techniker")])

    def plan(anlage, datum, **f):
        return auftraege.anlegen(con, anlage, {"auftragsart": "wartung", "datum": datum, **f}, None)
    ids = {
        "tom_morgen": plan(a1, tag(1), uhrzeit="10:00", techniker=[tom], notiz_intern="nur fürs Büro"),
        "pool_morgen": plan(a2, tag(1)),
        "ute_spaeter": plan(a2, tag(20), techniker=[ute], auftragsart="installation"),
        "tom_fertig": plan(a1, tag(2), techniker=[tom]),
        "storno": plan(a1, tag(3), techniker=[tom]),
    }
    auftraege.status_setzen(con, ids["tom_fertig"], "abgeschlossen", None)
    auftraege.status_setzen(con, ids["storno"], "storniert", None, grund="Test")
    return {"c": c, "con": con, "tom": tom, "ute": ute, "ids": ids}


def nummern(zeilen):
    return [z["id"] for z in zeilen]


def test_filter(bestand):
    con, ids = bestand["con"], bestand["ids"]
    # Standard „offen“: geplant + aktiv; ganztägige vor solchen mit Uhrzeit am selben Tag
    assert nummern(auftraege.liste(con)) == [ids["pool_morgen"], ids["tom_morgen"], ids["ute_spaeter"]]
    assert nummern(auftraege.liste(con, "abzurechnen")) == [ids["tom_fertig"]]
    assert ids["storno"] not in nummern(auftraege.liste(con, "alle"))
    assert len(auftraege.liste(con, "alle")) == 4
    assert nummern(auftraege.liste(con, "storniert")) == [ids["storno"]]
    assert len(auftraege.liste(con, "quatsch")) == 3  # unbekannt = offen
    assert nummern(auftraege.liste(con, "offen", von=tag(5))) == [ids["ute_spaeter"]]
    assert nummern(auftraege.liste(con, "offen", bis=tag(1))) == [ids["pool_morgen"], ids["tom_morgen"]]
    assert len(auftraege.liste(con, "offen", von="31.12.2026", bis="kaputt")) == 3  # ungültig = ignoriert
    assert nummern(auftraege.liste(con, techniker_id=bestand["tom"])) == [ids["tom_morgen"]]
    assert nummern(auftraege.liste(con, techniker_id="pool")) == [ids["pool_morgen"]]
    assert nummern(auftraege.liste(con, auftragsart="installation")) == [ids["ute_spaeter"]]
    assert nummern(auftraege.liste(con, suche="fürth")) == [ids["pool_morgen"], ids["ute_spaeter"]]
    assert nummern(auftraege.liste(con, suche="Alpha")) == [ids["tom_morgen"]]
    assert auftraege.liste(con, suche="%") == []  # Platzhalter zählen als normales Zeichen
    assert auftraege.liste(con)[1]["techniker_namen"] == "Tom" and auftraege.liste(con)[0]["techniker_namen"] is None


def test_sichtbarkeit(bestand):
    con, ids = bestand["con"], bestand["ids"]
    tom = bestand["tom"]
    techniker_rechte = rechte.rechte_von_rolle(con, rolle_id(con, "techniker"))
    sicht = auftraege.sicht(techniker_rechte, tom)
    assert sicht == (tom, True)
    assert nummern(auftraege.liste(con, "alle", eingeschraenkt=sicht)) == \
        [ids["pool_morgen"], ids["tom_morgen"], ids["tom_fertig"]]  # eigene + Pool, nicht Utes
    assert auftraege.darf_sehen(con, ids["tom_morgen"], techniker_rechte, tom)
    assert auftraege.darf_sehen(con, ids["pool_morgen"], techniker_rechte, tom)
    assert not auftraege.darf_sehen(con, ids["ute_spaeter"], techniker_rechte, tom)
    # nur Webzugang (kein Techniker): nur eigene, kein Pool
    assert auftraege.sicht({"web.zugang"}, tom) == (tom, False)
    assert nummern(auftraege.liste(con, "alle", eingeschraenkt=(tom, False))) == [ids["tom_morgen"],
                                                                                 ids["tom_fertig"]]
    # Büro und Planende sehen alles
    assert auftraege.sicht({"web.zugang", "stammdaten.lesen"}, tom) is None
    assert auftraege.sicht({"web.zugang", "auftraege.planen"}, tom) is None


def test_woche_und_montag():
    assert auftraege.montag("2026-10-18") == date(2026, 10, 12)   # Sonntag -> Montag davor
    assert auftraege.montag("2026-10-12") == date(2026, 10, 12)
    assert auftraege.montag("kaputt") == HEUTE - timedelta(days=HEUTE.weekday())


def test_woche_inhalt(bestand):
    con, ids = bestand["con"], bestand["ids"]
    mo, tage = auftraege.woche(con, tag(1))
    assert len(tage) == 7 and tage[0][0] == mo and mo.weekday() == 0
    alle = {x["id"]: t for t, eintraege in tage for x in eintraege}
    assert alle[ids["tom_morgen"]] == HEUTE + timedelta(days=1)
    assert ids["storno"] not in alle and ids["ute_spaeter"] not in alle


def test_seiten_buero(bestand):
    c, ids = bestand["c"], bestand["ids"]
    anmelden(c)
    seite = c.get("/auftraege").text
    assert 'href="/auftraege">Aufträge</a>' in seite and "alle Techniker" in seite
    assert seite.count('href="/auftraege/') == 3 and "Pool" in seite and "Fürth" in seite
    assert "3 Aufträge" in seite
    seite = c.get("/auftraege", params={"status": "abzurechnen"}).text
    assert f'href="/auftraege/{ids["tom_fertig"]}"' in seite and "1 Auftrag<" in seite
    woche = c.get("/auftraege", params={"ansicht": "woche", "woche": tag(1)}).text
    assert datum_de(tag(1), True) in woche and f'href="/auftraege/{ids["tom_morgen"]}"' in woche
    assert "Vorwoche" in woche and "Nächste Woche" in woche
    assert c.get("/auftraege", params={"ansicht": "woche", "woche": "kaputt"}).status_code == 200


def test_seiten_techniker(bestand):
    c, ids = bestand["c"], bestand["ids"]
    tom = TestClient(c.app)
    anmelden(tom, "tom@example.org")
    seite = tom.get("/auftraege", params={"status": "alle"}).text
    assert "meine und Pool" in seite and "alle Techniker" not in seite
    assert f'href="/auftraege/{ids["ute_spaeter"]}"' not in seite and f'href="/auftraege/{ids["pool_morgen"]}"' in seite
    # Filter nach fremdem Techniker wird für Techniker ignoriert (kein Umgehen der Sicht)
    seite = tom.get("/auftraege", params={"status": "alle", "techniker": bestand["ute"]}).text
    assert f'href="/auftraege/{ids["ute_spaeter"]}"' not in seite
    detail = tom.get(f"/auftraege/{ids['tom_morgen']}")
    assert detail.status_code == 200 and "nur fürs Büro" not in detail.text
    assert 'href="/anlagen/' not in detail.text and "Status ändern" not in detail.text
    r = tom.get(f"/auftraege/{ids['ute_spaeter']}", follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]
    assert "nicht_gefunden" in tom.get("/auftraege/gibt-es-nicht", follow_redirects=False).headers["location"]


def test_liste_gekappt(bestand, monkeypatch):
    c = bestand["c"]
    anmelden(c)
    monkeypatch.setattr(auftraege, "MAX_LISTE", 2)
    seite = c.get("/auftraege").text
    assert seite.count('href="/auftraege/') == 2 and "es gibt mehr als 2" in seite
