-- fremdschluessel: aus
-- 010: Ein Kontakt kann zu mehreren Kunden gehören (z. B. ein Hausmeisterdienst). Die bisherige Spalte kontakt.kunde_id
-- wird durch die Verknüpfungstabelle kunde_kontakt ersetzt; vorhandene Zuordnungen werden übernommen.
-- Siehe docs/03-datenmodell.md.

CREATE TABLE kunde_kontakt (
    id          TEXT PRIMARY KEY,
    kunde_id    TEXT NOT NULL REFERENCES kunde (id),
    kontakt_id  TEXT NOT NULL REFERENCES kontakt (id),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX kunde_kontakt_eindeutig ON kunde_kontakt (kunde_id, kontakt_id) WHERE geloescht = 0;
CREATE INDEX kunde_kontakt_kontakt ON kunde_kontakt (kontakt_id);

CREATE TRIGGER kunde_kontakt_abgleich_neu AFTER INSERT ON kunde_kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kunde_kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER kunde_kontakt_abgleich_aenderung AFTER UPDATE ON kunde_kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kunde_kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;

-- bestehende Zuordnungen übernehmen (neue ID je Zeile, damit sie auch für den Abgleich neu sind)
INSERT INTO kunde_kontakt (id, kunde_id, kontakt_id, erstellt_am, erstellt_von, erstellt_auf, geloescht)
SELECT lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-a'
       || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6))),
       kunde_id, id, erstellt_am, erstellt_von, erstellt_auf, geloescht
FROM kontakt WHERE kunde_id IS NOT NULL;

-- kontakt ohne kunde_id neu aufbauen (SQLite kann eine Spalte mit Fremdschlüssel nicht einfach entfernen);
-- (Fremdschlüssel sind dafür ausgeschaltet; der Migrationslauf prüft sie vor dem Festschreiben mit foreign_key_check)
CREATE TABLE kontakt_neu (
    id          TEXT PRIMARY KEY,
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
INSERT INTO kontakt_neu (id, name, firma, funktion, telefon, mobil, fax, email, notiz, erstellt_am, erstellt_von,
                         erstellt_auf, geaendert_am, geaendert_von, version, geloescht, abgleich_nr)
SELECT id, name, firma, funktion, telefon, mobil, fax, email, notiz, erstellt_am, erstellt_von,
       erstellt_auf, geaendert_am, geaendert_von, version, geloescht, abgleich_nr
FROM kontakt;
DROP TRIGGER kontakt_nicht_loeschen;
DROP TABLE kontakt;
ALTER TABLE kontakt_neu RENAME TO kontakt;

CREATE TRIGGER kontakt_abgleich_neu AFTER INSERT ON kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER kontakt_abgleich_aenderung AFTER UPDATE ON kontakt BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE kontakt SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER kontakt_nicht_loeschen BEFORE DELETE ON kontakt BEGIN SELECT RAISE(ABORT, 'Kontakte werden nur als gelöscht markiert'); END;

