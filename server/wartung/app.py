"""Webanwendung zusammensetzen: Datenbank, Sitzungen, Sicherheitsköpfe, Seitenbereiche.

Die Seiten selbst stehen in wartung/web/ (je Bereich ein Modul). Seiten prüfen ausschließlich Einzelrechte
(wartung/rechte.py), nie Rollennamen.
"""
import os
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import anlagen as anlagen_logik, db, faelligkeit, felder, rechte
from .web import anlagen, anmeldung, gruppen, komponenten, kunden, objekte, typen, verwaltung
from .web.basis import Web, Weiterleitung

HIER = Path(__file__).parent


def _geheimnis(daten):
    datei = daten / "sitzungsschluessel"
    if not datei.exists():
        datei.write_text(secrets.token_hex(32))
        os.chmod(datei, 0o600)
    return datei.read_text().strip()


def erzeuge_app(daten_ordner=None, https=False):
    daten = Path(daten_ordner) if daten_ordner else db.daten_ordner()
    daten.mkdir(parents=True, exist_ok=True)
    pfad = daten / "wartung.db"
    einmal = db.verbinden(pfad)
    db.migrieren(einmal)
    einmal.close()
    con = db.ThreadVerbindung(pfad)

    app = FastAPI(title="PGH-Wartung", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.con = con
    app.add_middleware(SessionMiddleware, secret_key=_geheimnis(daten), session_cookie="pgh_sitzung",
                       max_age=12 * 3600, same_site="strict", https_only=https)
    app.mount("/static", StaticFiles(directory=HIER / "static"), name="static")
    vorlagen = Jinja2Templates(directory=HIER / "templates")
    vorlagen.env.globals.update(BEREICHE=rechte.BEREICHE, VERWALTUNG=verwaltung.MENUE, anzeige=felder.anzeige,
                                ANLAGENARTEN=dict(anlagen_logik.arten_auswahl()), AMPEL_TEXT=faelligkeit.AMPEL_TEXT)

    @app.middleware("http")
    async def sicherheitskoepfe(request, call_next):
        antwort = await call_next(request)
        antwort.headers["X-Frame-Options"] = "DENY"
        antwort.headers["X-Content-Type-Options"] = "nosniff"
        antwort.headers["Referrer-Policy"] = "no-referrer"
        antwort.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; "
                                                      "frame-ancestors 'none'; form-action 'self'")
        antwort.headers["Cache-Control"] = "no-store"
        return antwort

    @app.exception_handler(Weiterleitung)
    async def weiterleiten(request, exc):
        return RedirectResponse(exc.ziel, status_code=303)

    web = Web(con, vorlagen)
    for bereich in (anmeldung, kunden, objekte, anlagen, gruppen, komponenten, typen, verwaltung):
        app.include_router(bereich.router(web))
    return app
