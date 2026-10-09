-- 005: Maßnahmen an Komponenten (Austausch, Ausbau, …) – nur anhängen (⊕), siehe docs/03 Abschnitt 2.
-- Jede Maßnahme verweist auf die alte und ggf. neue Komponente. auftrag_id bleibt leer, solange die Maßnahme im Büro
-- erfasst wird; mit den Aufträgen (später) trägt der Techniker sie vor Ort ein.
CREATE TABLE massnahme (
    id                  TEXT PRIMARY KEY,
    art                 TEXT NOT NULL CHECK (art IN ('inbetriebnahme', 'ausbau', 'austausch', 'batteriewechsel',
                                                     'reinigung', 'versetzt')),
    komponente_alt_id   TEXT REFERENCES komponente (id),
    komponente_neu_id   TEXT REFERENCES komponente (id),
    grund               TEXT NOT NULL DEFAULT '',     -- Schlüssel (z. B. Mängeltyp) oder Text
    bemerkung           TEXT NOT NULL DEFAULT '',
    zeitpunkt           TEXT NOT NULL,                -- wann die Maßnahme stattfand (JJJJ-MM-TT)
    auftrag_id          TEXT,
    erstellt_am TEXT NOT NULL, erstellt_von TEXT, erstellt_auf TEXT,
    geaendert_am TEXT, geaendert_von TEXT,
    version INTEGER NOT NULL DEFAULT 1, geloescht INTEGER NOT NULL DEFAULT 0, abgleich_nr INTEGER NOT NULL DEFAULT 0,
    CHECK (komponente_alt_id IS NOT NULL OR komponente_neu_id IS NOT NULL)
);
CREATE INDEX massnahme_alt ON massnahme (komponente_alt_id);
CREATE INDEX massnahme_neu ON massnahme (komponente_neu_id);

CREATE TRIGGER massnahme_abgleich_neu AFTER INSERT ON massnahme BEGIN
  UPDATE abgleich_zaehler SET nr = nr + 1;
  UPDATE massnahme SET abgleich_nr = (SELECT nr FROM abgleich_zaehler) WHERE id = NEW.id; END;
-- nur anhängen: Änderungen nur an abgleich_nr (durch den Trigger oben), sonst nichts; Löschen nie
CREATE TRIGGER massnahme_nur_anhaengen_u BEFORE UPDATE ON massnahme
  WHEN NEW.id IS NOT OLD.id OR NEW.art IS NOT OLD.art OR NEW.komponente_alt_id IS NOT OLD.komponente_alt_id
    OR NEW.komponente_neu_id IS NOT OLD.komponente_neu_id OR NEW.grund IS NOT OLD.grund
    OR NEW.bemerkung IS NOT OLD.bemerkung OR NEW.zeitpunkt IS NOT OLD.zeitpunkt OR NEW.auftrag_id IS NOT OLD.auftrag_id
    OR NEW.geloescht IS NOT OLD.geloescht
BEGIN SELECT RAISE(ABORT, 'Maßnahmen werden nur angehängt, nicht geändert'); END;
CREATE TRIGGER massnahme_nur_anhaengen_d BEFORE DELETE ON massnahme
BEGIN SELECT RAISE(ABORT, 'Maßnahmen werden nicht gelöscht'); END;
