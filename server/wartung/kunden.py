"""Kunden und Kontakte: Felder, Suche, Anlegen, Ändern, Löschen (nur als gelöscht markieren).

Kontakte sind Ansprechpartner (Verwalter, Hausmeister); sie gehören optional zu einem Kunden und werden später den
Anlagen in Rollen zugeordnet (vor Ort, Berichtsempfänger, Terminankündigung).
"""
from . import db, nummern
from .felder import Feld, Ungueltig, adresse_pruefen, einlesen, fuer_bearbeiten, like_muster

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

KUNDE_FELDER_BEARBEITEN = fuer_bearbeiten(KUNDE_FELDER)

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
        parameter += [like_muster(suche.strip())] * 4
    if art:
        sql += " AND k.art = ?"
        parameter.append(art)
    return con.execute(sql + " ORDER BY k.name COLLATE NOCASE, k.nummer", parameter).fetchall()


def holen(con, kunde_id):
    return con.execute("SELECT * FROM kunde WHERE id = ? AND geloescht = 0", (kunde_id,)).fetchone()


def pruefen(con, form, eigene_id=None):
    """Formular -> geprüfte Werte. Wirft Ungueltig."""
    werte, fehler = einlesen(KUNDE_FELDER_BEARBEITEN if eigene_id else KUNDE_FELDER, form)
    adresse_pruefen(werte, fehler)
    if werte["nummer"]:
        fehler_nr = nummern.pruefen(con, "kunde", werte["nummer"], eigene_id)
        if fehler_nr:
            fehler["nummer"] = fehler_nr
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
        for k in kontakte(con, kunde_id):  # Kontakte anderer Kunden bleiben erhalten
            if any(x["id"] != kunde_id for x in kunden_von_kontakt(con, k["id"])):
                kontakt_loesen(con, kunde_id, k["id"], nutzer_id)
            else:
                kontakt_loeschen(con, k["id"], nutzer_id)
        db.aendern(con, "kunde", kunde_id, {"geloescht": 1}, nutzer_id)


# ---------- Kontakte ----------

def kontakte(con, kunde_id):
    """Kontakte des Kunden; „auch_bei“ nennt die übrigen Kunden, bei denen derselbe Kontakt geführt wird."""
    return con.execute(
        "SELECT c.*, (SELECT group_concat(k2.name, ', ') FROM kunde_kontakt z2 JOIN kunde k2 ON k2.id = z2.kunde_id "
        "             WHERE z2.kontakt_id = c.id AND z2.kunde_id != z.kunde_id AND z2.geloescht = 0 "
        "               AND k2.geloescht = 0) AS auch_bei "
        "FROM kunde_kontakt z JOIN kontakt c ON c.id = z.kontakt_id "
        "WHERE z.kunde_id = ? AND z.geloescht = 0 AND c.geloescht = 0 ORDER BY c.name COLLATE NOCASE",
        (kunde_id,)).fetchall()


def kunden_von_kontakt(con, kontakt_id):
    """Die Kunden, bei denen der Kontakt geführt wird."""
    return con.execute(
        "SELECT k.* FROM kunde_kontakt z JOIN kunde k ON k.id = z.kunde_id "
        "WHERE z.kontakt_id = ? AND z.geloescht = 0 AND k.geloescht = 0 ORDER BY k.name COLLATE NOCASE",
        (kontakt_id,)).fetchall()


def kontakt_holen(con, kontakt_id):
    return con.execute("SELECT * FROM kontakt WHERE id = ? AND geloescht = 0", (kontakt_id,)).fetchone()


def kontakt_pruefen(form):
    werte, fehler = einlesen(KONTAKT_FELDER, form)
    if fehler:
        raise Ungueltig(fehler)
    return werte


def _verknuepfung(con, kunde_id, kontakt_id):
    return con.execute("SELECT id FROM kunde_kontakt WHERE kunde_id = ? AND kontakt_id = ? AND geloescht = 0",
                       (kunde_id, kontakt_id)).fetchone()


def kontakt_anlegen(con, kunde_id, form, nutzer_id):
    """Legt einen neuen Kontakt an und führt ihn beim Kunden."""
    werte = kontakt_pruefen(form)
    with db.transaktion(con):
        kontakt_id = db.anlegen(con, "kontakt", werte, nutzer_id)
        db.anlegen(con, "kunde_kontakt", {"kunde_id": kunde_id, "kontakt_id": kontakt_id}, nutzer_id)
    return kontakt_id


def kontakt_verknuepfen(con, kunde_id, kontakt_id, nutzer_id):
    """Führt einen vorhandenen Kontakt zusätzlich bei diesem Kunden."""
    with db.transaktion(con):
        if holen(con, kunde_id) is None:
            raise Ungueltig({"": "Kunde nicht gefunden."})
        if kontakt_holen(con, kontakt_id) is None:
            raise Ungueltig({"": "Kontakt nicht gefunden."})
        if _verknuepfung(con, kunde_id, kontakt_id):
            raise Ungueltig({"": "Der Kontakt gehört schon zu diesem Kunden."})
        return db.anlegen(con, "kunde_kontakt", {"kunde_id": kunde_id, "kontakt_id": kontakt_id}, nutzer_id)


def kontakt_loesen(con, kunde_id, kontakt_id, nutzer_id):
    """Nimmt den Kontakt von diesem Kunden weg (er bleibt bei den übrigen Kunden). Seine Zuordnungen zu Anlagen dieses
    Kunden entfallen. Der letzte Kunde kann nicht gelöst werden – dann wird der Kontakt gelöscht."""
    with db.transaktion(con):
        z = _verknuepfung(con, kunde_id, kontakt_id)
        if z is None:
            raise Ungueltig({"": "Der Kontakt gehört nicht zu diesem Kunden."})
        if not any(k["id"] != kunde_id for k in kunden_von_kontakt(con, kontakt_id)):
            raise Ungueltig({"": "Der Kontakt gehört nur zu diesem Kunden und kann daher nur gelöscht werden."})
        for a in con.execute(
                "SELECT ak.id FROM anlage_kontakt ak JOIN anlage a ON a.id = ak.anlage_id "
                "JOIN objekt o ON o.id = a.objekt_id WHERE ak.kontakt_id = ? AND o.kunde_id = ? AND ak.geloescht = 0",
                (kontakt_id, kunde_id)).fetchall():
            db.aendern(con, "anlage_kontakt", a["id"], {"geloescht": 1}, nutzer_id)
        db.aendern(con, "kunde_kontakt", z["id"], {"geloescht": 1}, nutzer_id)


def kontakt_aendern(con, kontakt_id, form, nutzer_id):
    return db.aendern(con, "kontakt", kontakt_id, kontakt_pruefen(form), nutzer_id)


def kontakt_loeschen(con, kontakt_id, nutzer_id):
    """Markiert den Kontakt samt Verknüpfungen zu Kunden und Zuordnungen zu Anlagen als gelöscht (bei allen Kunden)."""
    with db.transaktion(con):
        for tabelle, spalte in (("anlage_kontakt", "kontakt_id"), ("kunde_kontakt", "kontakt_id")):
            for z in con.execute(f"SELECT id FROM {tabelle} WHERE {spalte} = ? AND geloescht = 0",
                                 (kontakt_id,)).fetchall():
                db.aendern(con, tabelle, z["id"], {"geloescht": 1}, nutzer_id)
        db.aendern(con, "kontakt", kontakt_id, {"geloescht": 1}, nutzer_id)


def kontakte_suchen(con, suche, ausser_kunde_id, grenze=30):
    """Kontakte, die noch nicht zu diesem Kunden gehören (Suche in Name, Firma, E-Mail, Telefon, Mobil)."""
    sql = ("SELECT c.*, (SELECT group_concat(k2.name, ', ') FROM kunde_kontakt z2 JOIN kunde k2 ON k2.id = z2.kunde_id "
           "             WHERE z2.kontakt_id = c.id AND z2.geloescht = 0 AND k2.geloescht = 0) AS bei_kunden "
           "FROM kontakt c WHERE c.geloescht = 0 AND NOT EXISTS ("
           "  SELECT 1 FROM kunde_kontakt z WHERE z.kontakt_id = c.id AND z.kunde_id = ? AND z.geloescht = 0)")
    parameter = [ausser_kunde_id]
    if suche.strip():
        felder = ("c.name", "c.firma", "c.email", "c.telefon", "c.mobil")
        sql += " AND (" + " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in felder) + ")"
        parameter += [like_muster(suche.strip())] * len(felder)
    return con.execute(sql + " ORDER BY c.name COLLATE NOCASE LIMIT ?", (*parameter, grenze)).fetchall()
