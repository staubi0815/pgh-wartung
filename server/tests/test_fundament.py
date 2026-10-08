"""Fundament der Stammdaten: Anlagenart-Konfiguration, Tabellenregeln, Abgleich-Nummer, Nummernkreise, Anlegen."""
import sqlite3

import pytest

from wartung import anlagenart, db, nummern


@pytest.fixture
def con(tmp_path):
    c = db.verbinden(tmp_path / "f.db")
    db.migrieren(c)
    return c


def typ_anlegen(con, bezeichnung="Testmelder"):
    return db.anlegen(con, "komponententyp", {"anlagenart": "rauchwarnmelder", "bezeichnung": bezeichnung}, None)


def kette(con):
    """Kunde -> Objekt -> Anlage -> Wohnung 43 + ein Typ. Gibt die ids zurück."""
    k = db.anlegen(con, "kunde", {"nummer": "K0001", "name": "Muster-Verwaltung"}, None)
    o = db.anlegen(con, "objekt", {"nummer": "O-0001", "kunde_id": k, "bezeichnung": "Musterstraße 1"}, None)
    a = db.anlegen(con, "anlage", {"nummer": "ANL-0001", "objekt_id": o, "anlagenart": "rauchwarnmelder"}, None)
    g = db.anlegen(con, "gruppe", {"anlage_id": a, "nummer": 43}, None)
    return k, o, a, g, typ_anlegen(con)


# ---------- Anlagenart-Konfiguration ----------

def test_rauchwarnmelder_konfiguration_ist_gueltig():
    rwm = anlagenart.holen("rauchwarnmelder")
    assert (rwm.gruppe, rwm.komponente, rwm.trenner) == ("Wohnung", "Melder", "/")
    assert rwm.pruefung_monate == 12 and rwm.austausch_jahre == 10 and not rwm.freigegeben
    assert rwm.raumart_fuer("Kinderzimmer") == "kinderzimmer" and rwm.raumart_fuer("Keller") == "sonstiger"
    assert rwm.nummer_anzeige(43, 1) == "43/1" and rwm.nummer_anzeige(43, 1, 2) == "43/1.2"
    assert {c.mangel_bei_nein for c in rwm.checkliste if c.mangel_bei_nein} <= {m.schluessel for m in rwm.maengel}


@pytest.mark.parametrize("aenderung, meldung", [
    (lambda t: t.replace('pruefung_monate = 12', 'pruefung_monate = 12\nraeume_falsch = 1'), "unbekannte Einträge"),
    (lambda t: t.replace('mangel_bei_nein = "kein_alarm"', 'mangel_bei_nein = "gibtsnicht"'), "fehlt"),
    (lambda t: t.replace('schweregrad = "schwer"', 'schweregrad = "mittel"', 1), "Schweregrad"),
    (lambda t: t.replace('schluessel = "rauchwarnmelder"', 'schluessel = "anders"'), "Dateinamen"),
    (lambda t: t.replace('kinderzimmer = ["Kinderzimmer"]', 'kinderzimmer = ["Spielzimmer"]'), "nicht in raeume"),
    (lambda t: t.replace('typ = "text"', 'typ = "text"\nfarbe = "rot"'), "Checkpunkt"),
    (lambda t: t + "\n[allgemein", "keine gültige TOML"),
])
def test_fehler_in_der_konfiguration_werden_erkannt(tmp_path, aenderung, meldung):
    original = (anlagenart.ORDNER / "rauchwarnmelder.toml").read_text(encoding="utf-8")
    datei = tmp_path / "rauchwarnmelder.toml"
    datei.write_text(aenderung(original), encoding="utf-8")
    with pytest.raises(anlagenart.KonfigFehler, match=meldung):
        anlagenart.laden(datei)


def test_unbekannte_anlagenart():
    with pytest.raises(anlagenart.KonfigFehler):
        anlagenart.holen("tueren")


# ---------- Tabellenregeln ----------

def test_abgleich_nummer_steigt_bei_anlegen_und_aendern(con):
    k, o, a, g, t = kette(con)
    nr = lambda tab, i: con.execute(f"SELECT abgleich_nr FROM {tab} WHERE id = ?", (i,)).fetchone()[0]  # noqa: E731
    reihe = [nr("kunde", k), nr("objekt", o), nr("anlage", a), nr("gruppe", g), nr("komponententyp", t)]
    assert reihe == sorted(reihe) and len(set(reihe)) == 5 and reihe[0] > 0
    db.aendern(con, "kunde", k, {"ort": "Teststadt"}, None)
    assert nr("kunde", k) > reihe[-1]


def test_physisches_loeschen_verboten(con):
    k, *_ = kette(con)
    for tabelle in ("kunde", "objekt", "anlage", "gruppe", "komponententyp"):
        with pytest.raises(sqlite3.IntegrityError, match="nur als gelöscht markiert"):
            con.execute(f"DELETE FROM {tabelle}")


def test_pflichtfelder_und_auswahlwerte(con):
    with pytest.raises(sqlite3.IntegrityError):
        db.anlegen(con, "kunde", {"nummer": "K1", "name": ""}, None)
    with pytest.raises(sqlite3.IntegrityError):
        db.anlegen(con, "kunde", {"nummer": "K2", "name": "X", "art": "erfunden"}, None)
    with pytest.raises(sqlite3.IntegrityError):  # Objekt ohne Kunde
        db.anlegen(con, "objekt", {"nummer": "O-9", "kunde_id": "gibtsnicht", "bezeichnung": "X"}, None)


def test_melderplatz_eindeutig_aber_ersetzte_duerfen_bleiben(con):
    _, _, a, g, t = kette(con)
    melder = {"anlage_id": a, "gruppe_id": g, "nummer": 1, "komponententyp_id": t}
    alt = db.anlegen(con, "komponente", melder, None)
    with pytest.raises(sqlite3.IntegrityError):
        db.anlegen(con, "komponente", melder, None)
    db.aendern(con, "komponente", alt, {"status": "ersetzt"}, None)
    neu = db.anlegen(con, "komponente", melder, None)  # gleicher Platz 43/1, alter Melder bleibt im Verlauf
    db.aendern(con, "komponente", alt, {"ersetzt_durch_id": neu}, None)
    assert con.execute("SELECT COUNT(*) FROM komponente WHERE gruppe_id = ?", (g,)).fetchone()[0] == 2


def test_verbauter_melder_braucht_platz_lager_nicht(con):
    *_, t = kette(con)
    with pytest.raises(sqlite3.IntegrityError):
        db.anlegen(con, "komponente", {"komponententyp_id": t}, None)
    db.anlegen(con, "komponente", {"komponententyp_id": t, "status": "lager"}, None)


def test_funk_id_und_barcode_eindeutig(con):
    _, _, a, g, t = kette(con)
    db.anlegen(con, "komponente", {"anlage_id": a, "gruppe_id": g, "nummer": 1, "komponententyp_id": t,
                                   "funk_id": "EIE-1234", "barcode": "PGH-1"}, None)
    for doppelt in ({"funk_id": "EIE-1234"}, {"barcode": "PGH-1"}):
        with pytest.raises(sqlite3.IntegrityError):
            db.anlegen(con, "komponente", {"anlage_id": a, "gruppe_id": g, "nummer": 2, "komponententyp_id": t,
                                           **doppelt}, None)


def test_wohnungsnummer_je_anlage_eindeutig(con):
    _, _, a, _, _ = kette(con)
    with pytest.raises(sqlite3.IntegrityError):
        db.anlegen(con, "gruppe", {"anlage_id": a, "nummer": 43}, None)


# ---------- Anlegen ----------

def test_anlegen_protokolliert_gefuellte_felder(con):
    k = db.anlegen(con, "kunde", {"nummer": "K0001", "name": "Muster", "ort": "", "telefon": "0911"}, "n1")
    felder = {z["feld"]: z["neu"] for z in con.execute(
        "SELECT feld, neu FROM aenderungsprotokoll WHERE datensatz = ? AND aktion = 'anlegen'", (k,))}
    assert felder == {None: None, "nummer": "K0001", "name": "Muster", "telefon": "0911"}
    assert con.execute("SELECT erstellt_von FROM kunde WHERE id = ?", (k,)).fetchone()[0] == "n1"


def test_ungueltige_bezeichner_abgelehnt(con):
    with pytest.raises(ValueError):
        db.anlegen(con, "kunde; DROP TABLE kunde", {"name": "x"}, None)
    with pytest.raises(ValueError):
        db.aendern(con, "kunde", "x", {"name = 'y' --": "z"}, None)


# ---------- Nummernkreise ----------

def test_nummern_fortlaufend_mit_praefix(con):
    assert [nummern.naechste(con, "kunde") for _ in range(3)] == ["K0001", "K0002", "K0003"]
    assert nummern.naechste(con, "objekt") == "O-0001"
    assert nummern.naechste(con, "anlage") == "ANL-0001"
    assert nummern.naechste(con, "auftrag") == "A-1001"


def test_von_hand_vergebene_nummern_werden_uebersprungen(con):
    db.anlegen(con, "kunde", {"nummer": "K0001", "name": "Import"}, None)
    db.anlegen(con, "kunde", {"nummer": "k0002", "name": "Import klein"}, None)
    assert nummern.vorschau(con, "kunde") == "K0003"
    assert nummern.naechste(con, "kunde") == "K0003"


def test_nummer_wird_nicht_wiederverwendet_und_zaehlt_mit_transaktion_zurueck(con):
    with pytest.raises(RuntimeError):
        with db.transaktion(con):
            nummern.naechste(con, "kunde")
            raise RuntimeError("Anlegen fehlgeschlagen")
    assert nummern.naechste(con, "kunde") == "K0001"  # nichts verbraucht, weil alles zurückgerollt wurde


def test_nummer_pruefen(con):
    db.anlegen(con, "kunde", {"nummer": "K0001", "name": "A"}, None)
    assert "schon vergeben" in nummern.pruefen(con, "kunde", "k0001")
    assert nummern.pruefen(con, "kunde", "") == "Nummer ist Pflicht."
    assert "Steuerzeichen" in nummern.pruefen(con, "kunde", "K;1")
    assert nummern.pruefen(con, "kunde", "K0001", eigene_id=con.execute("SELECT id FROM kunde").fetchone()[0]) is None
