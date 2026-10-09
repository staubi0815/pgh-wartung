"""Lebenslauf: austauschen, ausbauen, Maßnahmen nur anhängen, Verlauf, Wohnung kopieren, Rechte."""
import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, gruppen, komponenten, kunden, lebenslauf, objekte, rechte, typen
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort

RWM = anlagenart.holen("rauchwarnmelder")
TYP = {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "hersteller": "Ei Electronics",
       "kategorie": "komponente", "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}


@pytest.fixture
def bestand(umgebung):
    """Anlage, Wohnung 43 mit Melder 43/1 (Flur, Baujahr 2015) und 43/2 (Funk-ID EIE-2)."""
    c, con = umgebung
    anmelden(c)
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Musterstraße 12", "adresse_wie_kunde": "1"}, None)
    a = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    g = gruppen.holen(con, gruppen.anlegen(con, RWM, a, {"nummer": "43", "zugang": "frei"}, None))
    typ = typen.anlegen(con, TYP, None)
    m1 = komponenten.anlegen(con, RWM, g, {"komponententyp_id": typ, "raum": "Flur", "baujahr": "2015",
                                           "inbetriebnahme_am": "2015-09-01", "seriennummer": "ALT-1"}, None)
    m2 = komponenten.anlegen(con, RWM, g, {"komponententyp_id": typ, "raum": "Schlafzimmer", "funk_id": "EIE-2"}, None)
    return c, con, a, g, typ, m1, m2


def test_austausch_ueber_die_webseite(bestand):
    c, con, a, g, typ, m1, _ = bestand
    seite = c.get(f"/komponenten/{m1}/austauschen").text
    assert "Austauschfrist erreicht" in seite and date.today().isoformat() in seite  # Gründe, Datum vorbelegt
    r = c.post(f"/komponenten/{m1}/austauschen", data={
        "grund": "austausch_faellig", "zeitpunkt": "2025-09-01", "komponententyp_id": typ, "seriennummer": "NEU-1",
        "baujahr": "2025", "bemerkung": "Turnus", "csrf_token": csrf_aus(seite)}, follow_redirects=False)
    assert r.headers["location"] == f"/anlagen/{a}?hinweis=komponente_ersetzt#g-{g['id']}"
    alt = con.execute("SELECT status, ersetzt_durch_id FROM komponente WHERE id = ?", (m1,)).fetchone()
    neu = komponenten.holen(con, alt["ersetzt_durch_id"])
    assert alt["status"] == "ersetzt"
    assert (neu["nummer"], neu["raum"], neu["raumart"], neu["seriennummer"]) == (1, "Flur", "flur_rettungsweg", "NEU-1")
    assert (neu["inbetriebnahme_am"], neu["naechste_pruefung_am"], neu["austausch_faellig_am"]) == \
        ("2025-09-01", "2026-09-01", "2035-01-01")
    m = con.execute("SELECT * FROM massnahme").fetchone()
    assert (m["art"], m["komponente_alt_id"], m["komponente_neu_id"], m["grund"], m["zeitpunkt"]) == \
        ("austausch", m1, neu["id"], "austausch_faellig", "2025-09-01")
    detail = c.get(f"/anlagen/{a}").text
    assert "NEU-1" in detail and "ALT-1" not in detail  # nur der verbaute erscheint in der Liste …
    verlauf = c.get(f"/komponenten/{neu['id']}").text
    assert "ALT-1" in verlauf and "Austauschfrist erreicht" in verlauf and "01.09.2025" in verlauf  # … der alte im Verlauf


def test_austausch_fehler_aendert_nichts(bestand):
    _, con, a, g, typ, m1, _ = bestand
    k = komponenten.holen(con, m1)
    with pytest.raises(Ungueltig) as e:  # Funk-ID gehört schon Melder 43/2
        lebenslauf.austauschen(con, RWM, k, {"grund": "sonstiges", "zeitpunkt": "2025-01-01",
                                             "komponententyp_id": typ, "funk_id": "eie-2"}, None)
    assert "funk_id" in e.value.fehler
    assert con.execute("SELECT status FROM komponente WHERE id = ?", (m1,)).fetchone()[0] == "verbaut"
    assert con.execute("SELECT COUNT(*) FROM komponente").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM massnahme").fetchone()[0] == 0
    for daten, feld in (({"zeitpunkt": "2014-01-01"}, "zeitpunkt"),                      # vor Inbetriebnahme
                        ({"zeitpunkt": "2099-01-01"}, "zeitpunkt"),                      # Zukunft
                        ({"zeitpunkt": "2020-01-01", "baujahr": "2022"}, "baujahr")):    # Baujahr nach Tausch
        with pytest.raises(Ungueltig) as e:
            lebenslauf.austauschen(con, RWM, k, {"grund": "sonstiges", "komponententyp_id": typ, **daten}, None)
        assert feld in e.value.fehler


def test_ausbau_macht_platz_frei(bestand):
    c, con, a, g, typ, m1, m2 = bestand
    t = csrf_aus(c.get(f"/komponenten/{m2}/ausbauen").text)
    r = c.post(f"/komponenten/{m2}/ausbauen", data={"grund": "raum_entfaellt", "zeitpunkt": "2026-01-15",
                                                     "csrf_token": t}, follow_redirects=False)
    assert "komponente_ausgebaut" in r.headers["location"]
    assert con.execute("SELECT status FROM komponente WHERE id = ?", (m2,)).fetchone()[0] == "ausgebaut"
    assert komponenten.naechste_nummer(con, g["id"]) == 2
    assert con.execute("SELECT art, grund FROM massnahme").fetchone()[:] == ("ausbau", "raum_entfaellt")
    # Funk-ID des ausgebauten Melders bleibt im Nachweis gespeichert und ist damit weiter belegt
    with pytest.raises(Ungueltig):
        komponenten.anlegen(con, RWM, g, {"komponententyp_id": typ, "funk_id": "EIE-2"}, None)


def test_massnahmen_nur_anhaengen(bestand):
    _, con, a, g, typ, m1, _ = bestand
    lebenslauf.ausbauen(con, komponenten.holen(con, m1), {"grund": "kunde", "zeitpunkt": "2026-01-01"}, None)
    assert con.execute("SELECT abgleich_nr FROM massnahme").fetchone()[0] > 0
    with pytest.raises(sqlite3.IntegrityError, match="nur angehängt"):
        con.execute("UPDATE massnahme SET grund = 'anders'")
    with pytest.raises(sqlite3.IntegrityError, match="nicht gelöscht"):
        con.execute("DELETE FROM massnahme")


def test_wohnung_kopieren(bestand):
    c, con, a, g, typ, m1, m2 = bestand
    seite = c.get(f"/gruppen/{g['id']}/kopieren").text
    assert "2 Melder-Plätzen" in seite and 'placeholder="44"' in seite
    t = csrf_aus(seite)
    r = c.post(f"/gruppen/{g['id']}/kopieren", data={"nummer": "43", "zugang": "frei", "csrf_token": t})
    assert r.status_code == 400 and "gibt es in dieser Anlage schon" in r.text
    r = c.post(f"/gruppen/{g['id']}/kopieren", data={"bezeichnung": "2. OG links", "zugang": "frei", "csrf_token": t},
               follow_redirects=False)
    neu_gid = r.headers["location"].split("#g-")[1]
    kopie = con.execute("SELECT nummer, raum, baujahr, inbetriebnahme_am, seriennummer, funk_id, austausch_faellig_am "
                        "FROM komponente WHERE gruppe_id = ? ORDER BY nummer", (neu_gid,)).fetchall()
    assert [tuple(z) for z in kopie] == [(1, "Flur", 2015, "2015-09-01", "", None, "2025-01-01"),
                                         (2, "Schlafzimmer", None, None, "", None, None)]
    assert gruppen.holen(con, neu_gid)["nummer"] == 44


def test_nur_lesen_kein_lebenslauf(bestand):
    c, con, a, g, typ, m1, _ = bestand
    rid = rechte.rolle_anlegen(con, "Nur lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea", "lea@example.org", [rid])
    c2 = TestClient(c.app)
    anmelden(c2, "lea@example.org")
    t = csrf_aus(c2.get(f"/anlagen/{a}").text)
    for pfad in (f"/komponenten/{m1}/austauschen", f"/komponenten/{m1}/ausbauen", f"/gruppen/{g['id']}/kopieren"):
        assert "keine_berechtigung" in c2.get(pfad, follow_redirects=False).headers["location"], pfad
        r = c2.post(pfad, data={"grund": "kunde", "zeitpunkt": "2026-01-01", "zugang": "frei", "csrf_token": t},
                    follow_redirects=False)
        assert "keine_berechtigung" in r.headers["location"], pfad
    assert con.execute("SELECT COUNT(*) FROM massnahme").fetchone()[0] == 0
