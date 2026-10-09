"""Seiten: Anlagenliste, Anlage (Übersicht, Ansprechpartner), Anlage bearbeiten/löschen, Kontakte zuordnen."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, anlagenart, gruppen, komponenten, kunden
from ..felder import Ungueltig
from .kunden import BEARBEITEN, LESEN

NICHT_GEFUNDEN = "/anlagen?hinweis=nicht_gefunden"


def router(web):
    r = APIRouter(prefix="/anlagen")
    con = web.con

    def anlage_laden(anlage_id):
        return web.holen_oder_weiter(anlagen.holen(con, anlage_id), NICHT_GEFUNDEN)

    def detail_seite(request, n, a, hinweis="", fehler=None, status=200, zuordnung=None):
        return web.seite(request, "anlage.html", n, a=anlagen.bewerten(a), art=anlagenart.holen(a["anlagenart"]),
                         kontakte=anlagen.kontakte(con, a["id"]), kunden_kontakte=kunden.kontakte(con, a["kunde_id"]),
                         rollen=anlagen.KONTAKT_ROLLEN, rollen_namen=dict(anlagen.KONTAKT_ROLLEN),
                         felder=anlagen.felder_bearbeiten(), hinweis=hinweis, fehler=fehler or {},
                         zuordnung=zuordnung or {}, gruppen=gruppen.liste(con, a["id"]),
                         komponenten=komponenten.je_gruppe(con, a["id"], anlagenart.holen(a["anlagenart"])),
                         zugang_namen=dict(gruppen.ZUGANG), status=status)

    @r.get("", response_class=HTMLResponse)
    def liste(request: Request, q: str = "", art: str = "", faellig: str = "", hinweis: str = ""):
        n = web.nutzer(request, LESEN)
        return web.seite(request, "anlagen_liste.html", n, liste=anlagen.liste(con, q, art, faellig), q=q, art=art,
                         faellig=faellig, faellig_filter=anlagen.FAELLIG_FILTER, arten=anlagen.arten_auswahl(),
                         hinweis=hinweis)

    @r.get("/{anlage_id}", response_class=HTMLResponse)
    def detail(request: Request, anlage_id: str, hinweis: str = ""):
        n = web.nutzer(request, LESEN)
        return detail_seite(request, n, anlage_laden(anlage_id), hinweis)

    @r.get("/{anlage_id}/bearbeiten", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, anlage_id: str):
        n = web.nutzer(request, BEARBEITEN)
        a = anlage_laden(anlage_id)
        return web.seite(request, "anlage_form.html", n, o=None, a=dict(a), fehler={},
                         felder=anlagen.felder_bearbeiten(), art=anlagenart.alle().get(a["anlagenart"]))

    @r.post("/{anlage_id}/bearbeiten")
    async def bearbeiten(request: Request, anlage_id: str):
        n = web.nutzer(request, BEARBEITEN)
        a = anlage_laden(anlage_id)
        form = await web.formular(request)
        try:
            anlagen.aendern(con, anlage_id, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "anlage_form.html", n, o=None, status=400, fehler=e.fehler,
                             a={**dict(a), **dict(form)}, felder=anlagen.felder_bearbeiten(),
                             art=anlagenart.alle().get(a["anlagenart"]))
        return RedirectResponse(f"/anlagen/{anlage_id}?hinweis=gespeichert", status_code=303)

    @r.post("/{anlage_id}/loeschen")
    async def loeschen(request: Request, anlage_id: str):
        n = web.nutzer(request, BEARBEITEN)
        a = anlage_laden(anlage_id)
        await web.formular(request)
        try:
            anlagen.loeschen(con, anlage_id, n["id"])
        except Ungueltig:
            return RedirectResponse(f"/anlagen/{anlage_id}?hinweis=hat_wohnungen", status_code=303)
        return RedirectResponse(f"/objekte/{a['objekt_id']}?hinweis=anlage_geloescht", status_code=303)

    # ---------- Ansprechpartner ----------
    @r.post("/{anlage_id}/kontakte")
    async def kontakt_zuordnen(request: Request, anlage_id: str):
        n = web.nutzer(request, BEARBEITEN)
        a = anlage_laden(anlage_id)
        form = await web.formular(request)
        try:
            anlagen.kontakt_zuordnen(con, anlage_id, form.get("kontakt_id", ""), form.get("rolle", ""), n["id"])
        except Ungueltig as e:
            return detail_seite(request, n, a, fehler=e.fehler, status=400, zuordnung=dict(form))
        return RedirectResponse(f"/anlagen/{anlage_id}?hinweis=kontakt_zugeordnet#kontakte", status_code=303)

    @r.post("/{anlage_id}/kontakte/{zuordnung_id}/entfernen")
    async def kontakt_entfernen(request: Request, anlage_id: str, zuordnung_id: str):
        n = web.nutzer(request, BEARBEITEN)
        anlage_laden(anlage_id)
        await web.formular(request)
        try:
            anlagen.kontakt_entfernen(con, anlage_id, zuordnung_id, n["id"])
        except Ungueltig:
            return RedirectResponse(f"/anlagen/{anlage_id}?hinweis=nicht_gefunden#kontakte", status_code=303)
        return RedirectResponse(f"/anlagen/{anlage_id}?hinweis=kontakt_entfernt#kontakte", status_code=303)

    return r
