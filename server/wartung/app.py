"""Webseite fürs Büro – Grundgerüst: Anmeldung, Start, Verwaltung (Firma, Nutzer, Protokoll)."""
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db

HIER = Path(__file__).parent
ROLLEN = {"admin": "Admin", "buero": "Büro", "techniker": "Techniker"}
FIRMA_FELDER = ["name", "inhaber", "strasse", "plz", "ort", "telefon", "email", "praefix_kunde", "praefix_objekt",
                "praefix_anlage", "praefix_auftrag", "berichtsfusszeile"]


class Weiterleitung(Exception):
    def __init__(self, ziel):
        self.ziel = ziel


def _geheimnis(daten):
    datei = daten / "sitzungsschluessel"
    if not datei.exists():
        datei.write_text(secrets.token_hex(32))
        os.chmod(datei, 0o600)
    return datei.read_text().strip()


def erzeuge_app(daten_ordner=None, https=False):
    daten = Path(daten_ordner) if daten_ordner else db.daten_ordner()
    daten.mkdir(parents=True, exist_ok=True)
    con = db.verbinden(daten / "wartung.db")
    db.migrieren(con)

    app = FastAPI(title="PGH-Wartung", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.con = con
    app.add_middleware(SessionMiddleware, secret_key=_geheimnis(daten), session_cookie="pgh_sitzung",
                       max_age=12 * 3600, same_site="strict", https_only=https)
    app.mount("/static", StaticFiles(directory=HIER / "static"), name="static")
    vorlagen = Jinja2Templates(directory=HIER / "templates")
    vorlagen.env.globals["ROLLEN"] = ROLLEN

    @app.middleware("http")
    async def sicherheitskoepfe(request, call_next):
        antwort = await call_next(request)
        antwort.headers["X-Frame-Options"] = "DENY"
        antwort.headers["X-Content-Type-Options"] = "nosniff"
        antwort.headers["Referrer-Policy"] = "no-referrer"
        antwort.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; "
                                                      "frame-ancestors 'none'; form-action 'self'")
        antwort.headers["Cache-Control"] = "no-store"
        return antwort

    @app.exception_handler(Weiterleitung)
    async def weiterleiten(request, exc):
        return RedirectResponse(exc.ziel, status_code=303)

    def nutzer(request, rollen=None):
        s = request.session
        n = con.execute("SELECT * FROM nutzer WHERE id = ? AND aktiv = 1 AND geloescht = 0",
                        (s.get("nutzer_id"),)).fetchone() if s.get("nutzer_id") else None
        if n is None or n["sitzung_zaehler"] != s.get("zaehler"):
            s.clear()
            raise Weiterleitung("/anmelden")
        if rollen and n["rolle"] not in rollen:
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        return n

    def seite(request, name, n=None, status=200, **werte):
        firma = con.execute("SELECT name FROM firma WHERE id = 1").fetchone()
        return vorlagen.TemplateResponse(request, name, {"ich": n, "csrf": auth.csrf_token(request.session),
                                                         "firmenname": firma["name"], **werte}, status_code=status)

    def csrf(request, token):
        if not auth.csrf_ok(request.session, token):
            raise Weiterleitung("/?hinweis=sitzung_abgelaufen")

    # ---------- Anmeldung ----------
    @app.get("/anmelden", response_class=HTMLResponse)
    def anmelden_form(request: Request):
        return seite(request, "anmelden.html")

    @app.post("/anmelden")
    def anmelden(request: Request, email: str = Form(""), passwort: str = Form(""), csrf_token: str = Form("")):
        csrf(request, csrf_token)
        n, fehler = auth.anmelden(con, email, passwort)
        if fehler:
            return seite(request, "anmelden.html", fehler=fehler, email=email, status=401)
        request.session.clear()
        request.session.update({"nutzer_id": n["id"], "zaehler": n["sitzung_zaehler"]})
        return RedirectResponse("/", status_code=303)

    @app.post("/abmelden")
    def abmelden(request: Request, csrf_token: str = Form("")):
        csrf(request, csrf_token)
        request.session.clear()
        return RedirectResponse("/anmelden", status_code=303)

    @app.get("/einrichten", response_class=HTMLResponse)
    def einrichten_form(request: Request, code: str = ""):
        n = auth.einladung_pruefen(con, code)
        return seite(request, "einrichten.html", eingeladen=n, code=code, status=200 if n else 404)

    @app.post("/einrichten")
    def einrichten(request: Request, code: str = Form(""), passwort: str = Form(""), passwort2: str = Form(""),
                   csrf_token: str = Form("")):
        csrf(request, csrf_token)
        n = auth.einladung_pruefen(con, code)
        if n is None:
            return seite(request, "einrichten.html", eingeladen=None, code=code, status=404)
        fehler = "Die Passwörter stimmen nicht überein." if passwort != passwort2 else auth.passwort_regeln(passwort)
        if fehler:
            return seite(request, "einrichten.html", eingeladen=n, code=code, fehler=fehler, status=400)
        auth.passwort_setzen(con, n["id"], passwort, n["id"])
        return RedirectResponse("/anmelden?hinweis=passwort_gesetzt", status_code=303)

    # ---------- Start ----------
    @app.get("/", response_class=HTMLResponse)
    def start(request: Request, hinweis: str = ""):
        n = nutzer(request)
        return seite(request, "start.html", n, hinweis=hinweis)

    # ---------- Eigenes Konto ----------
    @app.get("/konto/passwort", response_class=HTMLResponse)
    def passwort_form(request: Request):
        return seite(request, "passwort.html", nutzer(request))

    @app.post("/konto/passwort")
    def passwort_aendern(request: Request, alt: str = Form(""), neu: str = Form(""), neu2: str = Form(""),
                         csrf_token: str = Form("")):
        n = nutzer(request)
        csrf(request, csrf_token)
        geprueft, _ = auth.anmelden(con, n["email"], alt)
        fehler = ("Das bisherige Passwort ist falsch." if geprueft is None else
                  "Die neuen Passwörter stimmen nicht überein." if neu != neu2 else auth.passwort_regeln(neu))
        if fehler:
            return seite(request, "passwort.html", n, fehler=fehler, status=400)
        auth.passwort_setzen(con, n["id"], neu, n["id"])
        request.session.clear()
        return RedirectResponse("/anmelden?hinweis=passwort_gesetzt", status_code=303)

    # ---------- Verwaltung: Firma ----------
    @app.get("/verwaltung/firma", response_class=HTMLResponse)
    def firma_form(request: Request, gespeichert: int = 0):
        n = nutzer(request, ("admin",))
        return seite(request, "firma.html", n, f=con.execute("SELECT * FROM firma WHERE id = 1").fetchone(),
                     gespeichert=gespeichert)

    @app.post("/verwaltung/firma")
    async def firma_speichern(request: Request):
        n = nutzer(request, ("admin",))
        form = await request.form()
        csrf(request, form.get("csrf_token"))
        werte = {k: str(form.get(k, "")).strip() for k in FIRMA_FELDER}
        if not werte["name"]:
            return seite(request, "firma.html", n, f=werte, fehler="Name ist Pflicht.", status=400)
        db.aendern(con, "firma", 1, werte, n["id"])
        return RedirectResponse("/verwaltung/firma?gespeichert=1", status_code=303)

    # ---------- Verwaltung: Nutzer ----------
    @app.get("/verwaltung/nutzer", response_class=HTMLResponse)
    def nutzer_liste(request: Request):
        n = nutzer(request, ("admin",))
        liste = con.execute("SELECT * FROM nutzer WHERE geloescht = 0 ORDER BY aktiv DESC, name").fetchall()
        return seite(request, "nutzer_liste.html", n, liste=liste)

    @app.get("/verwaltung/nutzer/neu", response_class=HTMLResponse)
    def nutzer_neu_form(request: Request):
        return seite(request, "nutzer_form.html", nutzer(request, ("admin",)), u=None)

    @app.post("/verwaltung/nutzer/neu")
    def nutzer_neu(request: Request, name: str = Form(""), email: str = Form(""), rolle: str = Form("techniker"),
                   kuerzel: str = Form(""), personalnummer: str = Form(""), csrf_token: str = Form("")):
        n = nutzer(request, ("admin",))
        csrf(request, csrf_token)
        u = {"name": name, "email": email, "rolle": rolle, "kuerzel": kuerzel, "personalnummer": personalnummer}
        fehler = _nutzer_pruefen(con, u)
        if fehler:
            return seite(request, "nutzer_form.html", n, u=u, fehler=fehler, status=400)
        nid = auth.nutzer_anlegen(con, name, email, rolle, n["id"], kuerzel, personalnummer.strip() or None)
        code = auth.einladung_erzeugen(con, nid, n["id"])
        return seite(request, "einladung.html", n, u=u, link=f"{str(request.base_url).rstrip('/')}/einrichten?code={code}")

    @app.get("/verwaltung/nutzer/{nid}", response_class=HTMLResponse)
    def nutzer_form(request: Request, nid: str, gespeichert: int = 0):
        n = nutzer(request, ("admin",))
        u = con.execute("SELECT * FROM nutzer WHERE id = ? AND geloescht = 0", (nid,)).fetchone()
        if u is None:
            raise Weiterleitung("/verwaltung/nutzer")
        return seite(request, "nutzer_form.html", n, u=u, gespeichert=gespeichert)

    @app.post("/verwaltung/nutzer/{nid}")
    def nutzer_speichern(request: Request, nid: str, name: str = Form(""), rolle: str = Form(""),
                         kuerzel: str = Form(""), personalnummer: str = Form(""), aktiv: str = Form(""),
                         csrf_token: str = Form("")):
        n = nutzer(request, ("admin",))
        csrf(request, csrf_token)
        alt = con.execute("SELECT * FROM nutzer WHERE id = ? AND geloescht = 0", (nid,)).fetchone()
        if alt is None:
            raise Weiterleitung("/verwaltung/nutzer")
        u = {"name": name, "email": alt["email"], "rolle": rolle, "kuerzel": kuerzel,
             "personalnummer": personalnummer, "id": nid, "aktiv": 1 if aktiv else 0}
        fehler = _nutzer_pruefen(con, u, nid)
        if not fehler and nid == n["id"] and (rolle != "admin" or not aktiv):
            fehler = "Das eigene Admin-Konto kann nicht herabgestuft oder deaktiviert werden."
        if fehler:
            return seite(request, "nutzer_form.html", n, u=u, fehler=fehler, status=400)
        werte = {"name": name.strip(), "rolle": rolle, "kuerzel": kuerzel.strip(),
                 "personalnummer": personalnummer.strip() or None, "aktiv": u["aktiv"]}
        db.aendern(con, "nutzer", nid, werte, n["id"])
        if not u["aktiv"] or rolle != alt["rolle"]:
            con.execute("UPDATE nutzer SET sitzung_zaehler = sitzung_zaehler + 1 WHERE id = ?", (nid,))
        return RedirectResponse(f"/verwaltung/nutzer/{nid}?gespeichert=1", status_code=303)

    @app.post("/verwaltung/nutzer/{nid}/einladung")
    def nutzer_einladung(request: Request, nid: str, csrf_token: str = Form("")):
        n = nutzer(request, ("admin",))
        csrf(request, csrf_token)
        u = con.execute("SELECT * FROM nutzer WHERE id = ? AND geloescht = 0", (nid,)).fetchone()
        if u is None:
            raise Weiterleitung("/verwaltung/nutzer")
        code = auth.einladung_erzeugen(con, nid, n["id"])
        return seite(request, "einladung.html", n, u=u, link=f"{str(request.base_url).rstrip('/')}/einrichten?code={code}")

    # ---------- Verwaltung: Protokoll ----------
    @app.get("/verwaltung/protokoll", response_class=HTMLResponse)
    def protokoll_liste(request: Request):
        n = nutzer(request, ("admin",))
        zeilen = con.execute("SELECT p.*, n.name AS nutzer_name FROM aenderungsprotokoll p "
                             "LEFT JOIN nutzer n ON n.id = p.nutzer_id ORDER BY p.id DESC LIMIT 300").fetchall()
        return seite(request, "protokoll.html", n, zeilen=zeilen)

    return app


def _nutzer_pruefen(con, u, eigene_id=None):
    if not u["name"].strip():
        return "Name ist Pflicht."
    if "@" not in u["email"]:
        return "Bitte eine gültige E-Mail-Adresse angeben."
    if u["rolle"] not in ROLLEN:
        return "Unbekannte Rolle."
    if con.execute("SELECT 1 FROM nutzer WHERE email = ? AND id != ?", (u["email"].strip().lower(), eigene_id or "")).fetchone():
        return "Diese E-Mail-Adresse ist schon vergeben."
    pn = (u.get("personalnummer") or "").strip()
    if pn and con.execute("SELECT 1 FROM nutzer WHERE personalnummer = ? AND id != ?", (pn, eigene_id or "")).fetchone():
        return "Diese Personalnummer ist schon vergeben."
    return None
