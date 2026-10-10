"""Objekte (Gebäude beim Kunden): Felder, Anschrift, Anlegen, Ändern, Kunde wechseln, Löschen.

Die Anschrift eines Objekts ist entweder eine eigene oder „wie Kunde“ (z. B. Einfamilienhaus des Eigentümers).
Für Listen und Berichte zählt immer die wirksame Anschrift (ADRESSE_SQL).
"""
from . import db, nummern
from .felder import Feld, Ungueltig, adresse_pruefen, einlesen, fuer_bearbeiten

OBJEKT_FELDER = (
    Feld("nummer", "Objektnummer", max_laenge=nummern.MAX_LAENGE, hilfe="leer lassen = automatisch"),
    Feld("bezeichnung", "Bezeichnung", pflicht=True, platzhalter="z. B. Musterstraße 12 oder Wohnanlage Süd"),
    Feld("adresse_wie_kunde", "Anschrift wie beim Kunden", "ja_nein", breit=True),
    Feld("strasse", "Straße und Hausnummer"),
    Feld("plz", "PLZ", max_laenge=10),
    Feld("ort", "Ort"),
    Feld("land", "Land", max_laenge=2, platzhalter="DE"),
    Feld("zugangshinweise", "Zugangshinweise", "textarea", max_laenge=2000, breit=True,
         platzhalter="z. B. Schlüssel beim Hausmeister, Parken im Hof"),
    Feld("notiz", "Notiz", "textarea", max_laenge=4000, breit=True),
)

# Wirksame Anschrift in Abfragen mit „objekt o JOIN kunde k“
ADRESSE_SQL = ("CASE WHEN o.adresse_wie_kunde = 1 THEN k.strasse ELSE o.strasse END AS adr_strasse, "
               "CASE WHEN o.adresse_wie_kunde = 1 THEN k.plz ELSE o.plz END AS adr_plz, "
               "CASE WHEN o.adresse_wie_kunde = 1 THEN k.ort ELSE o.ort END AS adr_ort")


def holen(con, objekt_id):
    """Objekt mit Kunde (Nummer, Name) und wirksamer Anschrift, oder None."""
    return con.execute(
        f"SELECT o.*, k.nummer AS kunde_nummer, k.name AS kunde_name, {ADRESSE_SQL} "
        "FROM objekt o JOIN kunde k ON k.id = o.kunde_id WHERE o.id = ? AND o.geloescht = 0 AND k.geloescht = 0",
        (objekt_id,)).fetchone()


def liste_fuer_kunde(con, kunde_id):
    return con.execute(
        f"SELECT o.*, {ADRESSE_SQL}, "
        " (SELECT COUNT(*) FROM anlage a WHERE a.objekt_id = o.id AND a.geloescht = 0) AS anlagen "
        "FROM objekt o JOIN kunde k ON k.id = o.kunde_id "
        "WHERE o.kunde_id = ? AND o.geloescht = 0 ORDER BY o.bezeichnung COLLATE NOCASE", (kunde_id,)).fetchall()


def kunden_auswahl(con):
    """(id, „K0001 Name“) aller Kunden – für „Objekt einem anderen Kunden zuordnen“."""
    return tuple((k["id"], f"{k['nummer']} {k['name']}") for k in con.execute(
        "SELECT id, nummer, name FROM kunde WHERE geloescht = 0 ORDER BY name COLLATE NOCASE"))


def felder_bearbeiten(con):
    """Beim Bearbeiten zusätzlich: Kunde (Objekt kann den Eigentümer/Verwalter wechseln)."""
    return (Feld("kunde_id", "Kunde", "auswahl", pflicht=True, auswahl=kunden_auswahl(con), breit=True),
            *fuer_bearbeiten(OBJEKT_FELDER))


def pruefen(con, felder, form, eigene_id=None):
    werte, fehler = einlesen(felder, form)
    adresse_pruefen(werte, fehler, pflicht=not werte["adresse_wie_kunde"])
    if werte["nummer"]:
        fehler_nr = nummern.pruefen(con, "objekt", werte["nummer"], eigene_id)
        if fehler_nr:
            fehler["nummer"] = fehler_nr
    if fehler:
        raise Ungueltig(fehler)
    return werte


def anlegen(con, kunde_id, form, nutzer_id):
    werte = pruefen(con, OBJEKT_FELDER, form)
    with db.transaktion(con):
        werte["nummer"] = werte["nummer"] or nummern.naechste(con, "objekt")
        return db.anlegen(con, "objekt", {**werte, "kunde_id": kunde_id}, nutzer_id)


def aendern(con, objekt_id, form, nutzer_id):
    werte = pruefen(con, felder_bearbeiten(con), form, objekt_id)
    with db.transaktion(con):
        wechsel = con.execute("SELECT kunde_id FROM objekt WHERE id = ?", (objekt_id,)).fetchone()["kunde_id"] != werte["kunde_id"]
        anzahl = db.aendern(con, "objekt", objekt_id, werte, nutzer_id)
        if wechsel:  # Ansprechpartner des alten Kunden passen nicht mehr
            from . import anlagen  # spät, weil anlagen seinerseits objekte braucht
            for z in con.execute("SELECT id FROM anlage WHERE objekt_id = ? AND geloescht = 0", (objekt_id,)).fetchall():
                anlagen.kontakte_bereinigen(con, z["id"], nutzer_id)
    return anzahl


def loeschen(con, objekt_id, nutzer_id):
    """Markiert das Objekt als gelöscht – nur ohne aktive Anlagen."""
    with db.transaktion(con):
        if con.execute("SELECT 1 FROM anlage WHERE objekt_id = ? AND geloescht = 0", (objekt_id,)).fetchone():
            raise Ungueltig({"": "Das Objekt hat noch Anlagen. Bitte zuerst diese löschen."})
        db.aendern(con, "objekt", objekt_id, {"geloescht": 1}, nutzer_id)
