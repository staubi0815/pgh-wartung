"""Befehle für den Server:  python -m wartung <befehl>

  migrieren                          Datenbank anlegen/aktualisieren, Fälligkeiten neu berechnen
  admin-einladen <name> <email>      Admin anlegen (vorhandenes Konto: Rolle Administration + aktiv)
                                     und Einmal-Link zum Passwort-Setzen ausgeben
  starten [--port 8000]              Webserver starten (für systemd)
"""
import sys

from . import auth, db, faelligkeit, rechte


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
        # Regeln stehen in der Anlagenart-Konfiguration; nach jedem Einspielen alle Fälligkeiten nachführen
        with db.transaktion(con):
            print("Fälligkeiten neu berechnet:", faelligkeit.alle_berechnen(con))
        return 0
    if befehl == "admin-einladen" and len(rest) == 2:
        name, email = rest
        admin = [rechte.admin_rolle_id(con)]
        n = con.execute("SELECT id FROM nutzer WHERE email = ?", (email.lower(),)).fetchone()
        if n:  # Notfallzugang: vorhandenes Konto bekommt (wieder) die Rolle Administration und wird aktiviert
            nid = n["id"]
            rechte.nutzer_rollen_setzen(con, nid, rechte.rollen_von_nutzer(con, nid) | set(admin), None)
            db.aendern(con, "nutzer", nid, {"aktiv": 1, "geloescht": 0}, None)
        else:
            nid = auth.nutzer_anlegen(con, name, email, admin, None)
        code = auth.einladung_erzeugen(con, nid, None)
        print(f"Einmal-Link (48 h gültig): /einrichten?code={code}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
