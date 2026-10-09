"""Seiten: Excel-Import (Verwaltung → Excel-Import). Recht: import.

Ablauf: Datei hochladen → Vorschau (Probelauf) → Übernehmen. Die Datei liegt bis dahin im geschützten Datenordner
(Unterordner „import“, nur für den Dienstbenutzer lesbar) unter einem Zufallsnamen, der nur in der Sitzung des
Hochladenden steht. Nach dem Übernehmen oder spätestens nach einem Tag wird sie gelöscht.
"""
import io
import os
import secrets
import time

import openpyxl
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from .. import anlagen, anlagenart, excel_import, kunden
from .basis import Weiterleitung

RECHT = "import"
AUFBEWAHRUNG_SEKUNDEN = 24 * 3600


def router(web):
    r = APIRouter(prefix="/verwaltung/import")
    con = web.con
    ordner = web.daten_ordner / "import"

    def anlagen_auswahl():
        return [(a["id"], f"{a['nummer']} – {a['adr_strasse']}, {a['adr_ort']} ({a['kunde_name']})")
                for a in anlagen.liste(con)]

    def startseite(request, n, fehler="", werte=None, status=200):
        return web.seite(request, "import_start.html", n, arten=[excel_import.ARTEN[a][0] for a in excel_import.REIHENFOLGE],
                         kundenarten=kunden.KUNDENARTEN, anlagen_auswahl=anlagen_auswahl(),
                         anlagenarten=[(a.schluessel, a.name) for a in anlagenart.alle().values()],
                         werte=werte or {}, fehler=fehler, status=status)

    def aufraeumen():
        """Liegengebliebene Dateien (Vorschau ohne Übernehmen) nach einem Tag löschen."""
        if ordner.exists():
            grenze = time.time() - AUFBEWAHRUNG_SEKUNDEN
            for datei in ordner.glob("*.xlsx"):
                if datei.stat().st_mtime < grenze:
                    datei.unlink(missing_ok=True)

    def optionen_aus(werte):
        """Optionen aus dem Formular prüfen und für den Import aufbereiten."""
        optionen = {}
        if werte.get("art") == "kunden":
            optionen["kundenart"] = werte.get("kundenart") if werte.get("kundenart") in dict(kunden.KUNDENARTEN) \
                else "hausverwaltung"
        if werte.get("art") == "typen":
            optionen["anlagenart"] = werte.get("anlagenart") if werte.get("anlagenart") in anlagenart.alle() \
                else "rauchwarnmelder"
        if werte.get("art") == "komponenten":
            anlage = anlagen.holen(con, werte.get("anlage_id", ""))
            if anlage is not None:
                optionen["anlage"] = anlage
        return optionen

    @r.get("", response_class=HTMLResponse)
    def start(request: Request, art: str = "", anlage: str = ""):
        n = web.nutzer(request, RECHT)
        return startseite(request, n, werte={"art": art or "kunden", "anlage_id": anlage})

    @r.post("/pruefen", response_class=HTMLResponse)
    async def pruefen(request: Request):
        n = web.nutzer(request, RECHT)
        form = await web.formular(request)
        werte = {k: form.get(k) for k in ("art", "kundenart", "anlagenart", "anlage_id")}
        datei = form.get("datei")
        if datei is None or not getattr(datei, "filename", ""):
            return startseite(request, n, "Bitte eine Excel-Datei auswählen.", werte, 400)
        inhalt = await datei.read(excel_import.MAX_BYTES + 1)
        try:
            ergebnis = excel_import.pruefen(con, werte["art"], inhalt, n["id"], optionen_aus(werte))
        except excel_import.DateiFehler as e:
            return startseite(request, n, str(e), werte, 400)
        aufraeumen()
        ordner.mkdir(mode=0o700, exist_ok=True)
        merkmal = secrets.token_urlsafe(18)
        ziel = ordner / f"{merkmal}.xlsx"
        with open(os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
            f.write(inhalt)
        request.session["import"] = {"merkmal": merkmal, "dateiname": os.path.basename(datei.filename)[:120],
                                     **{k: v for k, v in werte.items() if v}}
        return web.seite(request, "import_vorschau.html", n, ergebnis=ergebnis, merkmal=merkmal,
                         importart=excel_import.ARTEN[werte["art"]][0], dateiname=request.session["import"]["dateiname"],
                         anlage=optionen_aus(werte).get("anlage"))

    @r.post("/uebernehmen", response_class=HTMLResponse)
    async def uebernehmen(request: Request):
        n = web.nutzer(request, RECHT)
        form = await web.formular(request)
        sitzung = request.session.get("import") or {}
        merkmal = sitzung.get("merkmal", "")
        if not merkmal or not secrets.compare_digest(merkmal, form.get("merkmal", "")):
            raise Weiterleitung("/verwaltung/import?hinweis=abgelaufen")
        datei = ordner / f"{merkmal}.xlsx"
        if not datei.exists():
            raise Weiterleitung("/verwaltung/import?hinweis=abgelaufen")
        try:
            ergebnis = excel_import.uebernehmen(con, sitzung["art"], datei.read_bytes(), n["id"], optionen_aus(sitzung),
                                                sitzung.get("dateiname", ""))
        except excel_import.DateiFehler as e:
            return startseite(request, n, str(e), sitzung, 400)
        if ergebnis.gespeichert:
            datei.unlink(missing_ok=True)
            request.session.pop("import", None)
        return web.seite(request, "import_vorschau.html", n, ergebnis=ergebnis, merkmal=merkmal,
                         importart=excel_import.ARTEN[sitzung["art"]][0], dateiname=sitzung.get("dateiname", ""),
                         anlage=optionen_aus(sitzung).get("anlage"))

    @r.get("/vorlage/{art}.xlsx")
    def vorlage(request: Request, art: str):
        """Leere Vorlage mit den Spalten im Foxtag-Format (Pflichtspalten mit *)."""
        web.nutzer(request, RECHT)
        if art not in excel_import.ARTEN:
            raise Weiterleitung("/verwaltung/import")
        importart = excel_import.ARTEN[art][0]
        mappe = openpyxl.Workbook()
        mappe.active.title = importart.titel[:31]
        mappe.active.append(importart.kopfzeile())
        puffer = io.BytesIO()
        mappe.save(puffer)
        return Response(puffer.getvalue(), headers={"Content-Disposition": f'attachment; filename="Vorlage_{art}.xlsx"'},
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    return r
