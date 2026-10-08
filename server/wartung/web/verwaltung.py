"""Seiten der Verwaltung: Firma, Nutzer, Rollen und Rechte, Änderungsprotokoll."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth, db, rechte
from .basis import Weiterleitung

FIRMA_FELDER = ["name", "inhaber", "strasse", "plz", "ort", "telefon", "email", "praefix_kunde", "praefix_objekt",
                "praefix_anlage", "praefix_auftrag", "berichtsfusszeile"]
# Verwaltungsseiten in Menü-Reihenfolge: (Recht, Pfad, Titel)
MENUE = [("verwaltung.nutzer", "/verwaltung/nutzer", "Nutzer"),
         ("verwaltung.rollen", "/verwaltung/rollen", "Rollen und Rechte"),
         ("verwaltung.firma", "/verwaltung/firma", "Firma"),
         ("verwaltung.protokoll", "/verwaltung/protokoll", "Änderungsprotokoll")]


def router(web):
    r = APIRouter(prefix="/verwaltung")
    con = web.con

    @r.get("")
    def verwaltung(request: Request):
        web.nutzer(request)
        for recht, pfad, _ in MENUE:
            if recht in request.state.rechte:
                return RedirectResponse(pfad, status_code=303)
        raise Weiterleitung("/?hinweis=keine_berechtigung")

    # ---------- Firma ----------
    @r.get("/firma", response_class=HTMLResponse)
    def firma_form(request: Request, gespeichert: int = 0):
        n = web.nutzer(request, "verwaltung.firma")
        return web.seite(request, "firma.html", n, f=con.execute("SELECT * FROM firma WHERE id = 1").fetchone(),
                         gespeichert=gespeichert)

    @r.post("/firma")
    async def firma_speichern(request: Request):
        n = web.nutzer(request, "verwaltung.firma")
        form = await request.form()
        web.csrf(request, form.get("csrf_token"))
        werte = {k: str(form.get(k, "")).strip() for k in FIRMA_FELDER}
        if not werte["name"]:
            return web.seite(request, "firma.html", n, f=werte, fehler="Name ist Pflicht.", status=400)
        db.aendern(con, "firma", 1, werte, n["id"])
        return RedirectResponse("/verwaltung/firma?gespeichert=1", status_code=303)

    # ---------- Nutzer ----------
    def nutzer_seite(request, n, u, rollen_ids, status=200, **werte):
        vergebbar = {x["id"] for x in rechte.rollen(con)
                     if _darf_rolle_vergeben(con, request.state.rechte, n["id"], x["id"])}
        return web.seite(request, "nutzer_form.html", n, u=u, rollen=rechte.rollen(con), gewaehlt=set(rollen_ids),
                         vergebbar=vergebbar, status=status, **werte)

    def ziel_nutzer(request, nid):
        """Zu bearbeitender Nutzer – nur wenn er nicht mehr Rechte hat als der Bearbeiter."""
        u = con.execute("SELECT * FROM nutzer WHERE id = ? AND geloescht = 0", (nid,)).fetchone()
        if u is None:
            raise Weiterleitung("/verwaltung/nutzer")
        if not rechte.rechte_von_nutzer(con, nid) <= request.state.rechte:
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        return u

    def einladung_seite(request, n, u, code):
        link = f"{str(request.base_url).rstrip('/')}/einrichten?code={code}"
        return web.seite(request, "einladung.html", n, u=u, link=link)

    @r.get("/nutzer", response_class=HTMLResponse)
    def nutzer_liste(request: Request):
        n = web.nutzer(request, "verwaltung.nutzer")
        liste = con.execute(
            "SELECT n.*, (SELECT group_concat(r.name, ', ') FROM (SELECT r.name FROM nutzer_rolle nr "
            "   JOIN rolle r ON r.id = nr.rolle_id WHERE nr.nutzer_id = n.id AND r.geloescht = 0 "
            "   ORDER BY r.reihenfolge, r.name) r) AS rollen "
            "FROM nutzer n WHERE n.geloescht = 0 ORDER BY n.aktiv DESC, n.name").fetchall()
        return web.seite(request, "nutzer_liste.html", n, liste=liste)

    @r.get("/nutzer/neu", response_class=HTMLResponse)
    def nutzer_neu_form(request: Request):
        n = web.nutzer(request, "verwaltung.nutzer")
        techniker = con.execute("SELECT id FROM rolle WHERE kennung = 'techniker'").fetchone()
        return nutzer_seite(request, n, None, [techniker["id"]] if techniker else [])

    @r.post("/nutzer/neu")
    def nutzer_neu(request: Request, name: str = Form(""), email: str = Form(""), rollen: list[str] = Form([]),
                   kuerzel: str = Form(""), personalnummer: str = Form(""), csrf_token: str = Form("")):
        n = web.nutzer(request, "verwaltung.nutzer")
        web.csrf(request, csrf_token)
        u = {"name": name, "email": email, "kuerzel": kuerzel, "personalnummer": personalnummer}
        fehler = _nutzer_pruefen(con, u) or _rollen_pruefen(con, request.state.rechte, n["id"], set(), set(rollen))
        if fehler:
            return nutzer_seite(request, n, u, rollen, fehler=fehler, status=400)
        nid = auth.nutzer_anlegen(con, name, email, rollen, n["id"], kuerzel, personalnummer.strip() or None)
        return einladung_seite(request, n, u, auth.einladung_erzeugen(con, nid, n["id"]))

    @r.get("/nutzer/{nid}", response_class=HTMLResponse)
    def nutzer_form(request: Request, nid: str, gespeichert: int = 0):
        n = web.nutzer(request, "verwaltung.nutzer")
        u = ziel_nutzer(request, nid)
        return nutzer_seite(request, n, u, rechte.rollen_von_nutzer(con, nid), gespeichert=gespeichert)

    @r.post("/nutzer/{nid}")
    def nutzer_speichern(request: Request, nid: str, name: str = Form(""), rollen: list[str] = Form([]),
                         kuerzel: str = Form(""), personalnummer: str = Form(""), aktiv: str = Form(""),
                         csrf_token: str = Form("")):
        n = web.nutzer(request, "verwaltung.nutzer")
        web.csrf(request, csrf_token)
        alt = ziel_nutzer(request, nid)
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

    @r.post("/nutzer/{nid}/einladung")
    def nutzer_einladung(request: Request, nid: str, csrf_token: str = Form("")):
        n = web.nutzer(request, "verwaltung.nutzer")
        web.csrf(request, csrf_token)
        u = ziel_nutzer(request, nid)
        return einladung_seite(request, n, u, auth.einladung_erzeugen(con, nid, n["id"]))

    # ---------- Rollen und Rechte ----------
    def rolle_laden(rid):
        x = con.execute("SELECT * FROM rolle WHERE id = ? AND geloescht = 0", (rid,)).fetchone()
        if x is None:
            raise Weiterleitung("/verwaltung/rollen")
        return dict(x)

    def rolle_seite(request, n, x, gewaehlt, status=200, **werte):
        anzahl = con.execute("SELECT COUNT(*) FROM nutzer_rolle WHERE rolle_id = ?", (x["id"],)).fetchone()[0] \
            if x and x.get("id") else 0
        return web.seite(request, "rolle_form.html", n, r=x, gewaehlt=set(gewaehlt), anzahl=anzahl,
                         fest=bool(x and x.get("kennung") == rechte.ADMIN), status=status, **werte)

    @r.get("/rollen", response_class=HTMLResponse)
    def rollen_liste(request: Request):
        n = web.nutzer(request, "verwaltung.rollen")
        liste = rechte.rollen(con)
        matrix = {x["id"]: rechte.rechte_von_rolle(con, x["id"]) for x in liste}
        return web.seite(request, "rollen_liste.html", n, liste=liste, matrix=matrix)

    @r.get("/rollen/neu", response_class=HTMLResponse)
    def rolle_neu_form(request: Request):
        return rolle_seite(request, web.nutzer(request, "verwaltung.rollen"), None, [])

    @r.post("/rollen/neu")
    def rolle_neu(request: Request, name: str = Form(""), beschreibung: str = Form(""),
                  rechte_liste: list[str] = Form([], alias="rechte"), csrf_token: str = Form("")):
        n = web.nutzer(request, "verwaltung.rollen")
        web.csrf(request, csrf_token)
        x = {"name": name, "beschreibung": beschreibung}
        fehler = _rolle_pruefen(con, x, set(rechte_liste), request.state.rechte)
        if fehler:
            return rolle_seite(request, n, x, rechte_liste, fehler=fehler, status=400)
        rid = rechte.rolle_anlegen(con, name, beschreibung, rechte_liste, n["id"])
        return RedirectResponse(f"/verwaltung/rollen/{rid}?gespeichert=1", status_code=303)

    @r.get("/rollen/{rid}", response_class=HTMLResponse)
    def rolle_form(request: Request, rid: str, gespeichert: int = 0):
        n = web.nutzer(request, "verwaltung.rollen")
        return rolle_seite(request, n, rolle_laden(rid), rechte.rechte_von_rolle(con, rid), gespeichert=gespeichert)

    @r.post("/rollen/{rid}")
    def rolle_speichern(request: Request, rid: str, name: str = Form(""), beschreibung: str = Form(""),
                        rechte_liste: list[str] = Form([], alias="rechte"), csrf_token: str = Form("")):
        n = web.nutzer(request, "verwaltung.rollen")
        web.csrf(request, csrf_token)
        alt = rolle_laden(rid)
        if alt["kennung"] == rechte.ADMIN:
            return rolle_seite(request, n, alt, rechte.rechte_von_rolle(con, rid), status=400,
                               fehler="Die Rolle Administration ist fest und kann nicht geändert werden.")
        x = {**alt, "name": name, "beschreibung": beschreibung}
        # nur Rechte vergeben oder entziehen, die man selbst hat
        fehler = _rolle_pruefen(con, x, set(rechte_liste) ^ rechte.rechte_von_rolle(con, rid),
                                request.state.rechte, rid)
        if fehler:
            return rolle_seite(request, n, x, rechte_liste, fehler=fehler, status=400)
        with db.transaktion(con):
            db.aendern(con, "rolle", rid, {"name": name.strip(), "beschreibung": beschreibung.strip()}, n["id"])
            rechte.rolle_rechte_setzen(con, rid, rechte_liste, n["id"])
        return RedirectResponse(f"/verwaltung/rollen/{rid}?gespeichert=1", status_code=303)

    @r.post("/rollen/{rid}/loeschen")
    def rolle_loeschen(request: Request, rid: str, csrf_token: str = Form("")):
        n = web.nutzer(request, "verwaltung.rollen")
        web.csrf(request, csrf_token)
        x = rolle_laden(rid)
        fehler = None
        if x["kennung"]:
            fehler = "Standardrollen können nicht gelöscht werden."
        elif con.execute("SELECT 1 FROM nutzer_rolle WHERE rolle_id = ?", (rid,)).fetchone():
            fehler = "Die Rolle ist noch Nutzern zugeordnet. Bitte zuerst dort entfernen."
        elif not rechte.rechte_von_rolle(con, rid) <= request.state.rechte:
            fehler = "Diese Rolle hat Rechte, die Sie selbst nicht haben."
        if fehler:
            return rolle_seite(request, n, x, rechte.rechte_von_rolle(con, rid), fehler=fehler, status=400)
        db.aendern(con, "rolle", rid, {"geloescht": 1}, n["id"])
        return RedirectResponse("/verwaltung/rollen", status_code=303)

    # ---------- Änderungsprotokoll ----------
    @r.get("/protokoll", response_class=HTMLResponse)
    def protokoll_liste(request: Request):
        n = web.nutzer(request, "verwaltung.protokoll")
        zeilen = con.execute("SELECT p.*, n.name AS nutzer_name FROM aenderungsprotokoll p "
                             "LEFT JOIN nutzer n ON n.id = p.nutzer_id ORDER BY p.id DESC LIMIT 300").fetchall()
        return web.seite(request, "protokoll.html", n, zeilen=zeilen)

    return r


def _nutzer_pruefen(con, u, eigene_id=None):
    if not u["name"].strip():
        return "Name ist Pflicht."
    if "@" not in u["email"]:
        return "Bitte eine gültige E-Mail-Adresse angeben."
    if con.execute("SELECT 1 FROM nutzer WHERE email = ? AND id != ?",
                   (u["email"].strip().lower(), eigene_id or "")).fetchone():
        return "Diese E-Mail-Adresse ist schon vergeben."
    pn = (u.get("personalnummer") or "").strip()
    if pn and con.execute("SELECT 1 FROM nutzer WHERE personalnummer = ? AND id != ?",
                          (pn, eigene_id or "")).fetchone():
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
    if not neu <= {x["id"] for x in rechte.rollen(con)}:
        return "Unbekannte Rolle."
    if any(not _darf_rolle_vergeben(con, meine_rechte, mein_id, rid) for rid in alt ^ neu):
        return "Sie können nur Rollen vergeben oder entziehen, deren Rechte Sie selbst haben."
    return None


def _rolle_pruefen(con, x, geaenderte_rechte, meine_rechte, eigene_id=None):
    if not x["name"].strip():
        return "Name ist Pflicht."
    if con.execute("SELECT 1 FROM rolle WHERE name = ? COLLATE NOCASE AND geloescht = 0 AND id != ?",
                   (x["name"].strip(), eigene_id or "")).fetchone():
        return "Eine Rolle mit diesem Namen gibt es schon."
    if not geaenderte_rechte <= set(rechte.RECHTE):
        return "Unbekanntes Recht."
    if not geaenderte_rechte <= meine_rechte:
        return "Sie können nur Rechte vergeben oder entziehen, die Sie selbst haben."
    return None
