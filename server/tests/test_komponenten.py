"""Melder (Komponenten): Nummern, mehrere anlegen, Eindeutigkeit, Datumsregeln, Fälligkeiten, Typen, Rechte."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, db, gruppen, komponenten, kunden, objekte, rechte, typen
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort

RWM = anlagenart.holen("rauchwarnmelder")
TYP = {"anlagenart": "rauchwarnmelder", "bezeichnung": "Ei650", "hersteller": "Ei Electronics",
       "kategorie": "komponente", "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}


@pytest.fixture
def wohnung(umgebung):
    """Angemeldeter Admin, Anlage mit Wohnung 43 und einem Melder-Typ."""
    c, con = umgebung
    anmelden(c)
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Musterstraße 12", "adresse_wie_kunde": "1"}, None)
    a = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    g = gruppen.holen(con, gruppen.anlegen(con, RWM, a, {"nummer": "43", "zugang": "frei"}, None))
    return c, con, a, g, typen.anlegen(con, TYP, None)


def melder(con, g, typ, **werte):
    return komponenten.anlegen(con, RWM, g, {"komponententyp_id": typ, **werte}, None)


# ---------- einzeln anlegen ----------

def test_melder_anlegen_mit_nummer_raumart_und_faelligkeiten(wohnung):
    c, con, a, g, typ = wohnung
    seite = c.get(f"/gruppen/{g['id']}/komponenten/neu").text
    assert "Melder anlegen" in seite and "Kinderzimmer" in seite  # Raumvorschläge
    r = c.post(f"/gruppen/{g['id']}/komponenten/neu", data={
        "komponententyp_id": typ, "raum": "Kinderzimmer", "funk_id": "eie-1234", "baujahr": "2020",
        "inbetriebnahme_am": "2020-06-01", "letzte_pruefung_am": "2025-11-03", "csrf_token": csrf_aus(seite)},
        follow_redirects=False)
    assert r.headers["location"] == f"/anlagen/{a}?hinweis=komponente_angelegt#g-{g['id']}"
    m = con.execute("SELECT * FROM komponente").fetchone()
    assert (m["nummer"], m["raumart"], m["funk_id"]) == (1, "kinderzimmer", "EIE-1234")
    assert (m["naechste_pruefung_am"], m["austausch_faellig_am"]) == ("2026-11-03", "2030-01-01")
    detail = c.get(f"/anlagen/{a}").text
    assert "43/1" in detail and "03.11.2026" in detail and "01.01.2030" in detail and "Ei650" in detail


def test_speichern_und_naechsten(wohnung):
    c, con, a, g, typ = wohnung
    t = csrf_aus(c.get(f"/gruppen/{g['id']}/komponenten/neu").text)
    r = c.post(f"/gruppen/{g['id']}/komponenten/neu", data={"komponententyp_id": typ, "weiter": "1", "csrf_token": t},
               follow_redirects=False)
    assert r.headers["location"] == f"/gruppen/{g['id']}/komponenten/neu?hinweis=angelegt"
    assert 'placeholder="2"' in c.get(r.headers["location"]).text


# ---------- mehrere ----------

def test_mehrere_anlegen_fortlaufend(wohnung):
    c, con, a, g, typ = wohnung
    melder(con, g, typ, raum="Flur")
    t = csrf_aus(c.get(f"/gruppen/{g['id']}/komponenten/mehrere").text)
    r = c.post(f"/gruppen/{g['id']}/komponenten/mehrere", data={
        "komponententyp_id": typ, "baujahr": "2024", "raeume": ["Schlafzimmer", "Kinderzimmer"],
        "weitere_raeume": "Hobbyraum, ", "csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303
    zeilen = con.execute("SELECT nummer, raum, raumart, baujahr FROM komponente ORDER BY nummer").fetchall()
    assert [tuple(z) for z in zeilen] == [(1, "Flur", "flur_rettungsweg", None), (2, "Schlafzimmer", "schlafraum", 2024),
                                         (3, "Kinderzimmer", "kinderzimmer", 2024), (4, "Hobbyraum", "sonstiger", 2024)]
    r = c.post(f"/gruppen/{g['id']}/komponenten/mehrere", data={"komponententyp_id": typ, "csrf_token": t})
    assert r.status_code == 400 and "mindestens einen Raum" in r.text
    r = c.post(f"/gruppen/{g['id']}/komponenten/mehrere", data={
        "komponententyp_id": typ, "weitere_raeume": ",".join(f"R{i}" for i in range(21)), "csrf_token": t})
    assert r.status_code == 400 and "Höchstens 20" in r.text
    assert con.execute("SELECT COUNT(*) FROM komponente").fetchone()[0] == 4  # nichts halb angelegt


# ---------- Eindeutigkeit und Regeln ----------

def test_nummer_funk_id_barcode_eindeutig(wohnung):
    c, con, a, g, typ = wohnung
    melder(con, g, typ, nummer="1", funk_id="EIE-1", barcode="PGH-1")
    melder(con, g, typ)  # ohne Funk-ID/Barcode: mehrere leere sind erlaubt
    t = csrf_aus(c.get(f"/gruppen/{g['id']}/komponenten/neu").text)
    r = c.post(f"/gruppen/{g['id']}/komponenten/neu", data={
        "komponententyp_id": typ, "nummer": "1", "funk_id": "eie-1", "barcode": "pgh-1", "csrf_token": t})
    assert r.status_code == 400
    assert "Nr. 1 ist hier schon vergeben." in r.text
    assert "Diese Funk-ID ist schon anderweitig eingetragen." in r.text and "Diese Barcode" in r.text


def test_datumsregeln(wohnung):
    _, con, a, g, typ = wohnung
    morgen = date.fromordinal(date.today().toordinal() + 1).isoformat()
    with pytest.raises(Ungueltig) as e:
        melder(con, g, typ, inbetriebnahme_am=morgen)
    assert e.value.fehler == {"inbetriebnahme_am": "Das Datum liegt in der Zukunft."}
    with pytest.raises(Ungueltig) as e:
        melder(con, g, typ, inbetriebnahme_am="2022-05-01", letzte_pruefung_am="2021-01-01")
    assert "vor der Inbetriebnahme" in e.value.fehler["letzte_pruefung_am"]
    with pytest.raises(Ungueltig) as e:
        melder(con, g, typ, baujahr="2023", inbetriebnahme_am="2022-05-01")
    assert "vor dem Baujahr" in e.value.fehler["inbetriebnahme_am"]
    with pytest.raises(Ungueltig) as e:
        melder(con, g, typ, baujahr="1985")
    assert "baujahr" in e.value.fehler


def test_typ_auswahl_nur_passend_und_aktiv(wohnung):
    c, con, a, g, typ = wohnung
    tuer_typ = db.anlegen(con, "komponententyp", {"anlagenart": "tueren", "bezeichnung": "Tür T30"}, None)
    with pytest.raises(Ungueltig):
        melder(con, g, tuer_typ)  # Typ einer anderen Anlagenart
    m = melder(con, g, typ)
    typen.aendern(con, typ, {**TYP, "aktiv": ""}, None)  # Typ deaktiviert
    with pytest.raises(Ungueltig):
        melder(con, g, typ)  # für neue Melder nicht mehr wählbar …
    seite = c.get(f"/komponenten/{m}").text  # … der vorhandene Melder behält ihn
    assert "Ei650" in seite and "selected" in seite
    assert "keinen aktiven Melder-Typ" in c.get(f"/gruppen/{g['id']}/komponenten/neu").text


# ---------- ändern und löschen ----------

def test_melder_aendern_protokolliert_und_rechnet_neu(wohnung):
    c, con, a, g, typ = wohnung
    m = melder(con, g, typ, raum="Flur", baujahr="2016")
    seite = c.get(f"/komponenten/{m}").text
    assert "leer = nächste freie" not in seite
    r = c.post(f"/komponenten/{m}", data={"nummer": "1", "komponententyp_id": typ, "raum": "Schlafzimmer",
                                         "baujahr": "2021", "csrf_token": csrf_aus(seite)}, follow_redirects=False)
    assert r.status_code == 303
    neu = con.execute("SELECT raumart, austausch_faellig_am FROM komponente WHERE id = ?", (m,)).fetchone()
    assert tuple(neu) == ("schlafraum", "2031-01-01")
    felder = {z["feld"] for z in con.execute(
        "SELECT feld FROM aenderungsprotokoll WHERE datensatz = ? AND aktion = 'aendern'", (m,))}
    assert felder == {"raum", "raumart", "baujahr"}  # berechnete Fälligkeiten nicht im Protokoll
    r = c.post(f"/komponenten/{m}", data={"nummer": "", "komponententyp_id": typ, "csrf_token": csrf_aus(seite)})
    assert r.status_code == 400 and "Nr. ist Pflicht." in r.text


def test_fehleingabe_loeschen(wohnung):
    c, con, a, g, typ = wohnung
    m = melder(con, g, typ)
    t = csrf_aus(c.get(f"/komponenten/{m}").text)
    c.post(f"/komponenten/{m}/loeschen", data={"csrf_token": t})
    assert komponenten.holen(con, m) is None and komponenten.naechste_nummer(con, g["id"]) == 1
    assert c.get(f"/komponenten/{m}", follow_redirects=False).headers["location"] == "/anlagen?hinweis=nicht_gefunden"


# ---------- Rechte ----------

def test_nur_lesen_sieht_melder_aendert_nichts(wohnung):
    c, con, a, g, typ = wohnung
    m = melder(con, g, typ, raum="Flur")
    rid = rechte.rolle_anlegen(con, "Nur lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea", "lea@example.org", [rid])
    c2 = TestClient(c.app)
    anmelden(c2, "lea@example.org")
    seite = c2.get(f"/anlagen/{a}").text
    assert "43/1" in seite and f'href="/komponenten/{m}"' not in seite and "+ mehrere" not in seite
    t = csrf_aus(seite)
    for pfad in (f"/gruppen/{g['id']}/komponenten/neu", f"/gruppen/{g['id']}/komponenten/mehrere",
                 f"/komponenten/{m}", f"/komponenten/{m}/loeschen"):
        r = c2.post(pfad, data={"komponententyp_id": typ, "raeume": "Flur", "csrf_token": t}, follow_redirects=False)
        assert "keine_berechtigung" in r.headers["location"], pfad
    assert con.execute("SELECT COUNT(*) FROM komponente WHERE geloescht = 0").fetchone()[0] == 1
