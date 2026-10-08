"""Anmeldung: Passwort-Hash (Argon2), Einladungslinks, Sperre nach Fehlversuchen, CSRF-Schutz."""
import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from . import rechte
from .db import TZ, jetzt, neue_id, protokoll, transaktion

_ph = PasswordHasher()
MAX_FEHLVERSUCHE = 5
SPERRE_MINUTEN = 15
EINLADUNG_STUNDEN = 48
MIN_PASSWORT = 12


def hash_passwort(pw):
    return _ph.hash(pw)


def passwort_regeln(pw):
    """Gibt eine Fehlermeldung zurück oder None."""
    if len(pw) < MIN_PASSWORT:
        return f"Das Passwort muss mindestens {MIN_PASSWORT} Zeichen lang sein."
    if pw.isalpha() or pw.isdigit():
        return "Bitte Buchstaben und Ziffern oder Sonderzeichen mischen."
    return None


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def gesperrt(con, email):
    seit = (datetime.now(TZ) - timedelta(minutes=SPERRE_MINUTEN)).isoformat(timespec="seconds")
    n = con.execute("SELECT COUNT(*) FROM anmeldeversuch WHERE email = ? AND zeit >= ? AND erfolg = 0",
                    (email, seit)).fetchone()[0]
    return n >= MAX_FEHLVERSUCHE


def anmelden(con, email, pw):
    """Prüft Zugangsdaten. Rückgabe: (nutzer-Zeile oder None, Fehlermeldung oder None)."""
    email = (email or "").strip().lower()
    if gesperrt(con, email):
        return None, f"Zu viele Fehlversuche. Bitte {SPERRE_MINUTEN} Minuten warten."
    n = con.execute("SELECT * FROM nutzer WHERE email = ? AND geloescht = 0", (email,)).fetchone()
    ok = False
    if n is not None and n["aktiv"] and n["passwort_hash"]:
        try:
            ok = _ph.verify(n["passwort_hash"], pw)
        except (VerifyMismatchError, InvalidHashError):
            ok = False
    else:
        _ph.hash(pw or "x")  # gleiche Rechenzeit, damit man unbekannte Adressen nicht erkennt
    con.execute("INSERT INTO anmeldeversuch (email, zeit, erfolg) VALUES (?, ?, ?)", (email, jetzt(), int(ok)))
    if not ok:
        return None, "Anmeldung fehlgeschlagen."
    if _ph.check_needs_rehash(n["passwort_hash"]):
        con.execute("UPDATE nutzer SET passwort_hash = ? WHERE id = ?", (_ph.hash(pw), n["id"]))
    protokoll(con, n["id"], "nutzer", n["id"], "anmelden")
    return n, None


def einladung_erzeugen(con, nutzer_id, von):
    """Erzeugt einen Einmal-Link-Code (48 h gültig) zum Setzen des Passworts. Nur der Hash wird gespeichert."""
    code = secrets.token_urlsafe(24)
    bis = (datetime.now(TZ) + timedelta(hours=EINLADUNG_STUNDEN)).isoformat(timespec="seconds")
    con.execute("UPDATE nutzer SET einladung_hash = ?, einladung_bis = ? WHERE id = ?", (_sha(code), bis, nutzer_id))
    protokoll(con, von, "nutzer", nutzer_id, "einladung")
    return code


def einladung_pruefen(con, code):
    if not code:
        return None
    n = con.execute("SELECT * FROM nutzer WHERE einladung_hash = ? AND geloescht = 0", (_sha(code),)).fetchone()
    if n is None or not n["einladung_bis"] or n["einladung_bis"] < jetzt():
        return None
    return n


def passwort_setzen(con, nutzer_id, pw, von):
    pw_hash = _ph.hash(pw)  # rechenintensiv, daher vor der Transaktion
    with transaktion(con):
        con.execute("UPDATE nutzer SET passwort_hash = ?, einladung_hash = NULL, einladung_bis = NULL, "
                    "sitzung_zaehler = sitzung_zaehler + 1, geaendert_am = ?, geaendert_von = ?, version = version + 1 "
                    "WHERE id = ?", (pw_hash, jetzt(), von, nutzer_id))
        protokoll(con, von, "nutzer", nutzer_id, "passwort_gesetzt")


def nutzer_anlegen(con, name, email, rollen_ids, von, kuerzel="", personalnummer=None):
    nid = neue_id()
    with transaktion(con):
        con.execute("INSERT INTO nutzer (id, name, kuerzel, personalnummer, email, erstellt_am, erstellt_von) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (nid, name.strip(), kuerzel.strip(), personalnummer or None, email.strip().lower(), jetzt(), von))
        protokoll(con, von, "nutzer", nid, "anlegen", "email", None, email.strip().lower())
        rechte.nutzer_rollen_setzen(con, nid, rollen_ids, von)
    return nid


def csrf_token(session):
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def csrf_ok(session, wert):
    return bool(wert) and secrets.compare_digest(session.get("csrf", ""), wert)
