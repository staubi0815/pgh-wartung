"""Labels (Migration 011): Pflege, Zuordnung an Kunde/Objekt/Anlage/Auftrag, Filter, Anzeige, Rechte."""
from datetime import date, timedelta

import pytest

from wartung import anlagen, auftraege, kunden, labels, objekte
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
    datum = (date.today() + timedelta(days=3)).isoformat()
    u1 = auftraege.anlegen(con, anlagen.holen(con, a1), {"auftragsart": "wartung", "datum": datum}, None)
    u2 = auftraege.anlegen(con, anlagen.holen(con, a2), {"auftragsart": "wartung", "datum": datum}, None)
    gross = labels.anlegen(con, {"name": "Großkunde", "farbe": "rot"}, None)
    schluessel = labels.anlegen(con, {"name": "Schlüssel im Büro", "farbe": "gruen"}, None)
    return {"c": c, "con": con, "k1": k1, "k2": k2, "o1": o1, "o2": o2, "a1": a1, "a2": a2, "u1": u1, "u2": u2,
            "gross": gross, "schluessel": schluessel}


def namen(zeilen):
    return [z["name"] for z in zeilen]


# ---------- Migration ----------

def test_migration_tabellen_trigger_und_eindeutigkeit(umgebung):
    con = umgebung[1]
    for t in ("label", "label_zuordnung"):
        trigger = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (t,))}
        assert trigger == {f"{t}_abgleich_neu", f"{t}_abgleich_aenderung", f"{t}_nicht_loeschen"}
    lid = labels.anlegen(con, {"name": "Test", "farbe": "blau"}, None)
    assert con.execute("SELECT abgleich_nr FROM label WHERE id = ?", (lid,)).fetchone()[0] > 0
    with pytest.raises(Exception):
        con.execute("DELETE FROM label WHERE id = ?", (lid,))
    with pytest.raises(Exception):  # Farbe nur aus der Palette
        con.execute("UPDATE label SET farbe = 'pink' WHERE id = ?", (lid,))
    with pytest.raises(Exception):  # Art nur aus der Liste
        con.execute("INSERT INTO label_zuordnung (id, label_id, art, datensatz_id, erstellt_am) "
                    "VALUES ('x', ?, 'komponente', 'y', '2026-01-01')", (lid,))


# ---------- Pflege ----------

def test_anlegen_pruefen_aendern(lage):
    con = lage["con"]
    with pytest.raises(Ungueltig) as e:
        labels.anlegen(con, {"name": "", "farbe": "rot"}, None)
    assert "name" in e.value.fehler
    with pytest.raises(Ungueltig) as e:
        labels.anlegen(con, {"name": "GROßKUNDE", "farbe": "rot"}, None)  # Groß-/Kleinschreibung egal
    assert "schon" in e.value.fehler["name"]
    with pytest.raises(Ungueltig):
        labels.anlegen(con, {"name": "Neu", "farbe": "pink"}, None)
    labels.aendern(con, lage["gross"], {"name": "Großkunde", "farbe": "orange"}, None)  # eigener Name erlaubt
    assert labels.holen(con, lage["gross"])["farbe"] == "orange"
    with pytest.raises(Ungueltig):
        labels.aendern(con, lage["gross"], {"name": "schlüssel im büro", "farbe": "rot"}, None)
    assert con.execute(
        "SELECT COUNT(*) FROM aenderungsprotokoll WHERE tabelle = 'label' AND datensatz = ?", (lage["gross"],)
    ).fetchone()[0] >= 3


def test_loeschen_entfernt_zuordnungen_und_gibt_namen_frei(lage):
    con = lage["con"]
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    labels.setzen(con, "anlage", lage["a1"], [lage["gross"], lage["schluessel"]], None)
    assert labels.loeschen(con, lage["gross"], None) == 2
    assert labels.holen(con, lage["gross"]) is None
    assert labels.von(con, "kunde", lage["k1"]) == []
    assert namen(labels.von(con, "anlage", lage["a1"])) == ["Schlüssel im Büro"]
    labels.anlegen(con, {"name": "Großkunde", "farbe": "blau"}, None)  # Name wieder frei
    assert kunden.liste(con, label=lage["gross"]) == []


# ---------- Zuordnen ----------

def test_setzen_je_art(lage):
    con = lage["con"]
    ziele = {"kunde": lage["k1"], "objekt": lage["o1"], "anlage": lage["a1"], "auftrag": lage["u1"]}
    for art, i in ziele.items():
        assert labels.setzen(con, art, i, [lage["gross"], lage["schluessel"]], None) == (2, 0)
        assert namen(labels.von(con, art, i)) == ["Großkunde", "Schlüssel im Büro"]
        assert labels.setzen(con, art, i, [lage["gross"], lage["gross"]], None) == (0, 1)  # doppelt = einmal
        assert namen(labels.von(con, art, i)) == ["Großkunde"]
        assert labels.setzen(con, art, i, [lage["gross"]], None) == (0, 0)
    # gleiche id in anderer Art ist unabhängig
    assert labels.von(con, "kunde", lage["k2"]) == []
    # wieder anhaken nach Entfernen
    labels.setzen(con, "kunde", lage["k1"], [], None)
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    assert namen(labels.von(con, "kunde", lage["k1"])) == ["Großkunde"]
    assert con.execute("SELECT COUNT(*) FROM label_zuordnung WHERE art='kunde' AND datensatz_id=? AND geloescht=0",
                       (lage["k1"],)).fetchone()[0] == 1


def test_setzen_lehnt_unbekannte_ab_und_aendert_dann_nichts(lage):
    con = lage["con"]
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    with pytest.raises(Ungueltig):
        labels.setzen(con, "kunde", lage["k1"], [lage["schluessel"], "gibt-es-nicht"], None)
    assert namen(labels.von(con, "kunde", lage["k1"])) == ["Großkunde"]
    with pytest.raises(ValueError):
        labels.setzen(con, "komponente", lage["k1"], [], None)
    labels.loeschen(con, lage["schluessel"], None)
    with pytest.raises(Ungueltig):  # gelöschtes Label
        labels.setzen(con, "kunde", lage["k1"], [lage["schluessel"]], None)


def test_fuer_mehrere_und_viele_ids(lage):
    con = lage["con"]
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    labels.setzen(con, "kunde", lage["k2"], [lage["schluessel"], lage["gross"]], None)
    je = labels.fuer(con, "kunde", [lage["k1"], lage["k2"]] + [f"x{i}" for i in range(1200)])
    assert set(je) == {lage["k1"], lage["k2"]} and len(je[lage["k2"]]) == 2
    assert labels.fuer(con, "kunde", []) == {}


def test_liste_zaehlt_nur_lebende_datensaetze(lage):
    con = lage["con"]
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    k3 = kunden.anlegen(con, {"nummer": "K-3", "art": "privat", "name": "Ohne Objekte"}, None)  # lässt sich löschen
    labels.setzen(con, "kunde", k3, [lage["gross"]], None)
    labels.setzen(con, "auftrag", lage["u1"], [lage["gross"]], None)
    zeile = next(l for l in labels.liste(con) if l["id"] == lage["gross"])
    assert (zeile["n_kunde"], zeile["n_objekt"], zeile["n_anlage"], zeile["n_auftrag"]) == (2, 0, 0, 1)
    kunden.loeschen(con, k3, None)
    zeile = next(l for l in labels.liste(con) if l["id"] == lage["gross"])
    assert zeile["n_kunde"] == 1


# ---------- Filter ----------

def test_filter_in_den_listen(lage):
    con = lage["con"]
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    labels.setzen(con, "anlage", lage["a2"], [lage["gross"]], None)
    labels.setzen(con, "auftrag", lage["u2"], [lage["gross"]], None)
    assert [k["id"] for k in kunden.liste(con, label=lage["gross"])] == [lage["k1"]]
    assert kunden.liste(con, label=lage["schluessel"]) == []
    assert len(kunden.liste(con)) == 2
    assert [a["id"] for a in anlagen.liste(con, label=lage["gross"])] == [lage["a2"]]
    assert [u["id"] for u in auftraege.liste(con, "alle", label=lage["gross"])] == [lage["u2"]]
    # Label an einem Kunden gilt nicht für dessen Anlagen
    assert lage["a1"] not in [a["id"] for a in anlagen.liste(con, label=lage["gross"])]
    # Filter kombiniert mit Suche
    assert anlagen.liste(con, "Lindenweg", label=lage["schluessel"]) == []
    assert auftraege.woche(con, date.today().isoformat(), "alle", label=lage["gross"])


# ---------- Web ----------

def test_web_verwaltung_anlegen_aendern_loeschen(lage):
    c, con = lage["c"], lage["con"]
    anmelden(c)
    seite = c.get("/verwaltung/labels")
    assert seite.status_code == 200 and "Großkunde" in seite.text and "Labels" in seite.text
    t = csrf_aus(seite.text)
    r = c.post("/verwaltung/labels/neu", data={"name": "Neukunde", "farbe": "violett", "csrf_token": t},
               follow_redirects=False)
    assert r.status_code == 303 and "angelegt" in r.headers["location"]
    r = c.post("/verwaltung/labels/neu", data={"name": "neukunde", "farbe": "rot", "csrf_token": t})
    assert r.status_code == 400 and "schon" in r.text
    neu = next(l for l in labels.liste(con) if l["name"] == "Neukunde")["id"]
    assert "Label bearbeiten" in c.get(f"/verwaltung/labels/{neu}").text
    r = c.post(f"/verwaltung/labels/{neu}", data={"name": "Neukunde 2026", "farbe": "gelb", "csrf_token": t},
               follow_redirects=False)
    assert r.status_code == 303 and labels.holen(con, neu)["name"] == "Neukunde 2026"
    labels.setzen(con, "kunde", lage["k1"], [neu], None)
    r = c.post(f"/verwaltung/labels/{neu}/loeschen", data={"csrf_token": t}, follow_redirects=False)
    assert r.status_code == 303 and "anzahl=1" in r.headers["location"]
    assert labels.holen(con, neu) is None
    assert c.get("/verwaltung/labels/gibt-es-nicht", follow_redirects=False).status_code == 303


def test_web_anhaken_und_anzeigen_je_art(lage):
    c, con = lage["c"], lage["con"]
    anmelden(c)
    pfade = {"kunde": ("kunden", lage["k1"]), "objekt": ("objekte", lage["o1"]), "anlage": ("anlagen", lage["a1"]),
             "auftrag": ("auftraege", lage["u1"])}
    for art, (pfad, i) in pfade.items():
        seite = c.get(f"/{pfad}/{i}")
        assert seite.status_code == 200 and "Labels speichern" in seite.text and "Großkunde" in seite.text
        t = csrf_aus(seite.text)
        r = c.post(f"/{pfad}/{i}/labels", data={"label": [lage["gross"]], "csrf_token": t}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == f"/{pfad}/{i}#labels"
        assert namen(labels.von(con, art, i)) == ["Großkunde"]
        assert 'value="%s" checked' % lage["gross"] in c.get(f"/{pfad}/{i}").text
        c.post(f"/{pfad}/{i}/labels", data={"csrf_token": t})  # nichts angehakt = alle entfernt
        assert labels.von(con, art, i) == []
    # unbekannte Datensätze und Labels
    t = csrf_aus(c.get("/kunden").text)
    assert c.post("/kunden/gibt-es-nicht/labels", data={"csrf_token": t}, follow_redirects=False).status_code == 303
    c.post(f"/kunden/{lage['k1']}/labels", data={"label": ["gibt-es-nicht"], "csrf_token": t})
    assert labels.von(con, "kunde", lage["k1"]) == []


def test_web_listen_zeigen_chips_und_filtern(lage):
    c, con = lage["c"], lage["con"]
    anmelden(c)
    labels.setzen(con, "kunde", lage["k1"], [lage["gross"]], None)
    labels.setzen(con, "anlage", lage["a1"], [lage["gross"]], None)
    labels.setzen(con, "auftrag", lage["u1"], [lage["gross"]], None)
    for pfad, mit, ohne in (("/kunden", "Erste Verwaltung", "Zweite Verwaltung"),
                            ("/anlagen", lage["a1"], lage["a2"]), ("/auftraege", lage["u1"], lage["u2"])):
        alle = c.get(pfad).text
        assert 'class="etikett f-rot">Großkunde' in alle
        assert "alle Labels" in alle
        gefiltert = c.get(f"{pfad}?label={lage['gross']}").text
        assert "zurücksetzen" in gefiltert
        sicht = {"/anlagen": lambda x: f"/anlagen/{x}", "/auftraege": lambda x: f"/auftraege/{x}"}.get(pfad, lambda x: x)
        assert sicht(mit) in gefiltert and sicht(ohne) not in gefiltert
    assert "Keine Kunden gefunden" in c.get(f"/kunden?label={lage['schluessel']}").text
    woche = c.get(f"/auftraege?ansicht=woche&label={lage['gross']}")
    assert woche.status_code == 200 and f"label={lage['gross']}" in woche.text  # bleibt beim Blättern erhalten
    # unbekannter Filterwert bricht nichts
    assert c.get("/kunden?label=gibt-es-nicht").status_code == 200


def test_web_rechte(lage):
    c, con = lage["c"], lage["con"]
    nutzer_mit_passwort(con, "Tom", "tom@example.org", [rolle_id(con, "techniker")])
    anmelden(c, "tom@example.org")
    t = csrf_aus(c.get("/").text)
    assert c.get("/verwaltung/labels", follow_redirects=False).status_code in (303, 403)
    assert c.post("/verwaltung/labels/neu", data={"name": "X", "farbe": "rot", "csrf_token": t},
                  follow_redirects=False).status_code in (303, 403)
    for pfad in (f"/kunden/{lage['k1']}/labels", f"/anlagen/{lage['a1']}/labels", f"/auftraege/{lage['u1']}/labels"):
        c.post(pfad, data={"label": [lage["gross"]], "csrf_token": t}, follow_redirects=False)
    assert all(not labels.von(con, a, i) for a, i in (("kunde", lage["k1"]), ("anlage", lage["a1"]),
                                                      ("auftrag", lage["u1"])))
