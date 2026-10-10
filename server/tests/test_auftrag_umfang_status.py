"""Schritt 10: Status „in Planung“, Prüfumfang je Melder, extern beenden, Altprüfungen nachtragen (Migration 012)."""
import re
import shutil
import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from wartung import anlagen, anlagenart, auftraege, db, gruppen, komponenten, kunden, objekte, typen
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

RWM = anlagenart.holen("rauchwarnmelder")
HEUTE = date.today()
MORGEN = (HEUTE + timedelta(days=1)).isoformat()
VOR_EINEM_JAHR = (HEUTE - timedelta(days=365)).isoformat()
VOR_ZWEI_JAHREN = (HEUTE - timedelta(days=730)).isoformat()
ZUKUNFT = (HEUTE + timedelta(days=3)).isoformat()


@pytest.fixture
def welt(umgebung):
    c, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "adresse_wie_kunde": "1"}, None)
    a = anlagen.holen(con, anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None))
    g1 = gruppen.anlegen(con, RWM, a["id"], {"nummer": "1", "zugang": "frei"}, None)
    g2 = gruppen.anlegen(con, RWM, a["id"], {"nummer": "2", "zugang": "frei"}, None)
    typ = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "T", "kategorie": "komponente",
                              "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)

    def melder(gruppe, nummer, **form):
        return komponenten.anlegen(con, RWM, gruppen.holen(con, gruppe),
                                   {"nummer": str(nummer), "komponententyp_id": typ, "baujahr": "2022", **form}, None)
    m1, m2, m3 = melder(g1, 1), melder(g1, 2), melder(g2, 1)
    tom = nutzer_mit_passwort(con, "Tom Techniker", "tom@example.org", [rolle_id(con, "techniker")])
    bea = nutzer_mit_passwort(con, "Bea Büro", "bea@example.org", [rolle_id(con, "buero")])
    return {"c": c, "con": con, "anlage": a, "g1": g1, "g2": g2, "m1": m1, "m2": m2, "m3": m3, "tom": tom,
            "bea": bea, "melder": melder}


def planen(w, **form):
    return auftraege.anlegen(w["con"], w["anlage"], {"auftragsart": "wartung", "datum": MORGEN, **form}, w["bea"])


def letzte(w, m):
    return komponenten.holen(w["con"], m)["letzte_pruefung_am"]


# ---------- Migration ----------

def test_migration_012_erhaelt_auftraege(tmp_path):
    alt = tmp_path / "alt"
    alt.mkdir()
    for datei in db.MIGRATIONEN.glob("*.sql"):
        if not datei.name.startswith("012"):
            shutil.copy(datei, alt)
    voll = db.MIGRATIONEN
    db.MIGRATIONEN = alt
    try:
        con = db.verbinden(tmp_path / "t.db")
        db.migrieren(con)
    finally:
        db.MIGRATIONEN = voll

    def einfuegen(tabelle, **werte):
        werte.setdefault("erstellt_am", "2026-01-01T00:00:00")
        werte["id"] = db.neue_id()
        con.execute(f"INSERT INTO {tabelle} ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                    list(werte.values()))
        return werte["id"]
    k = einfuegen("kunde", nummer="K1", name="A")
    o = einfuegen("objekt", kunde_id=k, nummer="O1", bezeichnung="x", adresse_wie_kunde=1)
    a = einfuegen("anlage", objekt_id=o, nummer="A1", anlagenart="rauchwarnmelder", verfahren="A")
    u1 = einfuegen("auftrag", anlage_id=a, nummer="A-1001", auftragsart="wartung", datum="2026-11-01",
                   status="aktiv", umfang="ganze_anlage")
    u2 = einfuegen("auftrag", anlage_id=a, nummer="A-1002", auftragsart="wartung", datum="2026-11-02",
                   status="geplant", umfang="auswahl", geloescht=1)
    nr = con.execute("SELECT nr FROM abgleich_zaehler").fetchone()[0]

    assert db.migrieren(con) == ["012_auftrag_umfang_status.sql"]

    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    z = {r["id"]: r for r in con.execute("SELECT * FROM auftrag")}
    assert (z[u1]["status"], z[u1]["umfang"], z[u1]["extern"]) == ("aktiv", "ganze_anlage", 0)
    assert (z[u2]["umfang"], z[u2]["geloescht"]) == ("auswahl", 1)
    assert con.execute("SELECT nr FROM abgleich_zaehler").fetchone()[0] >= nr
    # neue Werte erlaubt, Unsinn nicht; Löschschutz und Abgleichnummer arbeiten weiter
    con.execute("UPDATE auftrag SET status = 'in_planung', umfang = 'melder', extern = 1 WHERE id = ?", (u1,))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE auftrag SET status = 'quatsch' WHERE id = ?", (u1,))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE auftrag SET extern = 2 WHERE id = ?", (u1,))
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM auftrag WHERE id = ?", (u1,))
    assert con.execute("SELECT abgleich_nr FROM auftrag WHERE id = ?", (u1,)).fetchone()[0] > nr


# ---------- Status „in Planung“ ----------

def test_in_planung_anlegen_und_uebergaenge(welt):
    con = welt["con"]
    aid = planen(welt, in_planung="1", techniker=[welt["tom"]])
    assert auftraege.holen(con, aid)["status"] == "in_planung"
    assert auftraege.holen(con, planen(welt))["status"] == "geplant"
    # nicht direkt starten, nicht direkt abschließen
    for neu in ("aktiv", "abgeschlossen"):
        with pytest.raises(Ungueltig):
            auftraege.status_setzen(con, aid, neu, welt["bea"])
    auftraege.status_setzen(con, aid, "geplant", welt["bea"])
    # zurück nur mit Grund
    with pytest.raises(Ungueltig) as e:
        auftraege.status_setzen(con, aid, "in_planung", welt["bea"])
    assert "grund" in e.value.fehler
    auftraege.status_setzen(con, aid, "in_planung", welt["bea"], grund="Termin unklar")
    auftraege.status_setzen(con, aid, "storniert", welt["bea"], grund="Kunde sagt ab")
    assert [v["status_neu"] for v in auftraege.verlauf(con, aid)] == ["in_planung", "geplant", "in_planung",
                                                                       "storniert"]


def test_in_planung_unsichtbar_fuer_techniker_sichtbar_im_buero(welt):
    con = welt["con"]
    aid = planen(welt, in_planung="1", techniker=[welt["tom"]])
    sicht = auftraege.sicht({auftraege.TECHNIKER_RECHT}, welt["tom"])
    assert not auftraege.darf_sehen(con, aid, {auftraege.TECHNIKER_RECHT}, welt["tom"])
    assert aid not in [u["id"] for u in auftraege.liste(con, eingeschraenkt=sicht)]
    assert aid in [u["id"] for u in auftraege.liste(con)]
    auftraege.status_setzen(con, aid, "geplant", welt["bea"])
    assert auftraege.darf_sehen(con, aid, {auftraege.TECHNIKER_RECHT}, welt["tom"])


def test_in_planung_sperrt_anlage_und_wohnung_loeschen(welt):
    con = welt["con"]
    planen(welt, in_planung="1", umfang="auswahl", gruppen=[welt["g2"]])
    with pytest.raises(Ungueltig):
        gruppen.loeschen(con, RWM, welt["g2"], None)
    with pytest.raises(Ungueltig):
        anlagen.loeschen(con, welt["anlage"]["id"], None)


# ---------- Umfang „melder“ ----------

def test_umfang_melder_anlegen_und_anzeigen(welt):
    con = welt["con"]
    aid = planen(welt, umfang="melder", komponenten=[welt["m1"], welt["m3"]])
    u = auftraege.holen(con, aid)
    assert u["umfang"] == "melder"
    assert {c["id"] for c in auftraege.komponenten_im_umfang(con, aid)} == {welt["m1"], welt["m3"]}
    assert auftraege.gruppen(con, aid) == []


def test_umfang_melder_pruefregeln(welt):
    con = welt["con"]
    with pytest.raises(Ungueltig) as e:
        planen(welt, umfang="melder")
    assert "umfang" in e.value.fehler
    with pytest.raises(Ungueltig) as e:
        planen(welt, umfang="melder", komponenten=["gibt-es-nicht"])
    assert "umfang" in e.value.fehler
    # Melder einer fremden Anlage
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Anderer"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus 2", "adresse_wie_kunde": "1"}, None)
    a2 = anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)
    g = gruppen.holen(con, gruppen.anlegen(con, RWM, a2, {"nummer": "1", "zugang": "frei"}, None))
    fremd = komponenten.anlegen(con, RWM, g, {"nummer": "1", "komponententyp_id": con.execute(
        "SELECT id FROM komponententyp LIMIT 1").fetchone()[0], "baujahr": "2022"}, None)
    with pytest.raises(Ungueltig):
        planen(welt, umfang="melder", komponenten=[fremd])
    assert con.execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 0


def test_umfang_melder_aendern_und_sperre(welt):
    con = welt["con"]
    aid = planen(welt, umfang="melder", komponenten=[welt["m1"]], in_planung="1")
    auftraege.aendern(con, aid, {"auftragsart": "wartung", "datum": MORGEN, "umfang": "melder",
                                 "komponenten": [welt["m2"], welt["m3"]]}, welt["bea"])
    assert {c["id"] for c in auftraege.komponenten_im_umfang(con, aid)} == {welt["m2"], welt["m3"]}
    auftraege.aendern(con, aid, {"auftragsart": "wartung", "datum": MORGEN, "umfang": "ganze_anlage"}, welt["bea"])
    assert auftraege.komponenten_im_umfang(con, aid) == []
    auftraege.status_setzen(con, aid, "geplant", welt["bea"])
    auftraege.status_setzen(con, aid, "aktiv", welt["bea"])
    with pytest.raises(Ungueltig):
        auftraege.aendern(con, aid, {"auftragsart": "wartung", "datum": MORGEN, "umfang": "melder",
                                     "komponenten": [welt["m1"]]}, welt["bea"])


# ---------- Extern beenden ----------

def test_extern_beenden_setzt_letzte_pruefung(welt):
    con = welt["con"]
    aid = planen(welt, umfang="melder", komponenten=[welt["m1"], welt["m2"]])
    assert auftraege.extern_beenden(con, aid, VOR_EINEM_JAHR, welt["bea"], "Altbestand") == (2, 0)
    u = auftraege.holen(con, aid)
    assert (u["status"], u["extern"], u["abgeschlossen_am"]) == ("abgeschlossen", 1, VOR_EINEM_JAHR)
    assert letzte(welt, welt["m1"]) == letzte(welt, welt["m2"]) == VOR_EINEM_JAHR
    assert letzte(welt, welt["m3"]) is None  # außerhalb des Umfangs
    assert komponenten.holen(con, welt["m1"])["naechste_pruefung_am"]  # Fälligkeit nachgerechnet
    v = auftraege.verlauf(con, aid)[-1]
    assert "Extern beendet" in v["grund"] and "Altbestand" in v["grund"] and v["status_neu"] == "abgeschlossen"


def test_extern_beenden_ueberspringt_neuere_pruefung_und_inbetriebnahme(welt):
    con = welt["con"]
    db.aendern(con, "komponente", welt["m1"], {"letzte_pruefung_am": HEUTE.isoformat()}, None)
    db.aendern(con, "komponente", welt["m2"], {"letzte_pruefung_am": VOR_ZWEI_JAHREN}, None)
    db.aendern(con, "komponente", welt["m3"], {"inbetriebnahme_am": HEUTE.isoformat()}, None)
    aid = planen(welt)
    assert auftraege.extern_beenden(con, aid, VOR_EINEM_JAHR, welt["bea"]) == (1, 2)
    assert letzte(welt, welt["m1"]) == HEUTE.isoformat()
    assert letzte(welt, welt["m2"]) == VOR_EINEM_JAHR
    assert letzte(welt, welt["m3"]) is None


def test_extern_beenden_fehler_aendern_nichts(welt):
    con = welt["con"]
    aid = planen(welt)
    for datum in ("", "31.02.2026", ZUKUNFT):
        with pytest.raises(Ungueltig) as e:
            auftraege.extern_beenden(con, aid, datum, welt["bea"])
        assert "datum" in e.value.fehler
    assert auftraege.holen(con, aid)["status"] == "geplant" and letzte(welt, welt["m1"]) is None
    # nur offene Aufträge
    auftraege.status_setzen(con, aid, "abgeschlossen", welt["bea"])
    with pytest.raises(Ungueltig):
        auftraege.extern_beenden(con, aid, VOR_EINEM_JAHR, welt["bea"])
    with pytest.raises(Ungueltig):
        auftraege.extern_beenden(con, "gibt-es-nicht", VOR_EINEM_JAHR, welt["bea"])


def test_extern_beenden_aus_in_planung_und_aktiv(welt):
    con = welt["con"]
    a1 = planen(welt, in_planung="1")
    a2 = planen(welt)
    auftraege.status_setzen(con, a2, "aktiv", welt["bea"])
    assert auftraege.extern_beenden(con, a1, VOR_EINEM_JAHR, welt["bea"])[0] == 3
    assert auftraege.extern_beenden(con, a2, VOR_EINEM_JAHR, welt["bea"]) == (0, 3)  # gleiches Datum: nicht neuer


def test_extern_beendeter_auftrag_bleibt_beendet(welt):
    con = welt["con"]
    aid = planen(welt)
    auftraege.extern_beenden(con, aid, VOR_EINEM_JAHR, welt["bea"])
    with pytest.raises(Ungueltig, match="extern"):
        auftraege.status_setzen(con, aid, "aktiv", welt["bea"], grund="Irrtum")
    # normal abgeschlossene Aufträge lassen sich weiterhin wieder öffnen
    b = planen(welt)
    auftraege.status_setzen(con, b, "abgeschlossen", welt["bea"])
    auftraege.status_setzen(con, b, "aktiv", welt["bea"], grund="Nacharbeit")
    assert auftraege.holen(con, b)["status"] == "aktiv"


# ---------- Altprüfung nachtragen ----------

def test_altpruefung_nachtragen(welt):
    con = welt["con"]
    aid, gesetzt, uebersprungen = auftraege.altpruefung_nachtragen(
        con, welt["anlage"], {"auftragsart": "wartung", "datum": VOR_EINEM_JAHR, "bemerkung": "aus Papierakte"},
        welt["bea"])
    u = auftraege.holen(con, aid)
    assert (gesetzt, uebersprungen) == (3, 0)
    assert (u["status"], u["extern"], u["datum"], u["abgeschlossen_am"]) == \
        ("abgeschlossen", 1, VOR_EINEM_JAHR, VOR_EINEM_JAHR)
    assert all(letzte(welt, m) == VOR_EINEM_JAHR for m in (welt["m1"], welt["m2"], welt["m3"]))
    assert [v["ereignis"] for v in auftraege.verlauf(con, aid)][0] == "angelegt"


def test_altpruefung_fehler_rollt_alles_zurueck(welt):
    con = welt["con"]
    for datum in (ZUKUNFT, "", "kaputt"):
        with pytest.raises(Ungueltig):
            auftraege.altpruefung_nachtragen(con, welt["anlage"], {"auftragsart": "wartung", "datum": datum},
                                             welt["bea"])
    with pytest.raises(Ungueltig):
        auftraege.altpruefung_nachtragen(con, welt["anlage"], {"auftragsart": "wartung", "datum": VOR_EINEM_JAHR,
                                                               "umfang": "melder"}, welt["bea"])
    assert con.execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 0
    assert letzte(welt, welt["m1"]) is None


# ---------- Web ----------

def id_aus(antwort):
    return re.search(r"/auftraege/([0-9a-f-]{36})", antwort.headers["location"]).group(1)


def test_web_umfang_melder_und_in_planung(welt):
    c, con = welt["c"], welt["con"]
    anmelden(c)
    aid_anlage = welt["anlage"]["id"]
    seite = c.get(f"/anlagen/{aid_anlage}/auftraege/neu")
    assert "Ausgewählte Melder" in seite.text and "in_planung" in seite.text
    r = c.post(f"/anlagen/{aid_anlage}/auftraege/neu", data={
        "csrf_token": csrf_aus(seite.text), "auftragsart": "wartung", "datum": MORGEN, "umfang": "melder",
        "komponenten": [welt["m1"], welt["m3"]], "in_planung": "1"}, follow_redirects=False)
    aid = id_aus(r)
    assert auftraege.holen(con, aid)["status"] == "in_planung"
    detail = c.get(f"/auftraege/{aid}")
    assert "In Planung" in detail.text and "Extern beenden" in detail.text and "Planung abschließen" in detail.text
    # Fehler: ohne Melder
    r = c.post(f"/anlagen/{aid_anlage}/auftraege/neu", data={
        "csrf_token": csrf_aus(seite.text), "auftragsart": "wartung", "datum": MORGEN, "umfang": "melder"})
    assert r.status_code == 400


def test_web_extern_beenden_und_altpruefung(welt):
    c, con = welt["c"], welt["con"]
    anmelden(c)
    aid = planen(welt)
    detail = c.get(f"/auftraege/{aid}")
    r = c.post(f"/auftraege/{aid}/extern-beenden", data={"csrf_token": csrf_aus(detail.text), "datum": ZUKUNFT},
               follow_redirects=False)
    assert r.status_code == 400 and auftraege.holen(con, aid)["status"] == "geplant"
    r = c.post(f"/auftraege/{aid}/extern-beenden", data={"csrf_token": csrf_aus(detail.text),
                                                         "datum": VOR_EINEM_JAHR}, follow_redirects=False)
    assert "hinweis=extern" in r.headers["location"] and "gesetzt=3" in r.headers["location"]
    assert "extern" in c.get(r.headers["location"]).text.lower()
    # Altprüfung über die Anlage
    anlage_seite = c.get(f"/anlagen/{welt['anlage']['id']}")
    assert "Altprüfung nachtragen" in anlage_seite.text
    form = c.get(f"/anlagen/{welt['anlage']['id']}/altpruefung")
    assert form.status_code == 200
    r = c.post(f"/anlagen/{welt['anlage']['id']}/altpruefung", data={
        "csrf_token": csrf_aus(form.text), "auftragsart": "wartung", "datum": VOR_ZWEI_JAHREN},
        follow_redirects=False)
    assert r.status_code == 303 and "hinweis=extern" in r.headers["location"]
    r = c.post(f"/anlagen/{welt['anlage']['id']}/altpruefung", data={
        "csrf_token": csrf_aus(form.text), "auftragsart": "wartung", "datum": ZUKUNFT})
    assert r.status_code == 400


def test_web_rechte_extern(welt):
    c, con = welt["c"], welt["con"]
    aid = planen(welt, techniker=[welt["tom"]])
    tom = TestClient(c.app)
    anmelden(tom, "tom@example.org")
    seite = tom.get(f"/auftraege/{aid}")
    assert "Extern beenden" not in seite.text
    r = tom.post(f"/auftraege/{aid}/extern-beenden", data={"csrf_token": csrf_aus(seite.text),
                                                           "datum": VOR_EINEM_JAHR}, follow_redirects=False)
    assert "keine_berechtigung" in r.headers["location"]
    assert tom.get(f"/anlagen/{welt['anlage']['id']}/altpruefung", follow_redirects=False).status_code == 303
    assert auftraege.holen(con, aid)["status"] == "geplant"
