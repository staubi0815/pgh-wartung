"""Seiten: Gruppe (Wohnung) einer Anlage anlegen, bearbeiten, löschen. Angezeigt werden sie auf der Anlagenseite."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, anlagenart, gruppen
from ..felder import Ungueltig
from .anlagen import NICHT_GEFUNDEN
from .kunden import BEARBEITEN


def router(web):
    r = APIRouter()
    con = web.con

    def anlage_laden(anlage_id):
        a = web.holen_oder_weiter(anlagen.holen(con, anlage_id), NICHT_GEFUNDEN)
        return a, anlagenart.holen(a["anlagenart"])

    def gruppe_laden(gruppe_id):
        g = web.holen_oder_weiter(gruppen.holen(con, gruppe_id), NICHT_GEFUNDEN)
        return g, anlagenart.holen(g["anlagenart"])

    def formular(request, n, a, art, g, fehler, status=200):
        return web.seite(request, "gruppe_form.html", n, a=a, art=art, g=g, fehler=fehler, felder=gruppen.felder(art),
                         vorschau=gruppen.naechste_nummer(con, a["id"]), status=status)

    @r.get("/anlagen/{anlage_id}/gruppen/neu", response_class=HTMLResponse)
    def neu_form(request: Request, anlage_id: str):
        n = web.nutzer(request, BEARBEITEN)
        a, art = anlage_laden(anlage_id)
        return formular(request, n, a, art, {"zugang": "frei"}, {})

    @r.post("/anlagen/{anlage_id}/gruppen/neu")
    async def neu(request: Request, anlage_id: str):
        n = web.nutzer(request, BEARBEITEN)
        a, art = anlage_laden(anlage_id)
        form = await web.formular(request)
        try:
            gid = gruppen.anlegen(con, art, anlage_id, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, a, art, dict(form), e.fehler, 400)
        ziel = f"/anlagen/{anlage_id}/gruppen/neu?hinweis=angelegt" if form.get("weiter") else \
            f"/anlagen/{anlage_id}?hinweis=gruppe_angelegt#g-{gid}"
        return RedirectResponse(ziel, status_code=303)

    @r.get("/gruppen/{gruppe_id}", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        return formular(request, n, anlagen.holen(con, g["anlage_id"]), art, dict(g), {})

    @r.post("/gruppen/{gruppe_id}")
    async def bearbeiten(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        form = await web.formular(request)
        try:
            gruppen.aendern(con, art, gruppe_id, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, anlagen.holen(con, g["anlage_id"]), art, {**dict(form), "id": gruppe_id},
                            e.fehler, 400)
        return RedirectResponse(f"/anlagen/{g['anlage_id']}?hinweis=gruppe_gespeichert#g-{gruppe_id}", status_code=303)

    @r.post("/gruppen/{gruppe_id}/loeschen")
    async def loeschen(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        await web.formular(request)
        try:
            gruppen.loeschen(con, art, gruppe_id, n["id"])
        except Ungueltig as e:
            hinweis = "gruppe_in_auftrag" if "auftraege" in e.fehler else "gruppe_hat_komponenten"
            return RedirectResponse(f"/anlagen/{g['anlage_id']}?hinweis={hinweis}#g-{gruppe_id}", status_code=303)
        return RedirectResponse(f"/anlagen/{g['anlage_id']}?hinweis=gruppe_geloescht#wohnungen", status_code=303)

    return r
