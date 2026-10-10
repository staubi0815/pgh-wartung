"""Einzelrechte, Rollen, Schutz gegen Rechte-Ausweitung, Transaktionen."""
import re
import threading

import pytest
from fastapi.testclient import TestClient

from wartung import __main__ as befehle
from wartung import db, rechte

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id


def zweiter_client(c, con, name, email, rollen_ids):
    nutzer_mit_passwort(con, name, email, rollen_ids)
    c2 = TestClient(c.app)
    return c2, anmelden(c2, email)


# ---------- Datenbank / Modell ----------

def test_standardrollen_nur_bekannte_rechte(umgebung):
    _, con = umgebung
    rechte_in_db = {z["recht"] for z in con.execute("SELECT recht FROM rolle_recht")}
    assert rechte_in_db and rechte_in_db <= set(rechte.RECHTE)
    assert {r["kennung"] for r in rechte.rollen(con)} == {"admin", "buero", "techniker", "techniker_app"}


def test_admin_hat_alle_rechte_auch_kuenftige(umgebung, monkeypatch):
    _, con = umgebung
    aid = con.execute("SELECT id FROM nutzer WHERE email = 'admin@example.org'").fetchone()["id"]
    assert rechte.rechte_von_nutzer(con, aid) == set(rechte.RECHTE)
    monkeypatch.setitem(rechte.RECHTE, "kuenftig.neu", "kommt später")
    assert "kuenftig.neu" in rechte.rechte_von_nutzer(con, aid)


def test_mehrere_rollen_ergeben_vereinigung(umgebung):
    _, con = umgebung
    nid = nutzer_mit_passwort(con, "Mia", "mia@example.org", [rolle_id(con, "buero"), rolle_id(con, "techniker_app")])
    r = rechte.rechte_von_nutzer(con, nid)
    assert {"stammdaten.bearbeiten", "app.auftraege", "web.zugang"} <= r
    assert "verwaltung.rollen" not in r


def test_migration_uebernimmt_alte_einzelrolle(tmp_path):
    con = db.verbinden(tmp_path / "alt.db")
    con.execute("CREATE TABLE schema_version (name TEXT PRIMARY KEY, am TEXT NOT NULL)")
    for befehl in db._befehle((db.MIGRATIONEN / "001_grundgeruest.sql").read_text(encoding="utf-8")):
        con.execute(befehl)
    con.execute("INSERT INTO schema_version VALUES ('001_grundgeruest.sql', 'x')")
    for nid, rolle in (("n1", "admin"), ("n2", "buero"), ("n3", "techniker")):
        con.execute("INSERT INTO nutzer (id, name, email, rolle, erstellt_am) VALUES (?, ?, ?, ?, 'x')",
                    (nid, nid, f"{nid}@example.org", rolle))
    assert db.migrieren(con)[0] == "002_rechte_und_rollen.sql"
    zuordnung = {z["nutzer_id"]: z["kennung"] for z in con.execute(
        "SELECT nr.nutzer_id, r.kennung FROM nutzer_rolle nr JOIN rolle r ON r.id = nr.rolle_id")}
    assert zuordnung == {"n1": "admin", "n2": "buero", "n3": "techniker"}
    assert "rolle" not in [s[1] for s in con.execute("PRAGMA table_info(nutzer)")]


# ---------- Anmeldung und Seitenzugriff ----------

def test_techniker_nur_app_kommt_nicht_auf_die_webseite(umgebung):
    c, con = umgebung
    c2, r = zweiter_client(c, con, "Tim", "tim@example.org", [rolle_id(con, "techniker_app")])
    assert r.status_code == 403 and "nur für die App" in r.text
    assert c2.get("/", follow_redirects=False).headers["location"] == "/anmelden"


def test_techniker_mit_web_sieht_keine_verwaltung(umgebung):
    c, con = umgebung
    c2, r = zweiter_client(c, con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    assert r.status_code == 303
    start = c2.get("/")
    assert start.status_code == 200 and 'href="/verwaltung"' not in start.text
    for pfad in ("/verwaltung", "/verwaltung/nutzer", "/verwaltung/rollen", "/verwaltung/firma", "/verwaltung/protokoll"):
        assert "keine_berechtigung" in c2.get(pfad, follow_redirects=False).headers["location"], pfad


def test_admin_sieht_alle_verwaltungsseiten(umgebung):
    c, _ = umgebung
    anmelden(c)
    seite = c.get("/verwaltung/nutzer").text
    for pfad in ("/verwaltung/nutzer", "/verwaltung/rollen", "/verwaltung/firma", "/verwaltung/protokoll"):
        assert f'href="{pfad}"' in seite
        assert c.get(pfad).status_code == 200
    assert 'href="/verwaltung"' in seite
    matrix = c.get("/verwaltung/rollen").text
    assert "Techniker ohne Webzugang" in matrix and "Funk-Ferninspektion" in matrix


def test_rechteaenderung_wirkt_sofort(umgebung):
    c, con = umgebung
    anmelden(c)
    rid = rechte.rolle_anlegen(con, "Prüfer Protokoll", "", ["web.zugang", "verwaltung.protokoll"], None)
    c2, _ = zweiter_client(c, con, "Paul", "paul@example.org", [rid])
    assert c2.get("/verwaltung/protokoll").status_code == 200
    t = csrf_aus(c.get(f"/verwaltung/rollen/{rid}").text)
    c.post(f"/verwaltung/rollen/{rid}", data={"name": "Prüfer Protokoll", "rechte": ["web.zugang"], "csrf_token": t})
    assert "keine_berechtigung" in c2.get("/verwaltung/protokoll", follow_redirects=False).headers["location"]


# ---------- Schutz gegen Rechte-Ausweitung ----------

@pytest.fixture
def personalchef(umgebung):
    """Nutzer mit eigener Rolle: darf Nutzer verwalten und hat Techniker-Rechte, aber nicht Büro oder Administration."""
    c, con = umgebung
    rid = rechte.rolle_anlegen(con, "Personal", "", ["web.zugang", "verwaltung.nutzer", "app.zugang", "app.auftraege",
                                                     "app.stammdaten", "app.fotos"], None)
    c2, r = zweiter_client(c, con, "Petra", "petra@example.org", [rid])
    assert r.status_code == 303
    return c2, con


def test_nutzerverwalter_darf_nur_eigene_rechte_vergeben(personalchef):
    c2, con = personalchef
    seite = c2.get("/verwaltung/nutzer/neu").text
    assert re.search(rf'value="{rolle_id(con, "admin")}"[^>]*disabled', seite)
    t = csrf_aus(seite)
    daten = {"name": "Neu", "email": "neu@example.org", "csrf_token": t}
    for kennung in ("admin", "buero"):
        r = c2.post("/verwaltung/nutzer/neu", data={**daten, "rollen": rolle_id(con, kennung)})
        assert r.status_code == 400 and "deren Rechte Sie selbst haben" in r.text, kennung
    r = c2.post("/verwaltung/nutzer/neu", data={**daten, "rollen": rolle_id(con, "techniker")})
    assert r.status_code == 200 and "/einrichten?code=" in r.text


def test_nutzerverwalter_kann_admin_nicht_bearbeiten(personalchef):
    c2, con = personalchef
    aid = con.execute("SELECT id FROM nutzer WHERE email = 'admin@example.org'").fetchone()["id"]
    assert "keine_berechtigung" in c2.get(f"/verwaltung/nutzer/{aid}", follow_redirects=False).headers["location"]
    t = csrf_aus(c2.get("/verwaltung/nutzer").text)
    r = c2.post(f"/verwaltung/nutzer/{aid}", data={"name": "weg", "rollen": rolle_id(con, "techniker"), "csrf_token": t},
                follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]
    assert con.execute("SELECT aktiv FROM nutzer WHERE id = ?", (aid,)).fetchone()["aktiv"] == 1
    r = c2.post(f"/verwaltung/nutzer/{aid}/einladung", data={"csrf_token": t}, follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]


def test_ohne_auswahl_keine_rolle_geht_nicht(umgebung):
    c, _ = umgebung
    anmelden(c)
    t = csrf_aus(c.get("/verwaltung/nutzer/neu").text)
    r = c.post("/verwaltung/nutzer/neu", data={"name": "X", "email": "x@example.org", "csrf_token": t})
    assert r.status_code == 400 and "mindestens eine Rolle" in r.text


# ---------- Rollen pflegen ----------

def test_rolle_anlegen_aendern_wird_protokolliert(umgebung):
    c, con = umgebung
    anmelden(c)
    t = csrf_aus(c.get("/verwaltung/rollen/neu").text)
    r = c.post("/verwaltung/rollen/neu", data={"name": "Azubi", "beschreibung": "nur schauen",
                                               "rechte": ["web.zugang", "stammdaten.lesen"], "csrf_token": t},
               follow_redirects=False)
    rid = r.headers["location"].split("/")[3].split("?")[0]
    assert rechte.rechte_von_rolle(con, rid) == {"web.zugang", "stammdaten.lesen"}
    c.post(f"/verwaltung/rollen/{rid}", data={"name": "Azubi", "beschreibung": "nur schauen",
                                              "rechte": ["web.zugang", "app.zugang"], "csrf_token": t})
    p = {(z["aktion"], z["neu"] or z["alt"]) for z in con.execute(
        "SELECT aktion, alt, neu FROM aenderungsprotokoll WHERE tabelle = 'rolle' AND datensatz = ?", (rid,))}
    assert {("anlegen", "Azubi"), ("recht_hinzu", "stammdaten.lesen"), ("recht_weg", "stammdaten.lesen"),
            ("recht_hinzu", "app.zugang")} <= p
    r = c.post("/verwaltung/rollen/neu", data={"name": "azubi", "rechte": ["web.zugang"], "csrf_token": t})
    assert r.status_code == 400 and "gibt es schon" in r.text
    r = c.post("/verwaltung/rollen/neu", data={"name": "Fremd", "rechte": ["gibt.es.nicht"], "csrf_token": t})
    assert r.status_code == 400 and "Unbekanntes Recht" in r.text


def test_administration_ist_fest(umgebung):
    c, con = umgebung
    anmelden(c)
    aid = rolle_id(con, "admin")
    t = csrf_aus(c.get(f"/verwaltung/rollen/{aid}").text)
    r = c.post(f"/verwaltung/rollen/{aid}", data={"name": "Admin", "rechte": ["web.zugang"], "csrf_token": t})
    assert r.status_code == 400
    assert con.execute("SELECT name FROM rolle WHERE id = ?", (aid,)).fetchone()["name"] == "Administration"


def test_rolle_loeschen_nur_ohne_nutzer_und_nicht_standard(umgebung):
    c, con = umgebung
    anmelden(c)
    t = csrf_aus(c.get("/verwaltung/rollen").text)
    r = c.post(f"/verwaltung/rollen/{rolle_id(con, 'buero')}/loeschen", data={"csrf_token": t})
    assert r.status_code == 400 and "Standardrollen" in r.text
    rid = rechte.rolle_anlegen(con, "Saison", "", ["web.zugang"], None)
    nid = nutzer_mit_passwort(con, "Sam", "sam@example.org", [rid])
    r = c.post(f"/verwaltung/rollen/{rid}/loeschen", data={"csrf_token": t})
    assert r.status_code == 400 and "noch Nutzern zugeordnet" in r.text
    rechte.nutzer_rollen_setzen(con, nid, [rolle_id(con, "techniker")], None)
    assert c.post(f"/verwaltung/rollen/{rid}/loeschen", data={"csrf_token": t}, follow_redirects=False).status_code == 303
    assert rid not in {r["id"] for r in rechte.rollen(con)}


# ---------- Transaktionen und Verbindungen ----------

def test_transaktion_alles_oder_nichts(tmp_path):
    con = db.verbinden(tmp_path / "t.db")
    con.execute("CREATE TABLE t (x INTEGER)")
    with pytest.raises(ValueError):
        with db.transaktion(con):
            con.execute("INSERT INTO t VALUES (1)")
            raise ValueError
    assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    with db.transaktion(con):
        con.execute("INSERT INTO t VALUES (1)")
        with pytest.raises(ValueError):
            with db.transaktion(con):  # innen: nur der innere Teil wird zurückgerollt
                con.execute("INSERT INTO t VALUES (2)")
                raise ValueError
    assert [z[0] for z in con.execute("SELECT x FROM t")] == [1]
    assert not con.in_transaction


def test_eigene_verbindung_je_thread(tmp_path):
    db.verbinden(tmp_path / "v.db").close()
    tv = db.ThreadVerbindung(tmp_path / "v.db")
    ids = []
    t = threading.Thread(target=lambda: ids.append(id(tv._con())))
    t.start()
    t.join()
    assert ids[0] != id(tv._con()) and id(tv._con()) == id(tv._con())


# ---------- Notfallzugang über die Kommandozeile ----------

def test_admin_einladen_stellt_konto_wieder_her(umgebung, monkeypatch, capsys, tmp_path):
    _, con = umgebung
    nid = nutzer_mit_passwort(con, "Ex", "ex@example.org", [rolle_id(con, "techniker")])
    db.aendern(con, "nutzer", nid, {"aktiv": 0}, None)
    monkeypatch.setenv("WARTUNG_DATEN", str(tmp_path))
    assert befehle.main(["admin-einladen", "Ex", "ex@example.org"]) == 0
    assert "/einrichten?code=" in capsys.readouterr().out
    assert con.execute("SELECT aktiv FROM nutzer WHERE id = ?", (nid,)).fetchone()["aktiv"] == 1
    assert rolle_id(con, "admin") in rechte.rollen_von_nutzer(con, nid)


def test_standardrollen_wie_foxtag(umgebung):
    _, con = umgebung
    namen = {r["kennung"]: r["name"] for r in con.execute("SELECT kennung, name FROM rolle WHERE kennung IS NOT NULL")}
    assert namen == {"admin": "Administration", "buero": "Planen und Daten pflegen", "techniker": "Techniker",
                     "techniker_app": "Techniker ohne Webzugang"}
    rechte = lambda k: {r[0] for r in con.execute(  # noqa: E731
        "SELECT recht FROM rolle_recht rr JOIN rolle r ON r.id = rr.rolle_id WHERE r.kennung = ?", (k,))}
    assert "verwaltung.nutzer" in rechte("buero") and "auswertungen" not in rechte("buero")
    assert not {r for r in rechte("buero") if r.startswith("app.")}
    assert "web.zugang" not in rechte("techniker_app") and "web.zugang" in rechte("techniker")
