"""Einzelrechte und Rollen.

Rechte sind eine feste Liste im Code (Seiten prüfen nur Rechte, nie Rollennamen). Rollen sind benannte Bündel aus
Rechten in der Datenbank; ein Nutzer kann mehrere Rollen haben. Die Rolle mit der Kennung „admin“ (Administration)
hat immer alle Rechte – auch solche, die in späteren Versionen dazukommen – und ist nicht änderbar.
Siehe docs/06-foxtag-rollen-und-app.md.
"""
from .db import jetzt, neue_id, protokoll, transaktion

ADMIN = "admin"

# Bereich -> [(recht, Beschreibung)]. Reihenfolge = Anzeige in der Rollen-Maske.
BEREICHE = {
    "Webseite": [
        ("web.zugang", "Webseite betreten (ohne weitere Rechte: nur eigene Aufträge)"),
        ("stammdaten.lesen", "Kunden, Objekte, Anlagen, Wohnungen und Melder ansehen"),
        ("stammdaten.bearbeiten", "Kunden, Objekte, Anlagen, Wohnungen und Melder anlegen und ändern"),
        ("auftraege.planen", "Aufträge planen, zuweisen und ändern"),
        ("maengel.bearbeiten", "Mängel bearbeiten und abschließen"),
        ("berichte.versenden", "Berichte freigeben und versenden"),
        ("rechnung.entwurf", "Rechnungsentwürfe erzeugen"),
        ("auswertungen", "Auswertungen erstellen"),
    ],
    "Daten": [
        ("import", "Daten importieren (Excel)"),
        ("export", "Daten exportieren (Vollexport, Foxtag-Format)"),
    ],
    "Verwaltung": [
        ("verwaltung.firma", "Firmendaten und Nummernkreise"),
        ("verwaltung.katalog", "Artikel, Melder-Typen und Labels pflegen"),
        ("verwaltung.nutzer", "Nutzer einladen, ändern und deaktivieren"),
        ("verwaltung.rollen", "Rollen und Rechte festlegen"),
        ("verwaltung.geraete", "Geräte freischalten und sperren"),
        ("verwaltung.protokoll", "Änderungsprotokoll einsehen"),
    ],
    "App": [
        ("app.zugang", "In der App anmelden"),
        ("app.auftraege", "Aufträge in der App durchführen"),
        ("app.stammdaten", "Wohnungen und Melder vor Ort anlegen und ändern"),
        ("app.fotos", "Fotos aufnehmen"),
        ("app.auftrag_anlegen", "Neue Aufträge in der App anlegen"),
        ("app.termin_verschieben", "Termin eines Auftrags verschieben (vor Beginn)"),
        ("app.ferninspektion", "Funk-Ferninspektion durchführen (Laptop)"),
    ],
}
RECHTE = {r: text for liste in BEREICHE.values() for r, text in liste}


def rechte_von_nutzer(con, nutzer_id):
    """Menge der Rechte eines Nutzers (Vereinigung über alle seine Rollen)."""
    rollen = con.execute("SELECT r.id, r.kennung FROM nutzer_rolle nr JOIN rolle r ON r.id = nr.rolle_id "
                         "WHERE nr.nutzer_id = ? AND r.geloescht = 0", (nutzer_id,)).fetchall()
    if any(r["kennung"] == ADMIN for r in rollen):
        return set(RECHTE)
    rechte = set()
    for r in rollen:
        rechte |= rechte_von_rolle(con, r["id"])
    return rechte


def rechte_von_rolle(con, rolle_id):
    r = con.execute("SELECT kennung FROM rolle WHERE id = ?", (rolle_id,)).fetchone()
    if r is not None and r["kennung"] == ADMIN:
        return set(RECHTE)
    return {z["recht"] for z in con.execute("SELECT recht FROM rolle_recht WHERE rolle_id = ?", (rolle_id,))
            if z["recht"] in RECHTE}


def rollen(con):
    """Alle Rollen mit Anzahl aktiver Nutzer, Administration zuerst."""
    return con.execute(
        "SELECT r.*, (SELECT COUNT(*) FROM nutzer_rolle nr JOIN nutzer n ON n.id = nr.nutzer_id "
        "             WHERE nr.rolle_id = r.id AND n.aktiv = 1 AND n.geloescht = 0) AS anzahl "
        "FROM rolle r WHERE r.geloescht = 0 ORDER BY r.reihenfolge, r.name").fetchall()


def rollen_von_nutzer(con, nutzer_id):
    return {z["rolle_id"] for z in con.execute(
        "SELECT nr.rolle_id FROM nutzer_rolle nr JOIN rolle r ON r.id = nr.rolle_id "
        "WHERE nr.nutzer_id = ? AND r.geloescht = 0", (nutzer_id,))}


def admin_rolle_id(con):
    return con.execute("SELECT id FROM rolle WHERE kennung = ?", (ADMIN,)).fetchone()["id"]


def aktive_admins(con):
    return con.execute("SELECT COUNT(*) FROM nutzer_rolle nr JOIN nutzer n ON n.id = nr.nutzer_id "
                       "WHERE nr.rolle_id = ? AND n.aktiv = 1 AND n.geloescht = 0",
                       (admin_rolle_id(con),)).fetchone()[0]


def nutzer_rollen_setzen(con, nutzer_id, rollen_ids, von):
    """Setzt die Rollen eines Nutzers und protokolliert Zu- und Abgänge. Gibt True zurück, wenn sich etwas geändert hat."""
    with transaktion(con):
        alt = rollen_von_nutzer(con, nutzer_id)
        neu = set(rollen_ids)
        for rid in sorted(neu - alt):
            con.execute("INSERT INTO nutzer_rolle (nutzer_id, rolle_id) VALUES (?, ?)", (nutzer_id, rid))
            protokoll(con, von, "nutzer", nutzer_id, "rolle_hinzu", "rolle", None, _rollenname(con, rid))
        for rid in sorted(alt - neu):
            con.execute("DELETE FROM nutzer_rolle WHERE nutzer_id = ? AND rolle_id = ?", (nutzer_id, rid))
            protokoll(con, von, "nutzer", nutzer_id, "rolle_weg", "rolle", _rollenname(con, rid), None)
    return alt != neu


def rolle_anlegen(con, name, beschreibung, rechte, von):
    rid = neue_id()
    with transaktion(con):
        con.execute("INSERT INTO rolle (id, name, beschreibung, erstellt_am, erstellt_von) VALUES (?, ?, ?, ?, ?)",
                    (rid, name.strip(), beschreibung.strip(), jetzt(), von))
        protokoll(con, von, "rolle", rid, "anlegen", "name", None, name.strip())
        _rechte_setzen(con, rid, rechte, von)
    return rid


def rolle_rechte_setzen(con, rolle_id, rechte, von):
    """Ersetzt die Rechte einer Rolle (nicht für Administration). Gibt True zurück, wenn sich etwas geändert hat."""
    with transaktion(con):
        geaendert = _rechte_setzen(con, rolle_id, rechte, von)
        if geaendert:
            con.execute("UPDATE rolle SET geaendert_am = ?, geaendert_von = ?, version = version + 1 WHERE id = ?",
                        (jetzt(), von, rolle_id))
    return geaendert


def _rechte_setzen(con, rolle_id, rechte, von):
    unbekannt = set(rechte) - set(RECHTE)
    if unbekannt:
        raise ValueError(f"unbekannte Rechte: {sorted(unbekannt)}")
    alt = {z["recht"] for z in con.execute("SELECT recht FROM rolle_recht WHERE rolle_id = ?", (rolle_id,))}
    neu = set(rechte)
    for r in sorted(neu - alt):
        con.execute("INSERT INTO rolle_recht (rolle_id, recht) VALUES (?, ?)", (rolle_id, r))
        protokoll(con, von, "rolle", rolle_id, "recht_hinzu", "recht", None, r)
    for r in sorted(alt - neu):
        con.execute("DELETE FROM rolle_recht WHERE rolle_id = ? AND recht = ?", (rolle_id, r))
        protokoll(con, von, "rolle", rolle_id, "recht_weg", "recht", r, None)
    return alt != neu


def _rollenname(con, rolle_id):
    r = con.execute("SELECT name FROM rolle WHERE id = ?", (rolle_id,)).fetchone()
    return r["name"] if r else rolle_id
