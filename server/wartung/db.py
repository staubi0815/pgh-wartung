"""Datenbank (SQLite): Verbindung, Migrationen, Änderungsprotokoll."""
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
MIGRATIONEN = Path(__file__).parent / "migrationen"


def jetzt():
    return datetime.now(TZ).isoformat(timespec="seconds")


def neue_id():
    return str(uuid.uuid4())


def daten_ordner():
    return Path(os.environ.get("WARTUNG_DATEN", "/var/lib/pgh-wartung"))


def verbinden(pfad=None):
    pfad = pfad or daten_ordner() / "wartung.db"
    con = sqlite3.connect(pfad, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


class ThreadVerbindung:
    """Eine eigene SQLite-Verbindung je Thread, nach außen wie eine Verbindung benutzbar.

    Der Webserver bearbeitet Anfragen parallel in mehreren Threads. Mit einer gemeinsamen Verbindung würden sich
    Transaktionen gleichzeitiger Anfragen vermischen; so hat jede Anfrage ihre eigene, SQLite regelt das Sperren.
    """

    def __init__(self, pfad):
        self._pfad = pfad
        self._lokal = threading.local()

    def _con(self):
        con = getattr(self._lokal, "con", None)
        if con is None:
            con = self._lokal.con = verbinden(self._pfad)
        return con

    def __getattr__(self, name):
        return getattr(self._con(), name)


@contextmanager
def transaktion(con):
    """Alles oder nichts. Verschachtelbar (innen SAVEPOINT), damit Funktionen sich gegenseitig aufrufen können.

    Außen BEGIN IMMEDIATE: die Schreibsperre wird gleich zu Beginn geholt, so sehen Lesen-dann-Schreiben-Abläufe
    (z. B. alter Wert fürs Protokoll) garantiert den aktuellen Stand.
    """
    if not con.in_transaction:
        con.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            con.execute("ROLLBACK")
            raise
        con.execute("COMMIT")
        return
    name = f"sp_{uuid.uuid4().hex[:12]}"
    con.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        con.execute(f"ROLLBACK TO {name}")
        con.execute(f"RELEASE {name}")
        raise
    con.execute(f"RELEASE {name}")


def migrieren(con):
    """Spielt fehlende Migrationen (NNN_name.sql) der Reihe nach ein. Gibt die Namen der neuen zurück."""
    con.execute("CREATE TABLE IF NOT EXISTS schema_version (name TEXT PRIMARY KEY, am TEXT NOT NULL)")
    vorhanden = {r["name"] for r in con.execute("SELECT name FROM schema_version")}
    neu = []
    for datei in sorted(MIGRATIONEN.glob("[0-9][0-9][0-9]_*.sql")):
        if datei.name in vorhanden:
            continue
        text = datei.read_text(encoding="utf-8")
        # Migrationen, die eine Tabelle neu aufbauen, tragen in der ersten Zeile diese Marke (Vorgehen laut SQLite-Doku)
        ohne_fremdschluessel = text.startswith("-- fremdschluessel: aus")
        if ohne_fremdschluessel:
            con.execute("PRAGMA foreign_keys = OFF")
        con.execute("BEGIN")
        try:
            for befehl in _befehle(text):
                con.execute(befehl)
            if ohne_fremdschluessel and con.execute("PRAGMA foreign_key_check").fetchone():
                raise sqlite3.IntegrityError(f"Migration {datei.name}: Fremdschlüssel verletzt")
            con.execute("INSERT INTO schema_version VALUES (?, ?)", (datei.name, jetzt()))
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            if ohne_fremdschluessel:
                con.execute("PRAGMA foreign_keys = ON")
        neu.append(datei.name)
    return neu


def _befehle(sql):
    """Zerlegt ein SQL-Skript in einzelne Befehle (Trigger mit BEGIN … END bleiben zusammen)."""
    teile, puffer = [], ""
    for zeile in sql.splitlines():
        if zeile.strip().startswith("--"):
            continue
        puffer += zeile + "\n"
        if sqlite3.complete_statement(puffer):
            if puffer.strip():
                teile.append(puffer.strip())
            puffer = ""
    if puffer.strip():
        teile.append(puffer.strip())
    return teile


def protokoll(con, nutzer_id, tabelle, datensatz, aktion, feld=None, alt=None, neu=None, geraet_id=None):
    con.execute(
        "INSERT INTO aenderungsprotokoll (zeit, nutzer_id, geraet_id, tabelle, datensatz, aktion, feld, alt, neu) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (jetzt(), nutzer_id, geraet_id, tabelle, str(datensatz), aktion, feld,
         None if alt is None else str(alt), None if neu is None else str(neu)))


GEHEIME_FELDER = ("passwort_hash", "einladung_hash")
_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def _namen_pruefen(*namen):
    """Tabellen- und Spaltennamen werden in SQL eingesetzt – nur einfache Bezeichner zulassen."""
    for n in namen:
        if not _NAME.match(n):
            raise ValueError(f"ungültiger Bezeichner: {n!r}")


def anlegen(con, tabelle, werte, nutzer_id, geraet_id=None):
    """Legt einen Datensatz an (id wird erzeugt, falls nicht angegeben) und protokolliert alle gefüllten Felder.
    Gibt die id zurück."""
    werte = dict(werte)
    datensatz_id = werte.pop("id", None) or neue_id()
    _namen_pruefen(tabelle, *werte)
    spalten = ["id", *werte, "erstellt_am", "erstellt_von", "erstellt_auf"]
    with transaktion(con):
        con.execute(f"INSERT INTO {tabelle} ({', '.join(spalten)}) VALUES ({', '.join('?' * len(spalten))})",
                    (datensatz_id, *werte.values(), jetzt(), nutzer_id, geraet_id))
        protokoll(con, nutzer_id, tabelle, datensatz_id, "anlegen", geraet_id=geraet_id)
        for k, v in werte.items():
            if v not in (None, ""):
                protokoll(con, nutzer_id, tabelle, datensatz_id, "anlegen", k, None,
                          "***" if k in GEHEIME_FELDER else v, geraet_id)
    return datensatz_id


def aendern(con, tabelle, datensatz_id, werte, nutzer_id, schluessel="id"):
    """Ändert Felder eines Datensatzes und protokolliert jede tatsächliche Änderung. Gibt Anzahl geänderter Felder zurück."""
    _namen_pruefen(tabelle, schluessel, *werte)
    with transaktion(con):
        alt = con.execute(f"SELECT * FROM {tabelle} WHERE {schluessel} = ?", (datensatz_id,)).fetchone()
        if alt is None:
            raise KeyError(f"{tabelle} {datensatz_id} nicht gefunden")
        geaendert = {k: v for k, v in werte.items() if alt[k] != v}
        if not geaendert:
            return 0
        spalten = ", ".join(f"{k} = ?" for k in geaendert)
        con.execute(f"UPDATE {tabelle} SET {spalten}, geaendert_am = ?, geaendert_von = ?, version = version + 1 "
                    f"WHERE {schluessel} = ?", (*geaendert.values(), jetzt(), nutzer_id, datensatz_id))
        for k, v in geaendert.items():
            geheim = k in GEHEIME_FELDER
            protokoll(con, nutzer_id, tabelle, datensatz_id, "aendern", k,
                      "***" if geheim else alt[k], "***" if geheim else v)
    return len(geaendert)
