"""Erzeugt die automatischen Diagramme in docs/00-ueberblick.md aus dem echten Stand (Datenbankschema, Statusregeln).

Aufruf (aus server/):  ../.venv-test/bin/python werkzeuge/diagramme.py            schreibt die Abschnitte neu
                       ../.venv-test/bin/python werkzeuge/diagramme.py --pruefen  meldet nur, ob sie veraltet sind

Die Abschnitte stehen zwischen <!-- AUTO:name --> und <!-- /AUTO:name -->; alles andere in der Datei bleibt unberührt.
Ein Test (test_diagramme.py) schlägt fehl, wenn jemand das Schema ändert und vergisst, das Skript laufen zu lassen.
"""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wartung import auftraege  # noqa: E402
from wartung.app import erzeuge_app  # noqa: E402

DOKU = Path(__file__).resolve().parent.parent.parent / "docs" / "00-ueberblick.md"


def _schema():
    """Tabellen und Fremdschlüssel einer frisch angelegten Datenbank (alle Migrationen durchlaufen)."""
    with tempfile.TemporaryDirectory() as ordner:
        con = erzeuge_app(Path(ordner)).state.con
        tabellen = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        bezuege = sorted((t, r["from"], r["table"]) for t in tabellen
                         for r in con.execute(f"PRAGMA foreign_key_list({t})"))
        con.close()
    return tabellen, bezuege


def datenmodell():
    tabellen, bezuege = _schema()
    zeilen = ["```mermaid", "erDiagram"]
    paare = [(kind, eltern) for kind, _, eltern in bezuege]
    for kind, spalte, eltern in bezuege:
        # Spaltenname nur, wenn dasselbe Tabellenpaar mehrfach verknüpft ist – sonst überladen die Beschriftungen das Bild
        name = spalte if paare.count((kind, eltern)) > 1 else ""
        zeilen.append(f'    {eltern} ||--o{{ {kind} : "{name}"')
    zeilen.append("```")
    verbunden = {t for b in bezuege for t in (b[0], b[2])}
    rest = [t for t in tabellen if t not in verbunden]
    zeilen += ["", "Ohne Verknüpfung (Verwaltung und Technik): " + ", ".join(f"`{t}`" for t in rest) + "."]
    return "\n".join(zeilen)


def auftragsstatus():
    zeilen = ["```mermaid", "stateDiagram-v2", "    direction LR"]
    for s, text in auftraege.STATUS:
        zeilen.append(f'    state "{text}" as {s}')
    zeilen.append(f"    [*] --> {auftraege.STATUS[0][0]}")
    for alt, _ in auftraege.STATUS:
        for neu in auftraege.UEBERGAENGE[alt]:
            grund = (alt, neu) in auftraege.RUECKWAERTS or neu == "storniert"
            zeilen.append(f"    {alt} --> {neu}" + (" : mit Grund" if grund else ""))
    zeilen.append("```")
    return "\n".join(zeilen)


ABSCHNITTE = {"datenmodell": datenmodell, "auftragsstatus": auftragsstatus}


def erneuert(text):
    for name, erzeuger in ABSCHNITTE.items():
        muster = re.compile(rf"(<!-- AUTO:{name} -->\n)(?:.*?\n)?(<!-- /AUTO:{name} -->)", re.S)
        if not muster.search(text):
            raise SystemExit(f"Abschnitt AUTO:{name} fehlt in {DOKU.name}")
        text = muster.sub(lambda m: m.group(1) + erzeuger() + "\n" + m.group(2), text)
    return text


def main(pruefen):
    alt = DOKU.read_text(encoding="utf-8")
    neu = erneuert(alt)
    if pruefen:
        if neu != alt:
            raise SystemExit(f"{DOKU.name} ist veraltet – bitte werkzeuge/diagramme.py laufen lassen.")
        print("Diagramme aktuell.")
    elif neu != alt:
        DOKU.write_text(neu, encoding="utf-8")
        print(f"{DOKU.name} erneuert.")
    else:
        print("Diagramme waren schon aktuell.")


if __name__ == "__main__":
    main("--pruefen" in sys.argv[1:])
