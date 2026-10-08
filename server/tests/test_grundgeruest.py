import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from wartung import auth, db

from hilfen import PW, anmelden, csrf_aus, rolle_id


def test_ohne_anmeldung_umleitung(umgebung):
    c, _ = umgebung
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/anmelden"
    assert c.get("/verwaltung/nutzer", follow_redirects=False).status_code == 303


def test_anmelden_und_sicherheitskoepfe(umgebung):
    c, _ = umgebung
    assert anmelden(c).status_code == 303
    r = c.get("/")
    assert "Guten Tag, Test Admin" in r.text
    assert r.headers["X-Frame-Options"] == "DENY" and "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_falsches_passwort_und_sperre(umgebung):
    c, _ = umgebung
    for _ in range(auth.MAX_FEHLVERSUCHE):
        assert anmelden(c, pw="falsch").status_code == 401
    r = anmelden(c)  # richtiges Passwort, aber gesperrt
    assert r.status_code == 401 and "Zu viele Fehlversuche" in r.text


def test_unbekannte_adresse_gleiche_meldung(umgebung):
    c, _ = umgebung
    r = anmelden(c, email="gibtsnicht@example.org")
    assert r.status_code == 401 and "Anmeldung fehlgeschlagen." in r.text


def test_csrf_pflicht(umgebung):
    c, _ = umgebung
    anmelden(c)
    r = c.post("/verwaltung/firma", data={"name": "Böse"}, follow_redirects=False)
    assert r.status_code == 303 and "sitzung_abgelaufen" in r.headers["location"]


def test_einladung_passwort_setzen_und_rollen(umgebung):
    c, con = umgebung
    anmelden(c)
    t = csrf_aus(c.get("/verwaltung/nutzer/neu").text)
    r = c.post("/verwaltung/nutzer/neu", data={"name": "Tom Techniker", "email": "tom@example.org",
                                               "rollen": rolle_id(con, "techniker"), "personalnummer": "P-1",
                                               "csrf_token": t})
    link = re.search(r"<code>([^<]+)</code>", r.text).group(1)
    code = link.split("code=")[1]
    t2 = csrf_aus(c.post("/abmelden", data={"csrf_token": t}).text)
    # zu kurzes Passwort wird abgelehnt
    r = c.post("/einrichten", data={"code": code, "passwort": "kurz", "passwort2": "kurz", "csrf_token": t2})
    assert r.status_code == 400
    r = c.post("/einrichten", data={"code": code, "passwort": PW, "passwort2": PW, "csrf_token": t2},
               follow_redirects=False)
    assert r.status_code == 303
    # Link nur einmal gültig
    assert c.get(f"/einrichten?code={code}").status_code == 404
    assert anmelden(c, "tom@example.org").status_code == 303
    r = c.get("/verwaltung/nutzer", follow_redirects=False)  # Techniker darf nicht in die Verwaltung
    assert r.status_code == 303 and "keine_berechtigung" in r.headers["location"]


def test_deaktivieren_beendet_sitzung(umgebung):
    c, con = umgebung
    anmelden(c)
    nid = auth.nutzer_anlegen(con, "Bea Büro", "bea@example.org", [rolle_id(con, "buero")], None)
    auth.passwort_setzen(con, nid, PW, None)
    c2 = TestClient(c.app)
    assert anmelden(c2, "bea@example.org").status_code == 303
    assert c2.get("/", follow_redirects=False).status_code == 200
    t = csrf_aus(c.get(f"/verwaltung/nutzer/{nid}").text)
    c.post(f"/verwaltung/nutzer/{nid}", data={"name": "Bea Büro", "rollen": rolle_id(con, "buero"),
                                              "csrf_token": t})  # ohne aktiv
    assert c2.get("/", follow_redirects=False).status_code == 303


def test_eigenes_admin_konto_geschuetzt(umgebung):
    c, con = umgebung
    anmelden(c)
    aid = con.execute("SELECT id FROM nutzer WHERE email='admin@example.org'").fetchone()["id"]
    t = csrf_aus(c.get(f"/verwaltung/nutzer/{aid}").text)
    r = c.post(f"/verwaltung/nutzer/{aid}", data={"name": "X", "rollen": rolle_id(con, "techniker"), "aktiv": "1",
                                                  "csrf_token": t})
    assert r.status_code == 400 and "Administration kann nicht entfernt" in r.text
    r = c.post(f"/verwaltung/nutzer/{aid}", data={"name": "X", "rollen": rolle_id(con, "admin"), "csrf_token": t})
    assert r.status_code == 400 and "nicht deaktiviert" in r.text


def test_firma_aendern_wird_protokolliert(umgebung):
    c, con = umgebung
    anmelden(c)
    t = csrf_aus(c.get("/verwaltung/firma").text)
    form = {k: con.execute(f"SELECT {k} FROM firma").fetchone()[0] for k in
            ["name", "inhaber", "strasse", "plz", "ort", "telefon", "email", "praefix_kunde", "praefix_objekt",
             "praefix_anlage", "praefix_auftrag", "berichtsfusszeile"]}
    form.update({"ort": "Teststadt", "csrf_token": t})
    c.post("/verwaltung/firma", data=form)
    z = con.execute("SELECT * FROM aenderungsprotokoll WHERE tabelle='firma'").fetchall()
    assert len(z) == 1 and z[0]["feld"] == "ort" and z[0]["neu"] == "Teststadt"
    assert "Teststadt" in c.get("/verwaltung/protokoll").text


def test_protokoll_nicht_aenderbar(umgebung):
    _, con = umgebung
    db.protokoll(con, None, "x", "1", "test")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM aenderungsprotokoll")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE aenderungsprotokoll SET aktion='y'")


def test_passwort_nie_im_protokoll(umgebung):
    _, con = umgebung
    werte = [r["alt"] for r in con.execute("SELECT alt, neu FROM aenderungsprotokoll")] + \
            [r["neu"] for r in con.execute("SELECT alt, neu FROM aenderungsprotokoll")]
    assert not any(w and "argon2" in w for w in werte)


def test_migration_idempotent(tmp_path):
    con = db.verbinden(tmp_path / "x.db")
    alle = sorted(d.name for d in db.MIGRATIONEN.glob("[0-9][0-9][0-9]_*.sql"))
    assert alle[:2] == ["001_grundgeruest.sql", "002_rechte_und_rollen.sql"]
    assert db.migrieren(con) == alle
    assert db.migrieren(con) == []
