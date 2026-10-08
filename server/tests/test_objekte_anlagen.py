"""Objekte und Anlagen: Anschrift, Nummern, Kunde wechseln, Löschregeln, Anlagenart, Ansprechpartner, Rechte."""
import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, db, kunden, objekte, rechte
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort

KUNDE = {"art": "hausverwaltung", "name": "Muster-Hausverwaltung", "strasse": "Hauptstr. 1", "plz": "90402",
         "ort": "Nürnberg"}
OBJEKT = {"bezeichnung": "Musterstraße 12", "strasse": "Musterstraße 12", "plz": "90403", "ort": "Nürnberg"}


@pytest.fixture
def bestand(umgebung):
    """Angemeldeter Admin, ein Kunde mit Objekt und Rauchwarnmelder-Anlage."""
    c, con = umgebung
    anmelden(c)
    kid = kunden.anlegen(con, KUNDE, None)
    oid = objekte.anlegen(con, kid, OBJEKT, None)
    aid = anlagen.anlegen(con, oid, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    return c, con, kid, oid, aid


def id_aus(antwort):
    return antwort.headers["location"].split("/")[2].split("?")[0]


# ---------- Objekte ----------

def test_objekt_anlegen_mit_nummer_und_eigener_anschrift(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunden.anlegen(con, KUNDE, None)
    seite = c.get(f"/kunden/{kid}/objekte/neu").text
    assert "O-0001" in seite and "Hauptstr. 1" in seite  # Nummernvorschau, Anschrift des Kunden als Hilfe
    r = c.post(f"/kunden/{kid}/objekte/neu", data={**OBJEKT, "csrf_token": csrf_aus(seite)}, follow_redirects=False)
    oid = id_aus(r)
    o = objekte.holen(con, oid)
    assert o["nummer"] == "O-0001" and o["adr_strasse"] == "Musterstraße 12" and o["kunde_nummer"] == "K0001"
    assert "Musterstraße 12" in c.get(f"/kunden/{kid}").text  # erscheint beim Kunden


def test_objekt_anschrift_pflicht_ausser_wie_kunde(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunden.anlegen(con, KUNDE, None)
    t = csrf_aus(c.get(f"/kunden/{kid}/objekte/neu").text)
    r = c.post(f"/kunden/{kid}/objekte/neu", data={"bezeichnung": "Ohne Anschrift", "csrf_token": t})
    assert r.status_code == 400 and "Straße ist Pflicht." in r.text and "Ort ist Pflicht." in r.text
    r = c.post(f"/kunden/{kid}/objekte/neu", data={"bezeichnung": "Haus Eigentümer", "adresse_wie_kunde": "1",
                                                   "csrf_token": t}, follow_redirects=False)
    o = objekte.holen(con, id_aus(r))
    assert (o["adr_strasse"], o["adr_plz"], o["adr_ort"]) == ("Hauptstr. 1", "90402", "Nürnberg")
    # Kundenanschrift ändert sich -> Objekt zeigt automatisch die neue
    db.aendern(con, "kunde", kid, {"ort": "Fürth", "plz": "90762"}, None)
    assert objekte.holen(con, o["id"])["adr_ort"] == "Fürth"


def test_objekt_einem_anderen_kunden_zuordnen(bestand):
    c, con, kid, oid, aid = bestand
    neu = kunden.anlegen(con, {**KUNDE, "name": "Neue Verwaltung"}, None)
    seite = c.get(f"/objekte/{oid}/bearbeiten").text
    assert "Neue Verwaltung" in seite  # Kundenauswahl
    r = c.post(f"/objekte/{oid}/bearbeiten", data={**OBJEKT, "nummer": "O-0001", "kunde_id": neu,
                                                    "csrf_token": csrf_aus(seite)}, follow_redirects=False)
    assert r.status_code == 303
    assert objekte.holen(con, oid)["kunde_id"] == neu
    assert anlagen.holen(con, aid)["kunde_id"] == neu  # Anlage zieht mit
    protokoll = con.execute("SELECT alt, neu FROM aenderungsprotokoll WHERE tabelle = 'objekt' "
                            "AND feld = 'kunde_id' AND aktion = 'aendern'").fetchone()
    assert tuple(protokoll) == (kid, neu)
    r = c.post(f"/objekte/{oid}/bearbeiten", data={**OBJEKT, "nummer": "O-0001", "kunde_id": "gibtsnicht",
                                                    "csrf_token": csrf_aus(seite)})
    assert r.status_code == 400 and "ungültige Auswahl" in r.text


def test_objekt_nur_ohne_anlagen_loeschbar(bestand):
    c, con, kid, oid, aid = bestand
    t = csrf_aus(c.get(f"/objekte/{oid}").text)
    r = c.post(f"/objekte/{oid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert "hat_anlagen" in r.headers["location"] and objekte.holen(con, oid) is not None
    anlagen.loeschen(con, aid, None)
    r = c.post(f"/objekte/{oid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert r.headers["location"] == f"/kunden/{kid}?hinweis=objekt_geloescht#objekte"
    assert objekte.holen(con, oid) is None
    assert c.get(f"/objekte/{oid}", follow_redirects=False).headers["location"] == "/kunden?hinweis=nicht_gefunden"


# ---------- Anlagen ----------

def test_anlage_anlegen_ueber_objekt(umgebung):
    c, con = umgebung
    anmelden(c)
    kid = kunden.anlegen(con, KUNDE, None)
    oid = objekte.anlegen(con, kid, OBJEKT, None)
    seite = c.get(f"/objekte/{oid}/anlagen/neu").text
    assert "ANL-0001" in seite and "Rauchwarnmelder" in seite
    t = csrf_aus(seite)
    r = c.post(f"/objekte/{oid}/anlagen/neu", data={"anlagenart": "tueren", "verfahren": "A", "csrf_token": t})
    assert r.status_code == 400 and "ungültige Auswahl" in r.text  # Türen gibt es noch nicht
    r = c.post(f"/objekte/{oid}/anlagen/neu", data={"anlagenart": "rauchwarnmelder", "verfahren": "B",
                                                     "bezeichnung": "Haus A", "csrf_token": t}, follow_redirects=False)
    a = anlagen.holen(con, id_aus(r))
    assert (a["nummer"], a["verfahren"], a["objekt_id"], a["kunde_id"]) == ("ANL-0001", "B", oid, kid)
    detail = c.get(f"/anlagen/{a['id']}").text
    assert "Rauchwarnmelder" in detail and "B – teilweise Ferninspektion" in detail and "Musterstraße 12" in detail


def test_anlagenart_ist_nicht_aenderbar(bestand):
    c, con, kid, oid, aid = bestand
    seite = c.get(f"/anlagen/{aid}/bearbeiten").text
    assert 'name="anlagenart"' not in seite and "nicht mehr änderbar" in seite
    r = c.post(f"/anlagen/{aid}/bearbeiten", data={"nummer": "ANL-0001", "verfahren": "C", "anlagenart": "tueren",
                                                    "passiv": "1", "csrf_token": csrf_aus(seite)},
               follow_redirects=False)
    assert r.status_code == 303
    a = anlagen.holen(con, aid)
    assert (a["anlagenart"], a["verfahren"], a["passiv"]) == ("rauchwarnmelder", "C", 1)


def test_anlage_nur_ohne_wohnungen_loeschbar(bestand):
    c, con, kid, oid, aid = bestand
    gid = db.anlegen(con, "gruppe", {"anlage_id": aid, "nummer": 1}, None)
    t = csrf_aus(c.get(f"/anlagen/{aid}").text)
    r = c.post(f"/anlagen/{aid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert "hat_wohnungen" in r.headers["location"]
    db.aendern(con, "gruppe", gid, {"geloescht": 1}, None)
    r = c.post(f"/anlagen/{aid}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert r.headers["location"] == f"/objekte/{oid}?hinweis=anlage_geloescht"
    assert anlagen.holen(con, aid) is None


def test_anlagenliste_suche_und_zaehler(bestand):
    c, con, kid, oid, aid = bestand
    k2 = kunden.anlegen(con, {**KUNDE, "name": "Andere GmbH"}, None)
    o2 = objekte.anlegen(con, k2, {**OBJEKT, "bezeichnung": "Gartenweg 5", "strasse": "Gartenweg 5",
                                   "plz": "91052", "ort": "Erlangen"}, None)
    a2 = anlagen.anlegen(con, o2, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    g = db.anlegen(con, "gruppe", {"anlage_id": a2, "nummer": 1}, None)
    typ = db.anlegen(con, "komponententyp", {"anlagenart": "rauchwarnmelder", "bezeichnung": "Testmelder"}, None)
    for nr in (1, 2):
        db.anlegen(con, "komponente", {"anlage_id": a2, "gruppe_id": g, "nummer": nr, "komponententyp_id": typ}, None)
    assert [(a["nummer"], a["wohnungen"], a["komponenten"]) for a in anlagen.liste(con, "erlangen")] == \
        [("ANL-0002", 1, 2)]
    seite = c.get("/anlagen?q=gartenweg").text
    assert "ANL-0002" in seite and "ANL-0001" not in seite and "Andere GmbH" in seite
    assert "ANL-0001" in c.get("/anlagen?q=muster").text


# ---------- Ansprechpartner ----------

def test_ansprechpartner_zuordnen_und_entfernen(bestand):
    c, con, kid, oid, aid = bestand
    kt = kunden.kontakt_anlegen(con, kid, {"name": "Hans Hausmeister", "funktion": "Hausmeister"}, None)
    seite = c.get(f"/anlagen/{aid}").text
    t = csrf_aus(seite)
    assert "Hans Hausmeister" in seite  # zur Auswahl
    for rolle in ("vor_ort", "terminankuendigung"):  # eine Person kann mehrere Rollen haben
        r = c.post(f"/anlagen/{aid}/kontakte", data={"kontakt_id": kt, "rolle": rolle, "csrf_token": t},
                   follow_redirects=False)
        assert r.status_code == 303
    r = c.post(f"/anlagen/{aid}/kontakte", data={"kontakt_id": kt, "rolle": "vor_ort", "csrf_token": t})
    assert r.status_code == 400 and "schon zugeordnet" in r.text
    zuordnungen = anlagen.kontakte(con, aid)
    assert [z["rolle"] for z in zuordnungen] == ["vor_ort", "terminankuendigung"]
    c.post(f"/anlagen/{aid}/kontakte/{zuordnungen[0]['zuordnung_id']}/entfernen", data={"csrf_token": t})
    assert [z["rolle"] for z in anlagen.kontakte(con, aid)] == ["terminankuendigung"]


def test_nur_kontakte_des_eigenen_kunden(bestand):
    c, con, kid, oid, aid = bestand
    fremd_kunde = kunden.anlegen(con, {**KUNDE, "name": "Fremd"}, None)
    fremd = kunden.kontakt_anlegen(con, fremd_kunde, {"name": "Fremde Person"}, None)
    t = csrf_aus(c.get(f"/anlagen/{aid}").text)
    r = c.post(f"/anlagen/{aid}/kontakte", data={"kontakt_id": fremd, "rolle": "vor_ort", "csrf_token": t})
    assert r.status_code == 400 and "Kontakt dieses Kunden" in r.text
    with pytest.raises(Ungueltig):
        anlagen.kontakt_zuordnen(con, aid, fremd, "erfunden", None)


def test_geloeschter_kontakt_verschwindet_aus_anlage(bestand):
    _, con, kid, _, aid = bestand
    kt = kunden.kontakt_anlegen(con, kid, {"name": "Weg Damit"}, None)
    anlagen.kontakt_zuordnen(con, aid, kt, "berichtsempfaenger", None)
    kunden.kontakt_loeschen(con, kt, None)
    assert anlagen.kontakte(con, aid) == []


def test_fremde_zuordnung_kann_nicht_ueber_andere_anlage_entfernt_werden(bestand):
    c, con, kid, oid, aid = bestand
    a2 = anlagen.anlegen(con, oid, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    kt = kunden.kontakt_anlegen(con, kid, {"name": "Hans"}, None)
    zid = anlagen.kontakt_zuordnen(con, aid, kt, "vor_ort", None)
    t = csrf_aus(c.get(f"/anlagen/{a2}").text)
    r = c.post(f"/anlagen/{a2}/kontakte/{zid}/entfernen", data={"csrf_token": t}, follow_redirects=False)
    assert "nicht_gefunden" in r.headers["location"]
    assert len(anlagen.kontakte(con, aid)) == 1


# ---------- Rechte ----------

def test_nur_lesen_sieht_anlagen_aber_aendert_nichts(bestand):
    c, con, kid, oid, aid = bestand
    rid = rechte.rolle_anlegen(con, "Nur lesen", "", ["web.zugang", "stammdaten.lesen"], None)
    nutzer_mit_passwort(con, "Lea", "lea@example.org", [rid])
    c2 = TestClient(c.app)
    anmelden(c2, "lea@example.org")
    assert 'href="/anlagen"' in c2.get("/").text
    seite = c2.get(f"/anlagen/{aid}").text
    assert "ANL-0001" in seite and "Bearbeiten" not in seite and "Zuordnen" not in seite
    t = csrf_aus(seite)
    for pfad in (f"/kunden/{kid}/objekte/neu", f"/objekte/{oid}/bearbeiten", f"/objekte/{oid}/loeschen",
                 f"/objekte/{oid}/anlagen/neu", f"/anlagen/{aid}/bearbeiten", f"/anlagen/{aid}/loeschen",
                 f"/anlagen/{aid}/kontakte"):
        r = c2.post(pfad, data={**OBJEKT, "csrf_token": t}, follow_redirects=False)
        assert "keine_berechtigung" in r.headers["location"], pfad
    assert anlagen.holen(con, aid) is not None and len(objekte.liste_fuer_kunde(con, kid)) == 1


def test_nummer_beim_bearbeiten_pflicht_ohne_automatik_hinweis(bestand):
    c, con, kid, oid, aid = bestand
    for pfad, daten in ((f"/kunden/{kid}/bearbeiten", KUNDE), (f"/objekte/{oid}/bearbeiten", {**OBJEKT, "kunde_id": kid}),
                        (f"/anlagen/{aid}/bearbeiten", {"verfahren": "A"})):
        seite = c.get(pfad).text
        assert "leer lassen = automatisch" not in seite, pfad
        r = c.post(pfad, data={**daten, "nummer": "", "csrf_token": csrf_aus(seite)})
        assert r.status_code == 400 and "nummer ist Pflicht." in r.text, pfad
    assert "leer lassen = automatisch" in c.get(f"/kunden/{kid}/objekte/neu").text  # beim Anlegen schon
