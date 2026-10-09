"""Aufträge (Fachlogik): planen, Prüfregeln, ändern/verschieben, Statusübergänge, Verlauf nur anhängen, Löschregeln."""
import sqlite3
from datetime import date, timedelta

import pytest

from wartung import anlagen, anlagenart, auftraege, gruppen, komponenten, kunden, objekte, rechte, typen
from wartung.felder import Feld, Ungueltig, einlesen

from hilfen import nutzer_mit_passwort, rolle_id

RWM = anlagenart.holen("rauchwarnmelder")
MORGEN = (date.today() + timedelta(days=1)).isoformat()
NAECHSTE_WOCHE = (date.today() + timedelta(days=7)).isoformat()


@pytest.fixture
def welt(umgebung):
    """Anlage mit zwei Wohnungen, ein Techniker, eine Büro-Kraft, ein Admin (aus umgebung)."""
    _, con = umgebung
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "adresse_wie_kunde": "1"}, None)
    a = anlagen.holen(con, anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None))
    g1 = gruppen.anlegen(con, RWM, a["id"], {"nummer": "1", "zugang": "frei"}, None)
    g2 = gruppen.anlegen(con, RWM, a["id"], {"nummer": "2", "zugang": "frei"}, None)
    tom = nutzer_mit_passwort(con, "Tom Techniker", "tom@example.org", [rolle_id(con, "techniker")])
    bea = nutzer_mit_passwort(con, "Bea Büro", "bea@example.org", [rolle_id(con, "buero")])
    return {"con": con, "anlage": a, "g1": g1, "g2": g2, "tom": tom, "bea": bea}


def planen(w, **form):
    return auftraege.anlegen(w["con"], w["anlage"], {"auftragsart": "wartung", "datum": MORGEN, **form}, w["bea"])


# ---------- Felder ----------

def test_feldarten_datum_und_uhrzeit():
    felder = (Feld("d", "Datum", "datum"), Feld("u", "Uhrzeit", "uhrzeit"))
    assert einlesen(felder, {"d": "2026-10-12", "u": "08:45"}) == ({"d": "2026-10-12", "u": "08:45"}, {})
    assert einlesen(felder, {"d": "", "u": ""})[0] == {"d": None, "u": None}
    _, fehler = einlesen(felder, {"d": "2026-02-30", "u": "24:00"})
    assert fehler == {"d": "Datum: Datum bitte als JJJJ-MM-TT.", "u": "Uhrzeit: Uhrzeit bitte als HH:MM."}
    assert einlesen(felder, {"u": "8:45"})[1] == {"u": "Uhrzeit: Uhrzeit bitte als HH:MM."}


# ---------- Planen ----------

def test_planen(welt):
    con = welt["con"]
    aid = planen(welt, uhrzeit="08:45", dauer_minuten="90", hinweise="Schlüssel beim Hausmeister",
                 techniker=[welt["tom"]])
    u = auftraege.holen(con, aid)
    assert (u["nummer"], u["status"], u["auftragsart"], u["datum"], u["uhrzeit"], u["dauer_minuten"], u["umfang"]) == \
        ("A-1001", "geplant", "wartung", MORGEN, "08:45", 90, "ganze_anlage")
    assert u["erstellt_von"] == welt["bea"] and u["anlage_nummer"] == welt["anlage"]["nummer"]
    assert [t["name"] for t in auftraege.techniker(con, aid)] == ["Tom Techniker"]
    v = auftraege.verlauf(con, aid)
    assert [(x["ereignis"], x["status_neu"], x["termin_neu"], x["nutzer_name"]) for x in v] == \
        [("angelegt", "geplant", f"{MORGEN} 08:45", "Bea Büro")]
    # zweiter Auftrag: nächste Nummer, Pool (ohne Techniker), ganztägig, Auswahl einer Wohnung
    aid2 = planen(welt, umfang="auswahl", gruppen=[welt["g2"]])
    u2 = auftraege.holen(con, aid2)
    assert (u2["nummer"], u2["uhrzeit"], u2["umfang"]) == ("A-1002", None, "auswahl")
    assert auftraege.techniker(con, aid2) == [] and [g["nummer"] for g in auftraege.gruppen(con, aid2)] == [2]
    # neueste zuerst; am selben Tag: mit Uhrzeit vor ganztägig (aufsteigend stehen ganztägige oben)
    assert [x["nummer"] for x in auftraege.fuer_anlage(con, welt["anlage"]["id"])] == ["A-1001", "A-1002"]


def test_planen_pruefregeln(welt):
    con = welt["con"]
    gestern = (date.today() - timedelta(days=1)).isoformat()
    andere = anlagen.anlegen(con, welt["anlage"]["objekt_id"], {"anlagenart": "rauchwarnmelder", "verfahren": "A"},
                             None)
    fremd = gruppen.anlegen(con, RWM, andere, {"nummer": "9", "zugang": "frei"}, None)
    faelle = [
        ({"datum": gestern}, "datum", "Vergangenheit"),
        ({"datum": ""}, "datum", "Pflicht"),
        ({"auftragsart": "reparatur"}, "auftragsart", "ungültige Auswahl"),
        ({"uhrzeit": "25:00"}, "uhrzeit", "HH:MM"),
        ({"dauer_minuten": "5"}, "dauer_minuten", "15 bis 1440"),
        ({"techniker": [welt["bea"]]}, "techniker", "Ungültige Techniker"),   # Büro hat kein App-Recht
        ({"umfang": "auswahl"}, "umfang", "mindestens eine Wohnung"),
        ({"umfang": "auswahl", "gruppen": [fremd]}, "umfang", "Ungültige Wohnung"),
        ({"umfang": "alles"}, "umfang", "Ungültiger Umfang"),
    ]
    for form, feld, text in faelle:
        with pytest.raises(Ungueltig) as e:
            planen(welt, **form)
        assert text in e.value.fehler.get(feld, ""), (form, e.value.fehler)
    planen(welt, nummer="A-7")
    with pytest.raises(Ungueltig, match="schon vergeben"):
        planen(welt, nummer="a-7")
    assert con.execute("SELECT COUNT(*) FROM auftrag").fetchone()[0] == 1  # Fehlversuche speichern nichts
    assert con.execute("SELECT COUNT(*) FROM auftrag_verlauf").fetchone()[0] == 1


def test_passive_anlage_und_techniker_auswahl(welt):
    con = welt["con"]
    anlagen.aendern(con, welt["anlage"]["id"], {**dict(welt["anlage"]), "passiv": "1"}, None)
    with pytest.raises(Ungueltig, match="passiv"):
        planen({**welt, "anlage": anlagen.holen(con, welt["anlage"]["id"])})
    namen = [n for _, n in auftraege.techniker_auswahl(con)]
    assert "Tom Techniker" in namen and "Test Admin" in namen and "Bea Büro" not in namen
    # deaktivierter Techniker: nicht mehr wählbar, aber bei bestehender Zuordnung weiter sichtbar
    con.execute("UPDATE nutzer SET aktiv = 0 WHERE id = ?", (welt["tom"],))
    assert "Tom Techniker" not in [n for _, n in auftraege.techniker_auswahl(con)]
    assert "Tom Techniker" in [n for _, n in auftraege.techniker_auswahl(con, [welt["tom"]])]


# ---------- Ändern / Verschieben ----------

def test_aendern_und_verschieben(welt):
    con = welt["con"]
    aid = planen(welt, uhrzeit="08:00", techniker=[welt["tom"]])
    basis = {"auftragsart": "wartung", "datum": MORGEN, "uhrzeit": "08:00", "techniker": [welt["tom"]]}
    assert auftraege.aendern(con, aid, basis, welt["bea"]) is False  # nichts geändert
    assert auftraege.aendern(con, aid, {**basis, "datum": NAECHSTE_WOCHE, "uhrzeit": "",
                                        "grund": "Mieter  krank"}, welt["bea"]) is True
    u = auftraege.holen(con, aid)
    assert (u["datum"], u["uhrzeit"]) == (NAECHSTE_WOCHE, None)
    v = auftraege.verlauf(con, aid)[-1]
    assert (v["ereignis"], v["termin_alt"], v["termin_neu"], v["grund"]) == \
        ("verschoben", f"{MORGEN} 08:00", NAECHSTE_WOCHE, "Mieter krank")
    # Techniker tauschen -> Pool; Umfang auf eine Wohnung
    auftraege.aendern(con, aid, {**basis, "datum": NAECHSTE_WOCHE, "uhrzeit": "", "techniker": [],
                                 "umfang": "auswahl", "gruppen": [welt["g1"]]}, welt["bea"])
    assert auftraege.techniker(con, aid) == [] and [g["nummer"] for g in auftraege.gruppen(con, aid)] == [1]
    assert con.execute("SELECT COUNT(*) FROM auftrag_techniker WHERE auftrag_id = ? AND geloescht = 1",
                       (aid,)).fetchone()[0] == 1  # Zuordnung bleibt als gelöscht markiert erhalten
    # Verschieben in die Vergangenheit ist beim Ändern erlaubt (Nachtragen), beim Anlegen nicht
    gestern = (date.today() - timedelta(days=1)).isoformat()
    auftraege.aendern(con, aid, {**basis, "datum": gestern, "umfang": "auswahl", "gruppen": [welt["g1"]]}, None)
    assert auftraege.holen(con, aid)["datum"] == gestern


def test_aendern_je_status(welt):
    con = welt["con"]
    aid = planen(welt, umfang="auswahl", gruppen=[welt["g1"]])
    basis = {"auftragsart": "wartung", "datum": MORGEN, "umfang": "auswahl", "gruppen": [welt["g1"]]}
    auftraege.status_setzen(con, aid, "aktiv", None)
    auftraege.aendern(con, aid, {**basis, "techniker": [welt["tom"]], "hinweise": "neu"}, None)  # in Arbeit: ja
    with pytest.raises(Ungueltig, match="Umfang ist nur änderbar"):
        auftraege.aendern(con, aid, {**basis, "gruppen": [welt["g1"], welt["g2"]]}, None)
    with pytest.raises(Ungueltig, match="Umfang ist nur änderbar"):
        auftraege.aendern(con, aid, {**basis, "umfang": "ganze_anlage"}, None)
    auftraege.status_setzen(con, aid, "abgeschlossen", None)
    with pytest.raises(Ungueltig, match="nicht mehr geändert"):
        auftraege.aendern(con, aid, basis, None)


# ---------- Status ----------

def test_statusuebergaenge(welt):
    con = welt["con"]
    aid = planen(welt)
    with pytest.raises(Ungueltig, match="nicht möglich"):
        auftraege.status_setzen(con, aid, "abgerechnet", None)
    with pytest.raises(Ungueltig) as e:
        auftraege.status_setzen(con, aid, "storniert", None, grund="   ")
    assert e.value.fehler == {"grund": "Bitte einen Grund angeben."}
    auftraege.status_setzen(con, aid, "storniert", welt["bea"], grund="Kunde hat gekündigt")
    auftraege.status_setzen(con, aid, "geplant", welt["bea"], grund="doch nicht")
    auftraege.status_setzen(con, aid, "aktiv", welt["tom"])
    auftraege.status_setzen(con, aid, "abgeschlossen", welt["tom"])
    assert auftraege.holen(con, aid)["abgeschlossen_am"] == date.today().isoformat()
    with pytest.raises(Ungueltig):
        auftraege.status_setzen(con, aid, "aktiv", None)  # wieder öffnen braucht Grund
    auftraege.status_setzen(con, aid, "aktiv", None, grund="Melder vergessen")
    assert auftraege.holen(con, aid)["abgeschlossen_am"] is None
    auftraege.status_setzen(con, aid, "abgeschlossen", None)
    auftraege.status_setzen(con, aid, "abgerechnet", welt["bea"], rechnung_nummer=" RE-2026-0042 ")
    assert auftraege.holen(con, aid)["rechnung_nummer"] == "RE-2026-0042"
    auftraege.status_setzen(con, aid, "abgeschlossen", None, grund="Rechnung storniert")
    assert auftraege.holen(con, aid)["rechnung_nummer"] == ""
    auftraege.status_setzen(con, aid, "kostenlos", None)
    schritte = [(v["status_alt"], v["status_neu"], v["grund"]) for v in auftraege.verlauf(con, aid)
                if v["ereignis"] == "status"]
    assert schritte == [("geplant", "storniert", "Kunde hat gekündigt"), ("storniert", "geplant", "doch nicht"),
                        ("geplant", "aktiv", ""), ("aktiv", "abgeschlossen", ""),
                        ("abgeschlossen", "aktiv", "Melder vergessen"), ("aktiv", "abgeschlossen", ""),
                        ("abgeschlossen", "abgerechnet", ""), ("abgerechnet", "abgeschlossen", "Rechnung storniert"),
                        ("abgeschlossen", "kostenlos", "")]


def test_alle_uebergaenge_konsistent():
    status = set(auftraege.STATUS_TEXT)
    assert set(auftraege.UEBERGAENGE) == status
    assert all(set(ziele) <= status and alt not in ziele for alt, ziele in auftraege.UEBERGAENGE.items())
    assert all(neu in auftraege.UEBERGAENGE[alt] for alt, neu in auftraege.RUECKWAERTS)


# ---------- Nachweise: nur anhängen, nie löschen ----------

def test_verlauf_nur_anhaengen_und_auftrag_nicht_loeschbar(welt):
    con = welt["con"]
    aid = planen(welt)
    with pytest.raises(sqlite3.DatabaseError, match="nur angehängt"):
        con.execute("UPDATE auftrag_verlauf SET grund = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="nicht gelöscht"):
        con.execute("DELETE FROM auftrag_verlauf")
    with pytest.raises(sqlite3.DatabaseError, match="nur storniert"):
        con.execute("DELETE FROM auftrag WHERE id = ?", (aid,))
    abgleich_vorher = auftraege.holen(con, aid)["abgleich_nr"]
    auftraege.status_setzen(con, aid, "aktiv", None)
    assert auftraege.holen(con, aid)["abgleich_nr"] > abgleich_vorher


def test_loeschregeln_anlage_und_wohnung(welt):
    con = welt["con"]
    a = welt["anlage"]
    aid = planen(welt, umfang="auswahl", gruppen=[welt["g1"]])
    with pytest.raises(Ungueltig) as e:
        gruppen.loeschen(con, RWM, welt["g1"], None)
    assert "auftraege" in e.value.fehler
    gruppen.loeschen(con, RWM, welt["g2"], None)  # nicht im Auftrag: geht
    with pytest.raises(Ungueltig) as e:
        anlagen.loeschen(con, a["id"], None)
    assert "auftraege" in e.value.fehler
    auftraege.status_setzen(con, aid, "storniert", None, grund="Test")
    gruppen.loeschen(con, RWM, welt["g1"], None)  # Auftrag nicht mehr offen: geht
    anlagen.loeschen(con, a["id"], None)  # nur stornierte Aufträge: geht
    assert anlagen.holen(con, a["id"]) is None


def test_abgeschlossener_auftrag_sperrt_anlage(welt):
    con = welt["con"]
    aid = planen(welt)
    auftraege.status_setzen(con, aid, "abgeschlossen", None)
    gruppen.loeschen(con, RWM, welt["g1"], None)
    gruppen.loeschen(con, RWM, welt["g2"], None)
    with pytest.raises(Ungueltig, match="Aufträge"):
        anlagen.loeschen(con, welt["anlage"]["id"], None)


def test_komponenten_und_typen_unberuehrt(welt):
    """Aufträge ändern nichts an Meldern und Fälligkeiten (das kommt erst mit den Prüfungen)."""
    con = welt["con"]
    typ = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "T", "kategorie": "komponente",
                              "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)
    m = komponenten.anlegen(con, RWM, gruppen.holen(con, welt["g1"]), {"nummer": "1", "komponententyp_id": typ,
                                                                       "baujahr": "2022"}, None)
    vorher = dict(komponenten.holen(con, m))
    aid = planen(welt)
    auftraege.status_setzen(con, aid, "abgeschlossen", None)
    assert dict(komponenten.holen(con, m)) == vorher
    assert rechte.RECHTE[auftraege.TECHNIKER_RECHT]
