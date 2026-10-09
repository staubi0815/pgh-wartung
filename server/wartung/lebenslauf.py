"""Lebenslauf der Komponenten: austauschen und ausbauen (mit Maßnahme ⊕), Verlauf eines Platzes, Gruppe kopieren.

Austausch: Der alte Melder bekommt den Status „ersetzt“ und einen Verweis auf den neuen; der neue übernimmt Platz
(Gruppe, Nummer), Raum und Raumart. Beide bleiben dauerhaft gespeichert – der Nachweis, was wann verbaut war, geht
nicht verloren. Ausbau: Status „ausgebaut“, der Platz wird frei.
"""
from datetime import date

from . import db, faelligkeit, gruppen, komponenten, typen
from .felder import Feld, Ungueltig, einlesen

AUSBAU_GRUENDE = (("raum_entfaellt", "Raum entfällt / Umbau"), ("kunde", "auf Wunsch des Kunden"),
                  ("nicht_vorhanden", "Melder nicht vorhanden / doppelt erfasst"), ("sonstiges", "Sonstiges"))


def austausch_gruende(art):
    """Gründe aus den Mängeltypen der Anlagenart, die einen Austausch nahelegen, plus „Sonstiges“."""
    gruende = [(m.schluessel, m.name) for m in art.maengel if m.austausch_vorschlagen]
    if not any(s == "sonstiges" for s, _ in gruende):
        gruende.append(("sonstiges", "Sonstiges"))
    return tuple(gruende)


def felder_austausch(con, art):
    return (
        Feld("grund", "Grund", "auswahl", pflicht=True, auswahl=austausch_gruende(art)),
        Feld("zeitpunkt", "Ausgetauscht am", "datum", pflicht=True),
        Feld("komponententyp_id", "Typ (neu)", "auswahl", pflicht=True, auswahl=typen.auswahl(con, art.schluessel)),
        Feld("seriennummer", "Seriennummer (neu)", max_laenge=80),
        Feld("funk_id", "Funk-ID (neu)", max_laenge=40),
        Feld("barcode", "Barcode / QR-Aufkleber (neu)", max_laenge=80),
        Feld("baujahr", "Baujahr (neu)", "zahl", minimum=1990, maximum=date.today().year + 1),
        Feld("bemerkung", "Bemerkung", "textarea", max_laenge=2000, breit=True),
    )


def felder_ausbau():
    return (
        Feld("grund", "Grund", "auswahl", pflicht=True, auswahl=AUSBAU_GRUENDE),
        Feld("zeitpunkt", "Ausgebaut am", "datum", pflicht=True),
        Feld("bemerkung", "Bemerkung", "textarea", max_laenge=2000, breit=True),
    )


def _zeitpunkt_pruefen(werte, fehler, komponente):
    if werte.get("zeitpunkt"):
        if werte["zeitpunkt"] > date.today().isoformat():
            fehler["zeitpunkt"] = "Das Datum liegt in der Zukunft."
        elif komponente["inbetriebnahme_am"] and werte["zeitpunkt"] < komponente["inbetriebnahme_am"]:
            fehler["zeitpunkt"] = "Das Datum liegt vor der Inbetriebnahme."


def austauschen(con, art, komponente, form, nutzer_id):
    """Ersetzt eine verbaute Komponente durch eine neue am selben Platz. Gibt die id der neuen zurück."""
    werte, fehler = einlesen(felder_austausch(con, art), form)
    _zeitpunkt_pruefen(werte, fehler, komponente)
    neu = {k: werte[k] for k in ("komponententyp_id", "seriennummer", "funk_id", "barcode", "baujahr")}
    komponenten.normalisieren(art, neu)
    if neu["baujahr"] and werte["zeitpunkt"] and int(werte["zeitpunkt"][:4]) < neu["baujahr"]:
        fehler["baujahr"] = "Baujahr nach dem Austauschdatum ist nicht möglich."
    if fehler:
        raise Ungueltig(fehler)

    def ausfuehren():
        with db.transaktion(con):
            # erst den alten Platz freigeben, dann den neuen Melder auf denselben Platz setzen
            db.aendern(con, "komponente", komponente["id"], {"status": "ersetzt"}, nutzer_id)
            pruef_fehler = {}
            komponenten.eindeutig_pruefen(con, art, komponente["gruppe_id"], neu, pruef_fehler)
            if pruef_fehler:
                raise Ungueltig(pruef_fehler)
            neu_id = db.anlegen(con, "komponente", {
                **neu, "anlage_id": komponente["anlage_id"], "gruppe_id": komponente["gruppe_id"],
                "nummer": komponente["nummer"], "sub_nummer": komponente["sub_nummer"], "raum": komponente["raum"],
                "raumart": komponente["raumart"], "inbetriebnahme_am": werte["zeitpunkt"], "status": "verbaut"},
                nutzer_id)
            db.aendern(con, "komponente", komponente["id"], {"ersetzt_durch_id": neu_id}, nutzer_id)
            db.anlegen(con, "massnahme", {"art": "austausch", "komponente_alt_id": komponente["id"],
                                          "komponente_neu_id": neu_id, "grund": werte["grund"],
                                          "bemerkung": werte["bemerkung"], "zeitpunkt": werte["zeitpunkt"]}, nutzer_id)
            faelligkeit.komponente_berechnen(con, neu_id)
            return neu_id
    return komponenten.sicher_schreiben(ausfuehren)


def ausbauen(con, komponente, form, nutzer_id):
    werte, fehler = einlesen(felder_ausbau(), form)
    _zeitpunkt_pruefen(werte, fehler, komponente)
    if fehler:
        raise Ungueltig(fehler)
    with db.transaktion(con):
        db.aendern(con, "komponente", komponente["id"], {"status": "ausgebaut"}, nutzer_id)
        db.anlegen(con, "massnahme", {"art": "ausbau", "komponente_alt_id": komponente["id"], "grund": werte["grund"],
                                      "bemerkung": werte["bemerkung"], "zeitpunkt": werte["zeitpunkt"]}, nutzer_id)


def verlauf(con, gruppe_id, nummer, sub_nummer=0):
    """Frühere Komponenten an einem Platz (ersetzt/ausgebaut) mit der Maßnahme, neueste zuerst."""
    return con.execute(
        "SELECT c.*, t.bezeichnung AS typ_bezeichnung, m.art AS massnahme_art, m.grund, m.bemerkung, m.zeitpunkt "
        "FROM komponente c JOIN komponententyp t ON t.id = c.komponententyp_id "
        "LEFT JOIN massnahme m ON m.komponente_alt_id = c.id "
        "WHERE c.gruppe_id = ? AND c.nummer = ? AND c.sub_nummer = ? AND c.geloescht = 0 "
        "AND c.status IN ('ersetzt', 'ausgebaut') ORDER BY m.zeitpunkt DESC, c.erstellt_am DESC",
        (gruppe_id, nummer, sub_nummer)).fetchall()


def gruppe_kopieren(con, art, gruppe, form, nutzer_id):
    """Neue Gruppe (z. B. Wohnung mit gleichem Grundriss) mit denselben Komponenten-Plätzen anlegen:
    Typ, Raum, Raumart, Baujahr und Inbetriebnahme werden übernommen, Seriennummern/Funk-IDs/Barcodes nicht."""
    with db.transaktion(con):
        neu_id = gruppen.anlegen(con, art, gruppe["anlage_id"], form, nutzer_id)
        for k in con.execute("SELECT * FROM komponente WHERE gruppe_id = ? AND geloescht = 0 AND status = 'verbaut' "
                             "ORDER BY nummer, sub_nummer", (gruppe["id"],)).fetchall():
            kid = db.anlegen(con, "komponente", {
                "anlage_id": gruppe["anlage_id"], "gruppe_id": neu_id, "nummer": k["nummer"],
                "sub_nummer": k["sub_nummer"], "komponententyp_id": k["komponententyp_id"], "raum": k["raum"],
                "raumart": k["raumart"], "baujahr": k["baujahr"], "inbetriebnahme_am": k["inbetriebnahme_am"],
                "status": "verbaut"}, nutzer_id)
            faelligkeit.komponente_berechnen(con, kid)
        return neu_id
