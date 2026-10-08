"""Anlagenarten (Rauchwarnmelder, später Türen) aus konfig/anlagenarten/*.toml laden und prüfen.

Die Dateien sind Teil des Programms (im Repo, nicht in der Datenbank). Fehler in einer Datei verhindern den Start,
damit ein Tippfehler nicht erst beim Kunden auffällt.
"""
import tomllib
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

ORDNER = Path(__file__).parent / "konfig" / "anlagenarten"
RAUMARTEN = ("schlafraum", "kinderzimmer", "flur_rettungsweg", "sonstiger")
SCHWEREGRADE = ("hinweis", "normal", "schwer")
CHECK_TYPEN = ("ja_nein", "text", "zahl", "auswahl")
# zulässige Einträge je Abschnitt – Tippfehler und falsch zugeordnete Zeilen fallen so sofort auf
ERLAUBT = {
    "": {"allgemein", "intervalle", "raeume", "raumarten", "checkliste", "mangel", "auftragsart", "ablauf"},
    "allgemein": {"schluessel", "name", "gruppe", "gruppe_mehrzahl", "komponente", "komponente_mehrzahl", "trenner",
                  "unterschrift_je_gruppe", "einzelnachweis_je_gruppe", "fotos", "freigegeben"},
    "intervalle": {"pruefung_monate", "pruefung_gleitend", "vorwarnung_tage", "austausch_jahre", "austausch_ab",
                   "austausch_zugabe_monate"},
    "raeume": {"liste"},
}


class KonfigFehler(ValueError):
    pass


@dataclass(frozen=True)
class Checkpunkt:
    schluessel: str
    frage: str
    typ: str
    pflicht: bool = True
    mangel_bei_nein: str | None = None


@dataclass(frozen=True)
class Mangeltyp:
    schluessel: str
    name: str
    schweregrad: str
    austausch_vorschlagen: bool = False


@dataclass(frozen=True)
class Auftragsart:
    schluessel: str
    name: str
    schritte: tuple[str, ...]
    berichtstitel: str
    standard: bool = False


@dataclass(frozen=True)
class Anlagenart:
    schluessel: str
    name: str
    gruppe: str                 # „Wohnung“
    gruppe_mehrzahl: str
    komponente: str             # „Melder“
    komponente_mehrzahl: str
    trenner: str                # Anzeige 43/1
    unterschrift_je_gruppe: bool
    einzelnachweis_je_gruppe: bool
    fotos: bool
    freigegeben: bool
    pruefung_monate: int
    pruefung_gleitend: bool
    vorwarnung_tage: int
    austausch_jahre: int
    austausch_ab: str           # "baujahr" | "inbetriebnahme"
    austausch_zugabe_monate: int
    raeume: tuple[str, ...]
    raumarten: dict = field(hash=False)          # raumart -> Räume
    checkliste: tuple[Checkpunkt, ...] = ()
    maengel: tuple[Mangeltyp, ...] = ()
    auftragsarten: tuple[Auftragsart, ...] = ()

    def raumart_fuer(self, raum):
        """Vorbelegung der Raumart aus dem Raumnamen (frei eingegebene Räume: „sonstiger“)."""
        for art, raeume in self.raumarten.items():
            if raum in raeume:
                return art
        return "sonstiger"

    def nummer_anzeige(self, gruppe_nr, komponente_nr, sub_nr=0):
        text = f"{gruppe_nr}{self.trenner}{komponente_nr}"
        return f"{text}.{sub_nr}" if sub_nr else text


def _bauen(klasse, werte, datei):
    try:
        return klasse(**werte)
    except TypeError as e:  # unbekannter oder fehlender Schlüssel
        raise KonfigFehler(f"{Path(datei).name}: {klasse.__name__} {werte.get('schluessel', '?')}: {e}") from e


def laden(datei):
    """Liest und prüft eine Anlagenart-Datei. Wirft KonfigFehler mit verständlicher Meldung."""
    try:
        roh = tomllib.loads(Path(datei).read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise KonfigFehler(f"{Path(datei).name}: keine gültige TOML-Datei ({e})") from e

    def pflicht(abschnitt, schluessel):
        if schluessel not in roh.get(abschnitt, {}):
            raise KonfigFehler(f"{Path(datei).name}: [{abschnitt}] {schluessel} fehlt")
        return roh[abschnitt][schluessel]

    for abschnitt, erlaubt in ERLAUBT.items():
        unbekannt = set(roh if abschnitt == "" else roh.get(abschnitt, {})) - erlaubt
        if unbekannt:
            raise KonfigFehler(f"{Path(datei).name}: [{abschnitt}] unbekannte Einträge {sorted(unbekannt)}")
    a, iv = roh.get("allgemein", {}), roh.get("intervalle", {})
    if pflicht("allgemein", "schluessel") != Path(datei).stem:
        raise KonfigFehler(f"{Path(datei).name}: schluessel muss dem Dateinamen entsprechen")
    raeume = tuple(pflicht("raeume", "liste"))
    raumarten = roh.get("raumarten", {})
    for art, liste in raumarten.items():
        if art not in RAUMARTEN:
            raise KonfigFehler(f"{Path(datei).name}: unbekannte Raumart {art!r}")
        if not set(liste) <= set(raeume):
            raise KonfigFehler(f"{Path(datei).name}: Raumart {art!r} nennt Räume, die nicht in raeume stehen")
    maengel = tuple(_bauen(Mangeltyp, m, datei) for m in roh.get("mangel", ()))
    mangel_schluessel = {m.schluessel for m in maengel}
    for m in maengel:
        if m.schweregrad not in SCHWEREGRADE:
            raise KonfigFehler(f"{Path(datei).name}: Mangel {m.schluessel}: unbekannter Schweregrad {m.schweregrad!r}")
    checkliste = tuple(_bauen(Checkpunkt, c, datei) for c in roh.get("checkliste", ()))
    for c in checkliste:
        if c.typ not in CHECK_TYPEN:
            raise KonfigFehler(f"{Path(datei).name}: Checkpunkt {c.schluessel}: unbekannter Typ {c.typ!r}")
        if c.mangel_bei_nein and c.mangel_bei_nein not in mangel_schluessel:
            raise KonfigFehler(f"{Path(datei).name}: Checkpunkt {c.schluessel}: Mangel {c.mangel_bei_nein!r} fehlt")
    auftragsarten = tuple(_bauen(Auftragsart, {**x, "schritte": tuple(x.get("schritte", ()))}, datei)
                          for x in roh.get("auftragsart", ()))
    for liste, name in ((checkliste, "Checkpunkt"), (maengel, "Mangel"), (auftragsarten, "Auftragsart")):
        schluessel = [x.schluessel for x in liste]
        if len(schluessel) != len(set(schluessel)):
            raise KonfigFehler(f"{Path(datei).name}: {name}-Schlüssel doppelt")
    if iv.get("austausch_ab", "baujahr") not in ("baujahr", "inbetriebnahme"):
        raise KonfigFehler(f"{Path(datei).name}: austausch_ab muss baujahr oder inbetriebnahme sein")
    return Anlagenart(
        schluessel=a["schluessel"], name=pflicht("allgemein", "name"),
        gruppe=pflicht("allgemein", "gruppe"), gruppe_mehrzahl=pflicht("allgemein", "gruppe_mehrzahl"),
        komponente=pflicht("allgemein", "komponente"),
        komponente_mehrzahl=pflicht("allgemein", "komponente_mehrzahl"),
        trenner=a.get("trenner", "/"), unterschrift_je_gruppe=bool(a.get("unterschrift_je_gruppe", False)),
        einzelnachweis_je_gruppe=bool(a.get("einzelnachweis_je_gruppe", False)), fotos=bool(a.get("fotos", True)),
        freigegeben=bool(a.get("freigegeben", False)),
        pruefung_monate=int(pflicht("intervalle", "pruefung_monate")),
        pruefung_gleitend=bool(iv.get("pruefung_gleitend", True)),
        vorwarnung_tage=int(iv.get("vorwarnung_tage", 30)), austausch_jahre=int(pflicht("intervalle", "austausch_jahre")),
        austausch_ab=iv.get("austausch_ab", "baujahr"),
        austausch_zugabe_monate=int(iv.get("austausch_zugabe_monate", 0)), raeume=raeume, raumarten=raumarten,
        checkliste=checkliste, maengel=maengel, auftragsarten=auftragsarten)


@cache
def alle():
    """Alle Anlagenarten, Schlüssel -> Anlagenart (einmal geladen)."""
    return {d.stem: laden(d) for d in sorted(ORDNER.glob("*.toml"))}


def holen(schluessel):
    try:
        return alle()[schluessel]
    except KeyError:
        raise KonfigFehler(f"Unbekannte Anlagenart {schluessel!r}") from None
