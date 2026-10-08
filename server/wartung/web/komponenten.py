"""Seiten: Komponente (Melder) anlegen – einzeln oder mehrere auf einmal –, bearbeiten, löschen (Fehleingabe)."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, anlagenart, gruppen, komponenten, typen
from ..felder import Ungueltig, fuer_bearbeiten
from .anlagen import NICHT_GEFUNDEN
from .kunden import BEARBEITEN


def router(web):
    r = APIRouter()
    con = web.con

    def gruppe_laden(gruppe_id):
        g = web.holen_oder_weiter(gruppen.holen(con, gruppe_id), NICHT_GEFUNDEN)
        return g, anlagenart.holen(g["anlagenart"])

    def komponente_laden(komponente_id):
        k = web.holen_oder_weiter(komponenten.holen(con, komponente_id), NICHT_GEFUNDEN)
        return k, anlagenart.holen(k["anlagenart"])

    def zur_gruppe(g, hinweis):
        return RedirectResponse(f"/anlagen/{g['anlage_id']}?hinweis={hinweis}#g-{g['id']}", status_code=303)

    def formular(request, n, g, art, k, fehler, status=200):
        felder = komponenten.felder(con, art, k.get("komponententyp_id"))
        return web.seite(request, "komponente_form.html", n, g=g, a=anlagen.holen(con, g["anlage_id"]), art=art, k=k,
                         fehler=fehler, felder=fuer_bearbeiten(felder) if k.get("id") else felder,
                         vorschau=komponenten.naechste_nummer(con, g["id"]), status=status,
                         keine_typen=not typen.auswahl(con, art.schluessel, k.get("komponententyp_id")))

    # ---------- einzeln ----------
    @r.get("/gruppen/{gruppe_id}/komponenten/neu", response_class=HTMLResponse)
    def neu_form(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        return formular(request, n, g, art, {}, {})

    @r.post("/gruppen/{gruppe_id}/komponenten/neu")
    async def neu(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        form = await web.formular(request)
        try:
            komponenten.anlegen(con, art, g, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, g, art, dict(form), e.fehler, 400)
        if form.get("weiter"):
            return RedirectResponse(f"/gruppen/{gruppe_id}/komponenten/neu?hinweis=angelegt", status_code=303)
        return zur_gruppe(g, "komponente_angelegt")

    # ---------- mehrere ----------
    def mehrere_seite(request, n, g, art, werte, fehler, status=200):
        return web.seite(request, "komponenten_mehrere.html", n, g=g, a=anlagen.holen(con, g["anlage_id"]), art=art,
                         k=werte, fehler=fehler, felder=komponenten.felder_mehrere(con, art), status=status,
                         keine_typen=not typen.auswahl(con, art.schluessel))

    @r.get("/gruppen/{gruppe_id}/komponenten/mehrere", response_class=HTMLResponse)
    def mehrere_form(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        return mehrere_seite(request, n, g, art, {"raeume": []}, {})

    @r.post("/gruppen/{gruppe_id}/komponenten/mehrere")
    async def mehrere(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        form = await web.formular(request)
        raeume = form.getlist("raeume") + (form.get("weitere_raeume") or "").split(",")
        try:
            komponenten.mehrere_anlegen(con, art, g, form, raeume, n["id"])
        except Ungueltig as e:
            return mehrere_seite(request, n, g, art, {**dict(form), "raeume": form.getlist("raeume")}, e.fehler, 400)
        return zur_gruppe(g, "komponenten_angelegt")

    # ---------- bearbeiten / löschen ----------
    @r.get("/komponenten/{komponente_id}", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, komponente_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k, art = komponente_laden(komponente_id)
        return formular(request, n, gruppen.holen(con, k["gruppe_id"]), art, dict(k), {})

    @r.post("/komponenten/{komponente_id}")
    async def bearbeiten(request: Request, komponente_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k, art = komponente_laden(komponente_id)
        g = gruppen.holen(con, k["gruppe_id"])
        form = await web.formular(request)
        try:
            komponenten.aendern(con, art, k, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, g, art, {**dict(form), "id": komponente_id}, e.fehler, 400)
        return zur_gruppe(g, "komponente_gespeichert")

    @r.post("/komponenten/{komponente_id}/loeschen")
    async def loeschen(request: Request, komponente_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k, _ = komponente_laden(komponente_id)
        await web.formular(request)
        komponenten.loeschen(con, komponente_id, n["id"])
        return zur_gruppe(gruppen.holen(con, k["gruppe_id"]), "komponente_geloescht")

    return r
