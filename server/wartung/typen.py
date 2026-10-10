"""Komponententypen (Katalog je Anlagenart, z. B. Melder-Modelle): Felder, Liste, Anlegen, Ändern.

Typen werden nicht gelöscht, sondern deaktiviert, sobald Komponenten sie benutzen (Nachweis: welcher Melder war
verbaut). Ändern sich die Austauschjahre, werden die Fälligkeiten aller Komponenten dieses Typs neu berechnet. Doppelte Typen lassen sich
zu einem zusammenführen.
"""
from . import anlagenart, db, faelligkeit
from .felder import Feld, Ungueltig, einlesen

KATEGORIEN = (("komponente", "Komponente"), ("sub_komponente", "Sub-Komponente (Teil einer Komponente)"))
FUNK = (("keine", "kein Funk"), ("wmbus", "Funk wM-Bus (Ferninspektion)"), ("lorawan", "Funk LoRaWAN"))
BATTERIE = (("fest_10j", "fest eingebaut (10 Jahre)"), ("wechselbar", "wechselbar"))


def _felder():
    return (
        Feld("bezeichnung", "Bezeichnung", pflicht=True, max_laenge=80, platzhalter="z. B. Ei650",
             hilfe="so erscheint der Typ in Listen und im Bericht (Foxtag: TYP.NAME)"),
        Feld("hersteller", "Hersteller", max_laenge=80, platzhalter="z. B. Ei Electronics"),
        Feld("modell", "Modell", max_laenge=80),
        Feld("kategorie", "Kategorie", "auswahl", pflicht=True, auswahl=KATEGORIEN),
        Feld("zulassungsnummer", "Zulassungs-/Prüfnummer", max_laenge=80),
        Feld("funk", "Funk", "auswahl", pflicht=True, auswahl=FUNK),
        Feld("batterie", "Batterie", "auswahl", pflicht=True, auswahl=BATTERIE),
        Feld("austausch_jahre", "Austausch nach Jahren", "zahl", minimum=1, maximum=30,
             hilfe="leer = Vorgabe der Anlagenart"),
        Feld("datenblatt_link", "Link zum Datenblatt", max_laenge=500, breit=True, platzhalter="https://…"),
        Feld("aktiv", "aktiv (bei neuen Komponenten auswählbar)", "ja_nein", breit=True),
    )


def felder_neu():
    arten = tuple((a.schluessel, a.name) for a in anlagenart.alle().values())
    return (Feld("anlagenart", "Anlagenart", "auswahl", pflicht=True, auswahl=arten), *_felder())


def felder_bearbeiten():
    return _felder()


def liste(con, art=""):
    """Typen mit Anzahl verbauter Komponenten, aktive zuerst."""
    sql = ("SELECT t.*, (SELECT COUNT(*) FROM komponente c WHERE c.komponententyp_id = t.id AND c.geloescht = 0 "
           "  AND c.status = 'verbaut') AS verbaut FROM komponententyp t WHERE t.geloescht = 0")
    parameter = []
    if art:
        sql += " AND t.anlagenart = ?"
        parameter.append(art)
    return con.execute(sql + " ORDER BY t.aktiv DESC, t.hersteller COLLATE NOCASE, t.bezeichnung COLLATE NOCASE",
                       parameter).fetchall()


def auswahl(con, art, auch_id=None):
    """(id, Anzeigetext) der aktiven Typen einer Anlagenart – plus ggf. der bisherige (auch wenn inaktiv)."""
    zeilen = con.execute(
        "SELECT id, bezeichnung, hersteller FROM komponententyp WHERE geloescht = 0 AND anlagenart = ? "
        "AND (aktiv = 1 OR id = ?) ORDER BY hersteller COLLATE NOCASE, bezeichnung COLLATE NOCASE",
        (art, auch_id or "")).fetchall()
    return tuple((z["id"], f"{z['bezeichnung']} ({z['hersteller']})" if z["hersteller"] else z["bezeichnung"])
                 for z in zeilen)


def holen(con, typ_id):
    return con.execute("SELECT * FROM komponententyp WHERE id = ? AND geloescht = 0", (typ_id,)).fetchone()


def _pruefen(con, felder, form, anlagenart_schluessel, eigene_id=None):
    werte, fehler = einlesen(felder, form)
    link = werte.get("datenblatt_link") or ""
    if link and not link.startswith(("https://", "http://")):
        fehler["datenblatt_link"] = "Link bitte mit https:// angeben."
    if werte.get("bezeichnung") and con.execute(
            "SELECT 1 FROM komponententyp WHERE anlagenart = ? AND bezeichnung = ? COLLATE NOCASE AND geloescht = 0 "
            "AND id != ?", (anlagenart_schluessel, werte["bezeichnung"], eigene_id or "")).fetchone():
        fehler["bezeichnung"] = "Einen Typ mit dieser Bezeichnung gibt es schon."
    if fehler:
        raise Ungueltig(fehler)
    return werte


def anlegen(con, form, nutzer_id):
    werte = _pruefen(con, felder_neu(), form, form.get("anlagenart"))
    return db.anlegen(con, "komponententyp", werte, nutzer_id)


def aendern(con, typ_id, form, nutzer_id):
    typ = holen(con, typ_id)
    werte = _pruefen(con, felder_bearbeiten(), form, typ["anlagenart"], typ_id)
    with db.transaktion(con):
        anzahl = db.aendern(con, "komponententyp", typ_id, werte, nutzer_id)
        if werte["austausch_jahre"] != typ["austausch_jahre"]:
            faelligkeit.typ_berechnen(con, typ_id)
    return anzahl


def ziele_zum_zusammenfuehren(con, typ_id):
    """(id, Anzeigetext) der anderen Typen derselben Anlagenart – auch inaktive."""
    typ = holen(con, typ_id)
    zeilen = con.execute(
        "SELECT id, bezeichnung, hersteller FROM komponententyp WHERE geloescht = 0 AND anlagenart = ? AND id != ? "
        "ORDER BY hersteller COLLATE NOCASE, bezeichnung COLLATE NOCASE", (typ["anlagenart"], typ_id)).fetchall()
    return tuple((z["id"], f"{z['bezeichnung']} ({z['hersteller']})" if z["hersteller"] else z["bezeichnung"])
                 for z in zeilen)


def komponenten_zaehlen(con, typ_id):
    """Alle Komponenten mit diesem Typ, auch ausgebaute."""
    return con.execute("SELECT COUNT(*) FROM komponente WHERE komponententyp_id = ? AND geloescht = 0",
                       (typ_id,)).fetchone()[0]


def zusammenfuehren(con, quelle_id, ziel_id, nutzer_id):
    """Überträgt alle Komponenten (auch ausgebaute) vom Quelltyp auf den Zieltyp und löscht den Quelltyp.
    Beide müssen zur selben Anlagenart gehören. Gibt die Anzahl übertragener Komponenten zurück."""
    with db.transaktion(con):
        quelle, ziel = holen(con, quelle_id), holen(con, ziel_id)
        if quelle is None or ziel is None:
            raise Ungueltig({"ziel_id": "Bitte einen Typ wählen."})
        if quelle["id"] == ziel["id"]:
            raise Ungueltig({"ziel_id": "Bitte einen anderen Typ wählen."})
        if quelle["anlagenart"] != ziel["anlagenart"]:
            raise Ungueltig({"ziel_id": "Die Typen gehören zu verschiedenen Anlagenarten."})
        ids = [z["id"] for z in con.execute("SELECT id FROM komponente WHERE komponententyp_id = ?", (quelle_id,))]
        for komponente_id in ids:
            db.aendern(con, "komponente", komponente_id, {"komponententyp_id": ziel_id}, nutzer_id)
        db.protokoll(con, nutzer_id, "komponententyp", quelle_id, "zusammenfuehren", "komponententyp_id",
                     quelle_id, ziel_id)
        db.aendern(con, "komponententyp", quelle_id, {"geloescht": 1, "aktiv": 0}, nutzer_id)
        faelligkeit.typ_berechnen(con, ziel_id)
    return len(ids)


def finden(con, art_schluessel, name, hersteller="", modell=""):
    """Sucht einen vorhandenen Typ für Angaben aus einer Importdatei (Foxtag: TYP.NAME, TYP.HERSTELLER, TYP.MODELL).

    Reihenfolge: Hersteller + Modell gleich; sonst Bezeichnung = Modell bzw. Name bei gleichem Hersteller.
    Groß-/Kleinschreibung zählt nicht. Gibt die Zeile oder None zurück.
    """
    kandidaten = con.execute("SELECT * FROM komponententyp WHERE anlagenart = ? AND geloescht = 0 "
                             "ORDER BY aktiv DESC, erstellt_am", (art_schluessel,)).fetchall()
    h, m, n = (hersteller or "").strip().lower(), (modell or "").strip().lower(), (name or "").strip().lower()
    if m:
        for t in kandidaten:
            if t["hersteller"].lower() == h and t["modell"].lower() == m:
                return t
    for t in kandidaten:
        if t["hersteller"].lower() == h and t["bezeichnung"].lower() in {x for x in (m, n) if x}:
            return t
    return None
