"""Kunden und Kontakte: Eingabeprüfung, Rechte, Nummern, Löschregeln, Protokoll, Suche."""
import pytest
from fastapi.testclient import TestClient

from wartung import db, felder, kunden
from wartung.felder import Feld, Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

KUNDE = {"art": "hausverwaltung", "name": "Muster-Hausverwaltung GmbH", "strasse": "Hauptstr. 1", "plz": "90402",
         "ort": "Nürnberg", "telefon": "0911 123456", "email": "Info@Muster.example"}


def kunde_anlegen_web(c, daten=None):
    t = csrf_aus(c.get("/kunden/neu").text)
    return c.post("/kunden/neu", data={**KUNDE, **(daten or {}), "csrf_token": t}, follow_redirects=False)


# ---------- Feldprüfung (gemeinsamer Baustein) ----------

def test_felder_einlesen_bereinigt_und_prueft():
    fs = (Feld("name", "Name", pflicht=True), Feld("mail", "E-Mail", "email"), Feld("tel", "Telefon", "tel"),
          Feld("art", "Art", "auswahl", auswahl=(("a", "A"),)), Feld("jahr", "Jahr", "zahl", minimum=1990, maximum=2100),
          Feld("aktiv", "Aktiv", "ja_nein"), Feld("am", "Am", "datum"), Feld("notiz", "Notiz", "textarea"))
    werte, fehler = felder.einlesen(fs, {"name": "  Max \n Muster ", "mail": "A@B.DE", "tel": "0911/12-3",
                                         "art": "a", "jahr": "2016", "aktiv": "on", "am": "", "notiz": "Zeile1\nZeile2"})
    assert not fehler
    assert werte == {"name": "Max Muster", "mail": "a@b.de", "tel": "0911/12-3", "art": "a", "jahr": 2016,
                     "aktiv": 1, "am": None, "notiz": "Zeile1\nZeile2"}
    _, fehler = felder.einlesen(fs, {"name": "", "mail": "kein-at", "tel": "abc", "art": "x", "jahr": "1800",
                                     "am": "1.1.2026"})
    assert set(fehler) == {"name", "mail", "tel", "art", "jahr", "am"}


# ---------- Kunden über die Webseite ----------

def test_kunde_anlegen_mit_automatischer_nummer(umgebung):
    c, con = umgebung
    anmelden(c)
    assert "K0001" in c.get("/kunden/neu").text  # Vorschau der nächsten Nummer
    r = kunde_anlegen_web(c)
    assert r.status_code == 303
    k = con.execute("SELECT * FROM kunde").fetchone()
    assert k["nummer"] == "K0001" and k["email"] == "info@muster.example" and k["land"] == "DE"
    seite = c.get(r.headers["location"]).text
    assert "Muster-Hausverwaltung GmbH" in seite and "Kunde angelegt." in seite
    assert kunde_anlegen_web(c, {"name": "Zweiter"}).status_code == 303
    assert con.execute("SELECT nummer FROM kunde WHERE name = 'Zweiter'").fetchone()[0] == "K0002"


def test_kunde_eingabefehler_werden_angezeigt(umgebung):
    c, con = umgebung
    anmelden(c)
    r = kunde_anlegen_web(c, {"name": "", "plz": "123", "email": "x"})
    assert r.status_code == 400
    assert "Name ist Pflicht." in r.text and "fünf Ziffern" in r.text and "gültige E-Mail" in r.text
    assert 'value="Hauptstr. 1"' in r.text  # Eingaben bleiben erhalten
    assert con.execute("SELECT COUNT(*) FROM kunde").fetchone()[0] == 0


def test_handnummer_doppelt_abgelehnt(umgebung):
    c, _ = umgebung
    anmelden(c)
    assert kunde_anlegen_web(c, {"nummer": "K0815"}).status_code == 303
    r = kunde_anlegen_web(c, {"nummer": "k0815", "name": "Anderer"})
    assert r.status_code == 400 and "schon vergeben" in r.text


def test_kunde_aendern_wird_protokolliert(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunde_anlegen_web(c).headers["location"].split("/")[2].split("?")[0]
    seite = c.get(f"/kunden/{kid}/bearbeiten").text
    werte = {**KUNDE, "nummer": "K0001", "ort": "Fürth", "plz": "90762", "csrf_token": csrf_aus(seite)}
    assert c.post(f"/kunden/{kid}/bearbeiten", data=werte, follow_redirects=False).status_code == 303
    p = {(z["feld"], z["alt"], z["neu"]) for z in con.execute(
        "SELECT feld, alt, neu FROM aenderungsprotokoll WHERE tabelle = 'kunde' AND aktion = 'aendern'")}
    assert p == {("ort", "Nürnberg", "Fürth"), ("plz", "90402", "90762")}
    werte["nummer"] = ""
    r = c.post(f"/kunden/{kid}/bearbeiten", data=werte)
    assert r.status_code == 400 and "Kundennummer ist Pflicht." in r.text


def test_suche_und_filter(umgebung):
    c, _ = umgebung
    anmelden(c)
    kunde_anlegen_web(c)
    kunde_anlegen_web(c, {"name": "Familie Beispiel", "art": "privat", "ort": "Erlangen", "plz": "91052"})
    assert "Familie Beispiel" in c.get("/kunden?q=erlang").text
    assert "Muster-Hausverwaltung" not in c.get("/kunden?q=erlang").text
    assert "Muster-Hausverwaltung" not in c.get("/kunden?art=privat").text
    assert "Keine Kunden gefunden" in c.get("/kunden?q=100%25_").text  # Platzhalterzeichen werden nicht ausgewertet


# ---------- Kontakte ----------

def test_kontakt_anlegen_aendern_loeschen(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunde_anlegen_web(c).headers["location"].split("/")[2].split("?")[0]
    t = csrf_aus(c.get(f"/kunden/{kid}/kontakte/neu").text)
    r = c.post(f"/kunden/{kid}/kontakte/neu", data={"name": "Hans Hausmeister", "funktion": "Hausmeister",
                                                     "mobil": "0170 1234567", "csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303
    kt = con.execute("SELECT * FROM kontakt").fetchone()
    assert kt["kunde_id"] == kid and "Hans Hausmeister" in c.get(f"/kunden/{kid}").text
    r = c.post(f"/kontakte/{kt['id']}", data={"name": "Hans Hausmeister", "mobil": "falsch!", "csrf_token": t})
    assert r.status_code == 400 and "nur Ziffern" in r.text
    c.post(f"/kontakte/{kt['id']}/loeschen", data={"csrf_token": t})
    assert con.execute("SELECT geloescht FROM kontakt").fetchone()[0] == 1
    assert "Hans Hausmeister" not in c.get(f"/kunden/{kid}").text


# ---------- Löschregeln ----------

def test_kunde_nur_ohne_objekte_loeschbar(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunde_anlegen_web(c).headers["location"].split("/")[2].split("?")[0]
    oid = db.anlegen(con, "objekt", {"nummer": "O-0001", "kunde_id": kid, "bezeichnung": "Musterstraße 1"}, None)
    t = csrf_aus(c.get(f"/kunden/{kid}").text)
    r = c.post(f"/kunden/{kid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert "hat_objekte" in r.headers["location"]
    assert con.execute("SELECT geloescht FROM kunde").fetchone()[0] == 0
    db.aendern(con, "objekt", oid, {"geloescht": 1}, None)
    kunden.kontakt_anlegen(con, kid, {"name": "Kontakt A"}, None)
    r = c.post(f"/kunden/{kid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert r.headers["location"] == "/kunden?hinweis=geloescht"
    assert con.execute("SELECT geloescht FROM kunde").fetchone()[0] == 1
    assert con.execute("SELECT geloescht FROM kontakt").fetchone()[0] == 1  # Kontakte gehen mit
    assert c.get(f"/kunden/{kid}", follow_redirects=False).headers["location"] == "/kunden?hinweis=nicht_gefunden"


def test_loeschen_ohne_csrf_wirkt_nicht(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunde_anlegen_web(c).headers["location"].split("/")[2].split("?")[0]
    r = c.post(f"/kunden/{kid}/loeschen", data={}, follow_redirects=False)
    assert "sitzung_abgelaufen" in r.headers["location"]
    assert con.execute("SELECT geloescht FROM kunde").fetchone()[0] == 0


# ---------- Rechte ----------

def test_techniker_sieht_keine_kunden(umgebung):
    c, con = umgebung
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    c2 = TestClient(c.app)
    anmelden(c2, "tom@example.org")
    assert 'href="/kunden"' not in c2.get("/").text
    assert "keine_berechtigung" in c2.get("/kunden", follow_redirects=False).headers["location"]


def test_nur_lesen_darf_nicht_aendern(umgebung):
    c, con = umgebung
    from wartung import rechte
    rid = rechte.rolle_anlegen(con, "Nur lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea", "lea@example.org", [rid])
    kid = kunden.anlegen(con, KUNDE, None)
    c2 = TestClient(c.app)
    anmelden(c2, "lea@example.org")
    seite = c2.get(f"/kunden/{kid}").text
    assert "Muster-Hausverwaltung" in seite and "Bearbeiten" not in seite and "Kunde löschen" not in seite
    t = csrf_aus(seite)
    for pfad in ("/kunden/neu", f"/kunden/{kid}/bearbeiten", f"/kunden/{kid}/loeschen"):
        r = c2.post(pfad, data={**KUNDE, "csrf_token": t}, follow_redirects=False)
        assert "keine_berechtigung" in r.headers["location"], pfad
    assert con.execute("SELECT COUNT(*) FROM kunde WHERE geloescht = 0").fetchone()[0] == 1


def test_modul_kunden_ohne_web(umgebung):
    _, con = umgebung
    with pytest.raises(Ungueltig) as e:
        kunden.anlegen(con, {"art": "hausverwaltung", "name": "X", "land": "AT", "plz": "1010", "email": "@"}, None)
    assert set(e.value.fehler) == {"email"}  # österreichische PLZ mit 4 Ziffern ist erlaubt
