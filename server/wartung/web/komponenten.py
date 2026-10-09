"""Seiten: Komponente (Melder) anlegen – einzeln oder mehrere auf einmal –, bearbeiten, löschen (Fehleingabe),
austauschen, ausbauen; Gruppe (Wohnung) kopieren."""
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, anlagenart, gruppen, komponenten, lebenslauf, typen
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
        verlauf = lebenslauf.verlauf(con, g["id"], k["nummer"]) if k.get("id") and k.get("nummer") else []
        return web.seite(request, "komponente_form.html", n, g=g, a=anlagen.holen(con, g["anlage_id"]), art=art, k=k,
                         verlauf=verlauf, gruende=dict(lebenslauf.austausch_gruende(art) + lebenslauf.AUSBAU_GRUENDE),
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

    # ---------- Lebenslauf: austauschen, ausbauen ----------
    def massnahme_seite(request, n, k, art, vorgang, werte, fehler, status=200):
        felder = lebenslauf.felder_austausch(con, art) if vorgang == "austauschen" else lebenslauf.felder_ausbau()
        g = gruppen.holen(con, k["gruppe_id"])
        return web.seite(request, "komponente_massnahme.html", n, k=k, g=g, a=anlagen.holen(con, g["anlage_id"]),
                         art=art, vorgang=vorgang, werte=werte, fehler=fehler, felder=felder, status=status)

    def massnahme_start(request, komponente_id, vorgang):
        n = web.nutzer(request, BEARBEITEN)
        k, art = komponente_laden(komponente_id)
        return massnahme_seite(request, n, k, art, vorgang, {"zeitpunkt": date.today().isoformat(),
                                                             "komponententyp_id": k["komponententyp_id"]}, {})

    @r.get("/komponenten/{komponente_id}/austauschen", response_class=HTMLResponse)
    def austauschen_form(request: Request, komponente_id: str):
        return massnahme_start(request, komponente_id, "austauschen")

    @r.post("/komponenten/{komponente_id}/austauschen")
    async def austauschen(request: Request, komponente_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k, art = komponente_laden(komponente_id)
        form = await web.formular(request)
        try:
            lebenslauf.austauschen(con, art, k, form, n["id"])
        except Ungueltig as e:
            return massnahme_seite(request, n, k, art, "austauschen", dict(form), e.fehler, 400)
        return zur_gruppe(gruppen.holen(con, k["gruppe_id"]), "komponente_ersetzt")

    @r.get("/komponenten/{komponente_id}/ausbauen", response_class=HTMLResponse)
    def ausbauen_form(request: Request, komponente_id: str):
        return massnahme_start(request, komponente_id, "ausbauen")

    @r.post("/komponenten/{komponente_id}/ausbauen")
    async def ausbauen(request: Request, komponente_id: str):
        n = web.nutzer(request, BEARBEITEN)
        k, art = komponente_laden(komponente_id)
        form = await web.formular(request)
        try:
            lebenslauf.ausbauen(con, k, form, n["id"])
        except Ungueltig as e:
            return massnahme_seite(request, n, k, art, "ausbauen", dict(form), e.fehler, 400)
        return zur_gruppe(gruppen.holen(con, k["gruppe_id"]), "komponente_ausgebaut")

    # ---------- Gruppe kopieren ----------
    def kopieren_seite(request, n, g, art, werte, fehler, status=200):
        return web.seite(request, "gruppe_kopieren.html", n, g=g, a=anlagen.holen(con, g["anlage_id"]), art=art,
                         werte=werte, fehler=fehler, felder=gruppen.felder(art), status=status,
                         vorschau=gruppen.naechste_nummer(con, g["anlage_id"]),
                         anzahl=gruppen.anzahl_komponenten(con, g["id"]))

    @r.get("/gruppen/{gruppe_id}/kopieren", response_class=HTMLResponse)
    def kopieren_form(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        return kopieren_seite(request, n, g, art, {"zugang": g["zugang"]}, {})

    @r.post("/gruppen/{gruppe_id}/kopieren")
    async def kopieren(request: Request, gruppe_id: str):
        n = web.nutzer(request, BEARBEITEN)
        g, art = gruppe_laden(gruppe_id)
        form = await web.formular(request)
        try:
            neu_id = lebenslauf.gruppe_kopieren(con, art, g, form, n["id"])
        except Ungueltig as e:
            return kopieren_seite(request, n, g, art, dict(form), e.fehler, 400)
        return RedirectResponse(f"/anlagen/{g['anlage_id']}?hinweis=gruppe_kopiert#g-{neu_id}", status_code=303)

    return r
