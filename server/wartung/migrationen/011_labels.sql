-- 011: Labels (frei benennbar, mit Farbe) an Kunde, Objekt, Anlage und Auftrag; Vorbild Foxtag.
-- Siehe docs/03-datenmodell.md.

CREATE TABLE label (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL CHECK (name <> ''),
    farbe       TEXT NOT NULL DEFAULT 'grau' CHECK (farbe IN ('grau', 'rot', 'orange', 'gelb', 'gruen', 'blau', 'violett')),
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX label_name_eindeutig ON label (name COLLATE NOCASE) WHERE geloescht = 0;

CREATE TABLE label_zuordnung (
    id          TEXT PRIMARY KEY,
    label_id    TEXT NOT NULL REFERENCES label (id),
    art         TEXT NOT NULL CHECK (art IN ('kunde', 'objekt', 'anlage', 'auftrag')),
    datensatz_id TEXT NOT NULL,                       -- id des Kunden, Objekts, der Anlage oder des Auftrags (je nach art)
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX label_zuordnung_eindeutig ON label_zuordnung (label_id, art, datensatz_id) WHERE geloescht = 0;
CREATE INDEX label_zuordnung_datensatz ON label_zuordnung (art, datensatz_id);

CREATE TRIGGER label_abgleich_neu AFTER INSERT ON label BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE label SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER label_abgleich_aenderung AFTER UPDATE ON label BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE label SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER label_nicht_loeschen BEFORE DELETE ON label BEGIN SELECT RAISE(ABORT, 'Labels werden nur als gelöscht markiert'); END;

CREATE TRIGGER label_zuordnung_abgleich_neu AFTER INSERT ON label_zuordnung BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE label_zuordnung SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER label_zuordnung_abgleich_aenderung AFTER UPDATE ON label_zuordnung BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE label_zuordnung SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
CREATE TRIGGER label_zuordnung_nicht_loeschen BEFORE DELETE ON label_zuordnung BEGIN SELECT RAISE(ABORT, 'Label-Zuordnungen werden nur als gelöscht markiert'); END;
