"""Seite: globale Suche (Feld in der Kopfzeile). Reine Leseseite, Rechte regelt wartung.suche."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .. import suche


def router(web):
    r = APIRouter()
    con = web.con

    @r.get("/suche", response_class=HTMLResponse)
    def seite(request: Request, q: str = ""):
        n = web.nutzer(request)
        ergebnis = suche.suchen(con, q, request.state.rechte, n["id"])
        zu_kurz = 0 < len(q.strip()) < suche.MIN_ZEICHEN
        return web.seite(request, "suche.html", n, q=q.strip(), ergebnis=ergebnis, zu_kurz=zu_kurz,
                         pro_gruppe=suche.PRO_GRUPPE)
    return r
