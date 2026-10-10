"""Globale Suche über Kunden, Kontakte, Objekte, Anlagen, Wohnungen, Melder und Aufträge.

Nur lesend. Stammdaten-Treffer verlangen das Recht stammdaten.lesen; Aufträge richten sich nach der Sicht des Nutzers
(Techniker sehen nur eigene Aufträge und den Pool).
"""
from . import anlagen, auftraege
from .felder import like_muster

PRO_GRUPPE = 10
MIN_ZEICHEN = 2


def _abfrage(con, sql, felder, muster):
    bedingung = " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in felder)
    return con.execute(sql.replace("{BEDINGUNG}", bedingung) + f" LIMIT {PRO_GRUPPE + 1}",
                       [muster] * len(felder)).fetchall()


def suchen(con, begriff, rechte_menge, nutzer_id):
    """Treffer je Gruppe als {schluessel: (zeilen, mehr)}; zu kurze Begriffe liefern ein leeres Ergebnis."""
    begriff = (begriff or "").strip()
    if len(begriff) < MIN_ZEICHEN:
        return {}
    muster = like_muster(begriff)
    ergebnis = {}

    def merken(schluessel, zeilen):
        if zeilen:
            ergebnis[schluessel] = (list(zeilen[:PRO_GRUPPE]), len(zeilen) > PRO_GRUPPE)

    if "stammdaten.lesen" in rechte_menge:
        merken("kunden", _abfrage(
            con, "SELECT id, nummer, name, zusatz, plz, ort FROM kunde WHERE geloescht = 0 AND ({BEDINGUNG}) "
                 "ORDER BY name COLLATE NOCASE",
            ("nummer", "name", "zusatz", "ort", "strasse", "plz", "telefon", "email"), muster))
        merken("kontakte", _abfrage(
            con, "SELECT c.id, c.name, c.firma, c.funktion, c.telefon, c.mobil, "
                 "(SELECT group_concat(k.name, ', ') FROM kunde_kontakt z JOIN kunde k ON k.id = z.kunde_id "
                 " WHERE z.kontakt_id = c.id AND z.geloescht = 0 AND k.geloescht = 0) AS kunde_name "
                 "FROM kontakt c WHERE c.geloescht = 0 AND ({BEDINGUNG}) "
                 "ORDER BY c.name COLLATE NOCASE",
            ("c.name", "c.firma", "c.telefon", "c.mobil", "c.email"), muster))
        merken("objekte", _abfrage(
            con, "SELECT o.id, o.nummer, o.bezeichnung, k.name AS kunde_name, "
                 " CASE WHEN o.adresse_wie_kunde = 1 THEN k.strasse ELSE o.strasse END AS strasse, "
                 " CASE WHEN o.adresse_wie_kunde = 1 THEN k.plz ELSE o.plz END AS plz, "
                 " CASE WHEN o.adresse_wie_kunde = 1 THEN k.ort ELSE o.ort END AS ort "
                 "FROM objekt o JOIN kunde k ON k.id = o.kunde_id WHERE o.geloescht = 0 AND k.geloescht = 0 "
                 "AND ({BEDINGUNG}) ORDER BY o.bezeichnung COLLATE NOCASE",
            ("o.nummer", "o.bezeichnung", "o.strasse", "o.ort", "o.plz"), muster))
        treffer = anlagen.liste(con, begriff)
        merken("anlagen", treffer[:PRO_GRUPPE + 1])
        merken("wohnungen", _abfrage(
            con, "SELECT g.id, g.nummer, g.bezeichnung, g.bewohner, a.id AS anlage_id, a.nummer AS anlage_nummer "
                 "FROM gruppe g JOIN anlage a ON a.id = g.anlage_id WHERE g.geloescht = 0 AND a.geloescht = 0 "
                 "AND ({BEDINGUNG}) ORDER BY a.nummer, g.nummer",
            ("g.bezeichnung", "g.bewohner", "g.bewohner_telefon", "CAST(g.nummer AS TEXT)"), muster))
        merken("melder", _abfrage(
            con, "SELECT c.id, c.seriennummer, c.barcode, c.funk_id, c.raum, c.status, g.nummer AS gruppe_nummer, "
                 " c.nummer AS komp_nummer, a.nummer AS anlage_nummer, t.bezeichnung AS typ "
                 "FROM komponente c JOIN komponententyp t ON t.id = c.komponententyp_id "
                 "LEFT JOIN anlage a ON a.id = c.anlage_id LEFT JOIN gruppe g ON g.id = c.gruppe_id "
                 "WHERE c.geloescht = 0 AND ({BEDINGUNG}) ORDER BY c.seriennummer",
            ("c.seriennummer", "c.barcode", "c.funk_id"), muster))
    sicht = auftraege.sicht(rechte_menge, nutzer_id)
    merken("auftraege", auftraege.liste(con, status="alle", suche=begriff, eingeschraenkt=sicht)[:PRO_GRUPPE + 1])
    return ergebnis
