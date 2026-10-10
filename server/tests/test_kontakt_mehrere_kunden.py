"""Ein Kontakt bei mehreren Kunden (Migration 010, Verknüpfung kunde_kontakt)."""
import io
import shutil
import zipfile

import openpyxl
import pytest

from wartung import anlagen, db, export, kunden, objekte, suche
from wartung import excel_import as imp
from wartung.app import erzeuge_app
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

RWM = "rauchwarnmelder"


@pytest.fixture
def lage(umgebung):
    c, con = umgebung
    k1 = kunden.anlegen(con, {"nummer": "K-1", "art": "hausverwaltung", "name": "Erste Verwaltung"}, None)
    k2 = kunden.anlegen(con, {"nummer": "K-2", "art": "hausverwaltung", "name": "Zweite Verwaltung"}, None)
    adresse = {"strasse": "Lindenweg 3", "plz": "90402", "ort": "Nürnberg"}
    o1 = objekte.anlegen(con, k1, {"bezeichnung": "Haus Eins", **adresse}, None)
    o2 = objekte.anlegen(con, k2, {"bezeichnung": "Haus Zwei", **adresse}, None)
    a1 = anlagen.anlegen(con, o1, {"anlagenart": RWM, "verfahren": "A"}, None)
    a2 = anlagen.anlegen(con, o2, {"anlagenart": RWM, "verfahren": "A"}, None)
    dienst = kunden.kontakt_anlegen(con, k1, {"name": "Hausmeisterdienst Müller", "telefon": "0911 1234"}, None)
    nur_k1 = kunden.kontakt_anlegen(con, k1, {"name": "Frau Nur-Eins"}, None)
    return {"c": c, "con": con, "k1": k1, "k2": k2, "o1": o1, "o2": o2, "a1": a1, "a2": a2, "dienst": dienst,
            "nur_k1": nur_k1}


def namen(zeilen):
    return [z["name"] for z in zeilen]


# ---------- Migration ----------

def test_migration_uebernimmt_bestehende_zuordnungen(tmp_path):
    """Datenbank auf Stand 009 mit Kontakten (auch ohne Kunde, auch gelöscht) → Migration 010 erhält alles."""
    alt = tmp_path / "alt"
    alt.mkdir()
    for datei in db.MIGRATIONEN.glob("*.sql"):
        if not datei.name.startswith("010"):
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
    k1 = einfuegen("kunde", nummer="K1", name="A")
    k2 = einfuegen("kunde", nummer="K2", name="B")
    o = einfuegen("objekt", kunde_id=k1, nummer="O1", bezeichnung="x", adresse_wie_kunde=1)
    a = einfuegen("anlage", objekt_id=o, nummer="A1", anlagenart=RWM, verfahren="A")
    c1 = einfuegen("kontakt", kunde_id=k1, name="Eins", telefon="123")
    c_frei = einfuegen("kontakt", name="Ohne Kunde")
    c_weg = einfuegen("kontakt", kunde_id=k2, name="Gelöscht", geloescht=1)
    einfuegen("anlage_kontakt", anlage_id=a, kontakt_id=c1, rolle="vor_ort")
    nr = con.execute("SELECT nr FROM abgleich_zaehler").fetchone()[0]

    assert db.migrieren(con) == ["010_kontakt_mehrere_kunden.sql"]

    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert "kunde_id" not in [s["name"] for s in con.execute("PRAGMA table_info(kontakt)")]
    assert con.execute("SELECT count(*) FROM kontakt").fetchone()[0] == 3
    links = {(r["kontakt_id"], r["kunde_id"]): r["geloescht"] for r in con.execute("SELECT * FROM kunde_kontakt")}
    assert links == {(c1, k1): 0, (c_weg, k2): 1}  # der Kontakt ohne Kunde bekommt keine Verknüpfung
    assert [r["abgleich_nr"] > nr for r in con.execute("SELECT abgleich_nr FROM kunde_kontakt")] == [True, True]
    assert con.execute("SELECT name, telefon FROM kontakt WHERE id = ?", (c1,)).fetchone()["telefon"] == "123"
    assert con.execute("SELECT count(*) FROM anlage_kontakt WHERE kontakt_id = ?", (c1,)).fetchone()[0] == 1
    assert c_frei and con.execute("SELECT count(*) FROM kontakt WHERE id = ?", (c_frei,)).fetchone()[0] == 1
    # Trigger sind wieder da
    with pytest.raises(Exception, match="nur als gelöscht"):
        con.execute("DELETE FROM kontakt WHERE id = ?", (c1,))
    n = con.execute("SELECT nr FROM abgleich_zaehler").fetchone()[0]
    con.execute("UPDATE kontakt SET notiz = 'x' WHERE id = ?", (c1,))
    assert con.execute("SELECT abgleich_nr FROM kontakt WHERE id = ?", (c1,)).fetchone()[0] == n + 1


# ---------- Verknüpfen und Lösen ----------

def test_kontakt_bei_zweitem_kunden_fuehren(lage):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    assert namen(kunden.kontakte(con, lage["k2"])) == ["Hausmeisterdienst Müller"]
    assert kunden.kontakte(con, lage["k2"])[0]["auch_bei"] == "Erste Verwaltung"
    erste = {k["name"]: k["auch_bei"] for k in kunden.kontakte(con, lage["k1"])}
    assert erste["Hausmeisterdienst Müller"] == "Zweite Verwaltung" and erste["Frau Nur-Eins"] is None
    assert [k["name"] for k in kunden.kunden_von_kontakt(con, lage["dienst"])] == ["Erste Verwaltung",
                                                                                    "Zweite Verwaltung"]
    # eine Änderung gilt für alle Kunden
    kunden.kontakt_aendern(con, lage["dienst"], {"name": "Hausmeisterdienst Müller", "telefon": "0911 9999"}, None)
    assert kunden.kontakte(con, lage["k2"])[0]["telefon"] == "0911 9999"


@pytest.mark.parametrize("kunde,kontakt,text", [("k1", "dienst", "schon"), ("k1", "fehlt", "Kontakt nicht"),
                                                 ("fehlt", "dienst", "Kunde nicht")])
def test_verknuepfen_prueft(lage, kunde, kontakt, text):
    with pytest.raises(Ungueltig) as e:
        kunden.kontakt_verknuepfen(lage["con"], lage.get(kunde, "gibt-es-nicht"), lage.get(kontakt, "gibt-es-nicht"),
                                   None)
    assert text in e.value.fehler[""]


def test_geloeschter_kontakt_nicht_verknuepfbar(lage):
    kunden.kontakt_loeschen(lage["con"], lage["nur_k1"], None)
    with pytest.raises(Ungueltig):
        kunden.kontakt_verknuepfen(lage["con"], lage["k2"], lage["nur_k1"], None)


def test_loesen_entfernt_nur_zuordnungen_dieses_kunden(lage):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    anlagen.kontakt_zuordnen(con, lage["a1"], lage["dienst"], "vor_ort", None)
    anlagen.kontakt_zuordnen(con, lage["a2"], lage["dienst"], "vor_ort", None)
    kunden.kontakt_loesen(con, lage["k1"], lage["dienst"], None)
    assert [k["name"] for k in kunden.kunden_von_kontakt(con, lage["dienst"])] == ["Zweite Verwaltung"]
    assert anlagen.kontakte(con, lage["a1"]) == [] and namen(anlagen.kontakte(con, lage["a2"])) == [
        "Hausmeisterdienst Müller"]
    assert "Hausmeisterdienst Müller" not in namen(kunden.kontakte(con, lage["k1"]))
    # wieder hinzufügen ist möglich (eine gelöschte Verknüpfung blockiert nicht)
    kunden.kontakt_verknuepfen(con, lage["k1"], lage["dienst"], None)
    assert "Hausmeisterdienst Müller" in namen(kunden.kontakte(con, lage["k1"]))


def test_loesen_vom_letzten_kunden_geht_nicht(lage):
    with pytest.raises(Ungueltig, match="nur gelöscht"):
        kunden.kontakt_loesen(lage["con"], lage["k1"], lage["nur_k1"], None)
    with pytest.raises(Ungueltig, match="nicht zu diesem"):
        kunden.kontakt_loesen(lage["con"], lage["k2"], lage["nur_k1"], None)


def test_kontakt_loeschen_gilt_fuer_alle_kunden(lage):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    anlagen.kontakt_zuordnen(con, lage["a1"], lage["dienst"], "vor_ort", None)
    anlagen.kontakt_zuordnen(con, lage["a2"], lage["dienst"], "berichtsempfaenger", None)
    kunden.kontakt_loeschen(con, lage["dienst"], None)
    assert "Hausmeisterdienst Müller" not in namen(kunden.kontakte(con, lage["k1"])) + namen(
        kunden.kontakte(con, lage["k2"]))
    assert anlagen.kontakte(con, lage["a1"]) == [] and anlagen.kontakte(con, lage["a2"]) == []
    assert con.execute("SELECT count(*) FROM kunde_kontakt WHERE kontakt_id = ? AND geloescht = 0",
                       (lage["dienst"],)).fetchone()[0] == 0


def test_kunde_loeschen_behaelt_geteilte_kontakte(lage):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    db.aendern(con, "anlage", lage["a1"], {"geloescht": 1}, None)
    db.aendern(con, "objekt", lage["o1"], {"geloescht": 1}, None)
    kunden.loeschen(con, lage["k1"], None)
    assert namen(kunden.kontakte(con, lage["k2"])) == ["Hausmeisterdienst Müller"]
    assert kunden.kontakt_holen(con, lage["dienst"]) is not None
    assert kunden.kontakt_holen(con, lage["nur_k1"]) is None  # gehörte nur diesem Kunden


# ---------- Ansprechpartner an der Anlage ----------

def test_zuordnen_nur_fuer_kontakte_des_kunden(lage):
    con = lage["con"]
    with pytest.raises(Ungueltig, match="dieses Kunden"):
        anlagen.kontakt_zuordnen(con, lage["a2"], lage["dienst"], "vor_ort", None)
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    anlagen.kontakt_zuordnen(con, lage["a2"], lage["dienst"], "vor_ort", None)
    assert namen(anlagen.kontakte(con, lage["a2"])) == ["Hausmeisterdienst Müller"]


def test_objekt_wechselt_kunden_geteilter_kontakt_bleibt(lage):
    """Beim Kundenwechsel eines Objekts bleiben Ansprechpartner, die auch beim neuen Kunden geführt werden."""
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    anlagen.kontakt_zuordnen(con, lage["a1"], lage["dienst"], "vor_ort", None)
    anlagen.kontakt_zuordnen(con, lage["a1"], lage["nur_k1"], "vor_ort", None)
    o = objekte.holen(con, lage["o1"])
    objekte.aendern(con, lage["o1"], {"kunde_id": lage["k2"], "nummer": o["nummer"], "bezeichnung": o["bezeichnung"],
                                      "strasse": o["strasse"], "plz": o["plz"], "ort": o["ort"]}, None)
    assert namen(anlagen.kontakte(con, lage["a1"])) == ["Hausmeisterdienst Müller"]


def test_verschieben_geteilter_kontakt_bleibt(lage):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    anlagen.kontakt_zuordnen(con, lage["a1"], lage["dienst"], "vor_ort", None)
    anlagen.kontakt_zuordnen(con, lage["a1"], lage["nur_k1"], "vor_ort", None)
    entfernt = anlagen.verschieben(con, lage["a1"], lage["o2"], None)
    assert entfernt == ["Frau Nur-Eins"]
    assert namen(anlagen.kontakte(con, lage["a1"])) == ["Hausmeisterdienst Müller"]


# ---------- Suche ----------

def test_suche_nennt_alle_kunden_eines_kontakts(lage):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    treffer = suche.suchen(con, "Hausmeisterdienst", {"stammdaten.lesen"}, None)["kontakte"][0]
    assert len(treffer) == 1 and treffer[0]["kunde_name"] == "Erste Verwaltung, Zweite Verwaltung"


def test_kontakte_suchen_ohne_bereits_zugeordnete(lage):
    con = lage["con"]
    assert namen(kunden.kontakte_suchen(con, "", lage["k2"])) == ["Frau Nur-Eins", "Hausmeisterdienst Müller"]
    assert namen(kunden.kontakte_suchen(con, "müller", lage["k2"])) == ["Hausmeisterdienst Müller"]
    assert kunden.kontakte_suchen(con, "müller", lage["k1"]) == []
    assert kunden.kontakte_suchen(con, "100%", lage["k2"]) == []  # Platzhalter werden nicht ausgewertet


# ---------- Export und Import ----------

def blatt(inhalt):
    zeilen = list(openpyxl.load_workbook(io.BytesIO(inhalt)).active.iter_rows(values_only=True))
    kopf = [str(k).rstrip("*") for k in zeilen[0]]
    return kopf, [dict(zip(kopf, z)) for z in zeilen[1:]]


def test_export_eine_zeile_je_kunde_und_rundweg(lage, tmp_path):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    with zipfile.ZipFile(io.BytesIO(export.foxtag(con)[0])) as z:
        dateien = {n: z.read(n) for n in z.namelist()}
    _, zeilen = blatt(dateien["02_Kontakte.xlsx"])
    assert sorted((z["KUNDE"], z["NAME"]) for z in zeilen) == [
        ("K-1", "Frau Nur-Eins"), ("K-1", "Hausmeisterdienst Müller"), ("K-2", "Hausmeisterdienst Müller")]

    ziel = erzeuge_app(tmp_path / "ziel").state.con
    assert imp.uebernehmen(ziel, "kunden", dateien["01_Kunden.xlsx"], None).gespeichert
    e = imp.uebernehmen(ziel, "kontakte", dateien["02_Kontakte.xlsx"], None)
    assert e.gespeichert and e.anzahl("neu") == 3
    # derselbe Kontakt wurde bei beiden Kunden verknüpft, nicht doppelt angelegt
    assert ziel.execute("SELECT count(*) FROM kontakt WHERE name LIKE 'Hausmeisterdienst%'").fetchone()[0] == 1
    assert ziel.execute("SELECT count(*) FROM kunde_kontakt WHERE geloescht = 0").fetchone()[0] == 3


def test_import_legt_abweichenden_kontakt_neu_an(lage, tmp_path):
    """Gleicher Name, aber andere Telefonnummer → zwei verschiedene Personen."""
    con = lage["con"]
    kunden.kontakt_anlegen(con, lage["k2"], {"name": "Hausmeisterdienst Müller", "telefon": "0911 5555"}, None)
    with zipfile.ZipFile(io.BytesIO(export.foxtag(con)[0])) as z:
        dateien = {n: z.read(n) for n in z.namelist()}
    ziel = erzeuge_app(tmp_path / "ziel").state.con
    imp.uebernehmen(ziel, "kunden", dateien["01_Kunden.xlsx"], None)
    imp.uebernehmen(ziel, "kontakte", dateien["02_Kontakte.xlsx"], None)
    assert ziel.execute("SELECT count(*) FROM kontakt WHERE name LIKE 'Hausmeisterdienst%'").fetchone()[0] == 2


def test_import_zweimal_aendert_nichts(lage, tmp_path):
    con = lage["con"]
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    with zipfile.ZipFile(io.BytesIO(export.foxtag(con)[0])) as z:
        datei = z.read("02_Kontakte.xlsx")
    e = imp.uebernehmen(con, "kontakte", datei, None)
    assert e.anzahl("vorhanden") == 3 and e.anzahl("neu") == 0


# ---------- Web ----------

def test_web_hinzufuegen_ansehen_loesen_loeschen(lage):
    c, con = lage["c"], lage["con"]
    anmelden(c)
    k1, k2, dienst = lage["k1"], lage["k2"], lage["dienst"]
    seite = c.get(f"/kunden/{k2}/kontakte/hinzufuegen?q=Müller")
    assert seite.status_code == 200 and "Hausmeisterdienst Müller" in seite.text and "Erste Verwaltung" in seite.text
    t = csrf_aus(seite.text)
    r = c.post(f"/kunden/{k2}/kontakte/{dienst}/hinzufuegen", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and "kontakt_hinzugefuegt" in r.headers["location"]
    seite = c.get(f"/kunden/{k2}")
    assert "Hausmeisterdienst Müller" in seite.text and "Kontakt hinzugefügt" not in seite.text
    assert "Erste Verwaltung" in seite.text  # Spalte „Auch bei“
    # bereits zugeordnet: nicht mehr in der Trefferliste
    assert "Hausmeisterdienst Müller" not in c.get(f"/kunden/{k2}/kontakte/hinzufuegen").text
    # Kontaktseite zeigt beide Kunden und die Lösen-Knöpfe
    form = c.get(f"/kontakte/{dienst}?kunde={k2}")
    assert form.status_code == 200 and "Gehört zu" in form.text and "von diesem Kunden lösen" in form.text
    assert "bei allen 2 Kunden" in form.text
    r = c.post(f"/kunden/{k1}/kontakte/{dienst}/loesen", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and "kontakt_geloest" in r.headers["location"]
    assert [k["id"] for k in kunden.kunden_von_kontakt(con, dienst)] == [k2]
    # letzter Kunde: Lösen wird abgelehnt, Kontakt bleibt
    r = c.post(f"/kunden/{k2}/kontakte/{dienst}/loesen", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and kunden.kontakt_holen(con, dienst) is not None
    assert "von diesem Kunden lösen" not in c.get(f"/kontakte/{dienst}?kunde={k2}").text
    r = c.post(f"/kontakte/{dienst}/loeschen?kunde={k2}", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and f"/kunden/{k2}" in r.headers["location"]
    assert kunden.kontakt_holen(con, dienst) is None


def test_web_speichern_bleibt_beim_kunden_aus_dem_aufruf(lage):
    c, con = lage["c"], lage["con"]
    anmelden(c)
    kunden.kontakt_verknuepfen(con, lage["k2"], lage["dienst"], None)
    t = csrf_aus(c.get(f"/kontakte/{lage['dienst']}?kunde={lage['k2']}").text)
    r = c.post(f"/kontakte/{lage['dienst']}?kunde={lage['k2']}",
               data={"name": "Hausmeisterdienst Müller GmbH", "csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith(f"/kunden/{lage['k2']}?")
    assert kunden.kontakt_holen(con, lage["dienst"])["name"] == "Hausmeisterdienst Müller GmbH"
    # Fehler → Formular mit Status 400 und weiter der Kundenbezug
    r = c.post(f"/kontakte/{lage['dienst']}?kunde={lage['k2']}", data={"name": "", "csrf_token": t})
    assert r.status_code == 400 and "Gehört zu" in r.text


def test_web_rechte(lage):
    c, con = lage["c"], lage["con"]
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    anmelden(c, "tom@example.org")
    k2, dienst = lage["k2"], lage["dienst"]
    assert c.get(f"/kunden/{k2}/kontakte/hinzufuegen", follow_redirects=False).status_code in (303, 403)
    for pfad in (f"/kunden/{k2}/kontakte/{dienst}/hinzufuegen", f"/kunden/{lage['k1']}/kontakte/{dienst}/loesen"):
        assert c.post(pfad, data={}, follow_redirects=False).status_code in (303, 400, 403)
    assert [k["id"] for k in kunden.kunden_von_kontakt(con, dienst)] == [lage["k1"]]
