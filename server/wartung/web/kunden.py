"""Seiten: Kundenliste, Kunde (Daten, Kontakte, Objekte), Kunde und Kontakt anlegen/ändern/löschen.

Lesen braucht das Recht stammdaten.lesen, Ändern stammdaten.bearbeiten.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import kunden, nummern, objekte
from ..felder import Ungueltig

LESEN, BEARBEITEN = "stammdaten.lesen", "stammdaten.bearbeiten"
NICHT_GEFUNDEN = "/kunden?hinweis=nicht_gefunden"


def router(web):
    r = APIRouter()
    con = web.con

    def kunde_oder_liste(kunde_id):
        return web.holen_oder_weiter(kunden.holen(con, kunde_id), NICHT_GEFUNDEN)

    def kontakt_oder_liste(kontakt_id):
        return web.holen_oder_weiter(kunden.kontakt_holen(con, kontakt_id), NICHT_GEFUNDEN)

    # ---------- Kunden ----------
    @r.get("/kunden", response_class=HTMLResponse)
    def liste(request: Request, q: str = "", art: str = "", hinweis: str = "", label: str = ""):
        n = web.nutzer(request, LESEN)
        return web.seite(request, "kunden_liste.html", n, liste=kunden.liste(con, q, art, label), q=q, art=art, label=label,
                         arten=kunden.KUNDENARTEN, arten_namen=dict(kunden.KUNDENARTEN), hinweis=hinweis)

    @r.get("/kunden/neu", response_class=HTMLResponse)
    def neu_form(request: Request):
        n = web.nutzer(request, BEARBEITEN)
        return web.seite(request, "kunde_form.html", n, k={"art": "hausverwaltung", "land": "DE"}, fehler={},
                         felder=kunden.KUNDE_FELDER, vorschau=nummern.vorschau(con, "kunde"))

    @r.post("/kunden/neu")
    async def neu(request: Request):
        n = web.nutzer(request, BEARBEITEN)
        form = await web.formular(request)
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
        return web.seite(request, "kunde.html", n, k=k, kontakte=kunden.kontakte(con, kunde_id),
                         objekte=objekte.liste_fuer_kunde(con, kunde_id),
                         felder=kunden.KUNDE_FELDER, hinweis=hinweis)

    @r.get("/kunden/{kunde_id}/bearbeiten", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        return web.seite(request, "kunde_form.html", n, k=dict(kunde_oder_liste(kunde_id)), fehler={},
                         felder=kunden.KUNDE_FELDER_BEARBEITEN)

    @r.post("/kunden/{kunde_id}/bearbeiten")
    async def bearbeiten(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kunde_oder_liste(kunde_id)
        form = await web.formular(request)
        try:
            kunden.aendern(con, kunde_id, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "kunde_form.html", n, k={**dict(form), "id": kunde_id}, fehler=e.fehler,
                             felder=kunden.KUNDE_FELDER_BEARBEITEN, status=400)
        return RedirectResponse(f"/kunden/{kunde_id}?hinweis=gespeichert", status_code=303)

    @r.post("/kunden/{kunde_id}/loeschen")
    async def loeschen(request: Request, kunde_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kunde_oder_liste(kunde_id)
        await web.formular(request)
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
        form = await web.formular(request)
        try:
            kunden.kontakt_anlegen(con, kunde_id, form, n["id"])
        except Ungueltig as e:
            return web.seite(request, "kontakt_form.html", n, k=k, kt=dict(form), fehler=e.fehler,
                             felder=kunden.KONTAKT_FELDER, status=400)
        return RedirectResponse(f"/kunden/{kunde_id}?hinweis=kontakt_angelegt#kontakte", status_code=303)

    def kontext(kontakt_id, kunde_id):
        """Kunde, von dem aus der Kontakt geöffnet wurde (sonst der erste), und alle Kunden des Kontakts."""
        alle = kunden.kunden_von_kontakt(con, kontakt_id)
        k = next((x for x in alle if x["id"] == kunde_id), alle[0] if alle else None)
        return k, alle

    def kontakt_seite(request, n, kt, k, alle, fehler, status=200):
        return web.seite(request, "kontakt_form.html", n, k=k, kt=kt, fehler=fehler, felder=kunden.KONTAKT_FELDER,
                         kunden_des_kontakts=alle, status=status)

    @r.get("/kontakte/{kontakt_id}", response_class=HTMLResponse)
    def kontakt_form(request: Request, kontakt_id: str, kunde: str = ""):
        n = web.nutzer(request, BEARBEITEN)
        kt = kontakt_oder_liste(kontakt_id)
        k, alle = kontext(kontakt_id, kunde)
        return kontakt_seite(request, n, dict(kt), k, alle, {})

    @r.post("/kontakte/{kontakt_id}")
    async def kontakt_speichern(request: Request, kontakt_id: str, kunde: str = ""):
        n = web.nutzer(request, BEARBEITEN)
        kontakt_oder_liste(kontakt_id)
        form = await web.formular(request)
        k, alle = kontext(kontakt_id, kunde)
        try:
            kunden.kontakt_aendern(con, kontakt_id, form, n["id"])
        except Ungueltig as e:
            return kontakt_seite(request, n, {**dict(form), "id": kontakt_id}, k, alle, e.fehler, status=400)
        return RedirectResponse(f"/kunden/{k['id']}?hinweis=kontakt_gespeichert#kontakte" if k else "/kunden",
                                status_code=303)

    @r.post("/kontakte/{kontakt_id}/loeschen")
    async def kontakt_loeschen(request: Request, kontakt_id: str, kunde: str = ""):
        n = web.nutzer(request, BEARBEITEN)
        kontakt_oder_liste(kontakt_id)
        await web.formular(request)
        k, _ = kontext(kontakt_id, kunde)
        kunden.kontakt_loeschen(con, kontakt_id, n["id"])
        return RedirectResponse(f"/kunden/{k['id']}?hinweis=kontakt_geloescht#kontakte" if k else "/kunden",
                                status_code=303)

    @r.post("/kunden/{kunde_id}/kontakte/{kontakt_id}/loesen")
    async def kontakt_loesen(request: Request, kunde_id: str, kontakt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kunde_oder_liste(kunde_id)
        kontakt_oder_liste(kontakt_id)
        await web.formular(request)
        try:
            kunden.kontakt_loesen(con, kunde_id, kontakt_id, n["id"])
        except Ungueltig:
            return RedirectResponse(f"/kontakte/{kontakt_id}?kunde={kunde_id}", status_code=303)
        return RedirectResponse(f"/kunden/{kunde_id}?hinweis=kontakt_geloest#kontakte", status_code=303)

    @r.get("/kunden/{kunde_id}/kontakte/hinzufuegen", response_class=HTMLResponse)
    def kontakt_hinzufuegen_form(request: Request, kunde_id: str, q: str = ""):
        n = web.nutzer(request, BEARBEITEN)
        return web.seite(request, "kontakt_hinzufuegen.html", n, k=kunde_oder_liste(kunde_id), q=q,
                         treffer=kunden.kontakte_suchen(con, q, kunde_id))

    @r.post("/kunden/{kunde_id}/kontakte/{kontakt_id}/hinzufuegen")
    async def kontakt_hinzufuegen(request: Request, kunde_id: str, kontakt_id: str):
        n = web.nutzer(request, BEARBEITEN)
        kunde_oder_liste(kunde_id)
        await web.formular(request)
        try:
            kunden.kontakt_verknuepfen(con, kunde_id, kontakt_id, n["id"])
        except Ungueltig:
            return RedirectResponse(f"/kunden/{kunde_id}/kontakte/hinzufuegen", status_code=303)
        return RedirectResponse(f"/kunden/{kunde_id}?hinweis=kontakt_hinzugefuegt#kontakte", status_code=303)

    return r
