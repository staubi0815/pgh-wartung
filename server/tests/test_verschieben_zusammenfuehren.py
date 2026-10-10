"""Anlage in ein anderes Objekt verschieben und Melder-Typen zusammenführen."""
import pytest

from wartung import anlagen, anlagenart, gruppen, komponenten, kunden, lebenslauf, objekte, typen
from wartung.felder import Ungueltig

from hilfen import anmelden, csrf_aus, nutzer_mit_passwort, rolle_id

RWM = "rauchwarnmelder"


@pytest.fixture
def lage(umgebung):
    c, con = umgebung
    art = anlagenart.holen(RWM)
    k1 = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Erste Verwaltung", "ort": "Zwickau"}, None)
    k2 = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Zweite Verwaltung", "ort": "Plauen"}, None)
    adresse = {"strasse": "Lindenweg 3", "plz": "90402", "ort": "Nürnberg"}
    o1 = objekte.anlegen(con, k1, {"bezeichnung": "Haus Eins", **adresse}, None)
    o1b = objekte.anlegen(con, k1, {"bezeichnung": "Haus Eins B", **adresse}, None)
    o2 = objekte.anlegen(con, k2, {"bezeichnung": "Haus Zwei", **adresse}, None)
    a = anlagen.anlegen(con, o1, {"anlagenart": RWM, "verfahren": "A"}, None)
    typ_a = typen.anlegen(con, {"anlagenart": RWM, "bezeichnung": "Ei650", "kategorie": "komponente",
                                "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)
    typ_b = typen.anlegen(con, {"anlagenart": RWM, "bezeichnung": "Ei 650", "kategorie": "komponente",
                                "funk": "keine", "batterie": "fest_10j", "aktiv": "1", "austausch_jahre": "5"}, None)
    g = gruppen.holen(con, gruppen.anlegen(con, art, a, {"nummer": "1", "zugang": "frei"}, None))

    def melder(nummer, typ):
        return komponenten.anlegen(con, art, g, {"nummer": str(nummer), "komponententyp_id": typ, "baujahr": "2020",
                                                 "letzte_pruefung_am": "2025-10-20"}, None)
    return {"c": c, "con": con, "art": art, "k1": k1, "k2": k2, "o1": o1, "o1b": o1b, "o2": o2, "a": a,
            "typ_a": typ_a, "typ_b": typ_b, "g": g, "melder": melder}


# ---------- Anlage verschieben ----------

def test_verschieben_im_selben_kunden_behaelt_alles(lage):
    con = lage["con"]
    m = lage["melder"](1, lage["typ_a"])
    kt = kunden.kontakt_anlegen(con, lage["k1"], {"name": "Hanna"}, None)
    anlagen.kontakt_zuordnen(con, lage["a"], kt, "vor_ort", None)
    assert anlagen.verschieben(con, lage["a"], lage["o1b"], None) == []
    a = anlagen.holen(con, lage["a"])
    assert a["objekt_id"] == lage["o1b"] and a["wohnungen"] == 1 and a["komponenten"] == 1
    assert len(anlagen.kontakte(con, lage["a"])) == 1
    assert komponenten.holen(con, m)["gruppe_id"] == lage["g"]["id"]
    assert [x["id"] for x in anlagen.liste_fuer_objekt(con, lage["o1"])] == []
    assert con.execute("SELECT alt, neu FROM aenderungsprotokoll WHERE tabelle = 'anlage' AND feld = 'objekt_id' "
                       "AND aktion = 'aendern'").fetchone()["neu"] == lage["o1b"]


def test_verschieben_zu_anderem_kunden_entfernt_ansprechpartner(lage):
    con = lage["con"]
    kt = kunden.kontakt_anlegen(con, lage["k1"], {"name": "Hanna"}, None)
    anlagen.kontakt_zuordnen(con, lage["a"], kt, "vor_ort", None)
    assert anlagen.verschieben(con, lage["a"], lage["o2"], None) == ["Hanna"]
    a = anlagen.holen(con, lage["a"])
    assert a["kunde_id"] == lage["k2"] and anlagen.kontakte(con, lage["a"]) == []


@pytest.mark.parametrize("ziel", ["gibt-es-nicht", ""])
def test_verschieben_ungueltiges_ziel(lage, ziel):
    with pytest.raises(Ungueltig):
        anlagen.verschieben(lage["con"], lage["a"], ziel, None)


def test_verschieben_gleiches_oder_geloeschtes_objekt(lage):
    con = lage["con"]
    with pytest.raises(Ungueltig):
        anlagen.verschieben(con, lage["a"], lage["o1"], None)
    objekte.loeschen(con, lage["o1b"], None)
    with pytest.raises(Ungueltig):
        anlagen.verschieben(con, lage["a"], lage["o1b"], None)
    assert anlagen.holen(con, lage["a"])["objekt_id"] == lage["o1"]


def test_kundenwechsel_des_objekts_bereinigt_ansprechpartner(lage):
    con = lage["con"]
    kt = kunden.kontakt_anlegen(con, lage["k1"], {"name": "Hanna"}, None)
    anlagen.kontakt_zuordnen(con, lage["a"], kt, "vor_ort", None)
    o = objekte.holen(con, lage["o1"])
    objekte.aendern(con, lage["o1"], {"kunde_id": lage["k2"], "bezeichnung": o["bezeichnung"], "strasse": o["strasse"],
                                      "plz": o["plz"], "ort": o["ort"], "land": "DE", "nummer": o["nummer"]}, None)
    assert anlagen.holen(con, lage["a"])["kunde_id"] == lage["k2"]
    assert anlagen.kontakte(con, lage["a"]) == []


def test_ziel_suche(lage):
    con = lage["con"]
    namen = lambda s: {o["bezeichnung"] for o in anlagen.ziel_objekte(con, s, lage["o1"])}  # noqa: E731
    assert namen("") == {"Haus Eins B", "Haus Zwei"}
    assert namen("Zweite") == {"Haus Zwei"}
    assert namen("Haus Eins") == {"Haus Eins B"}
    assert namen("%") == set()


def test_verschieben_web(lage):
    c, con = lage["c"], lage["con"]
    anmelden(c)
    a = lage["a"]
    seite = c.get(f"/anlagen/{a}/verschieben", params={"q": "Zweite"})
    assert seite.status_code == 200 and "Haus Zwei" in seite.text and "Haus Eins B" not in seite.text
    token = csrf_aus(seite.text)
    r = c.post(f"/anlagen/{a}/verschieben", data={"csrf_token": token, "objekt_id": lage["o2"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("hinweis=verschoben")
    assert anlagen.holen(con, a)["objekt_id"] == lage["o2"]
    fehler = c.post(f"/anlagen/{a}/verschieben", data={"csrf_token": token, "objekt_id": lage["o2"]})
    assert fehler.status_code == 400 and "schon in diesem Objekt" in fehler.text
    ohne = c.post(f"/anlagen/{a}/verschieben", data={"objekt_id": lage["o1"]}, follow_redirects=False)
    assert ohne.status_code == 303 and "sitzung_abgelaufen" in ohne.headers["location"]
    assert anlagen.holen(con, a)["objekt_id"] == lage["o2"]


def test_verschieben_braucht_bearbeiten_recht(lage):
    c, con = lage["c"], lage["con"]
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    anmelden(c, "tom@example.org")
    assert c.get(f"/anlagen/{lage['a']}/verschieben", follow_redirects=False).status_code in (303, 403)
    r = c.post(f"/anlagen/{lage['a']}/verschieben", data={"objekt_id": lage["o2"]}, follow_redirects=False)
    assert r.status_code in (303, 400, 403)
    assert anlagen.holen(con, lage["a"])["objekt_id"] == lage["o1"]


# ---------- Typen zusammenführen ----------

def test_zusammenfuehren_stellt_alle_komponenten_um(lage):
    con = lage["con"]
    m1, m2 = lage["melder"](1, lage["typ_b"]), lage["melder"](2, lage["typ_b"])
    lebenslauf.ausbauen(con, komponenten.holen(con, m2), {"grund": "kunde", "zeitpunkt": "2026-01-02"}, None)
    ziel_faellig = komponenten.holen(con, m1)["austausch_faellig_am"]
    assert typen.komponenten_zaehlen(con, lage["typ_b"]) == 2
    assert typen.zusammenfuehren(con, lage["typ_b"], lage["typ_a"], None) == 2
    for m in (m1, m2):  # m2 ist ausgebaut, wechselt trotzdem mit
        assert con.execute("SELECT komponententyp_id FROM komponente WHERE id = ?",
                           (m,)).fetchone()[0] == lage["typ_a"]
    assert typen.holen(con, lage["typ_b"]) is None
    assert typen.holen(con, lage["typ_a"]) is not None
    assert [t["id"] for t in typen.liste(con)] == [lage["typ_a"]]
    # Austauschjahre des Zieltyps gelten jetzt (Vorgabe der Anlagenart statt 5 Jahre)
    assert komponenten.holen(con, m1)["austausch_faellig_am"] != ziel_faellig
    assert con.execute("SELECT neu FROM aenderungsprotokoll WHERE aktion = 'zusammenfuehren' AND datensatz = ?",
                       (lage["typ_b"],)).fetchone()["neu"] == lage["typ_a"]


def test_zusammenfuehren_gibt_namen_wieder_frei(lage):
    con = lage["con"]
    typen.zusammenfuehren(con, lage["typ_b"], lage["typ_a"], None)
    neu = typen.anlegen(con, {"anlagenart": RWM, "bezeichnung": "Ei 650", "kategorie": "komponente", "funk": "keine",
                              "batterie": "fest_10j", "aktiv": "1"}, None)
    assert typen.holen(con, neu) is not None


def test_zusammenfuehren_pruefungen(lage):
    con = lage["con"]
    with pytest.raises(Ungueltig):
        typen.zusammenfuehren(con, lage["typ_a"], lage["typ_a"], None)
    with pytest.raises(Ungueltig):
        typen.zusammenfuehren(con, lage["typ_a"], "gibt-es-nicht", None)
    fremd = con.execute("SELECT id FROM komponententyp WHERE id = ?", (lage["typ_b"],)).fetchone()["id"]
    con.execute("UPDATE komponententyp SET anlagenart = 'tueren' WHERE id = ?", (fremd,))
    with pytest.raises(Ungueltig):
        typen.zusammenfuehren(con, lage["typ_a"], fremd, None)
    assert typen.holen(con, lage["typ_a"]) is not None


def test_zusammenfuehren_web(lage):
    c, con = lage["c"], lage["con"]
    m = lage["melder"](1, lage["typ_b"])
    anmelden(c)
    seite = c.get(f"/verwaltung/typen/{lage['typ_b']}")
    assert "Mit anderem Typ zusammenführen" in seite.text and f'value="{lage["typ_a"]}"' in seite.text
    token = csrf_aus(seite.text)
    r = c.post(f"/verwaltung/typen/{lage['typ_b']}/zusammenfuehren", data={"csrf_token": token, "ziel_id": lage["typ_a"]},
               follow_redirects=False)
    assert r.status_code == 303 and "anzahl=1" in r.headers["location"]
    assert komponenten.holen(con, m)["komponententyp_id"] == lage["typ_a"]
    liste = c.get(r.headers["location"])
    assert "Typen zusammengeführt (1 Komponenten umgestellt)" in liste.text


def test_zusammenfuehren_formular_nur_bei_bestehendem_typ(lage):
    c = lage["c"]
    anmelden(c)
    assert "zusammenführen" not in c.get("/verwaltung/typen/neu").text.lower()
