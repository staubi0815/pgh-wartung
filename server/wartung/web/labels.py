"""Seiten: Labels pflegen (Verwaltung → Labels, Recht verwaltung.katalog) und an Kunde, Objekt, Anlage und Auftrag
anhaken (Recht stammdaten.bearbeiten, bei Aufträgen auftraege.planen)."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, auftraege, kunden, labels, objekte
from ..felder import Ungueltig

RECHT = "verwaltung.katalog"
LISTE = "/verwaltung/labels"
# art -> (Pfad, Recht zum Ändern, Suchfunktion)
ZIELE = {"kunde": ("kunden", "stammdaten.bearbeiten", kunden.holen),
         "objekt": ("objekte", "stammdaten.bearbeiten", objekte.holen),
         "anlage": ("anlagen", "stammdaten.bearbeiten", anlagen.holen),
         "auftrag": ("auftraege", "auftraege.planen", auftraege.holen)}


def router(web):
    r = APIRouter()
    con = web.con

    def label_laden(label_id):
        return web.holen_oder_weiter(labels.holen(con, label_id), LISTE)

    def formular(request, n, werte, fehler, status=200):
        return web.seite(request, "label_form.html", n, l=werte, fehler=fehler, felder=labels.FELDER, status=status)

    @r.get(LISTE, response_class=HTMLResponse)
    def liste(request: Request, hinweis: str = "", anzahl: int = 0):
        n = web.nutzer(request, RECHT)
        return web.seite(request, "labels_liste.html", n, liste=labels.liste(con), hinweis=hinweis, anzahl=anzahl)

    @r.get(LISTE + "/neu", response_class=HTMLResponse)
    def neu_form(request: Request):
        n = web.nutzer(request, RECHT)
        return formular(request, n, {"farbe": "blau"}, {})

    @r.post(LISTE + "/neu")
    async def neu(request: Request):
        n = web.nutzer(request, RECHT)
        form = await web.formular(request)
        try:
            labels.anlegen(con, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, dict(form), e.fehler, 400)
        return RedirectResponse(LISTE + "?hinweis=angelegt", status_code=303)

    @r.get(LISTE + "/{label_id}", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, label_id: str):
        n = web.nutzer(request, RECHT)
        return formular(request, n, dict(label_laden(label_id)), {})

    @r.post(LISTE + "/{label_id}")
    async def bearbeiten(request: Request, label_id: str):
        n = web.nutzer(request, RECHT)
        alt = label_laden(label_id)
        form = await web.formular(request)
        try:
            labels.aendern(con, label_id, form, n["id"])
        except Ungueltig as e:
            return formular(request, n, {**dict(alt), **dict(form)}, e.fehler, 400)
        return RedirectResponse(LISTE + "?hinweis=gespeichert", status_code=303)

    @r.post(LISTE + "/{label_id}/loeschen")
    async def loeschen(request: Request, label_id: str):
        n = web.nutzer(request, RECHT)
        label_laden(label_id)
        await web.formular(request)
        anzahl = labels.loeschen(con, label_id, n["id"])
        return RedirectResponse(f"{LISTE}?hinweis=geloescht&anzahl={anzahl}", status_code=303)

    def zuordnen_route(art, pfad, recht, holen):
        @r.post(f"/{pfad}/{{datensatz_id}}/labels", name=f"labels_{art}")
        async def zuordnen(request: Request, datensatz_id: str):
            n = web.nutzer(request, recht)
            web.holen_oder_weiter(holen(con, datensatz_id), f"/{pfad}?hinweis=nicht_gefunden")
            form = await web.formular(request)
            try:
                labels.setzen(con, art, datensatz_id, form.getlist("label"), n["id"])
            except Ungueltig:
                pass
            return RedirectResponse(f"/{pfad}/{datensatz_id}#labels", status_code=303)

    for art, (pfad, recht, holen) in ZIELE.items():
        zuordnen_route(art, pfad, recht, holen)

    return r
