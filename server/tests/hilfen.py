"""Gemeinsame Hilfen für die Tests."""
import re

from wartung import auth

PW = "Sicher-Test-2026!"


def csrf_aus(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def anmelden(c, email="admin@example.org", pw=PW):
    t = csrf_aus(c.get("/anmelden").text)
    return c.post("/anmelden", data={"email": email, "passwort": pw, "csrf_token": t}, follow_redirects=False)


def rolle_id(con, kennung):
    return con.execute("SELECT id FROM rolle WHERE kennung = ?", (kennung,)).fetchone()["id"]


def nutzer_mit_passwort(con, name, email, rollen_ids):
    nid = auth.nutzer_anlegen(con, name, email, rollen_ids, None)
    auth.passwort_setzen(con, nid, PW, None)
    return nid
