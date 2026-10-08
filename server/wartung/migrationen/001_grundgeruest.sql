-- 001: Firma, Nutzer, Anmeldeversuche, Änderungsprotokoll
-- Gemeinsame Spalten (siehe docs/03-datenmodell.md): id (UUID), erstellt_am/-von, geaendert_am/-von, version, geloescht

CREATE TABLE firma (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    name            TEXT NOT NULL DEFAULT 'PGH-Brandschutz',
    inhaber         TEXT NOT NULL DEFAULT '',
    strasse         TEXT NOT NULL DEFAULT '',
    plz             TEXT NOT NULL DEFAULT '',
    ort             TEXT NOT NULL DEFAULT '',
    telefon         TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    praefix_kunde   TEXT NOT NULL DEFAULT 'K',
    praefix_objekt  TEXT NOT NULL DEFAULT 'O-',
    praefix_anlage  TEXT NOT NULL DEFAULT 'ANL-',
    praefix_auftrag TEXT NOT NULL DEFAULT 'A-',
    berichtsfusszeile TEXT NOT NULL DEFAULT '',
    geaendert_am    TEXT,
    geaendert_von   TEXT,
    version         INTEGER NOT NULL DEFAULT 1
);
INSERT INTO firma (id) VALUES (1);

CREATE TABLE nutzer (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    kuerzel             TEXT NOT NULL DEFAULT '',
    personalnummer      TEXT UNIQUE,
    email               TEXT NOT NULL UNIQUE COLLATE NOCASE,
    rolle               TEXT NOT NULL CHECK (rolle IN ('admin', 'buero', 'techniker')),
    aktiv               INTEGER NOT NULL DEFAULT 1,
    qualifikation       TEXT NOT NULL DEFAULT '',
    passwort_hash       TEXT,
    sitzung_zaehler     INTEGER NOT NULL DEFAULT 0,   -- erhöhen = alle Sitzungen ungültig
    einladung_hash      TEXT,                          -- SHA-256 des Einmal-Links
    einladung_bis       TEXT,
    erstellt_am         TEXT NOT NULL,
    erstellt_von        TEXT,
    geaendert_am        TEXT,
    geaendert_von       TEXT,
    version             INTEGER NOT NULL DEFAULT 1,
    geloescht           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE anmeldeversuch (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    email   TEXT NOT NULL COLLATE NOCASE,
    zeit    TEXT NOT NULL,
    erfolg  INTEGER NOT NULL
);
CREATE INDEX anmeldeversuch_email_zeit ON anmeldeversuch (email, zeit);

-- nur anhängen: wer hat wann was geändert
CREATE TABLE aenderungsprotokoll (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zeit        TEXT NOT NULL,
    nutzer_id   TEXT,
    geraet_id   TEXT,
    tabelle     TEXT NOT NULL,
    datensatz   TEXT NOT NULL,
    aktion      TEXT NOT NULL,          -- anlegen | aendern | loeschen | anmelden | ...
    feld        TEXT,
    alt         TEXT,
    neu         TEXT
);
CREATE TRIGGER aenderungsprotokoll_nur_anhaengen_u BEFORE UPDATE ON aenderungsprotokoll
BEGIN SELECT RAISE(ABORT, 'Änderungsprotokoll darf nicht geändert werden'); END;
CREATE TRIGGER aenderungsprotokoll_nur_anhaengen_d BEFORE DELETE ON aenderungsprotokoll
BEGIN SELECT RAISE(ABORT, 'Änderungsprotokoll darf nicht gelöscht werden'); END;
