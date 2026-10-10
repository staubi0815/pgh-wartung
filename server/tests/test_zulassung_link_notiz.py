"""Schritt 7: Zulassungsnummer je Komponente, Link an der Wohnung, Zeilenumbrüche in importierten Notizen."""
import pytest

from wartung import anlagen, anlagenart, excel_import as imp, gruppen, komponenten, kunden, objekte, typen
from wartung.felder import Ungueltig

from hilfen import anmelden
from test_import import KUNDEN_KOPF, RWM_KOPF, xlsx

RWM = anlagenart.holen("rauchwarnmelder")


@pytest.fixture
def lage(umgebung):
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "adresse_wie_kunde": "1"}, None)
    a = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    t = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "kategorie": "komponente",
                            "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)
    return c, con, a, t


def test_link_an_wohnung(lage):
    c, con, a, _ = lage
    g = gruppen.anlegen(con, RWM, a, {"nummer": "1", "zugang": "frei", "link": "https://example.org/plan?x=1"}, None)
    assert gruppen.holen(con, g)["link"] == "https://example.org/plan?x=1"
    for schlecht in ("javascript:alert(1)", "ftp://x.de", "example.org", "https://a b"):
        with pytest.raises(Ungueltig):
            gruppen.anlegen(con, RWM, a, {"nummer": "2", "zugang": "frei", "link": schlecht}, None)
    anmelden(c)
    seite = c.get(f"/anlagen/{a}").text
    assert 'href="https://example.org/plan?x=1"' in seite and 'rel="noopener noreferrer"' in seite


def test_zulassungsnummer_komponente(lage):
    c, con, a, t = lage
    g = gruppen.holen(con, gruppen.anlegen(con, RWM, a, {"nummer": "1", "zugang": "frei"}, None))
    k = komponenten.anlegen(con, RWM, g, {"nummer": "1", "komponententyp_id": t, "zulassungsnummer": "Z-19.1-123"}, None)
    assert con.execute("SELECT zulassungsnummer FROM komponente WHERE id = ?", (k,)).fetchone()[0] == "Z-19.1-123"
    anmelden(c)
    assert "Z-19.1-123" in c.get(f"/komponenten/{k}").text


def test_import_liest_zulassungsnummer_wenn_vorhanden(lage):
    _, con, a, _ = lage
    kopf = RWM_KOPF[:9] + ["ZULASSUNGSNUMMER"] + RWM_KOPF[9:]
    inhalt = xlsx(kopf, [1, "Muster, EG", 1, 0, "Ei650", "Ei", "Ei650", "Flur", "SN1", "Z-1", None, 2020, None, None,
                         None, None])
    e = imp.uebernehmen(con, "komponenten", inhalt, None, {"anlage": anlagen.holen(con, a)})
    assert e.gespeichert and not [h for h in e.hinweise if "Nicht verwendete" in h]
    assert con.execute("SELECT zulassungsnummer FROM komponente").fetchone()[0] == "Z-1"


def test_notizen_behalten_zeilenumbrueche():
    assert imp.text_mehrzeilig("a  b\r\nc\n\n d ") == "a b\nc\n\nd"
    assert imp.text_mehrzeilig(None) == "" and imp.text_mehrzeilig(5.0) == "5"
    assert imp.text("a\nb") == "a b"


def test_import_kunde_notiz_mehrzeilig(umgebung):
    _, con = umgebung
    inhalt = xlsx(KUNDEN_KOPF, ["K1", "Kunde", "Str 1", None, "01067", "Dresden", "DE", "Zeile 1\nZeile 2"])
    assert imp.uebernehmen(con, "kunden", inhalt, None).gespeichert
    assert con.execute("SELECT notiz_intern FROM kunde").fetchone()[0] == "Zeile 1\nZeile 2"
