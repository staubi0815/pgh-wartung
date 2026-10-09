"""Excel-Import (Foxtag-Vorlagenformat): Lesen, Umwandeln, Probelauf, alles-oder-nichts, Doppelte, Reihenfolge."""
import io
from datetime import datetime

import openpyxl
import pytest

from wartung import anlagen, anlagenart, excel_import as imp, gruppen, komponenten, kunden, objekte, typen
from wartung.felder import Ungueltig

RWM = anlagenart.holen("rauchwarnmelder")


def xlsx(kopf, *zeilen, blatt="Tabelle1"):
    """Erzeugt eine Excel-Datei im Speicher (wie die Foxtag-Vorlagen: Kopfzeile, dann Daten)."""
    mappe = openpyxl.Workbook()
    ws = mappe.active
    ws.title = blatt
    ws.append(kopf)
    for z in zeilen:
        ws.append(list(z))
    puffer = io.BytesIO()
    mappe.save(puffer)
    return puffer.getvalue()


KUNDEN_KOPF = ["KUNDEN.NUMMER*", "KUNDE.NAME*", "ADRESSZEILE 1", "ADRESSZEILE 2", "PLZ", "ORT", "LAND", "NOTIZ"]
RWM_KOPF = ["GRUPPE.NUMMER", "GRUPPE.NAME", "NUMMER*", "SUB-NUMMER", "TYP.NAME*", "TYP.HERSTELLER", "TYP.MODELL",
            "STANDORT", "SERIENNUMMER", "QR-CODE", "BAUJAHR", "LABEL", "LABEL2", "LETZTE PRÜFUNG", "INBETRIEBNAHME AM"]


@pytest.fixture
def con(umgebung):
    return umgebung[1]


def anzahl(con, tabelle):
    return con.execute(f"SELECT COUNT(*) FROM {tabelle} WHERE geloescht = 0").fetchone()[0]


# ---------- Werte umwandeln ----------

def test_zellwerte():
    assert imp.text(10012.0) == "10012" and imp.text(20099) == "20099" and imp.text("  a \n b ") == "a b"
    assert imp.text(None) == "" and imp.text(datetime(2016, 11, 17)) == "2016-11-17"
    assert imp.datum(datetime(2014, 1, 12)) == "2014-01-12"
    assert imp.datum("17.11.2016") == imp.datum("2016-11-17") == imp.datum("17.11.16") == "2016-11-17"
    with pytest.raises(Ungueltig):
        imp.datum("11/17/2016")
    assert imp.land("Deutschland") == "DE" and imp.land("") == "DE" and imp.land("at") == "AT"
    assert imp.plz(1067, "DE") == "01067" and imp.plz(1010, "AT") == "1010"
    assert imp.wohnungsname("Friedrich, 1.OG Mitte") == ("Friedrich", "1.OG Mitte")
    assert imp.wohnungsname("EG links") == ("", "EG links")


# ---------- Datei lesen ----------

def test_keine_excel_datei_und_zu_gross():
    with pytest.raises(imp.DateiFehler, match="keine lesbare Excel"):
        imp.lesen(b"Name;Ort\nA;B")
    with pytest.raises(imp.DateiFehler, match="größer"):
        imp.lesen(b"0" * (imp.MAX_BYTES + 1))


def test_kopfzeile_leerzeilen_und_hinweisspalten():
    inhalt = xlsx(["OBJEKT.NUMMER*", "WARTUNGSANWENDUNG.NUMMER*", "ANLAGE.NUMMER*", None, "Hinweis: …"],
                  ["O-1", "RWM", "ANL-9", None, "Weitere Hinweise"], [None] * 5, [None, None, None, None, "https://…"])
    kopf, zeilen = imp.lesen(inhalt)
    assert kopf[:3] == ["OBJEKT.NUMMER", "WARTUNGSANWENDUNG.NUMMER", "ANLAGE.NUMMER"]
    assert [nr for nr, _ in zeilen] == [2, 4]  # Leerzeile übersprungen, Hinweiszeile wird später ignoriert


def test_pflichtspalten_fehlen(con):
    with pytest.raises(imp.DateiFehler, match="Pflichtspalten fehlen: KUNDE.NAME"):
        imp.pruefen(con, "kunden", xlsx(["KUNDEN.NUMMER"], ["K1"]), None)


# ---------- Kunden: Probelauf, Übernahme, Doppelte ----------

def test_probelauf_speichert_nichts_uebernehmen_schon(con):
    inhalt = xlsx(KUNDEN_KOPF, ["K1", "Kunde 1 GmbH", "Danziger Str. 36", None, 20099, "Hamburg", "DE", "Testnotiz"],
                  [10012, "Kunde 2 GmbH", "Hauptstr. 5", "z. Hd. Technik", 1067, "Dresden", "Deutschland", None])
    vorschau = imp.pruefen(con, "kunden", inhalt, None)
    assert vorschau.ok and [z.status for z in vorschau.zeilen] == ["neu", "neu"] and not vorschau.gespeichert
    assert anzahl(con, "kunde") == 0
    assert con.execute("SELECT naechste FROM nummernkreis WHERE art = 'kunde'").fetchone()[0] == 1
    ergebnis = imp.uebernehmen(con, "kunden", inhalt, "n1", {"kundenart": "weg"}, "kunden.xlsx")
    assert ergebnis.gespeichert
    k2 = con.execute("SELECT * FROM kunde WHERE nummer = '10012'").fetchone()
    assert (k2["plz"], k2["land"], k2["zusatz"], k2["art"], k2["erstellt_von"]) == \
        ("01067", "DE", "z. Hd. Technik", "weg", "n1")
    assert "kunden.xlsx: 2 neu, 0 vorhanden" in con.execute(
        "SELECT neu FROM aenderungsprotokoll WHERE aktion = 'import'").fetchone()[0]
    # zweiter Import derselben Datei: nichts doppelt, nichts überschrieben
    nochmal = imp.uebernehmen(con, "kunden", inhalt, None)
    assert [z.status for z in nochmal.zeilen] == ["vorhanden", "vorhanden"] and anzahl(con, "kunde") == 2


def test_ein_fehler_nichts_gespeichert(con):
    inhalt = xlsx(KUNDEN_KOPF, ["K1", "Gut GmbH", None, None, 90402, "Nürnberg", "DE", None],
                  ["K2", "Schlecht GmbH", None, None, 123, "Nürnberg", "DE", None],
                  ["k1", "Doppelt GmbH", None, None, None, None, None, None])
    ergebnis = imp.uebernehmen(con, "kunden", inhalt, None)
    assert not ergebnis.gespeichert and anzahl(con, "kunde") == 0
    status = {z.nr: (z.status, z.meldungen) for z in ergebnis.zeilen}
    assert status[2][0] == "neu" and status[3] == ("fehler", ["PLZ: in Deutschland fünf Ziffern."])
    assert status[4] == ("fehler", ["Doppelt in der Datei (wie Zeile 2)."])


# ---------- Reihenfolge Kunden -> Kontakte -> Objekte -> Anlagen ----------

def test_kette_bis_anlage(con):
    imp.uebernehmen(con, "kunden", xlsx(KUNDEN_KOPF, ["DEMO-1", "Beispiel GmbH", "Weg 1", None, 20099, "Hamburg",
                                                      "DE", None]), None)
    kontakt_kopf = ["NAME*", "FIRMA", "EMAIL", "TELEFON", "MOBIL", "FAX", "NOTIZ", "KUNDE"]
    peter = ["Peter Parker", "Beispiel GmbH", "max@example.com", "040 / 1231234", "0171 / 1231234", "040 / 2222222",
             "Beispiel-Kontakt", "DEMO-1"]
    e = imp.uebernehmen(con, "kontakte", xlsx(kontakt_kopf, peter, ["Niemand"] + [None] * 6 + ["GIBT-ES-NICHT"]), None)
    assert not e.gespeichert and "zuerst Kunden importieren" in e.zeilen[1].meldungen[0]
    assert imp.uebernehmen(con, "kontakte", xlsx(kontakt_kopf, peter), None).gespeichert
    assert con.execute("SELECT telefon FROM kontakt").fetchone()[0] == "040 / 1231234"
    objekte_datei = xlsx(["KUNDE.NUMMER", "OBJEKT.NAME", "OBJEKT.NUMMER", "ADRESSZEILE 1", "ADRESSZEILE 2", "PLZ",
                          "ORT", "LAND"], ["DEMO-1", "Grundschule", 240, "Danziger Straße 36", "Hinterhaus", 20099,
                                           "Hamburg", "Deutschland"])
    e = imp.uebernehmen(con, "objekte", objekte_datei, None)
    assert e.gespeichert and e.zeilen[0].meldungen == ["Adresszeile 2 in die Notiz übernommen."]
    anlagen_kopf = ["OBJEKT.NUMMER*", "WARTUNGSANWENDUNG.NUMMER*", "ANLAGE.NUMMER*", "ANLAGE.NAME", "TECHNIKER.NUMMER"]
    e = imp.uebernehmen(con, "anlagen", xlsx(anlagen_kopf, [240, "RWA", "RWA-1", None, None]), None)
    assert not e.gespeichert and "unbekannt" in e.zeilen[0].meldungen[0]
    e = imp.uebernehmen(con, "anlagen", xlsx(anlagen_kopf, [240, "RWM", "ANL-RWM-1", "Haus A", "PERSONAL-1"]), None)
    assert e.gespeichert and "Techniker" in e.zeilen[0].meldungen[0]
    a = con.execute("SELECT * FROM anlage").fetchone()
    assert (a["nummer"], a["anlagenart"], a["bezeichnung"]) == ("ANL-RWM-1", "rauchwarnmelder", "Haus A")


# ---------- Melder einer Anlage ----------

@pytest.fixture
def anlage(con):
    k = kunden.anlegen(con, {"art": "hausverwaltung", "name": "Muster"}, None)
    o = objekte.anlegen(con, k, {"bezeichnung": "Haus", "adresse_wie_kunde": "1"}, None)
    return anlagen.holen(con, anlagen.anlegen(con, o, {"anlagenart": "rauchwarnmelder", "verfahren": "A"}, None))


def rwm_datei(*zusatz):
    return xlsx(RWM_KOPF,
                [36, "Friedrich, 1.OG Mitte", 1, 0, "Rauchwarnmelder", "Ei Electronics", "Ei650", "Flur", "90024-1",
                 None, 2014, None, None, datetime(2016, 11, 17), datetime(2014, 1, 12)],
                [36, "Friedrich, 1.OG Mitte", 2, 0, "Rauchwarnmelder", "Ei Electronics", "Ei650", "Kinderzimmer",
                 "90024-2", None, 2014, None, None, "17.11.2016", "12.01.2014"],
                [43, "Reineke, 2.OG links", 1, 0, "Rauchwarnmelder", "Gira", "Basic Q", "Flur", 7461295, "QR-43-1",
                 2000, "10J", None, datetime(2016, 11, 17), datetime(2009, 5, 15)], *zusatz, blatt="Rauchwarnmelder")


def test_melder_import(con, anlage):
    with pytest.raises(imp.DateiFehler, match="Anlage wählen"):
        imp.pruefen(con, "komponenten", rwm_datei(), None, {})
    e = imp.uebernehmen(con, "komponenten", rwm_datei(), None, {"anlage": anlage})
    assert e.gespeichert and [z.status for z in e.zeilen] == ["neu"] * 3
    assert "Typ neu im Katalog angelegt." in e.zeilen[0].meldungen and "Typ neu im Katalog angelegt." not in \
        e.zeilen[1].meldungen  # zweiter Ei650 nutzt denselben Typ
    assert "Labels werden noch nicht übernommen." in e.zeilen[2].meldungen
    assert [t["bezeichnung"] for t in typen.liste(con)] == ["Ei650", "Basic Q"]
    g36 = con.execute("SELECT * FROM gruppe WHERE nummer = 36").fetchone()
    assert (g36["bewohner"], g36["bezeichnung"]) == ("Friedrich", "1.OG Mitte")
    m = con.execute("SELECT * FROM komponente WHERE seriennummer = '7461295'").fetchone()
    assert (m["raum"], m["raumart"], m["barcode"], m["baujahr"], m["letzte_pruefung_am"], m["inbetriebnahme_am"]) == \
        ("Flur", "flur_rettungsweg", "QR-43-1", 2000, "2016-11-17", "2009-05-15")
    assert (m["naechste_pruefung_am"], m["austausch_faellig_am"]) == ("2017-11-17", "2010-01-01")
    # nochmal: alles vorhanden
    assert [z.status for z in imp.uebernehmen(con, "komponenten", rwm_datei(), None, {"anlage": anlage}).zeilen] == \
        ["vorhanden"] * 3


def test_melder_import_fehler(con, anlage):
    typ = typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": "Alt", "hersteller": "X",
                              "kategorie": "komponente", "funk": "keine", "batterie": "fest_10j", "aktiv": ""}, None)
    assert typ
    e = imp.uebernehmen(con, "komponenten", rwm_datei(
        [50, None, 1, 1, "Rauchwarnmelder", "Ei Electronics", "Ei650", None, None, None, None, None, None, None, None],
        [51, None, 1, 0, "Alt", "X", None, None, None, None, None, None, None, None, None],
        [52, None, 1, 0, "Rauchwarnmelder", "Ei Electronics", "Ei650", None, None, None, None, None, None, "gestern",
         None],
        [36, None, 1, 0, "Rauchwarnmelder", "Ei Electronics", "Ei650", None, None, None, None, None, None, None, None]),
        None, {"anlage": anlage})
    assert not e.gespeichert and anzahl(con, "komponente") == 0 and anzahl(con, "gruppe") == 0
    meldungen = {z.nr: z.meldungen for z in e.zeilen if z.status == "fehler"}
    assert "Sub-Komponenten" in meldungen[5][0]
    assert "deaktiviert" in meldungen[6][0]
    assert "nicht lesbar" in meldungen[7][0]
    assert meldungen[8] == ["Doppelt in der Datei (wie Zeile 2)."]


def test_vorhandene_wohnung_wird_genutzt_und_nicht_geaendert(con, anlage):
    gid = gruppen.anlegen(con, RWM, anlage["id"], {"nummer": "36", "bezeichnung": "Original", "zugang": "frei"}, None)
    imp.uebernehmen(con, "komponenten", rwm_datei(), None, {"anlage": anlage})
    assert gruppen.holen(con, gid)["bezeichnung"] == "Original"
    assert len(komponenten.je_gruppe(con, anlage["id"], RWM)[gid]) == 2


def test_typen_import(con):
    kopf = ["TYP.NAME*", "TYP.HERSTELLER", "TYP.MODELL", "TYP.KATEGORIE*", "TYP.LINK"]
    e = imp.uebernehmen(con, "typen", xlsx(kopf, ["Rauchwarnmelder", "Ei Electronics", "Ei650iW", "Komponente",
                                                  "https://example.org/ei650iw"],
                                           ["Sockel", None, None, "Sub-Komponente", None],
                                           ["X", None, None, "Bauteil", None]), None)
    assert not e.gespeichert and "Kategorie" in e.zeilen[2].meldungen[0]
    e = imp.uebernehmen(con, "typen", xlsx(kopf, ["Rauchwarnmelder", "Ei Electronics", "Ei650iW", "Komponente",
                                                  "https://example.org/ei650iw"]), None)
    assert e.gespeichert and typen.finden(con, "rauchwarnmelder", "", "ei electronics", "EI650IW")["bezeichnung"] == \
        "Ei650iW"
