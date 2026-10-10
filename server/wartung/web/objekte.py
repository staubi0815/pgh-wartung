"""Seiten: Objekt anlegen (aus dem Kunden heraus), Objekt ansehen/bearbeiten/löschen, Anlage im Objekt anlegen."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, kunden, nummern, objekte
from ..felder import Ungueltig
from .kunden import BEARBEITEN, LESEN, NICHT_GEFUNDEN


def router(web):
    r = APIRouter()
    con = web.con

    def kunde_laden(kunde_id):
        return web.holen_oder_weiter(kunden.holen(con, kunde_id), NICHT_GEFUNDEN)

    def objekt_laden(objekt_id):
        return web.holen_oder_weiter(objekte.holen(con, objekt_id), NICHT_GEFUNDEN)

    def formular_seite(request, n, k, o, fehler, felder, status=200, vorschau=""):
        return web.seite(request, "objekt_form.html", n, k=k, o=o, fehler=fehler, felder=felder, status=status,
                         vorschau=vorschau)

    @r.get("/kunden/{kunde_id}/objekte/neu", response_class=HTMLResponse)
    def neu_form(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        return formular_seite(request, n, kunde_laden(kunde_id), {"land": "DE"}, {}, objekte.OBJEKT_FELDER,
                              vorschau=nummern.vorschau(con, "objekt"))

    @r.post("/kunden/{kunde_id}/objekte/neu")
    async def neu(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k = kunde_laden(kunde_id)
        form = await web.formular(request)
        try:
            oid = objekte.anlegen(con, kunde_id, form, n["id"])
        except Ungueltig as e:
            return formular_seite(request, n, k, dict(form), e.fehler, objekte.OBJEKT_FELDER, 400,
                                  nummern.vorschau(con, "objekt"))
        return RedirectResponse(f"/objekte/{oid}?hinweis=angelegt", status_code=303)

    @r.get("/objekte/{objekt_id}", response_class=HTMLResponse)
    def detail(request: Request, objekt_id: str, hinweis: str = ""):
        n = web.nutzer(request, LESEN)
        o = objekt_laden(objekt_id)
        return web.seite(request, "objekt.html", n, o=o, anlagen=anlagen.liste_fuer_objekt(con, objekt_id),
                         felder=objekte.OBJEKT_FELDER, hinweis=hinweis)

    @r.get("/objekte/{objekt_id}/bearbeiten", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, objekt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        o = objekt_laden(objekt_id)
        return formular_seite(request, n, kunden.holen(con, o["kunde_id"]), dict(o), {},
                              objekte.felder_bearbeiten(con))

    @r.post("/objekte/{objekt_id}/bearbeiten")
    async def bearbeiten(request: Request, objekt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        o = objekt_laden(objekt_id)
        form = await web.formular(request)
        try:
            objekte.aendern(con, objekt_id, form, n["id"])
        except Ungueltig as e:
            return formular_seite(request, n, kunden.holen(con, o["kunde_id"]), {**dict(form), "id": objekt_id},
                                  e.fehler, objekte.felder_bearbeiten(con), 400)
        return RedirectResponse(f"/objekte/{objekt_id}?hinweis=gespeichert", status_code=303)

    @r.post("/objekte/{objekt_id}/loeschen")
    async def loeschen(request: Request, objekt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        o = objekt_laden(objekt_id)
        await web.formular(request)
        try:
            objekte.loeschen(con, objekt_id, n["id"])
        except Ungueltig:
            return RedirectResponse(f"/objekte/{objekt_id}?hinweis=hat_anlagen", status_code=303)
        return RedirectResponse(f"/kunden/{o['kunde_id']}?hinweis=objekt_geloescht#objekte", status_code=303)

    # ---------- Anlage im Objekt anlegen ----------
    def anlage_formular(request, n, o, a, fehler, status=200):
        return web.seite(request, "anlage_form.html", n, o=o, a=a, fehler=fehler, felder=anlagen.felder_neu(anlagen.techniker_auswahl(con)),
                         vorschau=nummern.vorschau(con, "anlage"), status=status)

    @r.get("/objekte/{objekt_id}/anlagen/neu", response_class=HTMLResponse)
    def anlage_neu_form(request: Request, objekt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        return anlage_formular(request, n, objekt_laden(objekt_id), anlagen.vorbelegung(), {})

    @r.post("/objekte/{objekt_id}/anlagen/neu")
    async def anlage_neu(request: Request, objekt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        o = objekt_laden(objekt_id)
        form = await web.formular(request)
        try:
            aid = anlagen.anlegen(con, objekt_id, form, n["id"])
        except Ungueltig as e:
            return anlage_formular(request, n, o, dict(form), e.fehler, 400)
        return RedirectResponse(f"/anlagen/{aid}?hinweis=angelegt", status_code=303)

    return r
