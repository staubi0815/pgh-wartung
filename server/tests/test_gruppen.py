"""Wohnungen (Gruppen): Nummern, Anlegen in Serie, Ändern, Löschregel, Rechte."""
import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, db, gruppen, kunden, objekte, rechte, typen
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort

RWM = anlagenart.holen("rauchwarnmelder")


@pytest.fixture
def anlage(umgebung):
    c, con = umgebung
    anmelden(c)
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Musterstraße 12", "adresse_wie_kunde": "1"}, None)
    return c, con, anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)


def test_wohnungen_in_serie_anlegen(anlage):
    c, con, aid = anlage
    seite = c.get(f"/anlagen/{aid}/gruppen/neu").text
    assert "Wohnung anlegen" in seite and 'placeholder="1"' in seite
    t = csrf_aus(seite)
    r = c.post(f"/anlagen/{aid}/gruppen/neu", data={"bezeichnung": "EG links", "bewohner": "Müller", "zugang": "frei",
                                                     "weiter": "1", "csrf_token": t}, follow_redirects=False)
    assert r.headers["location"] == f"/anlagen/{aid}/gruppen/neu?hinweis=angelegt"  # gleich die nächste
    assert 'placeholder="2"' in c.get(r.headers["location"]).text
    c.post(f"/anlagen/{aid}/gruppen/neu", data={"nummer": "43", "zugang": "nur_termin", "csrf_token": t})
    c.post(f"/anlagen/{aid}/gruppen/neu", data={"zugang": "frei", "csrf_token": t})
    assert [(g["nummer"], g["zugang"]) for g in gruppen.liste(con, aid)] == [(1, "frei"), (43, "nur_termin"),
                                                                            (44, "frei")]
    seite = c.get(f"/anlagen/{aid}").text
    assert "Wohnung 43" in seite and "nur nach Termin" in seite and "Müller" in seite


def test_wohnungsnummer_eindeutig_und_beim_bearbeiten_pflicht(anlage):
    c, con, aid = anlage
    gid = gruppen.anlegen(con, RWM, aid, {"nummer": "5", "zugang": "frei"}, None)
    t = csrf_aus(c.get(f"/anlagen/{aid}/gruppen/neu").text)
    r = c.post(f"/anlagen/{aid}/gruppen/neu", data={"nummer": "5", "zugang": "frei", "csrf_token": t})
    assert r.status_code == 400 and "Wohnung 5 gibt es in dieser Anlage schon." in r.text
    r = c.post(f"/gruppen/{gid}", data={"nummer": "", "zugang": "frei", "csrf_token": t})
    assert r.status_code == 400 and "Wohnung-Nr. ist Pflicht." in r.text
    r = c.post(f"/gruppen/{gid}", data={"nummer": "6", "bezeichnung": "1. OG", "zugang": "schluessel",
                                        "csrf_token": t}, follow_redirects=False)
    assert r.headers["location"] == f"/anlagen/{aid}?hinweis=gruppe_gespeichert#g-{gid}"
    g = gruppen.holen(con, gid)
    assert (g["nummer"], g["bezeichnung"], g["zugang"]) == (6, "1. OG", "schluessel")
    # in einer anderen Anlage darf es dieselbe Nummer geben
    a2 = anlagen.anlegen(con, anlagen.holen(con, aid)["objekt_id"], {"anlagenart": "rauchwarnmelder", "verfahren": "A"},
                         None)
    gruppen.anlegen(con, RWM, a2, {"nummer": "6", "zugang": "frei"}, None)


def test_wohnung_mit_verbautem_melder_nicht_loeschbar(anlage):
    c, con, aid = anlage
    gid = gruppen.anlegen(con, RWM, aid, {"zugang": "frei"}, None)
    typ = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "kategorie": "komponente",
                              "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)
    mid = db.anlegen(con, "komponente", {"anlage_id": aid, "gruppe_id": gid, "nummer": 1, "komponententyp_id": typ},
                     None)
    t = csrf_aus(c.get(f"/gruppen/{gid}").text)
    r = c.post(f"/gruppen/{gid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert "gruppe_hat_komponenten" in r.headers["location"] and gruppen.holen(con, gid) is not None
    assert "kann nicht gelöscht werden" in c.get(r.headers["location"]).text
    db.aendern(con, "komponente", mid, {"status": "ausgebaut"}, None)
    r = c.post(f"/gruppen/{gid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert "gruppe_geloescht" in r.headers["location"] and gruppen.holen(con, gid) is None
    assert gruppen.naechste_nummer(con, aid) == 1  # gelöschte Nummern sind wieder frei
    # Anlage ist jetzt löschbar
    anlagen.loeschen(con, aid, None)


def test_ungueltige_eingaben(anlage):
    _, con, aid = anlage
    with pytest.raises(Ungueltig) as e:
        gruppen.anlegen(con, RWM, aid, {"nummer": "-1", "zugang": "irgendwie", "bewohner_telefon": "abc"}, None)
    assert set(e.value.fehler) == {"nummer", "zugang", "bewohner_telefon"}


def test_nur_lesen_sieht_wohnungen_aendert_nichts(anlage):
    c, con, aid = anlage
    gid = gruppen.anlegen(con, RWM, aid, {"zugang": "frei", "bewohner": "Müller"}, None)
    rid = rechte.rolle_anlegen(con, "Nur lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea", "lea@example.org", [rid])
    c2 = TestClient(c.app)
    anmelden(c2, "lea@example.org")
    seite = c2.get(f"/anlagen/{aid}").text
    assert "Wohnung 1" in seite and "Wohnung anlegen" not in seite and f'href="/gruppen/{gid}"' not in seite
    t = csrf_aus(seite)
    for pfad in (f"/anlagen/{aid}/gruppen/neu", f"/gruppen/{gid}", f"/gruppen/{gid}/loeschen"):
        r = c2.post(pfad, data={"zugang": "frei", "csrf_token": t}, follow_redirects=False)
        assert "keine_berechtigung" in r.headers["location"], pfad
