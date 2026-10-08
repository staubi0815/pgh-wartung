"""Kunden und Kontakte: Felder, Suche, Anlegen, Ändern, Löschen (nur als gelöscht markieren).

Kontakte sind Ansprechpartner (Verwalter, Hausmeister); sie gehören optional zu einem Kunden und werden später den
Anlagen in Rollen zugeordnet (vor Ort, Berichtsempfänger, Terminankündigung).
"""
from . import db, nummern
from .felder import Feld, Ungueltig, einlesen

KUNDENARTEN = (("hausverwaltung", "Hausverwaltung"), ("eigentuemer", "Eigentümer"),
               ("weg", "Eigentümergemeinschaft (WEG)"), ("vermieter", "Vermieter"), ("privat", "Privat"),
               ("sonstig", "Sonstige"))

KUNDE_FELDER = (
    Feld("nummer", "Kundennummer", max_laenge=nummern.MAX_LAENGE, hilfe="leer lassen = automatisch"),
    Feld("art", "Art", "auswahl", pflicht=True, auswahl=KUNDENARTEN),
    Feld("name", "Name", pflicht=True),
    Feld("zusatz", "Zusatz", hilfe="z. B. Abteilung, z. Hd."),
    Feld("strasse", "Straße und Hausnummer"),
    Feld("plz", "PLZ", max_laenge=10),
    Feld("ort", "Ort"),
    Feld("land", "Land", max_laenge=2, platzhalter="DE"),
    Feld("telefon", "Telefon", "tel"),
    Feld("email", "E-Mail", "email"),
    Feld("rechnungs_email", "E-Mail für Rechnungen", "email", hilfe="leer = wie E-Mail"),
    Feld("lieferantennummer", "Unsere Lieferantennummer beim Kunden"),
    Feld("notiz_intern", "Interne Notiz", "textarea", max_laenge=4000, breit=True),
)

KONTAKT_FELDER = (
    Feld("name", "Name", pflicht=True),
    Feld("funktion", "Funktion", platzhalter="z. B. Hausmeister, Verwalter"),
    Feld("firma", "Firma"),
    Feld("telefon", "Telefon", "tel"),
    Feld("mobil", "Mobil", "tel"),
    Feld("fax", "Fax", "tel"),
    Feld("email", "E-Mail", "email"),
    Feld("notiz", "Notiz", "textarea", max_laenge=2000, breit=True),
)


def _like(suche):
    return "%" + suche.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------- Kunden ----------

def liste(con, suche="", art=""):
    """Kunden mit Anzahl Objekte/Anlagen, sortiert nach Name. Suche in Nummer, Name, Zusatz, Ort."""
    sql = ("SELECT k.*, "
           " (SELECT COUNT(*) FROM objekt o WHERE o.kunde_id = k.id AND o.geloescht = 0) AS objekte, "
           " (SELECT COUNT(*) FROM anlage a JOIN objekt o ON o.id = a.objekt_id "
           "   WHERE o.kunde_id = k.id AND a.geloescht = 0 AND o.geloescht = 0) AS anlagen "
           "FROM kunde k WHERE k.geloescht = 0")
    parameter = []
    if suche.strip():
        sql += (" AND (k.nummer LIKE ? ESCAPE '\\' OR k.name LIKE ? ESCAPE '\\' OR k.zusatz LIKE ? ESCAPE '\\'"
                " OR k.ort LIKE ? ESCAPE '\\')")
        parameter += [_like(suche.strip())] * 4
    if art:
        sql += " AND k.art = ?"
        parameter.append(art)
    return con.execute(sql + " ORDER BY k.name COLLATE NOCASE, k.nummer", parameter).fetchall()


def holen(con, kunde_id):
    return con.execute("SELECT * FROM kunde WHERE id = ? AND geloescht = 0", (kunde_id,)).fetchone()


def pruefen(con, form, eigene_id=None):
    """Formular -> geprüfte Werte. Wirft Ungueltig."""
    werte, fehler = einlesen(KUNDE_FELDER, form)
    werte["land"] = (werte["land"] or "DE").upper()
    if werte["nummer"]:
        fehler_nr = nummern.pruefen(con, "kunde", werte["nummer"], eigene_id)
        if fehler_nr:
            fehler["nummer"] = fehler_nr
    elif eigene_id:
        fehler["nummer"] = "Kundennummer ist Pflicht."
    if werte["land"] == "DE" and werte["plz"] and not (werte["plz"].isdigit() and len(werte["plz"]) == 5):
        fehler["plz"] = "PLZ: in Deutschland fünf Ziffern."
    if fehler:
        raise Ungueltig(fehler)
    return werte


def anlegen(con, form, nutzer_id):
    werte = pruefen(con, form)
    with db.transaktion(con):
        werte["nummer"] = werte["nummer"] or nummern.naechste(con, "kunde")
        return db.anlegen(con, "kunde", werte, nutzer_id)


def aendern(con, kunde_id, form, nutzer_id):
    werte = pruefen(con, form, kunde_id)
    return db.aendern(con, "kunde", kunde_id, werte, nutzer_id)


def loeschen(con, kunde_id, nutzer_id):
    """Markiert den Kunden als gelöscht – nur ohne aktive Objekte (Nachweise sollen nicht verwaisen)."""
    with db.transaktion(con):  # Prüfung und Löschen in einem Schritt, damit kein Objekt dazwischenkommt
        if con.execute("SELECT 1 FROM objekt WHERE kunde_id = ? AND geloescht = 0", (kunde_id,)).fetchone():
            raise Ungueltig({"": "Der Kunde hat noch Objekte. Bitte zuerst diese löschen oder einem anderen "
                                 "Kunden zuordnen."})
        for k in con.execute("SELECT id FROM kontakt WHERE kunde_id = ? AND geloescht = 0", (kunde_id,)).fetchall():
            kontakt_loeschen(con, k["id"], nutzer_id)
        db.aendern(con, "kunde", kunde_id, {"geloescht": 1}, nutzer_id)


# ---------- Kontakte ----------

def kontakte(con, kunde_id):
    return con.execute("SELECT * FROM kontakt WHERE kunde_id = ? AND geloescht = 0 ORDER BY name COLLATE NOCASE",
                       (kunde_id,)).fetchall()


def kontakt_holen(con, kontakt_id):
    return con.execute("SELECT * FROM kontakt WHERE id = ? AND geloescht = 0", (kontakt_id,)).fetchone()


def kontakt_pruefen(form):
    werte, fehler = einlesen(KONTAKT_FELDER, form)
    if fehler:
        raise Ungueltig(fehler)
    return werte


def kontakt_anlegen(con, kunde_id, form, nutzer_id):
    werte = kontakt_pruefen(form)
    return db.anlegen(con, "kontakt", {**werte, "kunde_id": kunde_id}, nutzer_id)


def kontakt_aendern(con, kontakt_id, form, nutzer_id):
    return db.aendern(con, "kontakt", kontakt_id, kontakt_pruefen(form), nutzer_id)


def kontakt_loeschen(con, kontakt_id, nutzer_id):
    """Markiert den Kontakt und seine Zuordnungen zu Anlagen als gelöscht."""
    with db.transaktion(con):
        for z in con.execute("SELECT id FROM anlage_kontakt WHERE kontakt_id = ? AND geloescht = 0",
                             (kontakt_id,)).fetchall():
            db.aendern(con, "anlage_kontakt", z["id"], {"geloescht": 1}, nutzer_id)
        db.aendern(con, "kontakt", kontakt_id, {"geloescht": 1}, nutzer_id)
