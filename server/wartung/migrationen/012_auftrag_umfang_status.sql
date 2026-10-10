-- fremdschluessel: aus
-- 012: Aufträge: Status „in Planung“ (unfertige Planung), Umfang „ausgewählte Melder“ (auftrag_komponente) und die
-- Kennzeichnung extern beendeter Aufträge (auftrag.extern). Siehe docs/03-datenmodell.md Abschnitt 2.
-- auftrag wird neu aufgebaut, weil sich die CHECK-Bedingungen von status und umfang nicht nachträglich ändern lassen;
-- die Tabellen, die auf auftrag verweisen, bleiben unberührt (Fremdschlüssel sind dafür ausgeschaltet; der
-- Migrationslauf prüft sie vor dem Festschreiben mit foreign_key_check).

CREATE TABLE auftrag_neu (
    id                  TEXT PRIMARY KEY,
    nummer              TEXT NOT NULL UNIQUE COLLATE NOCASE,     -- A-1001; nie wiederverwendet
    anlage_id           TEXT NOT NULL REFERENCES anlage (id),
    auftragsart         TEXT NOT NULL,                           -- Schlüssel aus der Anlagenart-Konfiguration
    status              TEXT NOT NULL DEFAULT 'geplant'
                        CHECK (status IN ('in_planung', 'geplant', 'aktiv', 'abgeschlossen', 'abgerechnet', 'kostenlos',
                                          'storniert')),
    datum               TEXT NOT NULL,                           -- JJJJ-MM-TT
    uhrzeit             TEXT,                                    -- HH:MM; leer = ganztägig
    dauer_minuten       INTEGER CHECK (dauer_minuten IS NULL OR dauer_minuten > 0),
    umfang              TEXT NOT NULL DEFAULT 'ganze_anlage' CHECK (umfang IN ('ganze_anlage', 'auswahl', 'melder')),
    hinweise            TEXT NOT NULL DEFAULT '',                -- für den Techniker (erscheint in der App)
    notiz_intern        TEXT NOT NULL DEFAULT '',                -- nur Büro
    angekuendigt_am     TEXT,                                    -- Terminankündigung verschickt/ausgehängt
    abgeschlossen_am    TEXT,
    rechnung_nummer     TEXT NOT NULL DEFAULT '',
    extern              INTEGER NOT NULL DEFAULT 0 CHECK (extern IN (0, 1)),   -- 1 = ohne App „extern beendet“
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0,
    CHECK (uhrzeit IS NULL OR (length(uhrzeit) = 5 AND substr(uhrzeit, 3, 1) = ':'))
);
INSERT INTO auftrag_neu (id, nummer, anlage_id, auftragsart, status, datum, uhrzeit, dauer_minuten, umfang, hinweise,
                         notiz_intern, angekuendigt_am, abgeschlossen_am, rechnung_nummer, erstellt_am, erstellt_von,
                         erstellt_auf, geaendert_am, geaendert_von, version, geloescht, abgleich_nr)
SELECT id, nummer, anlage_id, auftragsart, status, datum, uhrzeit, dauer_minuten, umfang, hinweise,
       notiz_intern, angekuendigt_am, abgeschlossen_am, rechnung_nummer, erstellt_am, erstellt_von,
       erstellt_auf, geaendert_am, geaendert_von, version, geloescht, abgleich_nr
FROM auftrag;
DROP TRIGGER auftrag_nicht_loeschen;
DROP TABLE auftrag;
ALTER TABLE auftrag_neu RENAME TO auftrag;

CREATE INDEX auftrag_anlage ON auftrag (anlage_id);
CREATE INDEX auftrag_datum ON auftrag (datum) WHERE geloescht = 0;
CREATE TRIGGER auftrag_abgleich_neu AFTER INSERT ON auftrag BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_abgleich_aenderung AFTER UPDATE ON auftrag BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_nicht_loeschen BEFORE DELETE ON auftrag
BEGIN SELECT RAISE(ABORT, 'Aufträge werden nur storniert, nicht gelöscht'); END;

-- Umfang „melder“: die einzelnen Komponenten, die im Auftrag geprüft werden (z. B. Nachtermin für einzelne Melder)
CREATE TABLE auftrag_komponente (
    id           TEXT PRIMARY KEY,
    auftrag_id   TEXT NOT NULL REFERENCES auftrag (id),
    komponente_id TEXT NOT NULL REFERENCES komponente (id),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX auftrag_komponente_eindeutig ON auftrag_komponente (auftrag_id, komponente_id) WHERE geloescht = 0;
CREATE INDEX auftrag_komponente_komponente ON auftrag_komponente (komponente_id) WHERE geloescht = 0;
CREATE TRIGGER auftrag_komponente_abgleich_neu AFTER INSERT ON auftrag_komponente BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_komponente SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_komponente_abgleich_aenderung AFTER UPDATE ON auftrag_komponente BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE auftrag_komponente SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER auftrag_komponente_nicht_loeschen BEFORE DELETE ON auftrag_komponente
BEGIN SELECT RAISE(ABORT, 'Zuordnungen werden nur als gelöscht markiert'); END;
