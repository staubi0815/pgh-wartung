"""Seiten: Anmelden, Abmelden, Passwort per Einladung setzen, Startseite, eigenes Passwort ändern."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import anlagen, auth, rechte


def router(web):
    r = APIRouter()
    con = web.con

    @r.get("/anmelden", response_class=HTMLResponse)
    def anmelden_form(request: Request):
        return web.seite(request, "anmelden.html")

    @r.post("/anmelden")
    def anmelden(request: Request, email: str = Form(""), passwort: str = Form(""), csrf_token: str = Form("")):
        web.csrf(request, csrf_token)
        n, fehler = auth.anmelden(con, email, passwort)
        if fehler:
            return web.seite(request, "anmelden.html", fehler=fehler, email=email, status=401)
        if "web.zugang" not in rechte.rechte_von_nutzer(con, n["id"]):
            return web.seite(request, "anmelden.html", email=email, status=403,
                             fehler="Dieses Konto ist nur für die App freigeschaltet, nicht für die Webseite.")
        request.session.clear()
        request.session.update({"nutzer_id": n["id"], "zaehler": n["sitzung_zaehler"]})
        return RedirectResponse("/", status_code=303)

    @r.post("/abmelden")
    def abmelden(request: Request, csrf_token: str = Form("")):
        web.csrf(request, csrf_token)
        request.session.clear()
        return RedirectResponse("/anmelden", status_code=303)

    @r.get("/einrichten", response_class=HTMLResponse)
    def einrichten_form(request: Request, code: str = ""):
        n = auth.einladung_pruefen(con, code)
        return web.seite(request, "einrichten.html", eingeladen=n, code=code, status=200 if n else 404)

    @r.post("/einrichten")
    def einrichten(request: Request, code: str = Form(""), passwort: str = Form(""), passwort2: str = Form(""),
                   csrf_token: str = Form("")):
        web.csrf(request, csrf_token)
        n = auth.einladung_pruefen(con, code)
        if n is None:
            return web.seite(request, "einrichten.html", eingeladen=None, code=code, status=404)
        fehler = "Die Passwörter stimmen nicht überein." if passwort != passwort2 else auth.passwort_regeln(passwort)
        if fehler:
            return web.seite(request, "einrichten.html", eingeladen=n, code=code, fehler=fehler, status=400)
        auth.passwort_setzen(con, n["id"], passwort, n["id"])
        return RedirectResponse("/anmelden?hinweis=passwort_gesetzt", status_code=303)

    @r.get("/", response_class=HTMLResponse)
    def start(request: Request, hinweis: str = ""):
        n = web.nutzer(request)
        faellig = anlagen.faellig_zaehlen(con) if "stammdaten.lesen" in request.state.rechte else None
        return web.seite(request, "start.html", n, hinweis=hinweis, faellig=faellig)

    @r.get("/konto/passwort", response_class=HTMLResponse)
    def passwort_form(request: Request):
        return web.seite(request, "passwort.html", web.nutzer(request))

    @r.post("/konto/passwort")
    def passwort_aendern(request: Request, alt: str = Form(""), neu: str = Form(""), neu2: str = Form(""),
                         csrf_token: str = Form("")):
        n = web.nutzer(request)
        web.csrf(request, csrf_token)
        geprueft, _ = auth.anmelden(con, n["email"], alt)
        fehler = ("Das bisherige Passwort ist falsch." if geprueft is None else
                  "Die neuen Passwörter stimmen nicht überein." if neu != neu2 else auth.passwort_regeln(neu))
        if fehler:
            return web.seite(request, "passwort.html", n, fehler=fehler, status=400)
        auth.passwort_setzen(con, n["id"], neu, n["id"])
        request.session.clear()
        return RedirectResponse("/anmelden?hinweis=passwort_gesetzt", status_code=303)

    return r
