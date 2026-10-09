-- 006: Aufträge (Planung im Büro). Siehe docs/03-datenmodell.md Abschnitt 2 und docs/04 Abschnitt 5.
-- Prüfungen, Besuche, Mängel und Unterschriften folgen mit der App (Baustein 4); sie verweisen dann auf auftrag.id.
--
-- Status: geplant -> aktiv -> abgeschlossen -> abgerechnet | kostenlos; storniert. „Verschoben“ ist kein Status,
-- sondern ein Eintrag im Verlauf (auftrag_verlauf) mit altem und neuem Termin. Erlaubte Übergänge: wartung/auftraege.py.

CREATE TABLE auftrag (
    id                  TEXT PRIMARY KEY,
    nummer              TEXT NOT NULL UNIQUE COLLATE NOCASE,     -- A-1001; nie wiederverwendet
    anlage_id           TEXT NOT NULL REFERENCES anlage (id),
    auftragsart         TEXT NOT NULL,                           -- Schlüssel aus der Anlagenart-Konfiguration
    status              TEXT NOT NULL DEFAULT 'geplant'
                        CHECK (status IN ('geplant', 'aktiv', 'abgeschlossen', 'abgerechnet', 'kostenlos', 'storniert')),
    datum               TEXT NOT NULL,                           -- JJJJ-MM-TT
    uhrzeit             TEXT,                                    -- HH:MM; leer = ganztägig
    dauer_minuten       INTEGER CHECK (dauer_minuten IS NULL OR dauer_minuten > 0),
    umfang              TEXT NOT NULL DEFAULT 'ganze_anlage' CHECK (umfang IN ('ganze_anlage', 'auswahl')),
    hinweise            TEXT NOT NULL DEFAULT '',                -- für den Techniker (erscheint in der App)
    notiz_intern        TEXT NOT NULL DEFAULT '',                -- nur Büro
    angekuendigt_am     TEXT,                                    -- Terminankündigung verschickt/ausgehängt
    abgeschlossen_am    TEXT,
    rechnung_nummer     TEXT NOT NULL DEFAULT '',
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0,
    CHECK (uhrzeit IS NULL OR (length(uhrzeit) = 5 AND substr(uhrzeit, 3, 1) = ':'))
);
CREATE INDEX auftrag_anlage ON auftrag (anlage_id);
CREATE INDEX auftrag_datum ON auftrag (datum) WHERE geloescht = 0;

-- Techniker eines Auftrags (mehrere möglich). Kein Eintrag = Pool: jeder Techniker darf den Auftrag übernehmen.
CREATE TABLE auftrag_techniker (
    id          TEXT PRIMARY KEY,
    auftrag_id  TEXT NOT NULL REFERENCES auftrag (id),
    nutzer_id   TEXT NOT NULL REFERENCES nutzer (id),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX auftrag_techniker_eindeutig ON auftrag_techniker (auftrag_id, nutzer_id) WHERE geloescht = 0;
CREATE INDEX auftrag_techniker_nutzer ON auftrag_techniker (nutzer_id) WHERE geloescht = 0;

-- Umfang „auswahl“: die Wohnungen (Gruppen), die im Auftrag geprüft werden
CREATE TABLE auftrag_gruppe (
    id          TEXT PRIMARY KEY,
    auftrag_id  TEXT NOT NULL REFERENCES auftrag (id),
    gruppe_id   TEXT NOT NULL REFERENCES gruppe (id),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX auftrag_gruppe_eindeutig ON auftrag_gruppe (auftrag_id, gruppe_id) WHERE geloescht = 0;

-- Verlauf ⊕: Anlegen, Statuswechsel, Verschieben – wer, wann, warum. Nur anhängen.
CREATE TABLE auftrag_verlauf (
    id              TEXT PRIMARY KEY,
    auftrag_id      TEXT NOT NULL REFERENCES auftrag (id),
    ereignis        TEXT NOT NULL CHECK (ereignis IN ('angelegt', 'status', 'verschoben')),
    status_alt      TEXT,
    status_neu      TEXT,
    termin_alt      TEXT,                                        -- „JJJJ-MM-TT HH:MM“ bzw. nur Datum
    termin_neu      TEXT,
    grund           TEXT NOT NULL DEFAULT '',
    zeitpunkt       TEXT NOT NULL,
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX auftrag_verlauf_auftrag ON auftrag_verlauf (auftrag_id);

-- Abgleich-Nummer bei jedem Anlegen und Ändern
CREATE TRIGGER auftrag_abgleich_neu AFTER INSERT ON auftrag BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_abgleich_aenderung AFTER UPDATE ON auftrag BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_techniker_abgleich_neu AFTER INSERT ON auftrag_techniker BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_techniker SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_techniker_abgleich_aenderung AFTER UPDATE ON auftrag_techniker BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_techniker SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_gruppe_abgleich_neu AFTER INSERT ON auftrag_gruppe BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_gruppe SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_gruppe_abgleich_aenderung AFTER UPDATE ON auftrag_gruppe BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_gruppe SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_verlauf_abgleich_neu AFTER INSERT ON auftrag_verlauf BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_verlauf SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;

-- Nachweise dürfen nicht verschwinden
CREATE TRIGGER auftrag_nicht_loeschen BEFORE DELETE ON auftrag
BEGIN SELECT RAISE(ABORT, 'Aufträge werden nur storniert, nicht gelöscht'); END;
CREATE TRIGGER auftrag_techniker_nicht_loeschen BEFORE DELETE ON auftrag_techniker
BEGIN SELECT RAISE(ABORT, 'Zuordnungen werden nur als gelöscht markiert'); END;
CREATE TRIGGER auftrag_gruppe_nicht_loeschen BEFORE DELETE ON auftrag_gruppe
BEGIN SELECT RAISE(ABORT, 'Zuordnungen werden nur als gelöscht markiert'); END;
-- Verlauf: nur anhängen (Änderung nur an abgleich_nr durch den Trigger oben)
CREATE TRIGGER auftrag_verlauf_nur_anhaengen_u BEFORE UPDATE ON auftrag_verlauf
  WHEN NEW.id IS NOT OLD.id OR NEW.auftrag_id IS NOT OLD.auftrag_id OR NEW.ereignis IS NOT OLD.ereignis
    OR NEW.status_alt IS NOT OLD.status_alt OR NEW.status_neu IS NOT OLD.status_neu
    OR NEW.termin_alt IS NOT OLD.termin_alt OR NEW.termin_neu IS NOT OLD.termin_neu OR NEW.grund IS NOT OLD.grund
    OR NEW.zeitpunkt IS NOT OLD.zeitpunkt OR NEW.geloescht IS NOT OLD.geloescht
BEGIN SELECT RAISE(ABORT, 'Der Auftragsverlauf wird nur angehängt, nicht geändert'); END;
CREATE TRIGGER auftrag_verlauf_nur_anhaengen_d BEFORE DELETE ON auftrag_verlauf
BEGIN SELECT RAISE(ABORT, 'Der Auftragsverlauf wird nicht gelöscht'); END;
