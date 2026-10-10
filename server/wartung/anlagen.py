"""Anlagen (z. B. die Rauchwarnmelder eines Objekts): Felder, Liste, Anlegen, Ändern, Löschen,
Ansprechpartner mit Rolle zuordnen, in ein anderes Objekt verschieben.

Die Anlagenart (rauchwarnmelder, später tueren) wird beim Anlegen festgelegt und danach nicht mehr geändert, weil
Wohnungen, Melder, Checklisten und Mängeltypen an ihr hängen.
"""
from datetime import date

from . import anlagenart, db, faelligkeit, labels, nummern, objekte
from .felder import Feld, Ungueltig, einlesen, fuer_bearbeiten, like_muster
from .objekte import ADRESSE_SQL

VERFAHREN = (("A", "A – Inspektion vor Ort"), ("B", "B – teilweise Ferninspektion"), ("C", "C – Ferninspektion"))
KONTAKT_ROLLEN = (("vor_ort", "Ansprechpartner vor Ort"), ("berichtsempfaenger", "Berichtsempfänger"),
                  ("terminankuendigung", "Terminankündigung"))


def arten_auswahl():
    return tuple((a.schluessel, a.name) for a in anlagenart.alle().values())


def _gemeinsame_felder(techniker=()):
    return (
        Feld("nummer", "Anlagennummer", max_laenge=nummern.MAX_LAENGE, hilfe="leer lassen = automatisch"),
        Feld("bezeichnung", "Bezeichnung", platzhalter="z. B. Rauchwarnmelder Haus A"),
        Feld("verfahren", "Inspektionsverfahren", "auswahl", pflicht=True, auswahl=VERFAHREN),
        Feld("einzelnachweis_je_wohnung", "Einzelnachweis je Wohnung", "ja_nein", breit=True,
             hilfe="eigener Bericht je Wohnung, z. B. bei Eigentümern"),
        Feld("passiv", "Passiv", "ja_nein", breit=True, hilfe="Anlage ruht, keine Fälligkeiten"),
        Feld("stammtechniker_id", "Stammtechniker", "auswahl", auswahl=(("", "– keiner –"), *techniker),
             hilfe="wird beim Planen vorgeschlagen"),
        Feld("hinweise_techniker", "Hinweise für den Techniker", "textarea", max_laenge=2000, breit=True),
        Feld("notiz", "Notiz", "textarea", max_laenge=4000, breit=True),
    )


def techniker_auswahl(con, aktuell=None):
    """(id, Name) der wählbaren Stammtechniker; der bisherige bleibt wählbar, auch wenn er das Recht verloren hat."""
    from . import auftraege  # spät, weil auftraege seinerseits anlagen braucht
    return auftraege.techniker_auswahl(con, [aktuell] if aktuell else [])


def felder_neu(techniker=()):
    return (Feld("anlagenart", "Anlagenart", "auswahl", pflicht=True, auswahl=arten_auswahl()),
            *_gemeinsame_felder(techniker))


def felder_bearbeiten(techniker=()):
    return fuer_bearbeiten(_gemeinsame_felder(techniker))


# ---------- Lesen ----------

# frühester offener (geplant/in Arbeit) Auftrag der Anlage
_NAECHSTER_AUFTRAG = ("FROM auftrag u WHERE u.anlage_id = a.id AND u.geloescht = 0 "
                      "AND u.status IN ('geplant', 'aktiv') ORDER BY u.datum, u.uhrzeit, u.nummer LIMIT 1")
_GRUND_SQL = (f"SELECT a.*, o.nummer AS objekt_nummer, o.bezeichnung AS objekt_bezeichnung, o.kunde_id, "
              f"k.nummer AS kunde_nummer, k.name AS kunde_name, {ADRESSE_SQL}, "
              " (SELECT s.name FROM nutzer s WHERE s.id = a.stammtechniker_id) AS stammtechniker_name, "
              " (SELECT COUNT(*) FROM gruppe g WHERE g.anlage_id = a.id AND g.geloescht = 0) AS wohnungen, "
              " (SELECT COUNT(*) FROM komponente c WHERE c.anlage_id = a.id AND c.geloescht = 0 "
              "    AND c.status = 'verbaut') AS komponenten, "
              " (SELECT MIN(c.naechste_pruefung_am) FROM komponente c WHERE c.anlage_id = a.id AND c.geloescht = 0 "
              "    AND c.status = 'verbaut') AS naechste_pruefung_am, "
              " (SELECT MIN(c.austausch_faellig_am) FROM komponente c WHERE c.anlage_id = a.id AND c.geloescht = 0 "
              "    AND c.status = 'verbaut') AS naechster_austausch_am, "
              f" (SELECT u.id {_NAECHSTER_AUFTRAG}) AS naechster_auftrag_id, "
              f" (SELECT u.nummer {_NAECHSTER_AUFTRAG}) AS naechster_auftrag_nummer, "
              f" (SELECT u.datum {_NAECHSTER_AUFTRAG}) AS naechster_auftrag_datum "
              "FROM anlage a JOIN objekt o ON o.id = a.objekt_id JOIN kunde k ON k.id = o.kunde_id "
              "WHERE a.geloescht = 0 AND o.geloescht = 0 AND k.geloescht = 0")


def holen(con, anlage_id):
    return con.execute(_GRUND_SQL + " AND a.id = ?", (anlage_id,)).fetchone()


FAELLIG_FILTER = (("pruefung_ueberfaellig", "Prüfung überfällig"), ("pruefung_bald", "Prüfung überfällig oder bald"),
                  ("austausch_bald", "Austausch überfällig oder bald"))


def bewerten(zeile, heute=None):
    """Anlage als dict mit Ampeln: früheste Prüfung und frühester Austausch ihrer verbauten Komponenten.
    Passive Anlagen ruhen (keine Ampel)."""
    heute = heute or date.today()
    d = dict(zeile)
    art = anlagenart.holen(d["anlagenart"])
    if d["passiv"]:
        d["pruefung_ampel"] = d["austausch_ampel"] = "grau"
    else:
        d["pruefung_ampel"] = faelligkeit.ampel(d["naechste_pruefung_am"], heute, art.vorwarnung_tage)
        d["austausch_ampel"] = faelligkeit.ampel(d["naechster_austausch_am"], heute,
                                                 faelligkeit.AUSTAUSCH_VORWARNUNG_TAGE)
    return d


def passt(d, faellig):
    """Erfüllt eine bewertete Anlage den Fälligkeitsfilter?"""
    if not faellig:
        return True
    if d["passiv"]:
        return False
    return {"pruefung_ueberfaellig": d["pruefung_ampel"] == "rot",
            "pruefung_bald": d["pruefung_ampel"] in ("rot", "gelb"),
            "austausch_bald": d["austausch_ampel"] in ("rot", "gelb")}[faellig]


def liste(con, suche="", art="", faellig="", heute=None, ohne_auftrag=False, techniker="", label=""):
    """Alle Anlagen mit Objekt, Kunde, wirksamer Anschrift, Anzahl Wohnungen/Komponenten, Ampeln und nächstem
    offenen Auftrag; optional gefiltert nach Fälligkeit (FAELLIG_FILTER) und „ohne offenen Auftrag“."""
    sql, parameter = _GRUND_SQL, []
    if suche.strip():
        felder = ("a.nummer", "a.bezeichnung", "o.nummer", "o.bezeichnung", "k.nummer", "k.name",
                  "CASE WHEN o.adresse_wie_kunde = 1 THEN k.strasse ELSE o.strasse END",
                  "CASE WHEN o.adresse_wie_kunde = 1 THEN k.ort ELSE o.ort END")
        sql += " AND (" + " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in felder) + ")"
        parameter += [like_muster(suche.strip())] * len(felder)
    if art:
        sql += " AND a.anlagenart = ?"
        parameter.append(art)
    if techniker == "keiner":
        sql += " AND a.stammtechniker_id IS NULL"
    elif techniker:
        sql += " AND a.stammtechniker_id = ?"
        parameter.append(techniker)
    if label:
        sql += labels.filter_sql("anlage", "a.id")
        parameter.append(label)
    if faellig and faellig not in dict(FAELLIG_FILTER):
        faellig = ""
    zeilen = con.execute(sql + " ORDER BY adr_ort COLLATE NOCASE, adr_strasse COLLATE NOCASE, a.nummer",
                         parameter).fetchall()
    return [d for d in (bewerten(z, heute) for z in zeilen)
            if passt(d, faellig) and not (ohne_auftrag and d["naechster_auftrag_id"])]


def faellig_zaehlen(con, heute=None):
    """Anzahl Anlagen je Fälligkeitsfilter, z. B. für die Startseite."""
    alle = liste(con, heute=heute)
    zahlen = {schluessel: sum(1 for d in alle if passt(d, schluessel)) for schluessel, _ in FAELLIG_FILTER}
    zahlen["pruefung_bald_ohne_auftrag"] = sum(1 for d in alle if passt(d, "pruefung_bald")
                                               and not d["naechster_auftrag_id"])
    return zahlen


def liste_fuer_objekt(con, objekt_id):
    return con.execute(_GRUND_SQL + " AND a.objekt_id = ? ORDER BY a.nummer", (objekt_id,)).fetchall()


# ---------- Schreiben ----------

def _pruefen(con, felder, form, eigene_id=None):
    werte, fehler = einlesen(felder, form)
    werte["stammtechniker_id"] = werte.get("stammtechniker_id") or None
    if werte["nummer"]:
        fehler_nr = nummern.pruefen(con, "anlage", werte["nummer"], eigene_id)
        if fehler_nr:
            fehler["nummer"] = fehler_nr
    if fehler:
        raise Ungueltig(fehler)
    return werte


def vorbelegung(art_schluessel="rauchwarnmelder"):
    """Startwerte für das Formular „Anlage anlegen“ aus der Anlagenart."""
    art = anlagenart.alle().get(art_schluessel)
    return {"anlagenart": art_schluessel, "verfahren": "A",
            "einzelnachweis_je_wohnung": int(bool(art and art.einzelnachweis_je_gruppe))}


def anlegen(con, objekt_id, form, nutzer_id):
    werte = _pruefen(con, felder_neu(techniker_auswahl(con)), form)
    with db.transaktion(con):
        werte["nummer"] = werte["nummer"] or nummern.naechste(con, "anlage")
        return db.anlegen(con, "anlage", {**werte, "objekt_id": objekt_id}, nutzer_id)


def aendern(con, anlage_id, form, nutzer_id):
    """Ändert die Anlage; die Anlagenart ist nicht änderbar (steht nicht in den Feldern)."""
    alt = holen(con, anlage_id)
    felder = felder_bearbeiten(techniker_auswahl(con, alt["stammtechniker_id"] if alt else None))
    return db.aendern(con, "anlage", anlage_id, _pruefen(con, felder, form, anlage_id), nutzer_id)


def loeschen(con, anlage_id, nutzer_id):
    """Markiert die Anlage und ihre Kontakt-Zuordnungen als gelöscht – nur ohne Wohnungen und ohne Aufträge
    (außer stornierten): Aufträge sind Nachweise und sollen nicht verwaisen."""
    with db.transaktion(con):
        if con.execute("SELECT 1 FROM auftrag WHERE anlage_id = ? AND geloescht = 0 AND status != 'storniert'",
                       (anlage_id,)).fetchone():
            raise Ungueltig({"auftraege": "Die Anlage hat Aufträge und kann daher nicht gelöscht werden."})
        if con.execute("SELECT 1 FROM gruppe WHERE anlage_id = ? AND geloescht = 0", (anlage_id,)).fetchone():
            raise Ungueltig({"": "Die Anlage hat noch Wohnungen. Bitte zuerst diese löschen."})
        for z in con.execute("SELECT id FROM anlage_kontakt WHERE anlage_id = ? AND geloescht = 0",
                             (anlage_id,)).fetchall():
            db.aendern(con, "anlage_kontakt", z["id"], {"geloescht": 1}, nutzer_id)
        db.aendern(con, "anlage", anlage_id, {"geloescht": 1}, nutzer_id)


# ---------- Verschieben ----------

def ziel_objekte(con, suche, ausser_objekt_id, grenze=30):
    """Objekte, in die eine Anlage verschoben werden kann (Suche in Nummer, Bezeichnung, Kunde, Ort)."""
    sql = (f"SELECT o.id, o.nummer, o.bezeichnung, k.nummer AS kunde_nummer, k.name AS kunde_name, {ADRESSE_SQL} "
           "FROM objekt o JOIN kunde k ON k.id = o.kunde_id "
           "WHERE o.geloescht = 0 AND k.geloescht = 0 AND o.id != ?")
    parameter = [ausser_objekt_id]
    if suche.strip():
        felder = ("o.nummer", "o.bezeichnung", "k.nummer", "k.name",
                  "CASE WHEN o.adresse_wie_kunde = 1 THEN k.strasse ELSE o.strasse END",
                  "CASE WHEN o.adresse_wie_kunde = 1 THEN k.ort ELSE o.ort END")
        sql += " AND (" + " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in felder) + ")"
        parameter += [like_muster(suche.strip())] * len(felder)
    return con.execute(sql + " ORDER BY k.name COLLATE NOCASE, o.bezeichnung COLLATE NOCASE LIMIT ?",
                       (*parameter, grenze)).fetchall()


def verschieben(con, anlage_id, objekt_id, nutzer_id):
    """Hängt die Anlage samt Wohnungen, Komponenten und Aufträgen an ein anderes Objekt (auch eines anderen Kunden).
    Zugeordnete Ansprechpartner, die nicht zum Kunden des neuen Objekts gehören, werden entfernt.
    Gibt die Namen der entfernten Ansprechpartner zurück."""
    with db.transaktion(con):
        a = holen(con, anlage_id)
        if a is None:
            raise Ungueltig({"": "Anlage nicht gefunden."})
        ziel = objekte.holen(con, objekt_id)
        if ziel is None:
            raise Ungueltig({"objekt_id": "Bitte ein Objekt wählen."})
        if ziel["id"] == a["objekt_id"]:
            raise Ungueltig({"objekt_id": "Die Anlage liegt schon in diesem Objekt."})
        db.aendern(con, "anlage", anlage_id, {"objekt_id": objekt_id}, nutzer_id)
        return kontakte_bereinigen(con, anlage_id, nutzer_id)


def kontakte_bereinigen(con, anlage_id, nutzer_id):
    """Entfernt Ansprechpartner-Zuordnungen, deren Kontakt nicht (mehr) bei dem Kunden der Anlage geführt wird."""
    kunde_id = holen(con, anlage_id)["kunde_id"]
    namen = []
    for z in con.execute(
            "SELECT z.id, kt.name FROM anlage_kontakt z JOIN kontakt kt ON kt.id = z.kontakt_id "
            "WHERE z.anlage_id = ? AND z.geloescht = 0 AND NOT EXISTS ("
            "  SELECT 1 FROM kunde_kontakt kk WHERE kk.kontakt_id = z.kontakt_id AND kk.kunde_id = ? "
            "  AND kk.geloescht = 0)", (anlage_id, kunde_id)).fetchall():
        db.aendern(con, "anlage_kontakt", z["id"], {"geloescht": 1}, nutzer_id)
        namen.append(z["name"])
    return namen


# ---------- Ansprechpartner ----------

def kontakte(con, anlage_id):
    """Zugeordnete Kontakte mit Rolle, sortiert nach Rolle und Name."""
    reihenfolge = " ".join(f"WHEN '{w}' THEN {i}" for i, (w, _) in enumerate(KONTAKT_ROLLEN))
    return con.execute(
        "SELECT z.id AS zuordnung_id, z.rolle, kt.* FROM anlage_kontakt z JOIN kontakt kt ON kt.id = z.kontakt_id "
        f"WHERE z.anlage_id = ? AND z.geloescht = 0 AND kt.geloescht = 0 "
        f"ORDER BY CASE z.rolle {reihenfolge} END, kt.name COLLATE NOCASE", (anlage_id,)).fetchall()


def kontakt_zuordnen(con, anlage_id, kontakt_id, rolle, nutzer_id):
    """Ordnet einen Kontakt des Kunden der Anlage in einer Rolle zu."""
    if rolle not in dict(KONTAKT_ROLLEN):
        raise Ungueltig({"rolle": "Bitte eine Rolle wählen."})
    with db.transaktion(con):
        passend = con.execute(
            "SELECT 1 FROM kontakt kt JOIN kunde_kontakt kk ON kk.kontakt_id = kt.id AND kk.geloescht = 0 "
            "JOIN objekt o ON o.kunde_id = kk.kunde_id JOIN anlage a ON a.objekt_id = o.id "
            "WHERE kt.id = ? AND a.id = ? AND kt.geloescht = 0", (kontakt_id, anlage_id)).fetchone()
        if not passend:
            raise Ungueltig({"kontakt_id": "Bitte einen Kontakt dieses Kunden wählen."})
        if con.execute("SELECT 1 FROM anlage_kontakt WHERE anlage_id = ? AND kontakt_id = ? AND rolle = ? "
                       "AND geloescht = 0", (anlage_id, kontakt_id, rolle)).fetchone():
            raise Ungueltig({"kontakt_id": "Dieser Kontakt ist in dieser Rolle schon zugeordnet."})
        return db.anlegen(con, "anlage_kontakt", {"anlage_id": anlage_id, "kontakt_id": kontakt_id, "rolle": rolle},
                          nutzer_id)


def kontakt_entfernen(con, anlage_id, zuordnung_id, nutzer_id):
    z = con.execute("SELECT id FROM anlage_kontakt WHERE id = ? AND anlage_id = ? AND geloescht = 0",
                    (zuordnung_id, anlage_id)).fetchone()
    if z is None:
        raise Ungueltig({"": "Zuordnung nicht gefunden."})
    db.aendern(con, "anlage_kontakt", zuordnung_id, {"geloescht": 1}, nutzer_id)
