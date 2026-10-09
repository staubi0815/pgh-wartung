"""Seiten: Export (Verwaltung → Export). Recht: export.

Exporte enthalten Kunden- und Mieterdaten. Deshalb: nur per Formular (POST mit CSRF-Merkmal), jeder Export steht mit
Nutzer, Zeit und Umfang im Änderungsprotokoll, und die Antwort wird nicht zwischengespeichert (Cache-Control no-store).

Ein Export darf nichts enthalten, was der Nutzer in der Oberfläche nicht sehen dürfte: Der Foxtag-Export braucht
zusätzlich das Leserecht für Stammdaten, der Vollexport (enthält auch Nutzer und Änderungsprotokoll) zusätzlich die
Rechte für Nutzerverwaltung und Änderungsprotokoll.
"""
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from .. import db, export
from .basis import Weiterleitung

RECHT = "export"
FOXTAG_RECHTE = {"export", "stammdaten.lesen"}
VOLL_RECHTE = FOXTAG_RECHTE | {"verwaltung.nutzer", "verwaltung.protokoll"}


def router(web):
    r = APIRouter(prefix="/verwaltung/export")
    con = web.con

    def pruefen(request, noetig):
        n = web.nutzer(request, RECHT)
        if not noetig <= request.state.rechte:
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        return n

    @r.get("", response_class=HTMLResponse)
    def start(request: Request):
        n = web.nutzer(request, RECHT)
        letzte = con.execute("SELECT a.zeit, a.feld, n.name FROM aenderungsprotokoll a "
                             "LEFT JOIN nutzer n ON n.id = a.nutzer_id WHERE a.aktion = 'export' "
                             "ORDER BY a.id DESC LIMIT 5").fetchall()
        return web.seite(request, "export.html", n, letzte=letzte, darf_foxtag=FOXTAG_RECHTE <= request.state.rechte,
                         darf_voll=VOLL_RECHTE <= request.state.rechte)

    def herunterladen(n, art, inhalt, anzahl):
        datum = datetime.now(db.TZ).strftime("%Y-%m-%d")
        db.protokoll(con, n["id"], "export", db.neue_id(), "export", art, None,
                     f"{sum(anzahl.values())} Datensätze in {len(anzahl)} Dateien")
        return Response(inhalt, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="pgh-wartung-{art}-{datum}.zip"'})

    @r.post("/foxtag")
    async def foxtag(request: Request):
        n = pruefen(request, FOXTAG_RECHTE)
        await web.formular(request)
        inhalt, anzahl = export.foxtag(con)
        return herunterladen(n, "foxtag", inhalt, anzahl)

    @r.post("/voll")
    async def voll(request: Request):
        n = pruefen(request, VOLL_RECHTE)
        await web.formular(request)
        inhalt, anzahl = export.voll(con)
        return herunterladen(n, "vollexport", inhalt, anzahl)

    return r
