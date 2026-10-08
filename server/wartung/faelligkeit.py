"""Fälligkeiten: nächste Prüfung und Austausch je Komponente, Ampel. Rechnet nur der Server.

Regeln (docs/03 Abschnitt 5, Werte aus der Anlagenart-Konfiguration):
- Nächste Prüfung = letzte Prüfung + Prüfintervall (gleitend); ohne Prüfung: Inbetriebnahme + Intervall;
  ohne beides: unbekannt (None).
- Austausch = Baujahr + Austauschjahre (+ Zugabe). Vom Baujahr ist nur das Jahr bekannt, daher wird vorsichtig ab dem
  1. Januar gerechnet. Ohne Baujahr (oder bei austausch_ab = "inbetriebnahme"): Inbetriebnahme + Austauschjahre.
  Ein Komponententyp kann eigene Austauschjahre haben (z. B. Melder mit kürzerer Lebensdauer).
- Ampel: rot = überfällig, gelb = innerhalb der Vorwarnzeit, grün = später, grau = unbekannt.
"""
import calendar
from datetime import date

from . import anlagenart

AMPEL_TEXT = {"rot": "überfällig", "gelb": "bald fällig", "gruen": "in Ordnung", "grau": "unbekannt"}
AUSTAUSCH_VORWARNUNG_TAGE = 183   # Austausch rechtzeitig einplanen: gelb ab etwa sechs Monaten vorher (docs/04)


def monate_addieren(tag, monate):
    """Datum + Monate; am Monatsende auf den letzten gültigen Tag (31.01. + 1 Monat = 28./29.02.)."""
    monat_gesamt = tag.month - 1 + monate
    jahr, monat = tag.year + monat_gesamt // 12, monat_gesamt % 12 + 1
    return date(jahr, monat, min(tag.day, calendar.monthrange(jahr, monat)[1]))


def _datum(wert):
    if not wert:
        return None
    return wert if isinstance(wert, date) else date.fromisoformat(str(wert)[:10])


def naechste_pruefung(art, letzte_pruefung=None, inbetriebnahme=None):
    basis = _datum(letzte_pruefung) or _datum(inbetriebnahme)
    return monate_addieren(basis, art.pruefung_monate) if basis else None


def austausch_faellig(art, baujahr=None, inbetriebnahme=None, typ_jahre=None):
    jahre = typ_jahre or art.austausch_jahre
    if baujahr and art.austausch_ab == "baujahr":
        basis = date(int(baujahr), 1, 1)
    else:
        basis = _datum(inbetriebnahme)
    if basis is None:
        return None
    return monate_addieren(basis, jahre * 12 + art.austausch_zugabe_monate)


def ampel(datum, heute, vorwarnung_tage):
    datum = _datum(datum)
    if datum is None:
        return "grau"
    if datum < heute:
        return "rot"
    if (datum - heute).days <= vorwarnung_tage:
        return "gelb"
    return "gruen"


# ---------- in der Datenbank nachführen ----------

_KOMPONENTE_SQL = ("SELECT c.id, c.baujahr, c.inbetriebnahme_am, c.letzte_pruefung_am, c.naechste_pruefung_am, "
                   "c.austausch_faellig_am, t.austausch_jahre AS typ_jahre, a.anlagenart "
                   "FROM komponente c JOIN komponententyp t ON t.id = c.komponententyp_id "
                   "JOIN anlage a ON a.id = c.anlage_id WHERE c.geloescht = 0 AND c.status = 'verbaut'")


def _nachfuehren(con, zeilen):
    """Schreibt die berechneten Daten; abgeleitete Werte werden nicht ins Änderungsprotokoll geschrieben."""
    geaendert = 0
    for z in zeilen:
        art = anlagenart.holen(z["anlagenart"])
        pruefung = naechste_pruefung(art, z["letzte_pruefung_am"], z["inbetriebnahme_am"])
        austausch = austausch_faellig(art, z["baujahr"], z["inbetriebnahme_am"], z["typ_jahre"])
        neu = (pruefung.isoformat() if pruefung else None, austausch.isoformat() if austausch else None)
        if neu != (z["naechste_pruefung_am"], z["austausch_faellig_am"]):
            con.execute("UPDATE komponente SET naechste_pruefung_am = ?, austausch_faellig_am = ? WHERE id = ?",
                        (*neu, z["id"]))
            geaendert += 1
    return geaendert


def komponente_berechnen(con, komponente_id):
    return _nachfuehren(con, con.execute(_KOMPONENTE_SQL + " AND c.id = ?", (komponente_id,)).fetchall())


def typ_berechnen(con, typ_id):
    """Nach Änderung der Austauschjahre eines Typs alle verbauten Komponenten dieses Typs neu rechnen."""
    return _nachfuehren(con, con.execute(_KOMPONENTE_SQL + " AND c.komponententyp_id = ?", (typ_id,)).fetchall())


def alle_berechnen(con):
    """Alles neu rechnen (z. B. nach Änderung der Anlagenart-Konfiguration). Gibt die Anzahl Änderungen zurück."""
    return _nachfuehren(con, con.execute(_KOMPONENTE_SQL).fetchall())
