"""Seiten: Kundenliste, Kunde (Daten, Kontakte, Objekte), Kunde und Kontakt anlegen/ändern/löschen.

Lesen braucht das Recht stammdaten.lesen, Ändern stammdaten.bearbeiten.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import kunden, nummern
from ..felder import Ungueltig
from .basis import Weiterleitung

LESEN, BEARBEITEN = "stammdaten.lesen", "stammdaten.bearbeiten"


def router(web):
    r = APIRouter()
    con = web.con

    def kunde_oder_liste(kunde_id):
        k = kunden.holen(con, kunde_id)
        if k is None:
            raise Weiterleitung("/kunden?hinweis=nicht_gefunden")
        return k

    def kontakt_oder_liste(kontakt_id):
        k = kunden.kontakt_holen(con, kontakt_id)
        if k is None:
            raise Weiterleitung("/kunden?hinweis=nicht_gefunden")
        return k

    async def formular(request):
        form = await request.form()
        web.csrf(request, form.get("csrf_token"))
        return form

    # ---------- Kunden ----------
    @r.get("/kunden", response_class=HTMLResponse)
    def liste(request: Request, q: str = "", art: str = "", hinweis: str = ""):
        n = web.nutzer(request, LESEN)
        return web.seite(request, "kunden_liste.html", n, liste=kunden.liste(con, q, art), q=q, art=art,
                         arten=kunden.KUNDENARTEN, arten_namen=dict(kunden.KUNDENARTEN), hinweis=hinweis)

    @r.get("/kunden/neu", response_class=HTMLResponse)
    def neu_form(request: Request):
        n = web.nutzer(request, BEARBEITEN)
        return web.seite(request, "kunde_form.html", n, k={"art": "hausverwaltung", "land": "DE"}, fehler={},
                         felder=kunden.KUNDE_FELDER, vorschau=nummern.vorschau(con, "kunde"))

    @r.post("/kunden/neu")
    async def neu(request: Request):
        n = web.nutzer(request, BEARBEITEN)
        form = await formular(request)
        try:
            kid = kunden.anlegen(con, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "kunde_form.html", n, k=dict(form), fehler=e.fehler, status=400,
                             felder=kunden.KUNDE_FELDER, vorschau=nummern.vorschau(con, "kunde"))
        return RedirectResponse(f"/kunden/{kid}?hinweis=angelegt", status_code=303)

    @r.get("/kunden/{kunde_id}", response_class=HTMLResponse)
    def detail(request: Request, kunde_id: str, hinweis: str = ""):
        n = web.nutzer(request, LESEN)
        k = kunde_oder_liste(kunde_id)
        objekte = con.execute(
            "SELECT o.*, (SELECT COUNT(*) FROM anlage a WHERE a.objekt_id = o.id AND a.geloescht = 0) AS anlagen "
            "FROM objekt o WHERE o.kunde_id = ? AND o.geloescht = 0 ORDER BY o.bezeichnung COLLATE NOCASE",
            (kunde_id,)).fetchall()
        return web.seite(request, "kunde.html", n, k=k, kontakte=kunden.kontakte(con, kunde_id), objekte=objekte,
                         felder=kunden.KUNDE_FELDER, hinweis=hinweis)

    @r.get("/kunden/{kunde_id}/bearbeiten", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        return web.seite(request, "kunde_form.html", n, k=dict(kunde_oder_liste(kunde_id)), fehler={},
                         felder=kunden.KUNDE_FELDER)

    @r.post("/kunden/{kunde_id}/bearbeiten")
    async def bearbeiten(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kunde_oder_liste(kunde_id)
        form = await formular(request)
        try:
            kunden.aendern(con, kunde_id, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "kunde_form.html", n, k={**dict(form), "id": kunde_id}, fehler=e.fehler,
                             felder=kunden.KUNDE_FELDER, status=400)
        return RedirectResponse(f"/kunden/{kunde_id}?hinweis=gespeichert", status_code=303)

    @r.post("/kunden/{kunde_id}/loeschen")
    async def loeschen(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kunde_oder_liste(kunde_id)
        await formular(request)
        try:
            kunden.loeschen(con, kunde_id, n["id"])
        except Ungueltig:
            return RedirectResponse(f"/kunden/{kunde_id}?hinweis=hat_objekte", status_code=303)
        return RedirectResponse("/kunden?hinweis=geloescht", status_code=303)

    # ---------- Kontakte ----------
    @r.get("/kunden/{kunde_id}/kontakte/neu", response_class=HTMLResponse)
    def kontakt_neu_form(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        return web.seite(request, "kontakt_form.html", n, k=kunde_oder_liste(kunde_id), kt={}, fehler={},
                         felder=kunden.KONTAKT_FELDER)

    @r.post("/kunden/{kunde_id}/kontakte/neu")
    async def kontakt_neu(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k = kunde_oder_liste(kunde_id)
        form = await formular(request)
        try:
            kunden.kontakt_anlegen(con, kunde_id, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "kontakt_form.html", n, k=k, kt=dict(form), fehler=e.fehler,
                             felder=kunden.KONTAKT_FELDER, status=400)
        return RedirectResponse(f"/kunden/{kunde_id}?hinweis=kontakt_angelegt#kontakte", status_code=303)

    @r.get("/kontakte/{kontakt_id}", response_class=HTMLResponse)
    def kontakt_form(request: Request, kontakt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kt = kontakt_oder_liste(kontakt_id)
        return web.seite(request, "kontakt_form.html", n, k=kunden.holen(con, kt["kunde_id"]), kt=dict(kt),
                         fehler={}, felder=kunden.KONTAKT_FELDER)

    @r.post("/kontakte/{kontakt_id}")
    async def kontakt_speichern(request: Request, kontakt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kt = kontakt_oder_liste(kontakt_id)
        form = await formular(request)
        try:
            kunden.kontakt_aendern(con, kontakt_id, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "kontakt_form.html", n, k=kunden.holen(con, kt["kunde_id"]),
                             kt={**dict(form), "id": kontakt_id}, fehler=e.fehler, felder=kunden.KONTAKT_FELDER,
                             status=400)
        return RedirectResponse(f"/kunden/{kt['kunde_id']}?hinweis=kontakt_gespeichert#kontakte", status_code=303)

    @r.post("/kontakte/{kontakt_id}/loeschen")
    async def kontakt_loeschen(request: Request, kontakt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kt = kontakt_oder_liste(kontakt_id)
        await formular(request)
        kunden.kontakt_loeschen(con, kontakt_id, n["id"])
        return RedirectResponse(f"/kunden/{kt['kunde_id']}?hinweis=kontakt_geloescht#kontakte", status_code=303)

    return r
