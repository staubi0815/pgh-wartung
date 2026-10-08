"""Gemeinsame Bausteine aller Webseiten: angemeldeter Nutzer und Rechte, Seitenausgabe, CSRF-Prüfung."""
from .. import auth, rechte


class Weiterleitung(Exception):
    """Bricht die Bearbeitung ab und leitet um (z. B. nicht angemeldet, keine Berechtigung)."""

    def __init__(self, ziel):
        self.ziel = ziel


class Web:
    """Wird einmal je Anwendung erzeugt und an alle Seitenbereiche (Router) übergeben."""

    def __init__(self, con, vorlagen):
        self.con = con
        self.vorlagen = vorlagen

    def nutzer(self, request, recht=None):
        """Angemeldeter Nutzer mit Webzugang (und ggf. dem verlangten Recht), sonst Weiterleitung."""
        s = request.session
        n = self.con.execute("SELECT * FROM nutzer WHERE id = ? AND aktiv = 1 AND geloescht = 0",
                             (s.get("nutzer_id"),)).fetchone() if s.get("nutzer_id") else None
        if n is None or n["sitzung_zaehler"] != s.get("zaehler"):
            s.clear()
            raise Weiterleitung("/anmelden")
        meine = rechte.rechte_von_nutzer(self.con, n["id"])
        if "web.zugang" not in meine:
            s.clear()
            raise Weiterleitung("/anmelden?hinweis=nur_app")
        if recht and recht not in meine:
            raise Weiterleitung("/?hinweis=keine_berechtigung")
        request.state.rechte = meine
        return n

    def seite(self, request, name, n=None, status=200, **werte):
        firma = self.con.execute("SELECT name FROM firma WHERE id = 1").fetchone()
        return self.vorlagen.TemplateResponse(request, name, {
            "ich": n, "rechte": getattr(request.state, "rechte", set()), "csrf": auth.csrf_token(request.session),
            "firmenname": firma["name"], **werte}, status_code=status)

    def csrf(self, request, token):
        if not auth.csrf_ok(request.session, token):
            raise Weiterleitung("/?hinweis=sitzung_abgelaufen")
