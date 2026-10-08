"""Formularfelder: eine Beschreibung je Feld, daraus Prüfung der Eingaben und Darstellung im Formular.

So bekommen alle Masken (Kunde, Kontakt, Objekt, …) dieselben Regeln, ohne sie mehrfach zu schreiben.
"""
import re
from dataclasses import dataclass, replace

ARTEN = ("text", "textarea", "email", "tel", "auswahl", "zahl", "ja_nein", "datum")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TEL = re.compile(r"^[0-9+()/\-. ]{3,30}$")
_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Ungueltig(ValueError):
    """Eingaben verletzen eine Regel; .fehler enthält {feld: Meldung} (Feld '' = allgemeiner Fehler)."""

    def __init__(self, fehler):
        super().__init__("; ".join(fehler.values()))
        self.fehler = fehler


@dataclass(frozen=True)
class Feld:
    name: str
    titel: str
    art: str = "text"
    pflicht: bool = False
    auswahl: tuple = ()           # ((wert, anzeige), …) für art="auswahl"
    max_laenge: int = 200
    breit: bool = False           # im Formular über die ganze Breite
    hilfe: str = ""
    platzhalter: str = ""
    minimum: int | None = None    # für art="zahl"
    maximum: int | None = None
    vorschlaege: tuple = ()       # Vorschläge zum Antippen, freie Eingabe bleibt möglich (art="text")

    def __post_init__(self):
        if self.art not in ARTEN:
            raise ValueError(f"unbekannte Feldart {self.art!r}")


def einlesen(felder, form):
    """Liest die Felder aus einem Formular, bereinigt und prüft sie.

    Rückgabe: (werte, fehler) – werte passend für die Datenbank (Text: '' statt fehlend, Zahl: int oder None,
    ja_nein: 0/1), fehler: {feldname: Meldung}.
    """
    werte, fehler = {}, {}
    for f in felder:
        roh = form.get(f.name)
        if f.art == "ja_nein":
            werte[f.name] = 1 if roh in ("1", "on", "ja", "true") else 0
            continue
        text = str(roh or "").strip()
        if f.art != "textarea":
            text = " ".join(text.split())   # Zeilenumbrüche/Mehrfach-Leerzeichen aus einzeiligen Feldern entfernen
        if not text:
            if f.pflicht:
                fehler[f.name] = f"{f.titel} ist Pflicht."
            werte[f.name] = None if f.art in ("zahl", "datum") else ""
            continue
        if len(text) > f.max_laenge:
            fehler[f.name] = f"{f.titel}: höchstens {f.max_laenge} Zeichen."
        elif f.art == "email" and not _EMAIL.match(text):
            fehler[f.name] = f"{f.titel}: bitte eine gültige E-Mail-Adresse angeben."
        elif f.art == "tel" and not _TEL.match(text):
            fehler[f.name] = f"{f.titel}: nur Ziffern und + ( ) / - . erlaubt."
        elif f.art == "auswahl" and text not in {w for w, _ in f.auswahl}:
            fehler[f.name] = f"{f.titel}: ungültige Auswahl."
        elif f.art == "datum" and not _DATUM.match(text):
            fehler[f.name] = f"{f.titel}: Datum bitte als JJJJ-MM-TT."
        elif f.art == "zahl":
            try:
                zahl = int(text)
            except ValueError:
                fehler[f.name] = f"{f.titel}: bitte eine ganze Zahl angeben."
            else:
                if (f.minimum is not None and zahl < f.minimum) or (f.maximum is not None and zahl > f.maximum):
                    fehler[f.name] = f"{f.titel}: erlaubt ist {f.minimum} bis {f.maximum}."
                werte[f.name] = zahl
                continue
        werte[f.name] = text.lower() if f.art == "email" else text
    return werte, fehler


def anzeige(feld, wert):
    """Lesbarer Wert für Detailseiten (Auswahl -> Anzeigetext, ja_nein -> ja/nein)."""
    if feld.art == "auswahl":
        return dict(feld.auswahl).get(wert, wert or "")
    if feld.art == "ja_nein":
        return "ja" if wert else "nein"
    return "" if wert is None else wert


def adresse_pruefen(werte, fehler, pflicht=False):
    """Gemeinsame Regeln für Anschriften: Land groß (Standard DE), deutsche PLZ fünfstellig, ggf. Pflicht."""
    werte["land"] = (werte.get("land") or "DE").upper()
    if pflicht:
        for name, titel in (("strasse", "Straße"), ("plz", "PLZ"), ("ort", "Ort")):
            if not werte.get(name):
                fehler.setdefault(name, f"{titel} ist Pflicht.")
    plz = werte.get("plz") or ""
    if werte["land"] == "DE" and plz and not (plz.isdigit() and len(plz) == 5):
        fehler.setdefault("plz", "PLZ: in Deutschland fünf Ziffern.")


def like_muster(suche):
    """Suchtext für SQL LIKE … ESCAPE '\\': Platzhalterzeichen des Nutzers (%, _) zählen als normale Zeichen."""
    return "%" + suche.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def fuer_bearbeiten(felder):
    """Beim Bearbeiten ist die Nummer Pflicht (sie wurde beim Anlegen vergeben) – ohne Hinweis „leer = automatisch“."""
    return tuple(replace(f, pflicht=True, hilfe="") if f.name == "nummer" else f for f in felder)
