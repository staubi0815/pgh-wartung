"""Import-Seite: Hochladen, Vorschau, Übernehmen, Bindung an die Sitzung, Dateirechte, Vorlagen, Rechte."""
import io
import re
import stat

import openpyxl
from fastapi.testclient import TestClient

from wartung import anlagen, kunden, objekte

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id
from test_import import KUNDEN_KOPF, rwm_datei, xlsx

GUT = xlsx(KUNDEN_KOPF, ["K1", "Kunde 1 GmbH", "Weg 1", None, 90402, "Nürnberg", "DE", None],
           ["K2", "Kunde 2 GmbH", "Weg 2", None, 90403, "Nürnberg", "DE", None])
SCHLECHT = xlsx(KUNDEN_KOPF, ["K1", "Kunde 1 GmbH", None, None, 123, "Nürnberg", "DE", None])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def hochladen(c, inhalt, art="kunden", name="kunden.xlsx", **felder):
    t = csrf_aus(c.get("/verwaltung/import").text)
    return c.post("/verwaltung/import/pruefen", data={"art": art, "csrf_token": t, **felder},
                  files={"datei": (name, inhalt, XLSX)})


def merkmal_aus(html):
    return re.search(r'name="merkmal" value="([^"]+)"', html).group(1)


def test_vorschau_dann_uebernehmen(umgebung, tmp_path):
    c, con = umgebung
    anmelden(c)
    r = hochladen(c, GUT)
    assert r.status_code == 200 and "Vorschau: Kunden" in r.text and "2 Einträge übernehmen" in r.text
    assert con.execute("SELECT COUNT(*) FROM kunde").fetchone()[0] == 0  # Vorschau speichert nichts
    ordner = tmp_path / "import"
    dateien = list(ordner.glob("*.xlsx"))
    assert len(dateien) == 1
    assert stat.S_IMODE(ordner.stat().st_mode) == 0o700 and stat.S_IMODE(dateien[0].stat().st_mode) == 0o600
    merkmal = merkmal_aus(r.text)
    r = c.post("/verwaltung/import/uebernehmen", data={"merkmal": merkmal, "csrf_token": csrf_aus(r.text)})
    assert "Import abgeschlossen" in r.text and "Gespeichert: 2 neue Einträge." in r.text
    assert con.execute("SELECT COUNT(*) FROM kunde").fetchone()[0] == 2
    assert not list(ordner.glob("*.xlsx"))  # Datei nach dem Übernehmen gelöscht
    r = c.post("/verwaltung/import/uebernehmen", data={"merkmal": merkmal, "csrf_token": csrf_aus(r.text)},
               follow_redirects=False)
    assert r.headers["location"] == "/verwaltung/import?hinweis=abgelaufen"  # kein zweites Mal


def test_fehlerhafte_datei_kein_uebernehmen(umgebung):
    c, con = umgebung
    anmelden(c)
    r = hochladen(c, SCHLECHT)
    assert "PLZ: in Deutschland fünf Ziffern." in r.text and "übernehmen</button>" not in r.text
    assert "Es wurde nichts gespeichert" in r.text
    # auch wenn jemand das Formular von Hand abschickt: der Server prüft erneut und speichert nichts
    r = c.post("/verwaltung/import/uebernehmen", data={"merkmal": merkmal_aus_sitzung(c), "csrf_token": csrf_aus(r.text)})
    assert con.execute("SELECT COUNT(*) FROM kunde").fetchone()[0] == 0 and "Es wurde nichts gespeichert" in r.text


def merkmal_aus_sitzung(c):
    """Merkmal der zuletzt hochgeladenen Datei (steht in der Sitzung; der Test liest es aus dem Dateinamen)."""
    return next((c.app.state.daten_ordner / "import").glob("*.xlsx")).stem


def test_fremde_sitzung_kann_nicht_uebernehmen(umgebung):
    c, con = umgebung
    anmelden(c)
    merkmal = merkmal_aus(hochladen(c, GUT).text)
    nutzer_mit_passwort(con, "Bea", "bea@example.org", [rolle_id(con, "buero")])
    c2 = TestClient(c.app)
    anmelden(c2, "bea@example.org")
    t = csrf_aus(c2.get("/verwaltung/import").text)
    r = c2.post("/verwaltung/import/uebernehmen", data={"merkmal": merkmal, "csrf_token": t}, follow_redirects=False)
    assert r.headers["location"] == "/verwaltung/import?hinweis=abgelaufen"
    assert con.execute("SELECT COUNT(*) FROM kunde").fetchone()[0] == 0


def test_keine_excel_datei_und_ohne_datei(umgebung):
    c, _ = umgebung
    anmelden(c)
    r = hochladen(c, b"Nummer;Name\nK1;A", name="kunden.csv")
    assert r.status_code == 400 and "keine lesbare Excel-Datei" in r.text
    t = csrf_aus(c.get("/verwaltung/import").text)
    r = c.post("/verwaltung/import/pruefen", data={"art": "kunden", "csrf_token": t})
    assert r.status_code == 400 and "Bitte eine Excel-Datei auswählen." in r.text


def test_melder_import_ueber_die_anlage(umgebung):
    c, con = umgebung
    anmelden(c)
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "adresse_wie_kunde": "1"}, None)
    aid = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    assert f'/verwaltung/import?art=komponenten&amp;anlage={aid}' in c.get(f"/anlagen/{aid}").text
    seite = c.get(f"/verwaltung/import?art=komponenten&anlage={aid}").text
    assert re.search(rf'<option value="{aid}" selected>', seite)
    r = hochladen(c, rwm_datei(), art="komponenten", anlage_id=aid)
    assert "3 Einträge übernehmen" in r.text and "ANL-0001" in r.text
    r = c.post("/verwaltung/import/uebernehmen", data={"merkmal": merkmal_aus(r.text), "csrf_token": csrf_aus(r.text)})
    assert con.execute("SELECT COUNT(*) FROM komponente").fetchone()[0] == 3
    r = hochladen(c, rwm_datei(), art="komponenten")  # ohne Anlage
    assert r.status_code == 400 and "Anlage wählen" in r.text


def test_vorlage_in_foxtag_reihenfolge(umgebung):
    c, _ = umgebung
    anmelden(c)
    r = c.get("/verwaltung/import/vorlage/komponenten.xlsx")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    kopf = next(openpyxl.load_workbook(io.BytesIO(r.content)).active.iter_rows(values_only=True))
    assert kopf[:5] == ("GRUPPE.NUMMER", "GRUPPE.NAME", "NUMMER*", "SUB-NUMMER", "TYP.NAME*")


def test_rechte(umgebung):
    c, con = umgebung
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    nutzer_mit_passwort(con, "Bea", "bea@example.org", [rolle_id(con, "buero")])
    techniker, buero = TestClient(c.app), TestClient(c.app)
    anmelden(techniker, "tom@example.org")
    anmelden(buero, "bea@example.org")
    assert "keine_berechtigung" in techniker.get("/verwaltung/import", follow_redirects=False).headers["location"]
    assert "keine_berechtigung" in techniker.get("/verwaltung/import/vorlage/kunden.xlsx",
                                                 follow_redirects=False).headers["location"]
    assert buero.get("/verwaltung/import").status_code == 200  # Büro darf importieren
