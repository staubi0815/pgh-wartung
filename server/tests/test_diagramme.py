"""Die automatischen Diagramme in docs/00-ueberblick.md müssen zum Code passen (Schema, Statusregeln)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "werkzeuge"))

import diagramme  # noqa: E402


def test_diagramme_aktuell():
    text = diagramme.DOKU.read_text(encoding="utf-8")
    assert diagramme.erneuert(text) == text, \
        "docs/00-ueberblick.md ist veraltet – aus server/ ausführen: ../.venv-test/bin/python werkzeuge/diagramme.py"


def test_alle_status_im_diagramm():
    from wartung import auftraege
    bild = diagramme.auftragsstatus()
    for s, text in auftraege.STATUS:
        assert f'state "{text}" as {s}' in bild
