"""Excel-Import im Format der Foxtag-Importvorlagen (docs/05): Kunden, Kontakte, Objekte, Anlagen, Typen, Melder.

Ablauf: lesen → prüfen (Probelauf, der am Ende vollständig zurückgerollt wird) → übernehmen (alles oder nichts).
Jede Zeile läuft durch dieselbe Fachlogik wie die Eingabemasken (kunden.anlegen usw.); deshalb zeigt die Vorschau
genau das, was beim Übernehmen passiert. Vorhandene Datensätze (gleiche Nummer bzw. gleicher Platz) werden nicht
überschrieben, sondern übersprungen.
"""
import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from . import anlagen, anlagenart, db, gruppen, komponenten, kunden, objekte, typen
from .felder import Ungueltig

MAX_BYTES = 5 * 1024 * 1024
MAX_ZEILEN = 5000
LAENDER = {"deutschland": "DE", "germany": "DE", "österreich": "AT", "oesterreich": "AT", "austria": "AT",
           "schweiz": "CH", "switzerland": "CH"}


class DateiFehler(ValueError):
    """Die Datei als Ganzes ist nicht verwendbar (kein Excel, zu groß, Pflichtspalten fehlen)."""


@dataclass
class Zeile:
    nr: int                     # Zeilennummer in Excel
    status: str                 # neu | vorhanden | fehler
    text: str                   # kurze Beschreibung des Datensatzes
    meldungen: list = field(default_factory=list)


@dataclass
class Ergebnis:
    art: str
    zeilen: list = field(default_factory=list)
    hinweise: list = field(default_factory=list)   # betrifft die ganze Datei (z. B. ignorierte Spalten)
    gespeichert: bool = False

    def anzahl(self, status):
        return sum(1 for z in self.zeilen if z.status == status)

    @property
    def ok(self):
        return self.anzahl("fehler") == 0


# ---------- Werte aus Excel-Zellen ----------

def text(wert):
    """Zelle als Text; ganze Zahlen ohne „.0“ (Excel speichert Nummern oft als Zahl)."""
    if wert is None:
        return ""
    if isinstance(wert, bool):
        return "ja" if wert else ""
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    if isinstance(wert, (datetime, date)):
        return wert.strftime("%Y-%m-%d")
    return " ".join(str(wert).split())


def datum(wert):
    """Zelle als JJJJ-MM-TT; erlaubt Excel-Datum, 17.11.2016, 17.11.16, 2016-11-17. Leer = ''."""
    if wert is None or wert == "":
        return ""
    if isinstance(wert, (datetime, date)):
        return wert.strftime("%Y-%m-%d")
    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text(wert), muster).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise Ungueltig({"": f"Datum „{text(wert)}“ nicht lesbar (erwartet z. B. 17.11.2016)."})


def land(wert):
    t = text(wert)
    return LAENDER.get(t.lower(), t.upper()) if t else "DE"


def plz(wert, land_code):
    """PLZ als Text; in Deutschland eine von Excel verlorene führende Null ergänzen (1067 -> 01067)."""
    t = text(wert)
    if land_code == "DE" and t.isdigit() and len(t) == 4:
        return "0" + t
    return t


def wohnungsname(name):
    """Foxtag GRUPPE.NAME „Bewohner, Lage“ -> (bewohner, lage); ohne Komma nur Lage."""
    if "," in name:
        bewohner, lage = name.split(",", 1)
        return bewohner.strip(), lage.strip()
    return "", name.strip()


# ---------- Datei lesen ----------

def _spaltenname(wert):
    return text(wert).upper().replace("*", "").strip()


def lesen(inhalt):
    """Liest das erste Blatt. Rückgabe: (Spaltennamen, [(Excel-Zeilennummer, {Spalte: Wert})])."""
    if len(inhalt) > MAX_BYTES:
        raise DateiFehler(f"Die Datei ist größer als {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        mappe = openpyxl.load_workbook(io.BytesIO(inhalt), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as e:
        raise DateiFehler("Die Datei ist keine lesbare Excel-Datei (.xlsx).") from e
    try:
        kopf, zeilen = None, []
        for nr, werte in enumerate(mappe.worksheets[0].iter_rows(values_only=True), 1):
            if kopf is None:
                if any(v not in (None, "") for v in werte):
                    kopf = [_spaltenname(v) for v in werte]
                continue
            if all(v in (None, "") for v in werte):
                continue
            if len(zeilen) >= MAX_ZEILEN:
                raise DateiFehler(f"Höchstens {MAX_ZEILEN} Zeilen je Datei.")
            zeilen.append((nr, {k: v for k, v in zip(kopf, werte) if k}))
    finally:
        mappe.close()
    if kopf is None:
        raise DateiFehler("Die Datei ist leer.")
    return kopf, zeilen


# ---------- Importarten ----------

@dataclass(frozen=True)
class Importart:
    schluessel: str
    titel: str
    pflicht: tuple          # Spalten, die vorhanden sein müssen
    optional: tuple         # weitere bekannte Spalten
    ignoriert: tuple = ()   # bekannte Foxtag-Spalten, die (noch) nicht übernommen werden
    braucht_anlage: bool = False

    @property
    def spalten(self):
        return self.pflicht + self.optional


def _kunde_nach_nummer(con, nummer):
    if not nummer:
        raise Ungueltig({"": "Kundennummer fehlt."})
    k = con.execute("SELECT * FROM kunde WHERE nummer = ? COLLATE NOCASE AND geloescht = 0", (nummer,)).fetchone()
    if k is None:
        raise Ungueltig({"": f"Kunde {nummer} gibt es nicht (zuerst Kunden importieren)."})
    return k


def _kunde(con, w, nutzer_id, optionen):
    nummer = text(w.get("KUNDEN.NUMMER"))
    lc = land(w.get("LAND"))
    beschreibung = f"{nummer} {text(w.get('KUNDE.NAME'))}"
    if nummer and con.execute("SELECT 1 FROM kunde WHERE nummer = ? COLLATE NOCASE", (nummer,)).fetchone():
        return "vorhanden", beschreibung, []
    if not nummer:
        raise Ungueltig({"": "Kundennummer fehlt."})
    kunden.anlegen(con, {"nummer": nummer, "art": optionen.get("kundenart", "hausverwaltung"),
                         "name": text(w.get("KUNDE.NAME")), "strasse": text(w.get("ADRESSZEILE 1")),
                         "zusatz": text(w.get("ADRESSZEILE 2")), "plz": plz(w.get("PLZ"), lc), "ort": text(w.get("ORT")),
                         "land": lc, "notiz_intern": text(w.get("NOTIZ"))}, nutzer_id)
    return "neu", beschreibung, []


def _kontakt(con, w, nutzer_id, optionen):
    name = text(w.get("NAME"))
    k = _kunde_nach_nummer(con, text(w.get("KUNDE")))
    beschreibung = f"{name} ({k['nummer']})"
    if name and con.execute("SELECT 1 FROM kontakt WHERE kunde_id = ? AND name = ? COLLATE NOCASE AND geloescht = 0",
                            (k["id"], name)).fetchone():
        return "vorhanden", beschreibung, []
    kunden.kontakt_anlegen(con, k["id"], {"name": name, "firma": text(w.get("FIRMA")), "email": text(w.get("EMAIL")),
                                          "telefon": text(w.get("TELEFON")), "mobil": text(w.get("MOBIL")),
                                          "fax": text(w.get("FAX")), "notiz": text(w.get("NOTIZ"))}, nutzer_id)
    return "neu", beschreibung, []


def _objekt(con, w, nutzer_id, optionen):
    nummer, name = text(w.get("OBJEKT.NUMMER")), text(w.get("OBJEKT.NAME"))
    beschreibung = f"{nummer or '(neue Nummer)'} {name}"
    if nummer and con.execute("SELECT 1 FROM objekt WHERE nummer = ? COLLATE NOCASE", (nummer,)).fetchone():
        return "vorhanden", beschreibung, []
    k = _kunde_nach_nummer(con, text(w.get("KUNDE.NUMMER")))
    lc = land(w.get("LAND"))
    zusatz = text(w.get("ADRESSZEILE 2"))
    oid = objekte.anlegen(con, k["id"], {"nummer": nummer, "bezeichnung": name, "strasse": text(w.get("ADRESSZEILE 1")),
                                        "plz": plz(w.get("PLZ"), lc), "ort": text(w.get("ORT")), "land": lc,
                                        "notiz": f"Adresszusatz: {zusatz}" if zusatz else ""}, nutzer_id)
    if not nummer:
        beschreibung = f"{objekte.holen(con, oid)['nummer']} {name}"
    return "neu", beschreibung, ["Adresszeile 2 in die Notiz übernommen."] if zusatz else []


def _anlage(con, w, nutzer_id, optionen):
    nummer, objekt_nr = text(w.get("ANLAGE.NUMMER")), text(w.get("OBJEKT.NUMMER"))
    beschreibung = f"{nummer} in Objekt {objekt_nr}"
    if not nummer:
        raise Ungueltig({"": "Anlagennummer fehlt."})
    if con.execute("SELECT 1 FROM anlage WHERE nummer = ? COLLATE NOCASE", (nummer,)).fetchone():
        return "vorhanden", beschreibung, []
    o = con.execute("SELECT id FROM objekt WHERE nummer = ? COLLATE NOCASE AND geloescht = 0", (objekt_nr,)).fetchone()
    if o is None:
        raise Ungueltig({"": f"Objekt {objekt_nr or '(leer)'} gibt es nicht (zuerst Objekte importieren)."})
    art = anlagenart.zum_importnamen(text(w.get("WARTUNGSANWENDUNG.NUMMER")))
    if art is None:
        bekannt = ", ".join(n for a in anlagenart.alle().values() for n in (a.name, *a.import_namen))
        raise Ungueltig({"": f"Anlagenart „{text(w.get('WARTUNGSANWENDUNG.NUMMER'))}“ unbekannt (möglich: {bekannt})."})
    anlagen.anlegen(con, o["id"], {"nummer": nummer, "anlagenart": art.schluessel, "verfahren": "A",
                                   "bezeichnung": text(w.get("ANLAGE.NAME"))}, nutzer_id)
    hinweise = ["Techniker-Nummer wird erst mit den Aufträgen übernommen."] if text(w.get("TECHNIKER.NUMMER")) else []
    return "neu", beschreibung, hinweise


def _typ_finden_oder_anlegen(con, art, name, hersteller, modell, kategorie, link, nutzer_id, muss_aktiv=False):
    """Gibt (Typ-id, neu angelegt?) zurück."""
    vorhanden = typen.finden(con, art.schluessel, name, hersteller, modell)
    if vorhanden:
        if muss_aktiv and not vorhanden["aktiv"]:
            raise Ungueltig({"": f"Typ „{vorhanden['bezeichnung']}“ ist im Katalog deaktiviert."})
        return vorhanden["id"], False
    bezeichnung = modell or name
    if not bezeichnung:
        raise Ungueltig({"": "Typ-Name fehlt."})
    if con.execute("SELECT 1 FROM komponententyp WHERE anlagenart = ? AND bezeichnung = ? COLLATE NOCASE "
                   "AND geloescht = 0", (art.schluessel, bezeichnung)).fetchone():
        bezeichnung = f"{bezeichnung} ({hersteller})" if hersteller else bezeichnung
    tid = typen.anlegen(con, {"anlagenart": art.schluessel, "bezeichnung": bezeichnung, "hersteller": hersteller,
                              "modell": modell, "kategorie": kategorie, "funk": "keine", "batterie": "fest_10j",
                              "datenblatt_link": link, "aktiv": "1"}, nutzer_id)
    return tid, True


def _typ(con, w, nutzer_id, optionen):
    art = anlagenart.holen(optionen.get("anlagenart", "rauchwarnmelder"))
    name, hersteller, modell = text(w.get("TYP.NAME")), text(w.get("TYP.HERSTELLER")), text(w.get("TYP.MODELL"))
    kategorie = {"komponente": "komponente", "sub-komponente": "sub_komponente", "subkomponente": "sub_komponente"}.get(
        text(w.get("TYP.KATEGORIE")).lower())
    if kategorie is None:
        raise Ungueltig({"": f"Kategorie „{text(w.get('TYP.KATEGORIE'))}“ unbekannt (Komponente oder Sub-Komponente)."})
    _, neu = _typ_finden_oder_anlegen(con, art, name, hersteller, modell, kategorie, text(w.get("TYP.LINK")), nutzer_id)
    return ("neu" if neu else "vorhanden"), " ".join(x for x in (hersteller, modell or name) if x), []


def _komponente(con, w, nutzer_id, optionen):
    anlage = optionen["anlage"]
    art = anlagenart.holen(anlage["anlagenart"])
    hinweise = []
    gruppe_nr = w.get("GRUPPE.NUMMER")
    if gruppe_nr in (None, ""):
        gruppe_nr, hinweise = 1, [f"Ohne {art.gruppe}-Nummer: {art.gruppe} 1 verwendet."]
    try:
        gruppe_nr = int(text(gruppe_nr))
        nummer = int(text(w.get("NUMMER")))
        sub = int(text(w.get("SUB-NUMMER")) or 0)
    except ValueError:
        raise Ungueltig({"": f"{art.gruppe}-Nummer, Nummer und Sub-Nummer müssen ganze Zahlen sein."}) from None
    beschreibung = f"{art.nummer_anzeige(gruppe_nr, nummer, sub)} {text(w.get('STANDORT'))}"
    if sub:
        raise Ungueltig({"": "Sub-Komponenten werden noch nicht unterstützt (folgt mit den Türen)."})
    g = con.execute("SELECT * FROM gruppe WHERE anlage_id = ? AND nummer = ? AND geloescht = 0",
                    (anlage["id"], gruppe_nr)).fetchone()
    bewohner, lage = wohnungsname(text(w.get("GRUPPE.NAME")))
    if g is None:
        gid = gruppen.anlegen(con, art, anlage["id"], {"nummer": str(gruppe_nr), "bezeichnung": lage,
                                                       "bewohner": bewohner, "zugang": "frei"}, nutzer_id)
        g = gruppen.holen(con, gid)
        hinweise.append(f"{art.gruppe} {gruppe_nr} neu angelegt.")
    if con.execute("SELECT 1 FROM komponente WHERE gruppe_id = ? AND nummer = ? AND sub_nummer = 0 AND geloescht = 0 "
                   "AND status = 'verbaut'", (g["id"], nummer)).fetchone():
        return "vorhanden", beschreibung, hinweise
    typ_id, typ_neu = _typ_finden_oder_anlegen(con, art, text(w.get("TYP.NAME")), text(w.get("TYP.HERSTELLER")),
                                               text(w.get("TYP.MODELL")), "komponente", "", nutzer_id,
                                               muss_aktiv=True)
    if typ_neu:
        hinweise.append("Typ neu im Katalog angelegt.")
    if text(w.get("LABEL")) or text(w.get("LABEL2")):
        hinweise.append("Labels werden noch nicht übernommen.")
    komponenten.anlegen(con, art, g, {
        "nummer": str(nummer), "komponententyp_id": typ_id, "raum": text(w.get("STANDORT")),
        "seriennummer": text(w.get("SERIENNUMMER")), "barcode": text(w.get("QR-CODE")),
        "baujahr": text(w.get("BAUJAHR")), "letzte_pruefung_am": datum(w.get("LETZTE PRÜFUNG")),
        "inbetriebnahme_am": datum(w.get("INBETRIEBNAHME AM"))}, nutzer_id)
    return "neu", beschreibung, hinweise


ARTEN = {
    "kunden": (Importart("kunden", "Kunden", ("KUNDEN.NUMMER", "KUNDE.NAME"),
                         ("ADRESSZEILE 1", "ADRESSZEILE 2", "PLZ", "ORT", "LAND", "NOTIZ")), _kunde),
    "kontakte": (Importart("kontakte", "Kontakte", ("NAME", "KUNDE"),
                           ("FIRMA", "EMAIL", "TELEFON", "MOBIL", "FAX", "NOTIZ")), _kontakt),
    "objekte": (Importart("objekte", "Objekte", ("KUNDE.NUMMER", "OBJEKT.NAME"),
                          ("OBJEKT.NUMMER", "ADRESSZEILE 1", "ADRESSZEILE 2", "PLZ", "ORT", "LAND")), _objekt),
    "anlagen": (Importart("anlagen", "Anlagen", ("OBJEKT.NUMMER", "WARTUNGSANWENDUNG.NUMMER", "ANLAGE.NUMMER"),
                          ("ANLAGE.NAME", "TECHNIKER.NUMMER")), _anlage),
    "typen": (Importart("typen", "Melder-Typen", ("TYP.NAME", "TYP.KATEGORIE"),
                        ("TYP.HERSTELLER", "TYP.MODELL", "TYP.LINK")), _typ),
    "komponenten": (Importart("komponenten", "Melder einer Anlage", ("NUMMER", "TYP.NAME"),
                              ("GRUPPE.NUMMER", "GRUPPE.NAME", "SUB-NUMMER", "TYP.HERSTELLER", "TYP.MODELL",
                               "STANDORT", "SERIENNUMMER", "QR-CODE", "BAUJAHR", "LETZTE PRÜFUNG",
                               "INBETRIEBNAHME AM"), ("LABEL", "LABEL2", "ZULASSUNGSNUMMER"),
                              braucht_anlage=True), _komponente),
}
REIHENFOLGE = ("kunden", "kontakte", "objekte", "anlagen", "typen", "komponenten")


def _schluessel(art, w, optionen):
    """Schlüssel zum Erkennen doppelter Zeilen in derselben Datei (None = nicht prüfen)."""
    if art == "kunden":
        return text(w.get("KUNDEN.NUMMER")).lower() or None
    if art == "kontakte":
        return (text(w.get("KUNDE")).lower(), text(w.get("NAME")).lower())
    if art == "objekte":
        return text(w.get("OBJEKT.NUMMER")).lower() or None
    if art == "anlagen":
        return text(w.get("ANLAGE.NUMMER")).lower() or None
    if art == "komponenten":
        return (text(w.get("GRUPPE.NUMMER")) or "1", text(w.get("NUMMER")), text(w.get("SUB-NUMMER")) or "0")
    return None


# ---------- Durchlauf ----------

class _Zuruecksetzen(Exception):
    """Interner Auslöser, um den Probelauf (bzw. einen fehlerhaften Import) vollständig zurückzurollen."""


def _vorbereiten(art, inhalt, optionen):
    if art not in ARTEN:
        raise DateiFehler("Unbekannte Datenart.")
    importart, verarbeiten = ARTEN[art]
    if importart.braucht_anlage and not optionen.get("anlage"):
        raise DateiFehler("Bitte die Anlage wählen, in die die Melder importiert werden.")
    kopf, zeilen = lesen(inhalt)
    fehlend = [s for s in importart.pflicht if s not in kopf]
    if fehlend:
        raise DateiFehler(f"Pflichtspalten fehlen: {', '.join(fehlend)}. Bitte die Vorlage für „{importart.titel}“ "
                          f"verwenden.")
    ergebnis = Ergebnis(art)
    unbekannt = [s for s in kopf if s and s not in importart.spalten and s not in importart.ignoriert
                 and not s.startswith("HINWEIS")]
    if unbekannt:
        ergebnis.hinweise.append(f"Nicht verwendete Spalten: {', '.join(unbekannt)}.")
    if not zeilen:
        ergebnis.hinweise.append("Die Datei enthält keine Datenzeilen.")
    return importart, verarbeiten, zeilen, ergebnis


def _durchlauf(con, importart, verarbeiten, zeilen, ergebnis, nutzer_id, optionen):
    gesehen = {}
    for nr, werte in zeilen:
        if not any(text(werte.get(s)) for s in importart.spalten):
            continue  # z. B. Hinweiszeilen der Vorlage
        schluessel = _schluessel(importart.schluessel, werte, optionen)
        if schluessel is not None and schluessel in gesehen:
            ergebnis.zeilen.append(Zeile(nr, "fehler", "", [f"Doppelt in der Datei (wie Zeile {gesehen[schluessel]})."]))
            continue
        if schluessel is not None:
            gesehen[schluessel] = nr
        try:
            with db.transaktion(con):  # je Zeile ein Sicherungspunkt: Fehler betreffen nur diese Zeile
                status, beschreibung, hinweise = verarbeiten(con, werte, nutzer_id, optionen)
            ergebnis.zeilen.append(Zeile(nr, status, beschreibung, hinweise))
        except Ungueltig as e:
            ergebnis.zeilen.append(Zeile(nr, "fehler", text(next(iter(werte.values()), "")), list(e.fehler.values())))
    return ergebnis


def pruefen(con, art, inhalt, nutzer_id, optionen=None):
    """Probelauf: verarbeitet alle Zeilen wie beim Übernehmen und rollt danach alles zurück."""
    optionen = optionen or {}
    importart, verarbeiten, zeilen, ergebnis = _vorbereiten(art, inhalt, optionen)
    try:
        with db.transaktion(con):
            _durchlauf(con, importart, verarbeiten, zeilen, ergebnis, nutzer_id, optionen)
            raise _Zuruecksetzen
    except _Zuruecksetzen:
        pass
    return ergebnis


def uebernehmen(con, art, inhalt, nutzer_id, optionen=None, dateiname=""):
    """Übernimmt alle Zeilen in einem Schritt – oder bei einem einzigen Fehler gar nichts."""
    optionen = optionen or {}
    importart, verarbeiten, zeilen, ergebnis = _vorbereiten(art, inhalt, optionen)
    try:
        with db.transaktion(con):
            _durchlauf(con, importart, verarbeiten, zeilen, ergebnis, nutzer_id, optionen)
            if not ergebnis.ok:
                raise _Zuruecksetzen
            db.protokoll(con, nutzer_id, "import", db.neue_id(), "import", importart.schluessel, None,
                         f"{dateiname}: {ergebnis.anzahl('neu')} neu, {ergebnis.anzahl('vorhanden')} vorhanden")
            ergebnis.gespeichert = True
    except _Zuruecksetzen:
        pass
    return ergebnis
