"""Aufträge: planen, ändern, verschieben, Status wechseln; Techniker und Umfang (ganze Anlage oder Wohnungen).

Regeln:
- Erlaubte Statuswechsel stehen in UEBERGAENGE. Jeder Wechsel und jedes Verschieben steht mit Grund im
  Auftragsverlauf (nur anhängen). Stornieren und jeder Schritt zurück brauchen einen Grund.
- Termin, Techniker und Hinweise sind änderbar, solange der Auftrag geplant oder in Arbeit ist; der Umfang nur,
  solange er geplant ist (danach können schon Ergebnisse dazu vorliegen).
- Ein Auftrag ohne Techniker ist ein Pool-Auftrag: jeder Techniker darf ihn übernehmen.
- Aufträge werden nie gelöscht, nur storniert.
"""
from datetime import date

from . import anlagenart, db, nummern, rechte
from .felder import Feld, Ungueltig, einlesen

STATUS = (("geplant", "Geplant"), ("aktiv", "In Arbeit"), ("abgeschlossen", "Abgeschlossen"),
          ("abgerechnet", "Abgerechnet"), ("kostenlos", "Abgeschlossen ohne Rechnung"), ("storniert", "Storniert"))
STATUS_TEXT = dict(STATUS)
OFFEN = ("geplant", "aktiv")
UEBERGAENGE = {
    "geplant": ("aktiv", "abgeschlossen", "storniert"),
    "aktiv": ("abgeschlossen", "geplant"),
    "abgeschlossen": ("abgerechnet", "kostenlos", "aktiv"),
    "abgerechnet": ("abgeschlossen",),
    "kostenlos": ("abgeschlossen",),
    "storniert": ("geplant",),
}
# Schritte zurück (und Stornieren) brauchen eine Begründung im Verlauf
RUECKWAERTS = {("aktiv", "geplant"), ("abgeschlossen", "aktiv"), ("abgerechnet", "abgeschlossen"),
               ("kostenlos", "abgeschlossen"), ("storniert", "geplant")}
UMFANG = (("ganze_anlage", "Ganze Anlage"), ("auswahl", "Ausgewählte Wohnungen"))
TECHNIKER_RECHT = "app.auftraege"
MAX_GRUND = 500


def grund_noetig(alt, neu):
    return neu == "storniert" or (alt, neu) in RUECKWAERTS


def felder(art, mit_nummer=True):
    """Felder der Auftragsmaske. Techniker und Umfang kommen als eigene Auswahl dazu (Mehrfachauswahl)."""
    arten = tuple((a.schluessel, a.name) for a in art.auftragsarten)
    liste = (
        Feld("auftragsart", "Auftragsart", "auswahl", pflicht=True, auswahl=arten),
        Feld("datum", "Datum", "datum", pflicht=True),
        Feld("uhrzeit", "Uhrzeit", "uhrzeit", hilfe="leer = ganztägig"),
        Feld("dauer_minuten", "Dauer (Minuten)", "zahl", minimum=15, maximum=24 * 60, hilfe="geschätzt, optional"),
        Feld("hinweise", "Hinweise für den Techniker", "textarea", max_laenge=2000, breit=True),
        Feld("notiz_intern", "Interne Notiz (nur Büro)", "textarea", max_laenge=4000, breit=True),
    )
    if mit_nummer:
        liste = (Feld("nummer", "Auftragsnummer", max_laenge=nummern.MAX_LAENGE, hilfe="leer lassen = automatisch"),
                 *liste)
    return liste


def standard_auftragsart(art):
    return next((a.schluessel for a in art.auftragsarten if a.standard), art.auftragsarten[0].schluessel)


def auftragsart_name(art_schluessel, auftragsart):
    art = anlagenart.alle().get(art_schluessel)
    if art:
        for a in art.auftragsarten:
            if a.schluessel == auftragsart:
                return a.name
    return auftragsart


def termin_text(datum, uhrzeit):
    return f"{datum} {uhrzeit}" if uhrzeit else datum


# ---------- Lesen ----------

_GRUND_SQL = (
    "SELECT u.*, a.nummer AS anlage_nummer, a.bezeichnung AS anlage_bezeichnung, a.anlagenart, a.passiv, "
    " a.hinweise_techniker, o.id AS objekt_id, o.bezeichnung AS objekt_bezeichnung, k.id AS kunde_id, "
    " k.nummer AS kunde_nummer, k.name AS kunde_name, "
    " CASE WHEN o.adresse_wie_kunde = 1 THEN k.strasse ELSE o.strasse END AS adr_strasse, "
    " CASE WHEN o.adresse_wie_kunde = 1 THEN k.plz ELSE o.plz END AS adr_plz, "
    " CASE WHEN o.adresse_wie_kunde = 1 THEN k.ort ELSE o.ort END AS adr_ort "
    "FROM auftrag u JOIN anlage a ON a.id = u.anlage_id JOIN objekt o ON o.id = a.objekt_id "
    "JOIN kunde k ON k.id = o.kunde_id WHERE u.geloescht = 0")


def holen(con, auftrag_id):
    return con.execute(_GRUND_SQL + " AND u.id = ?", (auftrag_id,)).fetchone()


def techniker(con, auftrag_id):
    """Zugeordnete Techniker (Name, Kürzel), alphabetisch. Leer = Pool."""
    return con.execute("SELECT n.id, n.name, n.kuerzel, n.personalnummer FROM auftrag_techniker t "
                       "JOIN nutzer n ON n.id = t.nutzer_id WHERE t.auftrag_id = ? AND t.geloescht = 0 "
                       "ORDER BY n.name COLLATE NOCASE", (auftrag_id,)).fetchall()


def gruppen(con, auftrag_id):
    """Wohnungen im Umfang „auswahl“, nach Nummer."""
    return con.execute("SELECT g.* FROM auftrag_gruppe z JOIN gruppe g ON g.id = z.gruppe_id "
                       "WHERE z.auftrag_id = ? AND z.geloescht = 0 ORDER BY g.nummer", (auftrag_id,)).fetchall()


def verlauf(con, auftrag_id):
    return con.execute("SELECT v.*, n.name AS nutzer_name FROM auftrag_verlauf v "
                       "LEFT JOIN nutzer n ON n.id = v.erstellt_von WHERE v.auftrag_id = ? "
                       "ORDER BY v.zeitpunkt, v.rowid", (auftrag_id,)).fetchall()


def fuer_anlage(con, anlage_id):
    """Alle Aufträge einer Anlage, neueste zuerst."""
    return con.execute("SELECT * FROM auftrag WHERE anlage_id = ? AND geloescht = 0 ORDER BY datum DESC, "
                       "uhrzeit DESC, nummer DESC", (anlage_id,)).fetchall()


def techniker_auswahl(con, auch_ids=()):
    """(id, Name) aller aktiven Nutzer mit dem Recht, Aufträge in der App durchzuführen – plus bereits
    zugeordnete (auch wenn sie das Recht inzwischen nicht mehr haben), damit beim Ändern niemand verloren geht."""
    auswahl = []
    for n in con.execute("SELECT id, name, aktiv FROM nutzer WHERE geloescht = 0 ORDER BY name COLLATE NOCASE"):
        if (n["aktiv"] and TECHNIKER_RECHT in rechte.rechte_von_nutzer(con, n["id"])) or n["id"] in auch_ids:
            auswahl.append((n["id"], n["name"]))
    return tuple(auswahl)


# ---------- Prüfen ----------

def _pruefen(con, art, anlage_id, form, auftrag=None):
    """Formular -> (werte, techniker_ids, gruppen_ids). Wirft Ungueltig."""
    neu = auftrag is None
    werte, fehler = einlesen(felder(art, mit_nummer=neu), form)
    if neu and werte["nummer"]:
        fehler_nr = nummern.pruefen(con, "auftrag", werte["nummer"])
        if fehler_nr:
            fehler["nummer"] = fehler_nr
    if neu and werte.get("datum") and werte["datum"] < date.today().isoformat():
        fehler["datum"] = "Das Datum liegt in der Vergangenheit."

    bisher = [t["id"] for t in techniker(con, auftrag["id"])] if auftrag else []
    erlaubt = {i for i, _ in techniker_auswahl(con, bisher)}
    techniker_ids = list(dict.fromkeys(form.getlist("techniker") if hasattr(form, "getlist")
                                       else form.get("techniker", [])))
    if set(techniker_ids) - erlaubt:
        fehler["techniker"] = "Ungültige Techniker-Auswahl."

    umfang = form.get("umfang") or "ganze_anlage"
    gruppen_ids = []
    if umfang not in dict(UMFANG):
        fehler["umfang"] = "Ungültiger Umfang."
    elif umfang == "auswahl":
        gruppen_ids = list(dict.fromkeys(form.getlist("gruppen") if hasattr(form, "getlist")
                                         else form.get("gruppen", [])))
        vorhanden = {g["id"] for g in con.execute("SELECT id FROM gruppe WHERE anlage_id = ? AND geloescht = 0",
                                                  (anlage_id,))}
        if not gruppen_ids:
            fehler["umfang"] = f"Bitte mindestens eine {art.gruppe} wählen (oder „Ganze Anlage“)."
        elif set(gruppen_ids) - vorhanden:
            fehler["umfang"] = f"Ungültige {art.gruppe}-Auswahl."
    werte["umfang"] = umfang
    if fehler:
        raise Ungueltig(fehler)
    return werte, techniker_ids, gruppen_ids


# ---------- Schreiben ----------

def _techniker_setzen(con, auftrag_id, ids, nutzer_id):
    bisher = {z["nutzer_id"]: z["id"] for z in con.execute(
        "SELECT id, nutzer_id FROM auftrag_techniker WHERE auftrag_id = ? AND geloescht = 0", (auftrag_id,))}
    for nid in ids:
        if nid not in bisher:
            db.anlegen(con, "auftrag_techniker", {"auftrag_id": auftrag_id, "nutzer_id": nid}, nutzer_id)
    for nid, zid in bisher.items():
        if nid not in ids:
            db.aendern(con, "auftrag_techniker", zid, {"geloescht": 1}, nutzer_id)


def _gruppen_setzen(con, auftrag_id, ids, nutzer_id):
    bisher = {z["gruppe_id"]: z["id"] for z in con.execute(
        "SELECT id, gruppe_id FROM auftrag_gruppe WHERE auftrag_id = ? AND geloescht = 0", (auftrag_id,))}
    for gid in ids:
        if gid not in bisher:
            db.anlegen(con, "auftrag_gruppe", {"auftrag_id": auftrag_id, "gruppe_id": gid}, nutzer_id)
    for gid, zid in bisher.items():
        if gid not in ids:
            db.aendern(con, "auftrag_gruppe", zid, {"geloescht": 1}, nutzer_id)


def _verlauf(con, auftrag_id, ereignis, nutzer_id, **werte):
    db.anlegen(con, "auftrag_verlauf", {"auftrag_id": auftrag_id, "ereignis": ereignis, "zeitpunkt": db.jetzt(),
                                        **werte}, nutzer_id)


def anlegen(con, anlage, form, nutzer_id):
    """Plant einen Auftrag für eine Anlage. anlage: Zeile aus anlagen.holen. Gibt die id zurück."""
    if anlage["passiv"]:
        raise Ungueltig({"": "Die Anlage ist passiv – für sie werden keine Aufträge geplant."})
    art = anlagenart.holen(anlage["anlagenart"])
    with db.transaktion(con):
        werte, techniker_ids, gruppen_ids = _pruefen(con, art, anlage["id"], form)
        werte["nummer"] = werte["nummer"] or nummern.naechste(con, "auftrag")
        aid = db.anlegen(con, "auftrag", {**werte, "anlage_id": anlage["id"], "status": "geplant"}, nutzer_id)
        _techniker_setzen(con, aid, techniker_ids, nutzer_id)
        _gruppen_setzen(con, aid, gruppen_ids, nutzer_id)
        _verlauf(con, aid, "angelegt", nutzer_id, status_neu="geplant",
                 termin_neu=termin_text(werte["datum"], werte["uhrzeit"]))
    return aid


def aendern(con, auftrag_id, form, nutzer_id):
    """Ändert Termin, Art, Techniker, Umfang und Hinweise. Ein neuer Termin wird als „verschoben“ mit dem Grund aus
    dem Formularfeld „grund“ im Verlauf vermerkt. Gibt True zurück, wenn sich etwas geändert hat."""
    with db.transaktion(con):
        u = holen(con, auftrag_id)
        if u is None:
            raise Ungueltig({"": "Den Auftrag gibt es nicht."})
        if u["status"] not in OFFEN:
            raise Ungueltig({"": f"Ein Auftrag mit Status „{STATUS_TEXT[u['status']]}“ kann nicht mehr geändert "
                                 "werden."})
        art = anlagenart.holen(u["anlagenart"])
        werte, techniker_ids, gruppen_ids = _pruefen(con, art, u["anlage_id"], form, u)
        if u["status"] != "geplant" and (werte["umfang"] != u["umfang"] or set(gruppen_ids) != {
                g["id"] for g in gruppen(con, auftrag_id)}):
            raise Ungueltig({"umfang": "Der Umfang ist nur änderbar, solange der Auftrag geplant ist."})
        grund = " ".join(str(form.get("grund") or "").split())[:MAX_GRUND]
        termin_alt, termin_neu = termin_text(u["datum"], u["uhrzeit"]), termin_text(werte["datum"], werte["uhrzeit"])
        geaendert = db.aendern(con, "auftrag", auftrag_id, werte, nutzer_id) > 0
        vorher_t = {t["id"] for t in techniker(con, auftrag_id)}
        vorher_g = {g["id"] for g in gruppen(con, auftrag_id)}
        _techniker_setzen(con, auftrag_id, techniker_ids, nutzer_id)
        _gruppen_setzen(con, auftrag_id, gruppen_ids, nutzer_id)
        geaendert = geaendert or vorher_t != set(techniker_ids) or vorher_g != set(gruppen_ids)
        if termin_alt != termin_neu:
            _verlauf(con, auftrag_id, "verschoben", nutzer_id, termin_alt=termin_alt, termin_neu=termin_neu,
                     grund=grund)
    return geaendert


def status_setzen(con, auftrag_id, neu, nutzer_id, grund="", rechnung_nummer=""):
    """Wechselt den Status, wenn der Übergang erlaubt ist. Prüft gegen den aktuellen Stand in der Datenbank."""
    grund = " ".join(str(grund or "").split())[:MAX_GRUND]
    rechnung_nummer = " ".join(str(rechnung_nummer or "").split())[:nummern.MAX_LAENGE]
    with db.transaktion(con):
        u = holen(con, auftrag_id)
        if u is None:
            raise Ungueltig({"": "Den Auftrag gibt es nicht."})
        alt = u["status"]
        if neu not in UEBERGAENGE.get(alt, ()):
            raise Ungueltig({"": f"Von „{STATUS_TEXT[alt]}“ nach „{STATUS_TEXT.get(neu, neu)}“ ist nicht möglich."})
        if grund_noetig(alt, neu) and not grund:
            raise Ungueltig({"grund": "Bitte einen Grund angeben."})
        werte = {"status": neu}
        if neu == "abgeschlossen" and not u["abgeschlossen_am"]:
            werte["abgeschlossen_am"] = date.today().isoformat()
        if neu in ("geplant", "aktiv"):
            werte["abgeschlossen_am"] = None
        if neu == "abgerechnet":
            werte["rechnung_nummer"] = rechnung_nummer
        if alt == "abgerechnet":
            werte["rechnung_nummer"] = ""
        db.aendern(con, "auftrag", auftrag_id, werte, nutzer_id)
        _verlauf(con, auftrag_id, "status", nutzer_id, status_alt=alt, status_neu=neu, grund=grund)


def offene_fuer_gruppe(con, gruppe_id):
    """Offene Aufträge, in deren Umfang („auswahl“) die Wohnung steht."""
    return con.execute("SELECT u.nummer FROM auftrag_gruppe z JOIN auftrag u ON u.id = z.auftrag_id "
                       "WHERE z.gruppe_id = ? AND z.geloescht = 0 AND u.geloescht = 0 AND u.status IN ('geplant', "
                       "'aktiv') ORDER BY u.nummer", (gruppe_id,)).fetchall()


def anzahl_fuer_anlage(con, anlage_id):
    """Aufträge der Anlage, die nicht storniert sind (Nachweise – die Anlage darf dann nicht gelöscht werden)."""
    return con.execute("SELECT COUNT(*) FROM auftrag WHERE anlage_id = ? AND geloescht = 0 AND status != 'storniert'",
                       (anlage_id,)).fetchone()[0]
