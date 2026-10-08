"""Komponententypen (Katalog je Anlagenart, z. B. Melder-Modelle): Felder, Liste, Anlegen, Ändern.

Typen werden nicht gelöscht, sondern deaktiviert, sobald Komponenten sie benutzen (Nachweis: welcher Melder war
verbaut). Ändern sich die Austauschjahre, werden die Fälligkeiten aller Komponenten dieses Typs neu berechnet.
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
