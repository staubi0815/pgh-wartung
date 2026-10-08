"""Befehle für den Server:  python -m wartung <befehl>

  migrieren                          Datenbank anlegen/aktualisieren
  admin-einladen <name> <email>      Admin anlegen (falls neu) und Einmal-Link zum Passwort-Setzen ausgeben
  starten [--port 8000]              Webserver starten (für systemd)
"""
import sys

from . import auth, db


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    befehl, rest = argv[0], argv[1:]
    if befehl == "starten":
        import uvicorn
        from .app import erzeuge_app
        port = int(rest[rest.index("--port") + 1]) if "--port" in rest else 8000
        uvicorn.run(erzeuge_app(), host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                    server_header=False)
        return 0
    con = db.verbinden(db.daten_ordner() / "wartung.db")
    neu = db.migrieren(con)
    if befehl == "migrieren":
        print("Migrationen eingespielt:", ", ".join(neu) or "keine (aktuell)")
        return 0
    if befehl == "admin-einladen" and len(rest) == 2:
        name, email = rest
        n = con.execute("SELECT id FROM nutzer WHERE email = ?", (email.lower(),)).fetchone()
        nid = n["id"] if n else auth.nutzer_anlegen(con, name, email, "admin", None)
        code = auth.einladung_erzeugen(con, nid, None)
        print(f"Einmal-Link (48 h gültig): /einrichten?code={code}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
