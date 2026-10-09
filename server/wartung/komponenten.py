"""Komponenten (bei Rauchwarnmeldern: die Melder) einer Gruppe: Felder, Anzeige mit Ampel, Anlegen (einzeln und
mehrere), Ändern, Löschen (Fehleingabe).

Nummer: laufend je Gruppe („43/1“), eindeutig unter den verbauten Komponenten der Gruppe. Funk-ID und Barcode sind
überall eindeutig. Fälligkeiten rechnet nach jedem Speichern faelligkeit.py. Austausch und Ausbau (Lebenslauf) folgen
in lebenslauf.py.
"""
import sqlite3
from datetime import date

from . import db, faelligkeit, typen
from .felder import Feld, Ungueltig, einlesen

RAUMARTEN = (("schlafraum", "Schlafraum"), ("kinderzimmer", "Kinderzimmer"),
             ("flur_rettungsweg", "Flur / Rettungsweg"), ("sonstiger", "sonstiger Raum"))
MAX_NUMMER = 999


def _baujahr_feld():
    return Feld("baujahr", "Baujahr", "zahl", minimum=1990, maximum=date.today().year + 1,
                hilfe="laut Aufdruck / Herstelldatum")


def felder(con, art, typ_bisher=None):
    """Felder für eine Komponente; Typ-Auswahl aus dem Katalog der Anlagenart (inaktive nur, wenn schon gewählt)."""
    return (
        Feld("nummer", "Nr.", "zahl", minimum=1, maximum=MAX_NUMMER, hilfe="leer = nächste freie"),
        Feld("komponententyp_id", "Typ", "auswahl", pflicht=True, auswahl=typen.auswahl(con, art.schluessel, typ_bisher)),
        Feld("raum", "Raum", vorschlaege=art.raeume, max_laenge=80),
        Feld("raumart", "Raumart", "auswahl", auswahl=RAUMARTEN, hilfe="leer = aus dem Raum ableiten"),
        Feld("seriennummer", "Seriennummer", max_laenge=80),
        Feld("funk_id", "Funk-ID", max_laenge=40, hilfe="nur bei Funkmeldern (Ferninspektion)"),
        Feld("barcode", "Barcode / QR-Aufkleber", max_laenge=80),
        _baujahr_feld(),
        Feld("inbetriebnahme_am", "In Betrieb seit", "datum"),
        Feld("letzte_pruefung_am", "Zuletzt geprüft am", "datum",
             hilfe="für übernommene Bestände; später setzt das die Prüfung selbst"),
        Feld("notiz", "Notiz", "textarea", max_laenge=2000, breit=True),
    )


def felder_mehrere(con, art):
    """Gemeinsame Angaben für „mehrere anlegen“; die Räume kommen als Liste dazu."""
    return (
        Feld("komponententyp_id", "Typ", "auswahl", pflicht=True, auswahl=typen.auswahl(con, art.schluessel)),
        _baujahr_feld(),
        Feld("inbetriebnahme_am", "In Betrieb seit", "datum"),
    )


# ---------- Lesen ----------

_SPALTEN = ("c.*, t.bezeichnung AS typ_bezeichnung, t.hersteller AS typ_hersteller, t.funk AS typ_funk, "
            "g.nummer AS gruppe_nummer, a.anlagenart")
_VON = ("FROM komponente c JOIN komponententyp t ON t.id = c.komponententyp_id JOIN gruppe g ON g.id = c.gruppe_id "
        "JOIN anlage a ON a.id = c.anlage_id")
_VERBAUT = "c.geloescht = 0 AND c.status = 'verbaut' AND g.geloescht = 0 AND a.geloescht = 0"


def holen(con, komponente_id):
    """Verbaute Komponente mit Typ, Gruppe und Anlagenart, oder None."""
    return con.execute(f"SELECT {_SPALTEN} {_VON} WHERE c.id = ? AND {_VERBAUT}", (komponente_id,)).fetchone()


def bewerten(zeile, art, heute=None):
    """Zeile als dict mit Ampeln für Prüfung und Austausch."""
    heute = heute or date.today()
    d = dict(zeile)
    d["pruefung_ampel"] = faelligkeit.ampel(d["naechste_pruefung_am"], heute, art.vorwarnung_tage)
    d["austausch_ampel"] = faelligkeit.ampel(d["austausch_faellig_am"], heute, faelligkeit.AUSTAUSCH_VORWARNUNG_TAGE)
    d["anzeige_nummer"] = art.nummer_anzeige(d["gruppe_nummer"], d["nummer"], d["sub_nummer"])
    return d


def je_gruppe(con, anlage_id, art, heute=None):
    """{gruppe_id: [Komponenten mit Ampel, nach Nummer]} – nur verbaute."""
    ergebnis = {}
    for z in con.execute(f"SELECT {_SPALTEN} {_VON} WHERE c.anlage_id = ? AND {_VERBAUT} "
                         "ORDER BY g.nummer, c.nummer, c.sub_nummer", (anlage_id,)):
        ergebnis.setdefault(z["gruppe_id"], []).append(bewerten(z, art, heute))
    return ergebnis


def naechste_nummer(con, gruppe_id):
    zeile = con.execute("SELECT MAX(nummer) FROM komponente WHERE gruppe_id = ? AND geloescht = 0 "
                        "AND status = 'verbaut'", (gruppe_id,)).fetchone()
    return (zeile[0] or 0) + 1


# ---------- Prüfen ----------

def eindeutig_pruefen(con, art, gruppe_id, werte, fehler, eigene_id=None):
    andere = "AND geloescht = 0 AND id != ?"
    if werte.get("nummer") is not None and con.execute(
            f"SELECT 1 FROM komponente WHERE gruppe_id = ? AND nummer = ? AND sub_nummer = 0 AND status = 'verbaut' "
            f"{andere}", (gruppe_id, werte["nummer"], eigene_id or "")).fetchone():
        fehler["nummer"] = f"Nr. {werte['nummer']} ist hier schon vergeben."
    for feld, titel in (("funk_id", "Funk-ID"), ("barcode", "Barcode")):
        if werte.get(feld) and con.execute(f"SELECT 1 FROM komponente WHERE {feld} = ? {andere}",
                                           (werte[feld], eigene_id or "")).fetchone():
            fehler[feld] = f"Diese {titel} ist schon anderweitig eingetragen."


def _daten_pruefen(werte, fehler):
    heute = date.today().isoformat()
    for feld in ("inbetriebnahme_am", "letzte_pruefung_am"):
        if werte.get(feld) and werte[feld] > heute:
            fehler.setdefault(feld, "Das Datum liegt in der Zukunft.")
    if werte.get("letzte_pruefung_am") and werte.get("inbetriebnahme_am") and \
            werte["letzte_pruefung_am"] < werte["inbetriebnahme_am"]:
        fehler.setdefault("letzte_pruefung_am", "Die Prüfung liegt vor der Inbetriebnahme.")
    if werte.get("baujahr") and werte.get("inbetriebnahme_am") and \
            int(werte["inbetriebnahme_am"][:4]) < werte["baujahr"]:
        fehler.setdefault("inbetriebnahme_am", "Inbetriebnahme vor dem Baujahr ist nicht möglich.")


def normalisieren(art, werte):
    """Leere eindeutige Felder als NULL (sonst kollidieren zwei leere), Raumart aus dem Raum ableiten."""
    for feld in ("funk_id", "barcode"):
        if feld in werte:
            werte[feld] = werte[feld].upper() if werte[feld] else None
    if "raumart" in werte and not werte["raumart"]:
        werte["raumart"] = art.raumart_fuer(werte.get("raum", ""))
    return werte


def _pruefen(con, art, gruppe_id, form, eigene_id=None, typ_bisher=None):
    werte, fehler = einlesen(felder(con, art, typ_bisher), form)
    normalisieren(art, werte)
    _daten_pruefen(werte, fehler)
    if eigene_id and werte["nummer"] is None:
        fehler["nummer"] = "Nr. ist Pflicht."
    eindeutig_pruefen(con, art, gruppe_id, werte, fehler, eigene_id)
    if fehler:
        raise Ungueltig(fehler)
    return werte


def sicher_schreiben(funktion):
    """Letzte Sicherung: verletzt ein gleichzeitiger Zugriff doch eine Eindeutigkeit, gibt es eine klare Meldung."""
    try:
        return funktion()
    except sqlite3.IntegrityError as e:
        raise Ungueltig({"": "Speichern nicht möglich: Nummer, Funk-ID oder Barcode wurde gerade anderweitig "
                             "vergeben. Bitte Eingaben prüfen."}) from e


# ---------- Schreiben ----------

def anlegen(con, art, gruppe, form, nutzer_id):
    def ausfuehren():
        with db.transaktion(con):
            werte = _pruefen(con, art, gruppe["id"], form)
            if werte["nummer"] is None:
                werte["nummer"] = naechste_nummer(con, gruppe["id"])
            kid = db.anlegen(con, "komponente", {**werte, "anlage_id": gruppe["anlage_id"],
                                                 "gruppe_id": gruppe["id"], "status": "verbaut"}, nutzer_id)
            faelligkeit.komponente_berechnen(con, kid)
            return kid
    return sicher_schreiben(ausfuehren)


def mehrere_anlegen(con, art, gruppe, form, raeume, nutzer_id):
    """Legt je Raum eine Komponente mit fortlaufender Nummer an (gleicher Typ, Baujahr, Inbetriebnahme)."""
    raeume = [r.strip() for r in raeume if r and r.strip()]
    werte, fehler = einlesen(felder_mehrere(con, art), form)
    _daten_pruefen(werte, fehler)
    if not raeume:
        fehler["raeume"] = "Bitte mindestens einen Raum wählen."
    elif len(raeume) > 20:
        fehler["raeume"] = "Höchstens 20 auf einmal."
    elif any(len(r) > 80 for r in raeume):
        fehler["raeume"] = "Raumnamen höchstens 80 Zeichen."
    if fehler:
        raise Ungueltig(fehler)

    def ausfuehren():
        with db.transaktion(con):
            nummer, ids = naechste_nummer(con, gruppe["id"]), []
            for raum in raeume:
                kid = db.anlegen(con, "komponente", {
                    **werte, "raum": raum, "raumart": art.raumart_fuer(raum), "nummer": nummer,
                    "anlage_id": gruppe["anlage_id"], "gruppe_id": gruppe["id"], "status": "verbaut"}, nutzer_id)
                faelligkeit.komponente_berechnen(con, kid)
                ids.append(kid)
                nummer += 1
            return ids
    return sicher_schreiben(ausfuehren)


def aendern(con, art, komponente, form, nutzer_id):
    def ausfuehren():
        with db.transaktion(con):
            werte = _pruefen(con, art, komponente["gruppe_id"], form, komponente["id"],
                             komponente["komponententyp_id"])
            anzahl = db.aendern(con, "komponente", komponente["id"], werte, nutzer_id)
            faelligkeit.komponente_berechnen(con, komponente["id"])
            return anzahl
    return sicher_schreiben(ausfuehren)


def loeschen(con, komponente_id, nutzer_id):
    """Nur für Fehleingaben: markiert als gelöscht. Ein echter Ausbau läuft über den Lebenslauf (ausbauen)."""
    db.aendern(con, "komponente", komponente_id, {"geloescht": 1}, nutzer_id)
