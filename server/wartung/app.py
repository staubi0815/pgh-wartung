"""Webseite fürs Büro – Grundgerüst: Anmeldung, Start, Verwaltung (Firma, Nutzer, Rollen, Protokoll).

Seiten prüfen ausschließlich Einzelrechte (wartung/rechte.py), nie Rollennamen.
"""
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db, rechte

HIER = Path(__file__).parent
FIRMA_FELDER = ["name", "inhaber", "strasse", "plz", "ort", "telefon", "email", "praefix_kunde", "praefix_objekt",
                "praefix_anlage", "praefix_auftrag", "berichtsfusszeile"]
# Verwaltungsseiten in Menü-Reihenfolge: (Recht, Pfad, Titel)
VERWALTUNG = [("verwaltung.nutzer", "/verwaltung/nutzer", "Nutzer"),
              ("verwaltung.rollen", "/verwaltung/rollen", "Rollen und Rechte"),
              ("verwaltung.firma", "/verwaltung/firma", "Firma"),
              ("verwaltung.protokoll", "/verwaltung/protokoll", "Änderungsprotokoll")]


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
    pfad = daten / "wartung.db"
    einmal = db.verbinden(pfad)
    db.migrieren(einmal)
    einmal.close()
    con = db.ThreadVerbindung(pfad)

    app = FastAPI(title="PGH-Wartung", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.con = con
    app.add_middleware(SessionMiddleware, secret_key=_geheimnis(daten), session_cookie="pgh_sitzung",
                       max_age=12 * 3600, same_site="strict", https_only=https)
    app.mount("/static", StaticFiles(directory=HIER / "static"), name="static")
    vorlagen = Jinja2Templates(directory=HIER / "templates")
    vorlagen.env.globals.update(BEREICHE=rechte.BEREICHE, VERWALTUNG=VERWALTUNG)

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

    def nutzer(request, recht=None):
        """Angemeldeter Nutzer mit Webzugang (und ggf. dem verlangten Recht), sonst Weiterleitung."""
        s = request.session
        n = con.execute("SELECT * FROM nutzer WHERE id = ? AND aktiv = 1 AND geloescht = 0",
                        (s.get("nutzer_id"),)).fetchone() if s.get("nutzer_id") else None
        if n is None or n["sitzung_zaehler"] != s.get("zaehler"):
            s.clear()
            raise Weiterleitung("/anmelden")
        meine = rechte.rechte_von_nutzer(con, n["id"])
        if "web.zugang" not in meine:
            s.clear()
            raise Weiterleitung("/anmelden?hinweis=nur_app")
        if recht and recht not in meine:
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        request.state.rechte = meine
        return n

    def seite(request, name, n=None, status=200, **werte):
        firma = con.execute("SELECT name FROM firma WHERE id = 1").fetchone()
        return vorlagen.TemplateResponse(request, name, {
            "ich": n, "rechte": getattr(request.state, "rechte", set()), "csrf": auth.csrf_token(request.session),
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
        if "web.zugang" not in rechte.rechte_von_nutzer(con, n["id"]):
            return seite(request, "anmelden.html", email=email, status=403,
                         fehler="Dieses Konto ist nur für die App freigeschaltet, nicht für die Webseite.")
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

    # ---------- Verwaltung ----------
    @app.get("/verwaltung")
    def verwaltung(request: Request):
        nutzer(request)
        for recht, pfad, _ in VERWALTUNG:
            if recht in request.state.rechte:
                return RedirectResponse(pfad, status_code=303)
        raise Weiterleitung("/?hinweis=keine_berechtigung")

    # ---------- Verwaltung: Firma ----------
    @app.get("/verwaltung/firma", response_class=HTMLResponse)
    def firma_form(request: Request, gespeichert: int = 0):
        n = nutzer(request, "verwaltung.firma")
        return seite(request, "firma.html", n, f=con.execute("SELECT * FROM firma WHERE id = 1").fetchone(),
                     gespeichert=gespeichert)

    @app.post("/verwaltung/firma")
    async def firma_speichern(request: Request):
        n = nutzer(request, "verwaltung.firma")
        form = await request.form()
        csrf(request, form.get("csrf_token"))
        werte = {k: str(form.get(k, "")).strip() for k in FIRMA_FELDER}
        if not werte["name"]:
            return seite(request, "firma.html", n, f=werte, fehler="Name ist Pflicht.", status=400)
        db.aendern(con, "firma", 1, werte, n["id"])
        return RedirectResponse("/verwaltung/firma?gespeichert=1", status_code=303)

    # ---------- Verwaltung: Nutzer ----------
    def rollen_auswahl(request, n):
        """Rollen, die der angemeldete Nutzer vergeben darf (keine Rolle mit mehr Rechten als er selbst)."""
        return [r for r in rechte.rollen(con) if _darf_rolle_vergeben(con, request.state.rechte, n["id"], r["id"])]

    def nutzer_seite(request, n, u, rollen_ids, status=200, **werte):
        alle = rechte.rollen(con)
        return seite(request, "nutzer_form.html", n, u=u, rollen=alle, gewaehlt=set(rollen_ids),
                     vergebbar={r["id"] for r in rollen_auswahl(request, n)}, status=status, **werte)

    @app.get("/verwaltung/nutzer", response_class=HTMLResponse)
    def nutzer_liste(request: Request):
        n = nutzer(request, "verwaltung.nutzer")
        liste = con.execute(
            "SELECT n.*, (SELECT group_concat(r.name, ', ') FROM (SELECT r.name FROM nutzer_rolle nr "
            "   JOIN rolle r ON r.id = nr.rolle_id WHERE nr.nutzer_id = n.id AND r.geloescht = 0 "
            "   ORDER BY r.reihenfolge, r.name) r) AS rollen "
            "FROM nutzer n WHERE n.geloescht = 0 ORDER BY n.aktiv DESC, n.name").fetchall()
        return seite(request, "nutzer_liste.html", n, liste=liste)

    @app.get("/verwaltung/nutzer/neu", response_class=HTMLResponse)
    def nutzer_neu_form(request: Request):
        n = nutzer(request, "verwaltung.nutzer")
        techniker = con.execute("SELECT id FROM rolle WHERE kennung = 'techniker'").fetchone()
        return nutzer_seite(request, n, None, [techniker["id"]] if techniker else [])

    @app.post("/verwaltung/nutzer/neu")
    def nutzer_neu(request: Request, name: str = Form(""), email: str = Form(""), rollen: list[str] = Form([]),
                   kuerzel: str = Form(""), personalnummer: str = Form(""), csrf_token: str = Form("")):
        n = nutzer(request, "verwaltung.nutzer")
        csrf(request, csrf_token)
        u = {"name": name, "email": email, "kuerzel": kuerzel, "personalnummer": personalnummer}
        fehler = _nutzer_pruefen(con, u) or _rollen_pruefen(con, request.state.rechte, n["id"], set(), set(rollen))
        if fehler:
            return nutzer_seite(request, n, u, rollen, fehler=fehler, status=400)
        nid = auth.nutzer_anlegen(con, name, email, rollen, n["id"], kuerzel, personalnummer.strip() or None)
        code = auth.einladung_erzeugen(con, nid, n["id"])
        return seite(request, "einladung.html", n, u=u, link=f"{str(request.base_url).rstrip('/')}/einrichten?code={code}")

    def ziel_nutzer(request, n, nid):
        """Zu bearbeitender Nutzer – nur wenn er nicht mehr Rechte hat als der Bearbeiter."""
        u = con.execute("SELECT * FROM nutzer WHERE id = ? AND geloescht = 0", (nid,)).fetchone()
        if u is None:
            raise Weiterleitung("/verwaltung/nutzer")
        if not rechte.rechte_von_nutzer(con, nid) <= request.state.rechte:
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        return u

    @app.get("/verwaltung/nutzer/{nid}", response_class=HTMLResponse)
    def nutzer_form(request: Request, nid: str, gespeichert: int = 0):
        n = nutzer(request, "verwaltung.nutzer")
        u = ziel_nutzer(request, n, nid)
        return nutzer_seite(request, n, u, rechte.rollen_von_nutzer(con, nid), gespeichert=gespeichert)

    @app.post("/verwaltung/nutzer/{nid}")
    def nutzer_speichern(request: Request, nid: str, name: str = Form(""), rollen: list[str] = Form([]),
                         kuerzel: str = Form(""), personalnummer: str = Form(""), aktiv: str = Form(""),
                         csrf_token: str = Form("")):
        n = nutzer(request, "verwaltung.nutzer")
        csrf(request, csrf_token)
        alt = ziel_nutzer(request, n, nid)
        u = {"name": name, "email": alt["email"], "kuerzel": kuerzel, "personalnummer": personalnummer,
             "id": nid, "aktiv": 1 if aktiv else 0}
        alte_rollen, neue_rollen = rechte.rollen_von_nutzer(con, nid), set(rollen)
        admin = rechte.admin_rolle_id(con)
        fehler = _nutzer_pruefen(con, u, nid) or _rollen_pruefen(con, request.state.rechte, n["id"], alte_rollen,
                                                                 neue_rollen)
        if not fehler and nid == n["id"] and not u["aktiv"]:
            fehler = "Das eigene Konto kann nicht deaktiviert werden."
        if not fehler and nid == n["id"] and admin in alte_rollen and admin not in neue_rollen:
            fehler = "Die eigene Rolle Administration kann nicht entfernt werden."
        if fehler:
            return nutzer_seite(request, n, u, rollen, fehler=fehler, status=400)
        werte = {"name": name.strip(), "kuerzel": kuerzel.strip(),
                 "personalnummer": personalnummer.strip() or None, "aktiv": u["aktiv"]}
        with db.transaktion(con):
            db.aendern(con, "nutzer", nid, werte, n["id"])
            rechte.nutzer_rollen_setzen(con, nid, neue_rollen, n["id"])
            if not u["aktiv"] and alt["aktiv"]:
                con.execute("UPDATE nutzer SET sitzung_zaehler = sitzung_zaehler + 1 WHERE id = ?", (nid,))
            if rechte.aktive_admins(con) == 0:
                raise RuntimeError("Es muss immer mindestens ein aktiver Nutzer mit Administration bleiben.")
        return RedirectResponse(f"/verwaltung/nutzer/{nid}?gespeichert=1", status_code=303)

    @app.post("/verwaltung/nutzer/{nid}/einladung")
    def nutzer_einladung(request: Request, nid: str, csrf_token: str = Form("")):
        n = nutzer(request, "verwaltung.nutzer")
        csrf(request, csrf_token)
        u = ziel_nutzer(request, n, nid)
        code = auth.einladung_erzeugen(con, nid, n["id"])
        return seite(request, "einladung.html", n, u=u, link=f"{str(request.base_url).rstrip('/')}/einrichten?code={code}")

    # ---------- Verwaltung: Rollen und Rechte ----------
    def rolle_laden(rid):
        r = con.execute("SELECT * FROM rolle WHERE id = ? AND geloescht = 0", (rid,)).fetchone()
        if r is None:
            raise Weiterleitung("/verwaltung/rollen")
        return r

    def rolle_seite(request, n, r, gewaehlt, status=200, **werte):
        anzahl = con.execute("SELECT COUNT(*) FROM nutzer_rolle WHERE rolle_id = ?", (r["id"],)).fetchone()[0] \
            if r and r.get("id") else 0
        return seite(request, "rolle_form.html", n, r=r, gewaehlt=set(gewaehlt), anzahl=anzahl,
                     fest=bool(r and r.get("kennung") == rechte.ADMIN), status=status, **werte)

    @app.get("/verwaltung/rollen", response_class=HTMLResponse)
    def rollen_liste(request: Request):
        n = nutzer(request, "verwaltung.rollen")
        liste = rechte.rollen(con)
        matrix = {r["id"]: rechte.rechte_von_rolle(con, r["id"]) for r in liste}
        return seite(request, "rollen_liste.html", n, liste=liste, matrix=matrix)

    @app.get("/verwaltung/rollen/neu", response_class=HTMLResponse)
    def rolle_neu_form(request: Request):
        n = nutzer(request, "verwaltung.rollen")
        return rolle_seite(request, n, None, [])

    @app.post("/verwaltung/rollen/neu")
    def rolle_neu(request: Request, name: str = Form(""), beschreibung: str = Form(""),
                  rechte_liste: list[str] = Form([], alias="rechte"), csrf_token: str = Form("")):
        n = nutzer(request, "verwaltung.rollen")
        csrf(request, csrf_token)
        r = {"name": name, "beschreibung": beschreibung}
        fehler = _rolle_pruefen(con, r, set(rechte_liste), request.state.rechte)
        if fehler:
            return rolle_seite(request, n, r, rechte_liste, fehler=fehler, status=400)
        rid = rechte.rolle_anlegen(con, name, beschreibung, rechte_liste, n["id"])
        return RedirectResponse(f"/verwaltung/rollen/{rid}?gespeichert=1", status_code=303)

    @app.get("/verwaltung/rollen/{rid}", response_class=HTMLResponse)
    def rolle_form(request: Request, rid: str, gespeichert: int = 0):
        n = nutzer(request, "verwaltung.rollen")
        r = rolle_laden(rid)
        return rolle_seite(request, n, dict(r), rechte.rechte_von_rolle(con, rid), gespeichert=gespeichert)

    @app.post("/verwaltung/rollen/{rid}")
    def rolle_speichern(request: Request, rid: str, name: str = Form(""), beschreibung: str = Form(""),
                        rechte_liste: list[str] = Form([], alias="rechte"), csrf_token: str = Form("")):
        n = nutzer(request, "verwaltung.rollen")
        csrf(request, csrf_token)
        alt = dict(rolle_laden(rid))
        if alt["kennung"] == rechte.ADMIN:
            return rolle_seite(request, n, alt, rechte.rechte_von_rolle(con, rid), status=400,
                               fehler="Die Rolle Administration ist fest und kann nicht geändert werden.")
        r = {**alt, "name": name, "beschreibung": beschreibung}
        # nur Rechte vergeben oder entziehen, die man selbst hat
        bisher = rechte.rechte_von_rolle(con, rid)
        fehler = _rolle_pruefen(con, r, set(rechte_liste) ^ bisher, request.state.rechte, rid)
        if fehler:
            return rolle_seite(request, n, r, rechte_liste, fehler=fehler, status=400)
        with db.transaktion(con):
            db.aendern(con, "rolle", rid, {"name": name.strip(), "beschreibung": beschreibung.strip()}, n["id"])
            rechte.rolle_rechte_setzen(con, rid, rechte_liste, n["id"])
        return RedirectResponse(f"/verwaltung/rollen/{rid}?gespeichert=1", status_code=303)

    @app.post("/verwaltung/rollen/{rid}/loeschen")
    def rolle_loeschen(request: Request, rid: str, csrf_token: str = Form("")):
        n = nutzer(request, "verwaltung.rollen")
        csrf(request, csrf_token)
        r = dict(rolle_laden(rid))
        fehler = None
        if r["kennung"]:
            fehler = "Standardrollen können nicht gelöscht werden."
        elif con.execute("SELECT 1 FROM nutzer_rolle WHERE rolle_id = ?", (rid,)).fetchone():
            fehler = "Die Rolle ist noch Nutzern zugeordnet. Bitte zuerst dort entfernen."
        elif not rechte.rechte_von_rolle(con, rid) <= request.state.rechte:
            fehler = "Diese Rolle hat Rechte, die Sie selbst nicht haben."
        if fehler:
            return rolle_seite(request, n, r, rechte.rechte_von_rolle(con, rid), fehler=fehler, status=400)
        db.aendern(con, "rolle", rid, {"geloescht": 1}, n["id"])
        return RedirectResponse("/verwaltung/rollen", status_code=303)

    # ---------- Verwaltung: Protokoll ----------
    @app.get("/verwaltung/protokoll", response_class=HTMLResponse)
    def protokoll_liste(request: Request):
        n = nutzer(request, "verwaltung.protokoll")
        zeilen = con.execute("SELECT p.*, n.name AS nutzer_name FROM aenderungsprotokoll p "
                             "LEFT JOIN nutzer n ON n.id = p.nutzer_id ORDER BY p.id DESC LIMIT 300").fetchall()
        return seite(request, "protokoll.html", n, zeilen=zeilen)

    return app


def _nutzer_pruefen(con, u, eigene_id=None):
    if not u["name"].strip():
        return "Name ist Pflicht."
    if "@" not in u["email"]:
        return "Bitte eine gültige E-Mail-Adresse angeben."
    if con.execute("SELECT 1 FROM nutzer WHERE email = ? AND id != ?", (u["email"].strip().lower(), eigene_id or "")).fetchone():
        return "Diese E-Mail-Adresse ist schon vergeben."
    pn = (u.get("personalnummer") or "").strip()
    if pn and con.execute("SELECT 1 FROM nutzer WHERE personalnummer = ? AND id != ?", (pn, eigene_id or "")).fetchone():
        return "Diese Personalnummer ist schon vergeben."
    return None


def _darf_rolle_vergeben(con, meine_rechte, mein_id, rolle_id):
    """Eine Rolle darf nur vergeben/entziehen, wer alle ihre Rechte selbst hat; Administration nur Administratoren."""
    if rolle_id == rechte.admin_rolle_id(con):
        return rolle_id in rechte.rollen_von_nutzer(con, mein_id)
    return rechte.rechte_von_rolle(con, rolle_id) <= meine_rechte


def _rollen_pruefen(con, meine_rechte, mein_id, alt, neu):
    if not neu:
        return "Bitte mindestens eine Rolle wählen."
    gueltig = {r["id"] for r in rechte.rollen(con)}
    if not neu <= gueltig:
        return "Unbekannte Rolle."
    if any(not _darf_rolle_vergeben(con, meine_rechte, mein_id, rid) for rid in alt ^ neu):
        return "Sie können nur Rollen vergeben oder entziehen, deren Rechte Sie selbst haben."
    return None


def _rolle_pruefen(con, r, geaenderte_rechte, meine_rechte, eigene_id=None):
    if not r["name"].strip():
        return "Name ist Pflicht."
    if con.execute("SELECT 1 FROM rolle WHERE name = ? COLLATE NOCASE AND geloescht = 0 AND id != ?",
                   (r["name"].strip(), eigene_id or "")).fetchone():
        return "Eine Rolle mit diesem Namen gibt es schon."
    if not geaenderte_rechte <= set(rechte.RECHTE):
        return "Unbekanntes Recht."
    if not geaenderte_rechte <= meine_rechte:
        return "Sie können nur Rechte vergeben oder entziehen, die Sie selbst haben."
    return None
