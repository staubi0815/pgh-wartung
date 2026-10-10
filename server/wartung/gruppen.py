"""Gruppen einer Anlage – bei Rauchwarnmeldern die Wohnungen, bei Türen später Geschosse/Bauteile.

Die Nummer ist je Anlage eindeutig und eine Zahl (Foxtag: GRUPPE.NUMMER). Bewohnername und -telefon sind
personenbezogene Daten: nur so viel wie nötig (Name am Klingelschild), siehe Löschkonzept.
"""
from . import db
from .felder import Feld, Ungueltig, einlesen

ZUGANG = (("frei", "frei zugänglich"), ("nur_termin", "nur nach Termin"), ("schluessel", "Schlüssel hinterlegt"))
MAX_NUMMER = 99999


def felder(art):
    """Felder mit den Bezeichnungen der Anlagenart („Wohnung“)."""
    return (
        Feld("nummer", f"{art.gruppe}-Nr.", "zahl", minimum=0, maximum=MAX_NUMMER, hilfe="leer = nächste freie"),
        Feld("bezeichnung", "Lage", platzhalter="z. B. 1. OG links"),
        Feld("bewohner", "Bewohner", hilfe="nur Name am Klingelschild"),
        Feld("bewohner_telefon", "Telefon Bewohner", "tel"),
        Feld("zugang", "Zugang", "auswahl", pflicht=True, auswahl=ZUGANG),
        Feld("link", "Link", "link", max_laenge=500, hilfe="z. B. Mieterportal oder Grundriss (https://…)"),
        Feld("notiz", "Notiz", "textarea", max_laenge=2000, breit=True),
    )


def holen(con, gruppe_id):
    """Gruppe mit Anlage (Nummer, Art, Kunde), nur wenn nichts davon gelöscht ist."""
    return con.execute(
        "SELECT g.*, a.nummer AS anlage_nummer, a.anlagenart, o.id AS objekt_id, o.bezeichnung AS objekt_bezeichnung, "
        "k.id AS kunde_id, k.name AS kunde_name FROM gruppe g JOIN anlage a ON a.id = g.anlage_id "
        "JOIN objekt o ON o.id = a.objekt_id JOIN kunde k ON k.id = o.kunde_id "
        "WHERE g.id = ? AND g.geloescht = 0 AND a.geloescht = 0 AND o.geloescht = 0 AND k.geloescht = 0",
        (gruppe_id,)).fetchone()


def liste(con, anlage_id):
    return con.execute(
        "SELECT g.*, (SELECT COUNT(*) FROM komponente c WHERE c.gruppe_id = g.id AND c.geloescht = 0 "
        "  AND c.status = 'verbaut') AS komponenten FROM gruppe g WHERE g.anlage_id = ? AND g.geloescht = 0 "
        "ORDER BY g.nummer", (anlage_id,)).fetchall()


def anzahl_komponenten(con, gruppe_id):
    return con.execute("SELECT COUNT(*) FROM komponente WHERE gruppe_id = ? AND geloescht = 0 AND status = 'verbaut'",
                       (gruppe_id,)).fetchone()[0]


def naechste_nummer(con, anlage_id):
    zeile = con.execute("SELECT MAX(nummer) FROM gruppe WHERE anlage_id = ? AND geloescht = 0",
                        (anlage_id,)).fetchone()
    return (zeile[0] or 0) + 1


def _pruefen(con, art, anlage_id, form, eigene_id=None):
    werte, fehler = einlesen(felder(art), form)
    if werte["nummer"] is not None and con.execute(
            "SELECT 1 FROM gruppe WHERE anlage_id = ? AND nummer = ? AND geloescht = 0 AND id != ?",
            (anlage_id, werte["nummer"], eigene_id or "")).fetchone():
        fehler["nummer"] = f"{art.gruppe} {werte['nummer']} gibt es in dieser Anlage schon."
    if eigene_id and werte["nummer"] is None:
        fehler["nummer"] = f"{art.gruppe}-Nr. ist Pflicht."
    if fehler:
        raise Ungueltig(fehler)
    return werte


def anlegen(con, art, anlage_id, form, nutzer_id):
    with db.transaktion(con):  # Nummernprüfung und Anlegen ohne Lücke für einen zweiten Nutzer
        werte = _pruefen(con, art, anlage_id, form)
        if werte["nummer"] is None:
            werte["nummer"] = naechste_nummer(con, anlage_id)
        return db.anlegen(con, "gruppe", {**werte, "anlage_id": anlage_id}, nutzer_id)


def aendern(con, art, gruppe_id, form, nutzer_id):
    g = holen(con, gruppe_id)
    with db.transaktion(con):
        werte = _pruefen(con, art, g["anlage_id"], form, gruppe_id)
        return db.aendern(con, "gruppe", gruppe_id, werte, nutzer_id)


def loeschen(con, art, gruppe_id, nutzer_id):
    """Markiert die Gruppe als gelöscht – nur ohne verbaute Komponenten und nicht, solange sie im Umfang eines
    offenen Auftrags steht."""
    with db.transaktion(con):
        if con.execute("SELECT 1 FROM auftrag_gruppe z JOIN auftrag u ON u.id = z.auftrag_id WHERE z.gruppe_id = ? "
                       "AND z.geloescht = 0 AND u.geloescht = 0 AND u.status IN ('in_planung', 'geplant', 'aktiv')",
                       (gruppe_id,)).fetchone():
            raise Ungueltig({"auftraege": f"Die {art.gruppe} steht in einem offenen Auftrag."})
        if con.execute("SELECT 1 FROM komponente WHERE gruppe_id = ? AND geloescht = 0 AND status = 'verbaut'",
                       (gruppe_id,)).fetchone():
            raise Ungueltig({"": f"Hier sind noch {art.komponente_mehrzahl} verbaut. "
                                 f"Bitte zuerst diese ausbauen oder löschen."})
        db.aendern(con, "gruppe", gruppe_id, {"geloescht": 1}, nutzer_id)
