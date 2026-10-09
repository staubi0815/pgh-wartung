"""Auftrags-Seiten: planen aus der Anlage, ansehen, bearbeiten/verschieben, Status, Rechte, CSRF."""
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, auftraege, gruppen, kunden, objekte, rechte
from wartung.felder import datum_de

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

RWM = anlagenart.holen("rauchwarnmelder")
MORGEN = (date.today() + timedelta(days=1)).isoformat()
SPAETER = (date.today() + timedelta(days=14)).isoformat()
MORGEN_DE, SPAETER_DE = datum_de(MORGEN), datum_de(SPAETER)


@pytest.fixture
def web(umgebung):
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "strasse": "Weg 1", "plz": "90402", "ort": "Nürnberg"}, None)
    aid = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A",
                                   "hinweise_techniker": "Hund im Hof"}, None)
    g1 = gruppen.anlegen(con, RWM, aid, {"nummer": "1", "bezeichnung": "EG", "zugang": "frei"}, None)
    tom = nutzer_mit_passwort(con, "Tom Techniker", "tom@example.org", [rolle_id(con, "techniker")])
    anmelden(c)
    return {"c": c, "con": con, "anlage_id": aid, "g1": g1, "tom": tom}


def planen_formular(w, **werte):
    c = w["c"]
    seite = c.get(f"/anlagen/{w['anlage_id']}/auftraege/neu")
    daten = {"csrf_token": csrf_aus(seite.text), "auftragsart": "wartung", "datum": MORGEN, **werte}
    return c.post(f"/anlagen/{w['anlage_id']}/auftraege/neu", data=daten, follow_redirects=False)


def auftrag_id(antwort):
    return re.search(r"/auftraege/([0-9a-f-]{36})", antwort.headers["location"]).group(1)


def test_planen_ueber_formular(web):
    c = web["c"]
    seite = c.get(f"/anlagen/{web['anlage_id']}/auftraege/neu")
    assert seite.status_code == 200 and 'placeholder="A-1001"' in seite.text and "Tom Techniker" in seite.text
    assert "Hund im Hof" in seite.text and 'value="wartung" selected' in seite.text  # Standard-Auftragsart
    r = planen_formular(web, uhrzeit="08:30", techniker=[web["tom"]], hinweise="Klingel defekt")
    assert r.status_code == 303 and r.headers["location"].endswith("?hinweis=angelegt")
    detail = c.get(r.headers["location"]).text
    for erwartet in ("Auftrag geplant.", "A-1001", "Wartung / Inspektion", f"{datum_de(MORGEN, True)} um 08:30 Uhr",
                     "Tom Techniker", "Ganze Anlage", "Klingel defekt", "Geplant", f"geplant für {MORGEN_DE} 08:30",
                     "Stornieren"):
        assert erwartet in detail, erwartet
    anlage = c.get(f"/anlagen/{web['anlage_id']}").text
    assert f'href="/auftraege/{auftrag_id(r)}">A-1001</a>' in anlage and "Auftrag planen" in anlage


def test_planen_fehler_behalten_eingaben(web):
    r = planen_formular(web, umfang="auswahl", techniker=[web["tom"]], hinweise="bleibt stehen")
    assert r.status_code == 400 and "Bitte mindestens eine Wohnung wählen" in r.text
    assert re.search(rf'value="{web["tom"]}" checked', r.text) and "bleibt stehen" in r.text
    assert web["con"].execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 0


def test_verschieben_und_status(web):
    c, con = web["c"], web["con"]
    aid = auftrag_id(planen_formular(web, uhrzeit="08:30"))
    form = c.get(f"/auftraege/{aid}/bearbeiten")
    assert form.status_code == 200 and "Grund, falls sich der Termin ändert" in form.text
    r = c.post(f"/auftraege/{aid}/bearbeiten", data={"csrf_token": csrf_aus(form.text), "auftragsart": "wartung",
                                                    "datum": SPAETER, "uhrzeit": "", "grund": "Mieter verreist",
                                                    "umfang": "ganze_anlage"}, follow_redirects=False)
    assert r.headers["location"].endswith("?hinweis=gespeichert")
    detail = c.get(f"/auftraege/{aid}").text
    assert f"verschoben von {MORGEN_DE} 08:30 auf {SPAETER_DE}" in detail and "Mieter verreist" in detail
    assert f"{SPAETER_DE} (ganztägig)" in detail
    t = csrf_aus(detail)
    # Stornieren ohne Grund: Fehler, nichts geändert
    r = c.post(f"/auftraege/{aid}/status", data={"csrf_token": t, "neu": "storniert", "grund": ""})
    assert r.status_code == 400 and "Bitte einen Grund angeben." in r.text
    assert auftraege.holen(con, aid)["status"] == "geplant"
    # unzulässiger Übergang
    r = c.post(f"/auftraege/{aid}/status", data={"csrf_token": t, "neu": "abgerechnet"})
    assert r.status_code == 400 and "nicht möglich" in r.text
    r = c.post(f"/auftraege/{aid}/status", data={"csrf_token": t, "neu": "storniert", "grund": "Kunde abgesprungen"},
               follow_redirects=False)
    assert r.headers["location"].endswith("?hinweis=status")
    detail = c.get(f"/auftraege/{aid}").text
    assert "Storniert" in detail and "Bearbeiten / verschieben" not in detail and "Wieder einplanen" in detail
    assert c.get(f"/auftraege/{aid}/bearbeiten", follow_redirects=False).headers["location"].endswith(
        "?hinweis=nicht_aenderbar")
    anlage = c.get(f"/anlagen/{web['anlage_id']}").text
    assert "status-storniert" in anlage


def test_umfang_bei_laufendem_auftrag_gesperrt(web):
    c, con = web["c"], web["con"]
    aid = auftrag_id(planen_formular(web, umfang="auswahl", gruppen=[web["g1"]]))
    auftraege.status_setzen(con, aid, "aktiv", None)
    form = c.get(f"/auftraege/{aid}/bearbeiten").text
    assert "nur änderbar, solange der Auftrag geplant ist" in form
    assert re.search(rf'<input type="hidden" name="gruppen" value="{web["g1"]}">', form)
    # Absenden mit den mitgeschickten (gesperrten) Werten: Techniker ändern geht, Umfang bleibt
    r = c.post(f"/auftraege/{aid}/bearbeiten", data={"csrf_token": csrf_aus(form), "auftragsart": "wartung",
                                                    "datum": MORGEN, "umfang": "auswahl", "gruppen": [web["g1"]],
                                                    "techniker": [web["tom"]]}, follow_redirects=False)
    assert r.headers["location"].endswith("?hinweis=gespeichert")
    assert [t["name"] for t in auftraege.techniker(con, aid)] == ["Tom Techniker"]


def test_passive_anlage(web):
    c, con = web["c"], web["con"]
    a = anlagen.holen(con, web["anlage_id"])
    anlagen.aendern(con, a["id"], {**dict(a), "passiv": "1"}, None)
    seite = c.get(f"/anlagen/{a['id']}").text
    assert "Auftrag planen</a>" not in seite and "Die Anlage ist passiv" in seite
    r = planen_formular(web)
    assert r.status_code == 400 and "passiv" in r.text


def test_rechte_und_csrf(web):
    c, con = web["c"], web["con"]
    aid = auftrag_id(planen_formular(web))
    # Techniker: kein Planen (Ansicht für Techniker folgt mit der Auftragsliste)
    tech = TestClient(c.app)
    anmelden(tech, "tom@example.org")
    assert "keine_berechtigung" in tech.get(f"/anlagen/{web['anlage_id']}/auftraege/neu",
                                            follow_redirects=False).headers["location"]
    # nur Lesen: Auftrag sichtbar, aber ohne Bearbeiten und ohne Statusknöpfe; Status setzen verboten
    rid = rechte.rolle_anlegen(con, "Nur lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea Lesen", "lea@example.org", [rid])
    lea = TestClient(c.app)
    anmelden(lea, "lea@example.org")
    detail = lea.get(f"/auftraege/{aid}")
    assert detail.status_code == 200 and "Status ändern" not in detail.text and "Bearbeiten" not in detail.text
    assert "Auftrag planen" not in lea.get(f"/anlagen/{web['anlage_id']}").text
    r = lea.post(f"/auftraege/{aid}/status", data={"csrf_token": csrf_aus(detail.text), "neu": "aktiv"},
                 follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"] and auftraege.holen(con, aid)["status"] == "geplant"
    # Büro darf planen; ohne gültiges CSRF-Merkmal passiert nichts
    r = c.post(f"/auftraege/{aid}/status", data={"csrf_token": "falsch", "neu": "aktiv"}, follow_redirects=False)
    assert "sitzung_abgelaufen" in r.headers["location"] and auftraege.holen(con, aid)["status"] == "geplant"
    assert c.get("/auftraege/gibt-es-nicht", follow_redirects=False).status_code == 303
