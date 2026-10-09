"""Seiten: Auftragsliste und Wochenansicht, Auftrag planen (aus der Anlage), ansehen, bearbeiten/verschieben,
Status wechseln.

Rechte: Liste und Auftrag ansehen mit Webzugang – mit stammdaten.lesen alle Aufträge, sonst nur eigene (Techniker
zusätzlich Pool-Aufträge, siehe auftraege.sicht). Planen/ändern/Status mit auftraege.planen.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, anlagenart, auftraege, gruppen, nummern
from ..felder import Ungueltig
from .basis import Weiterleitung

PLANEN = "auftraege.planen"


def _formularwerte(form):
    """Formular -> Werte für die Maske (Mehrfachauswahl als Liste)."""
    werte = {k: v for k, v in form.items() if k not in ("techniker", "gruppen", "csrf_token")}
    werte["techniker"] = form.getlist("techniker")
    werte["gruppen"] = form.getlist("gruppen")
    return werte


def router(web):
    r = APIRouter()
    con = web.con

    def anlage_laden(anlage_id):
        return web.holen_oder_weiter(anlagen.holen(con, anlage_id), "/anlagen?hinweis=nicht_gefunden")

    def auftrag_laden(auftrag_id):
        return web.holen_oder_weiter(auftraege.holen(con, auftrag_id), "/auftraege?hinweis=nicht_gefunden")

    def alle_auftragsarten():
        """(Schlüssel, Name) aller Auftragsarten über alle Anlagenarten, ohne Doppelte."""
        arten = {}
        for art in anlagenart.alle().values():
            for x in art.auftragsarten:
                arten.setdefault(x.schluessel, x.name)
        return tuple(arten.items())

    # ---------- Liste / Woche ----------
    @r.get("/auftraege", response_class=HTMLResponse)
    def liste(request: Request, ansicht: str = "liste", status: str = "", von: str = "", bis: str = "",
              techniker: str = "", art: str = "", q: str = "", woche: str = "", hinweis: str = ""):
        n = web.nutzer(request)
        eingeschraenkt = auftraege.sicht(request.state.rechte, n["id"])
        filter_ = {"techniker_id": techniker if eingeschraenkt is None else "", "auftragsart": art, "suche": q,
                   "eingeschraenkt": eingeschraenkt}
        werte = {"ansicht": "woche" if ansicht == "woche" else "liste", "status": status, "von": von, "bis": bis,
                 "techniker": techniker, "art": art, "q": q}
        gemeinsam = dict(werte=werte, eingeschraenkt=eingeschraenkt, status_auswahl=auftraege.LISTE_STATUS,
                         auftragsarten=alle_auftragsarten(), arten_text=dict(alle_auftragsarten()),
                         techniker_auswahl=auftraege.techniker_auswahl(con) if eingeschraenkt is None else (),
                         hinweis=hinweis, max_liste=auftraege.MAX_LISTE, heute=date.today().isoformat())
        if werte["ansicht"] == "woche":
            montag, tage = auftraege.woche(con, woche, status or "alle", **filter_)
            return web.seite(request, "auftraege_liste.html", n, tage=tage, montag=montag,
                             vorher=(montag - timedelta(days=7)).isoformat(),
                             nachher=(montag + timedelta(days=7)).isoformat(), **gemeinsam)
        eintraege = auftraege.liste(con, status or "offen", von, bis, **filter_)
        return web.seite(request, "auftraege_liste.html", n, liste=eintraege[:auftraege.MAX_LISTE],
                         mehr=len(eintraege) > auftraege.MAX_LISTE, **gemeinsam)

    def formular_seite(request, n, a, u, werte, fehler=None, status=200):
        art = anlagenart.holen(a["anlagenart"])
        bisher = [t["id"] for t in auftraege.techniker(con, u["id"])] if u else []
        return web.seite(request, "auftrag_form.html", n, a=anlagen.bewerten(a), u=u, art=art, werte=werte,
                         fehler=fehler or {}, felder=auftraege.felder(art, mit_nummer=u is None),
                         techniker_auswahl=auftraege.techniker_auswahl(con, bisher),
                         gruppen=gruppen.liste(con, a["id"]), umfang=auftraege.UMFANG,
                         vorschau=nummern.vorschau(con, "auftrag") if u is None else "", status=status)

    def detail_seite(request, n, u, hinweis="", fehler=None, status=200, status_form=None):
        art = anlagenart.alle().get(u["anlagenart"])
        return web.seite(request, "auftrag.html", n, u=u, art=art,
                         auftragsart=auftraege.auftragsart_name(u["anlagenart"], u["auftragsart"]),
                         techniker=auftraege.techniker(con, u["id"]), gruppen=auftraege.gruppen(con, u["id"]),
                         verlauf=auftraege.verlauf(con, u["id"]), status_text=auftraege.STATUS_TEXT,
                         aktionen=[(neu, auftraege.AKTION_TEXT[(u["status"], neu)], auftraege.grund_noetig(u["status"],
                                                                                                         neu))
                                   for neu in auftraege.UEBERGAENGE[u["status"]]],
                         offen=u["status"] in auftraege.OFFEN, hinweis=hinweis, fehler=fehler or {},
                         status_form=status_form or {}, status=status)

    # ---------- planen ----------
    @r.get("/anlagen/{anlage_id}/auftraege/neu", response_class=HTMLResponse)
    def neu_form(request: Request, anlage_id: str):
        n = web.nutzer(request, PLANEN)
        a = anlage_laden(anlage_id)
        art = anlagenart.holen(a["anlagenart"])
        return formular_seite(request, n, a, None, {"auftragsart": auftraege.standard_auftragsart(art),
                                                    "umfang": "ganze_anlage", "techniker": [], "gruppen": []})

    @r.post("/anlagen/{anlage_id}/auftraege/neu")
    async def neu(request: Request, anlage_id: str):
        n = web.nutzer(request, PLANEN)
        a = anlage_laden(anlage_id)
        form = await web.formular(request)
        try:
            aid = auftraege.anlegen(con, a, form, n["id"])
        except Ungueltig as e:
            return formular_seite(request, n, a, None, _formularwerte(form), e.fehler, 400)
        return RedirectResponse(f"/auftraege/{aid}?hinweis=angelegt", status_code=303)

    # ---------- ansehen ----------
    @r.get("/auftraege/{auftrag_id}", response_class=HTMLResponse)
    def detail(request: Request, auftrag_id: str, hinweis: str = ""):
        n = web.nutzer(request)
        u = auftrag_laden(auftrag_id)
        if not auftraege.darf_sehen(con, auftrag_id, request.state.rechte, n["id"]):
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        return detail_seite(request, n, u, hinweis)

    # ---------- bearbeiten / verschieben ----------
    @r.get("/auftraege/{auftrag_id}/bearbeiten", response_class=HTMLResponse)
    def bearbeiten_form(request: Request, auftrag_id: str):
        n = web.nutzer(request, PLANEN)
        u = auftrag_laden(auftrag_id)
        if u["status"] not in auftraege.OFFEN:
            return RedirectResponse(f"/auftraege/{auftrag_id}?hinweis=nicht_aenderbar", status_code=303)
        werte = {**dict(u), "techniker": [t["id"] for t in auftraege.techniker(con, auftrag_id)],
                 "gruppen": [g["id"] for g in auftraege.gruppen(con, auftrag_id)]}
        return formular_seite(request, n, anlage_laden(u["anlage_id"]), u, werte)

    @r.post("/auftraege/{auftrag_id}/bearbeiten")
    async def bearbeiten(request: Request, auftrag_id: str):
        n = web.nutzer(request, PLANEN)
        u = auftrag_laden(auftrag_id)
        form = await web.formular(request)
        try:
            geaendert = auftraege.aendern(con, auftrag_id, form, n["id"])
        except Ungueltig as e:
            return formular_seite(request, n, anlage_laden(u["anlage_id"]), u, _formularwerte(form), e.fehler, 400)
        return RedirectResponse(f"/auftraege/{auftrag_id}?hinweis={'gespeichert' if geaendert else 'unveraendert'}",
                                status_code=303)

    # ---------- Status ----------
    @r.post("/auftraege/{auftrag_id}/status")
    async def status(request: Request, auftrag_id: str):
        n = web.nutzer(request, PLANEN)
        u = auftrag_laden(auftrag_id)
        form = await web.formular(request)
        neu = form.get("neu", "")
        try:
            auftraege.status_setzen(con, auftrag_id, neu, n["id"], form.get("grund", ""),
                                    form.get("rechnung_nummer", ""))
        except Ungueltig as e:
            return detail_seite(request, n, u, fehler=e.fehler, status=400, status_form={"neu": neu, **dict(form)})
        return RedirectResponse(f"/auftraege/{auftrag_id}?hinweis=status", status_code=303)

    return r
