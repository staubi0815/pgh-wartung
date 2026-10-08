-- 003: Stammdaten Kunde, Kontakt, Objekt, Anlage, Wohnung (gruppe), Komponententyp, Komponente (Melder).
-- Siehe docs/03-datenmodell.md Abschnitt 1 und 6, docs/07 Abschnitt 5.
--
-- Gemeinsame Spalten: id (UUID), erstellt_am/-von/-auf (Gerät), geaendert_am/-von, version, geloescht (nur Kennzeichen,
-- nichts wird physisch gelöscht) und abgleich_nr: fortlaufende Nummer, die der Server bei jedem Anlegen und Ändern
-- vergibt (Trigger unten). Geräte holen später „alles nach abgleich_nr X“. Da SQLite immer nur einen Schreiber
-- zulässt, steigt die Nummer in der Reihenfolge, in der Änderungen festgeschrieben werden.
-- Textfelder sind NOT NULL DEFAULT '' (leer = nicht angegeben); NULL nur, wo Eindeutigkeit gilt oder Verweise fehlen.

CREATE TABLE abgleich_zaehler (
    id  INTEGER PRIMARY KEY CHECK (id = 1),
    nr  INTEGER NOT NULL
);
INSERT INTO abgleich_zaehler (id, nr) VALUES (1, 0);

-- Nummernkreise: nächste freie laufende Nummer; Präfix steht in firma (praefix_kunde usw.)
CREATE TABLE nummernkreis (
    art         TEXT PRIMARY KEY CHECK (art IN ('kunde', 'objekt', 'anlage', 'auftrag')),
    naechste    INTEGER NOT NULL CHECK (naechste > 0),
    stellen     INTEGER NOT NULL DEFAULT 4        -- mit Nullen auffüllen: K0001
);
INSERT INTO nummernkreis (art, naechste, stellen) VALUES
  ('kunde', 1, 4), ('objekt', 1, 4), ('anlage', 1, 4), ('auftrag', 1001, 0);

CREATE TABLE kunde (
    id                  TEXT PRIMARY KEY,
    nummer              TEXT NOT NULL UNIQUE COLLATE NOCASE,   -- K0001; nie wiederverwendet
    art                 TEXT NOT NULL DEFAULT 'hausverwaltung'
                        CHECK (art IN ('hausverwaltung', 'eigentuemer', 'weg', 'vermieter', 'privat', 'sonstig')),
    name                TEXT NOT NULL CHECK (name <> ''),
    zusatz              TEXT NOT NULL DEFAULT '',
    strasse             TEXT NOT NULL DEFAULT '',
    plz                 TEXT NOT NULL DEFAULT '',
    ort                 TEXT NOT NULL DEFAULT '',
    land                TEXT NOT NULL DEFAULT 'DE',
    telefon             TEXT NOT NULL DEFAULT '',
    email               TEXT NOT NULL DEFAULT '',
    rechnungs_email     TEXT NOT NULL DEFAULT '',
    lieferantennummer   TEXT NOT NULL DEFAULT '',          -- unsere Nummer beim Kunden
    notiz_intern        TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE kontakt (
    id          TEXT PRIMARY KEY,
    kunde_id    TEXT REFERENCES kunde (id),               -- optional (z. B. Hausmeister ohne Kundenbezug)
    name        TEXT NOT NULL CHECK (name <> ''),
    firma       TEXT NOT NULL DEFAULT '',
    funktion    TEXT NOT NULL DEFAULT '',                  -- „Hausmeister“, „Verwalter“
    telefon     TEXT NOT NULL DEFAULT '',
    mobil       TEXT NOT NULL DEFAULT '',
    fax         TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL DEFAULT '',
    notiz       TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX kontakt_kunde ON kontakt (kunde_id);

CREATE TABLE objekt (
    id                  TEXT PRIMARY KEY,
    nummer              TEXT NOT NULL UNIQUE COLLATE NOCASE,   -- O-0001
    kunde_id            TEXT NOT NULL REFERENCES kunde (id),
    bezeichnung         TEXT NOT NULL CHECK (bezeichnung <> ''),  -- „Musterstraße 12“
    adresse_wie_kunde   INTEGER NOT NULL DEFAULT 0 CHECK (adresse_wie_kunde IN (0, 1)),
    strasse             TEXT NOT NULL DEFAULT '',
    plz                 TEXT NOT NULL DEFAULT '',
    ort                 TEXT NOT NULL DEFAULT '',
    land                TEXT NOT NULL DEFAULT 'DE',
    breite              REAL,
    laenge              REAL,
    zugangshinweise     TEXT NOT NULL DEFAULT '',
    notiz               TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX objekt_kunde ON objekt (kunde_id);

CREATE TABLE anlage (
    id                          TEXT PRIMARY KEY,
    nummer                      TEXT NOT NULL UNIQUE COLLATE NOCASE,   -- ANL-0001
    objekt_id                   TEXT NOT NULL REFERENCES objekt (id),
    anlagenart                  TEXT NOT NULL,          -- Schlüssel aus konfig/anlagenarten (Prüfung im Programm)
    bezeichnung                 TEXT NOT NULL DEFAULT '',
    hinweise_techniker          TEXT NOT NULL DEFAULT '',
    verfahren                   TEXT NOT NULL DEFAULT 'A' CHECK (verfahren IN ('A', 'B', 'C')),
    passiv                      INTEGER NOT NULL DEFAULT 0 CHECK (passiv IN (0, 1)),
    einzelnachweis_je_wohnung   INTEGER NOT NULL DEFAULT 0 CHECK (einzelnachweis_je_wohnung IN (0, 1)),
    notiz                       TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX anlage_objekt ON anlage (objekt_id);

CREATE TABLE anlage_kontakt (
    id          TEXT PRIMARY KEY,
    anlage_id   TEXT NOT NULL REFERENCES anlage (id),
    kontakt_id  TEXT NOT NULL REFERENCES kontakt (id),
    rolle       TEXT NOT NULL CHECK (rolle IN ('vor_ort', 'berichtsempfaenger', 'terminankuendigung')),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX anlage_kontakt_eindeutig ON anlage_kontakt (anlage_id, kontakt_id, rolle) WHERE geloescht = 0;

-- Wohnung (bei Türen: Geschoss/Bauteil). Bewohnername ist personenbezogen (Löschkonzept beachten).
CREATE TABLE gruppe (
    id                  TEXT PRIMARY KEY,
    anlage_id           TEXT NOT NULL REFERENCES anlage (id),
    nummer              INTEGER NOT NULL CHECK (nummer >= 0),   -- 43 (Foxtag: GRUPPE.NUMMER ist eine Zahl)
    bezeichnung         TEXT NOT NULL DEFAULT '',                -- „1. OG links“
    bewohner            TEXT NOT NULL DEFAULT '',
    bewohner_telefon    TEXT NOT NULL DEFAULT '',
    zugang              TEXT NOT NULL DEFAULT 'frei' CHECK (zugang IN ('frei', 'nur_termin', 'schluessel')),
    notiz               TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX gruppe_nummer ON gruppe (anlage_id, nummer) WHERE geloescht = 0;

CREATE TABLE komponententyp (
    id                  TEXT PRIMARY KEY,
    anlagenart          TEXT NOT NULL,
    hersteller          TEXT NOT NULL DEFAULT '',
    modell              TEXT NOT NULL DEFAULT '',
    bezeichnung         TEXT NOT NULL CHECK (bezeichnung <> ''),   -- Foxtag: TYP.NAME
    kategorie           TEXT NOT NULL DEFAULT 'komponente' CHECK (kategorie IN ('komponente', 'sub_komponente')),
    zulassungsnummer    TEXT NOT NULL DEFAULT '',
    funk                TEXT NOT NULL DEFAULT 'keine' CHECK (funk IN ('keine', 'wmbus', 'lorawan')),
    batterie            TEXT NOT NULL DEFAULT 'fest_10j' CHECK (batterie IN ('fest_10j', 'wechselbar')),
    austausch_jahre     INTEGER CHECK (austausch_jahre IS NULL OR austausch_jahre > 0),  -- leer: Anlagenart
    datenblatt_link     TEXT NOT NULL DEFAULT '',
    aktiv               INTEGER NOT NULL DEFAULT 1 CHECK (aktiv IN (0, 1)),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX komponententyp_name ON komponententyp (anlagenart, bezeichnung COLLATE NOCASE) WHERE geloescht = 0;

-- Melder bzw. Tür. Lebenslauf: lager -> verbaut -> ersetzt | ausgebaut.
CREATE TABLE komponente (
    id                      TEXT PRIMARY KEY,
    anlage_id               TEXT REFERENCES anlage (id),
    gruppe_id               TEXT REFERENCES gruppe (id),
    nummer                  INTEGER CHECK (nummer IS NULL OR nummer > 0),   -- laufend in der Wohnung: 43/1
    sub_nummer              INTEGER NOT NULL DEFAULT 0 CHECK (sub_nummer >= 0),
    eltern_id               TEXT REFERENCES komponente (id),               -- Türen: Teile einer Tür
    komponententyp_id       TEXT NOT NULL REFERENCES komponententyp (id),
    raum                    TEXT NOT NULL DEFAULT '',
    raumart                 TEXT NOT NULL DEFAULT 'sonstiger'
                            CHECK (raumart IN ('schlafraum', 'kinderzimmer', 'flur_rettungsweg', 'sonstiger')),
    seriennummer            TEXT NOT NULL DEFAULT '',
    funk_id                 TEXT,                     -- wM-Bus-Adresse, eindeutig
    barcode                 TEXT,                     -- eigener Aufkleber, eindeutig
    baujahr                 INTEGER CHECK (baujahr IS NULL OR baujahr BETWEEN 1990 AND 2100),
    inbetriebnahme_am       TEXT,                     -- JJJJ-MM-TT
    naechste_pruefung_am    TEXT,                     -- vom Server berechnet
    austausch_faellig_am    TEXT,                     -- vom Server berechnet
    status                  TEXT NOT NULL DEFAULT 'verbaut' CHECK (status IN ('lager', 'verbaut', 'ersetzt', 'ausgebaut')),
    ersetzt_durch_id        TEXT REFERENCES komponente (id),
    notiz                   TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0,
    CHECK (status = 'lager' OR (anlage_id IS NOT NULL AND gruppe_id IS NOT NULL AND nummer IS NOT NULL))
);
CREATE INDEX komponente_anlage ON komponente (anlage_id, gruppe_id);
CREATE UNIQUE INDEX komponente_platz ON komponente (gruppe_id, nummer, sub_nummer)
    WHERE geloescht = 0 AND status = 'verbaut';
CREATE UNIQUE INDEX komponente_funk_id ON komponente (funk_id) WHERE geloescht = 0 AND funk_id IS NOT NULL;
CREATE UNIQUE INDEX komponente_barcode ON komponente (barcode) WHERE geloescht = 0 AND barcode IS NOT NULL;

-- Abgleich-Nummer bei jedem Anlegen und Ändern vergeben (ohne Rekursion: recursive_triggers ist aus)
CREATE TRIGGER kunde_abgleich_neu AFTER INSERT ON kunde BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kunde SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER kunde_abgleich_aenderung AFTER UPDATE ON kunde BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kunde SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER kontakt_abgleich_neu AFTER INSERT ON kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER kontakt_abgleich_aenderung AFTER UPDATE ON kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER objekt_abgleich_neu AFTER INSERT ON objekt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE objekt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER objekt_abgleich_aenderung AFTER UPDATE ON objekt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE objekt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER anlage_abgleich_neu AFTER INSERT ON anlage BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE anlage SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER anlage_abgleich_aenderung AFTER UPDATE ON anlage BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE anlage SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER anlage_kontakt_abgleich_neu AFTER INSERT ON anlage_kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE anlage_kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER anlage_kontakt_abgleich_aenderung AFTER UPDATE ON anlage_kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE anlage_kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER gruppe_abgleich_neu AFTER INSERT ON gruppe BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE gruppe SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER gruppe_abgleich_aenderung AFTER UPDATE ON gruppe BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE gruppe SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER komponententyp_abgleich_neu AFTER INSERT ON komponententyp BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE komponententyp SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER komponententyp_abgleich_aenderung AFTER UPDATE ON komponententyp BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE komponententyp SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER komponente_abgleich_neu AFTER INSERT ON komponente BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE komponente SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER komponente_abgleich_aenderung AFTER UPDATE ON komponente BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE komponente SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;

-- Nachweise dürfen nicht verschwinden: physisches Löschen verbieten (Löschen = geloescht = 1)
CREATE TRIGGER kunde_nicht_loeschen BEFORE DELETE ON kunde BEGIN SELECT RAISE(ABORT, 'Kunden werden nur als gelöscht markiert'); END;
CREATE TRIGGER objekt_nicht_loeschen BEFORE DELETE ON objekt BEGIN SELECT RAISE(ABORT, 'Objekte werden nur als gelöscht markiert'); END;
CREATE TRIGGER anlage_nicht_loeschen BEFORE DELETE ON anlage BEGIN SELECT RAISE(ABORT, 'Anlagen werden nur als gelöscht markiert'); END;
CREATE TRIGGER gruppe_nicht_loeschen BEFORE DELETE ON gruppe BEGIN SELECT RAISE(ABORT, 'Wohnungen werden nur als gelöscht markiert'); END;
CREATE TRIGGER komponente_nicht_loeschen BEFORE DELETE ON komponente BEGIN SELECT RAISE(ABORT, 'Komponenten werden nur als gelöscht markiert'); END;
CREATE TRIGGER kontakt_nicht_loeschen BEFORE DELETE ON kontakt BEGIN SELECT RAISE(ABORT, 'Kontakte werden nur als gelöscht markiert'); END;
CREATE TRIGGER komponententyp_nicht_loeschen BEFORE DELETE ON komponententyp BEGIN SELECT RAISE(ABORT, 'Komponententypen werden nur als gelöscht markiert'); END;
