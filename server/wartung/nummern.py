"""Nummernkreise für Kunden, Objekte, Anlagen und Aufträge (K0001, O-0001, ANL-0001, A-1001).

Nummern sind Pflicht und eindeutig (Foxtag braucht sie beim Wechsel als Schlüssel) und werden nie wiederverwendet –
auch nicht nach dem Löschen. Von Hand vergebene Nummern (z. B. beim Import) werden bei der automatischen Vergabe
übersprungen.
"""
from .db import transaktion

# art -> (Tabelle, Präfix-Spalte in firma)
ARTEN = {"kunde": ("kunde", "praefix_kunde"), "objekt": ("objekt", "praefix_objekt"),
         "anlage": ("anlage", "praefix_anlage"), "auftrag": ("auftrag", "praefix_auftrag")}
MAX_LAENGE = 30


def formatieren(praefix, nr, stellen):
    return f"{praefix}{nr:0{stellen}d}" if stellen else f"{praefix}{nr}"


def _vergeben(con, tabelle, nummer):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabelle,)).fetchone():
        return False  # Tabelle gibt es noch nicht (z. B. auftrag vor dessen Migration)
    return con.execute(f"SELECT 1 FROM {tabelle} WHERE nummer = ? COLLATE NOCASE", (nummer,)).fetchone() is not None


def naechste(con, art):
    """Vergibt die nächste freie Nummer und zählt den Nummernkreis weiter."""
    tabelle, praefix_spalte = ARTEN[art]
    with transaktion(con):
        kreis = con.execute("SELECT naechste, stellen FROM nummernkreis WHERE art = ?", (art,)).fetchone()
        praefix = con.execute(f"SELECT {praefix_spalte} FROM firma WHERE id = 1").fetchone()[0]
        nr = kreis["naechste"]
        while _vergeben(con, tabelle, formatieren(praefix, nr, kreis["stellen"])):
            nr += 1
        con.execute("UPDATE nummernkreis SET naechste = ? WHERE art = ?", (nr + 1, art))
    return formatieren(praefix, nr, kreis["stellen"])


def vorschau(con, art):
    """Nummer, die als Nächstes vergeben würde (zur Anzeige im Formular, ohne zu zählen)."""
    tabelle, praefix_spalte = ARTEN[art]
    kreis = con.execute("SELECT naechste, stellen FROM nummernkreis WHERE art = ?", (art,)).fetchone()
    praefix = con.execute(f"SELECT {praefix_spalte} FROM firma WHERE id = 1").fetchone()[0]
    nr = kreis["naechste"]
    while _vergeben(con, tabelle, formatieren(praefix, nr, kreis["stellen"])):
        nr += 1
    return formatieren(praefix, nr, kreis["stellen"])


def pruefen(con, art, nummer, eigene_id=None):
    """Prüft eine von Hand eingegebene Nummer. Gibt eine Fehlermeldung zurück oder None."""
    tabelle, _ = ARTEN[art]
    nummer = (nummer or "").strip()
    if not nummer:
        return "Nummer ist Pflicht."
    if len(nummer) > MAX_LAENGE or any(z in nummer for z in ";\t\n\r"):
        return f"Die Nummer darf höchstens {MAX_LAENGE} Zeichen lang sein und keine Steuerzeichen enthalten."
    if con.execute(f"SELECT 1 FROM {tabelle} WHERE nummer = ? COLLATE NOCASE AND id != ?",
                   (nummer, eigene_id or "")).fetchone():
        return f"Die Nummer {nummer} ist schon vergeben."
    return None
