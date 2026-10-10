"""Stammtechniker je Anlage: speichern, prüfen, filtern, beim Planen vorschlagen."""
import pytest

from wartung import anlagen, kunden, objekte
from wartung.felder import Ungueltig

from hilfen import anmelden, nutzer_mit_passwort, rolle_id


@pytest.fixture
def lage(umgebung):
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "strasse": "Lindenweg 3", "plz": "90402", "ort": "Nürnberg"},
                        None)
    tom = nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    ute = nutzer_mit_passwort(con, "Ute", "ute@example.org", [rolle_id(con, "techniker")])
    buero = nutzer_mit_passwort(con, "Bea", "bea@example.org", [rolle_id(con, "buero")])

    def neu(**f):
        return anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A", **f}, None)
    return {"c": c, "con": con, "tom": tom, "ute": ute, "buero": buero, "neu": neu}


def test_speichern_und_anzeigen(lage):
    con = lage["con"]
    a = lage["neu"](stammtechniker_id=lage["tom"])
    assert anlagen.holen(con, a)["stammtechniker_name"] == "Tom"
    anlagen.aendern(con, a, {"nummer": anlagen.holen(con, a)["nummer"], "verfahren": "A", "stammtechniker_id": ""}, None)
    assert anlagen.holen(con, a)["stammtechniker_id"] is None


def test_nur_techniker_waehlbar(lage):
    with pytest.raises(Ungueltig):
        lage["neu"](stammtechniker_id=lage["buero"])
    with pytest.raises(Ungueltig):
        lage["neu"](stammtechniker_id="gibt-es-nicht")


def test_filter(lage):
    con = lage["con"]
    a1, a2 = lage["neu"](stammtechniker_id=lage["tom"]), lage["neu"]()
    ids = lambda **f: {x["id"] for x in anlagen.liste(con, **f)}  # noqa: E731
    assert ids(techniker=lage["tom"]) == {a1}
    assert ids(techniker=lage["ute"]) == set()
    assert ids(techniker="keiner") == {a2}
    assert ids() == {a1, a2}


def test_vorbelegung_beim_planen(lage):
    c = lage["c"]
    a = lage["neu"](stammtechniker_id=lage["tom"])
    b = lage["neu"](stammtechniker_id=lage["ute"])
    anmelden(c)
    seite = c.get(f"/anlagen/{a}/auftraege/neu").text
    assert f'value="{lage["tom"]}" checked' in seite and f'value="{lage["ute"]}" checked' not in seite
    gleich = c.get("/auftraege/mehrere", params=[("anlage", a), ("anlage", b)]).text
    assert "checked" not in gleich.split('name="techniker"', 1)[1].split("</label>", 1)[0]
    einzeln = c.get("/auftraege/mehrere", params=[("anlage", a)]).text
    assert f'value="{lage["tom"]}" checked' in einzeln


def test_seiten(lage):
    c = lage["c"]
    a = lage["neu"](stammtechniker_id=lage["tom"])
    anmelden(c)
    assert "Stammtechniker" in c.get(f"/anlagen/{a}").text
    assert "selected" in c.get(f"/anlagen/{a}/bearbeiten").text
    liste = c.get("/anlagen", params={"techniker": lage["ute"]}).text
    assert "ANL-" not in liste.split("<tbody", 1)[-1]
