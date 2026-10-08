"""Seiten: Katalog der Komponententypen (Verwaltung → Melder-Typen). Recht: verwaltung.katalog."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import typen
from ..felder import Ungueltig

RECHT = "verwaltung.katalog"


def router(web):
    r = APIRouter(prefix="/verwaltung/typen")
    con = web.con

    def typ_laden(typ_id):
        return web.holen_oder_weiter(typen.holen(con, typ_id), "/verwaltung/typen")

    def formular(request, n, t, fehler, felder, status=200):
        return web.seite(request, "typ_form.html", n, t=t, fehler=fehler, felder=felder, status=status)

    @r.get("", response_class=HTMLResponse)
    def liste(request: Request, hinweis: str = ""):
        n = web.nutzer(request, RECHT)
        return web.seite(request, "typen_liste.html", n, liste=typen.liste(con), hinweis=hinweis,
                         funk=dict(typen.FUNK), batterie=dict(typen.BATTERIE))

    @r.get("/neu", response_class=HTMLResponse)
    def neu_form(request: Request):
        n = web.nutzer(request, RECHT)
        return formular(request, n, {"anlagenart": "rauchwarnmelder", "kategorie": "komponente", "funk": "keine",
                                     "batterie": "fest_10j", "aktiv": 1}, {}, typen.felder_neu())

    @r.post("/neu")
    async def neu(request: Request):
        n = web.nutzer(request, RECHT)
        form = await web.formular(request)
        try:
            typen.anlegen(con, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, dict(form), e.fehler, typen.felder_neu(), 400)
        return RedirectResponse("/verwaltung/typen?hinweis=angelegt", status_code=303)

    @r.get("/{typ_id}", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, typ_id: str):
        n = web.nutzer(request, RECHT)
        return formular(request, n, dict(typ_laden(typ_id)), {}, typen.felder_bearbeiten())

    @r.post("/{typ_id}")
    async def bearbeiten(request: Request, typ_id: str):
        n = web.nutzer(request, RECHT)
        t = typ_laden(typ_id)
        form = await web.formular(request)
        try:
            typen.aendern(con, typ_id, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, {**dict(t), **dict(form), "aktiv": form.get("aktiv")}, e.fehler,
                            typen.felder_bearbeiten(), 400)
        return RedirectResponse("/verwaltung/typen?hinweis=gespeichert", status_code=303)

    return r
