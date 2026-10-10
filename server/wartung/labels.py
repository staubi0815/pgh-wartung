"""Labels: frei benennbare Etiketten mit Farbe an Kunde, Objekt, Anlage und Auftrag (Vorbild Foxtag).

Ein Label wird in der Verwaltung gepflegt und an den Datensätzen angehakt. Löschen markiert das Label und alle seine
Zuordnungen als gelöscht. Listen filtern über filter_sql().
"""
from . import db
from .felder import Feld, Ungueltig, einlesen

ARTEN = ("kunde", "objekt", "anlage", "auftrag")
FARBEN = (("grau", "grau"), ("rot", "rot"), ("orange", "orange"), ("gelb", "gelb"), ("gruen", "grün"),
          ("blau", "blau"), ("violett", "violett"))
FELDER = (
    Feld("name", "Name", pflicht=True, max_laenge=40, platzhalter="z. B. Großkunde, Schlüssel im Büro"),
    Feld("farbe", "Farbe", "auswahl", pflicht=True, auswahl=FARBEN),
)
_TABELLE = {"kunde": "kunde", "objekt": "objekt", "anlage": "anlage", "auftrag": "auftrag"}


def holen(con, label_id):
    return con.execute("SELECT * FROM label WHERE id = ? AND geloescht = 0", (label_id,)).fetchone()


def liste(con):
    """Alle Labels mit der Anzahl ihrer Verwendungen je Art (gelöschte Datensätze zählen nicht)."""
    zaehler = ", ".join(
        f"(SELECT COUNT(*) FROM label_zuordnung z JOIN {t} d ON d.id = z.datensatz_id AND d.geloescht = 0 "
        f"WHERE z.label_id = l.id AND z.art = '{art}' AND z.geloescht = 0) AS n_{art}"
        for art, t in _TABELLE.items())
    return con.execute(f"SELECT l.*, {zaehler} FROM label l WHERE l.geloescht = 0 ORDER BY l.name COLLATE NOCASE"
                       ).fetchall()


def auswahl(con):
    """Alle Labels für Auswahllisten und Filter."""
    return con.execute("SELECT id, name, farbe FROM label WHERE geloescht = 0 ORDER BY name COLLATE NOCASE").fetchall()


def _pruefen(con, form, eigene_id=None):
    werte, fehler = einlesen(FELDER, form)
    if werte.get("name") and con.execute("SELECT 1 FROM label WHERE name = ? COLLATE NOCASE AND geloescht = 0 "
                                         "AND id != ?", (werte["name"], eigene_id or "")).fetchone():
        fehler["name"] = "Ein Label mit diesem Namen gibt es schon."
    if fehler:
        raise Ungueltig(fehler)
    return werte


def anlegen(con, form, nutzer_id):
    return db.anlegen(con, "label", _pruefen(con, form), nutzer_id)


def aendern(con, label_id, form, nutzer_id):
    return db.aendern(con, "label", label_id, _pruefen(con, form, label_id), nutzer_id)


def loeschen(con, label_id, nutzer_id):
    """Markiert das Label und alle seine Zuordnungen als gelöscht. Gibt die Anzahl gelöster Zuordnungen zurück."""
    with db.transaktion(con):
        ids = [z["id"] for z in con.execute("SELECT id FROM label_zuordnung WHERE label_id = ? AND geloescht = 0",
                                            (label_id,))]
        for zid in ids:
            db.aendern(con, "label_zuordnung", zid, {"geloescht": 1}, nutzer_id)
        db.aendern(con, "label", label_id, {"geloescht": 1}, nutzer_id)
    return len(ids)


def fuer(con, art, ids):
    """Labels je Datensatz: {datensatz_id: [Label, …]} nach Name sortiert; Datensätze ohne Label fehlen."""
    ids = list(ids)
    ergebnis = {}
    for i in range(0, len(ids), 500):
        teil = ids[i:i + 500]
        for z in con.execute(
                "SELECT z.datensatz_id, l.id, l.name, l.farbe FROM label_zuordnung z JOIN label l ON l.id = z.label_id "
                f"WHERE z.art = ? AND z.geloescht = 0 AND l.geloescht = 0 AND z.datensatz_id IN ({','.join('?' * len(teil))}) "
                "ORDER BY l.name COLLATE NOCASE", (art, *teil)):
            ergebnis.setdefault(z["datensatz_id"], []).append(z)
    return ergebnis


def von(con, art, datensatz_id):
    return fuer(con, art, [datensatz_id]).get(datensatz_id, [])


def setzen(con, art, datensatz_id, label_ids, nutzer_id):
    """Setzt die Labels eines Datensatzes auf genau die angegebenen (fehlende kommen dazu, abgewählte fallen weg).
    Unbekannte oder gelöschte Label-ids werden abgelehnt. Gibt (hinzugefügt, entfernt) zurück."""
    if art not in ARTEN:
        raise ValueError(f"unbekannte Art {art!r}")
    gewuenscht = set(label_ids)
    with db.transaktion(con):
        bekannt = {l["id"] for l in auswahl(con)}
        if not gewuenscht <= bekannt:
            raise Ungueltig({"labels": "Ein gewähltes Label gibt es nicht (mehr)."})
        aktuell = {z["label_id"]: z["id"] for z in con.execute(
            "SELECT id, label_id FROM label_zuordnung WHERE art = ? AND datensatz_id = ? AND geloescht = 0",
            (art, datensatz_id))}
        for lid in sorted(gewuenscht - set(aktuell)):
            db.anlegen(con, "label_zuordnung", {"label_id": lid, "art": art, "datensatz_id": datensatz_id}, nutzer_id)
        for lid in sorted(set(aktuell) - gewuenscht):
            db.aendern(con, "label_zuordnung", aktuell[lid], {"geloescht": 1}, nutzer_id)
    return len(gewuenscht - set(aktuell)), len(set(aktuell) - gewuenscht)


def filter_sql(art, spalte):
    """SQL-Teil „… hat Label ?“ für Listen; Parameter ist die Label-id. spalte: id-Spalte des Datensatzes."""
    if art not in ARTEN:
        raise ValueError(f"unbekannte Art {art!r}")
    return (f" AND EXISTS (SELECT 1 FROM label_zuordnung lz WHERE lz.label_id = ? AND lz.art = '{art}' "
            f"AND lz.datensatz_id = {spalte} AND lz.geloescht = 0)")
