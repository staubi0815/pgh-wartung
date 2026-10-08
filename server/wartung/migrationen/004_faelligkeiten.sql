-- 004: Datum der letzten Prüfung je Komponente und Index für Fälligkeitslisten.
-- letzte_pruefung_am wird bis zur Einführung der Prüfungen (Aufträge) von Hand bzw. beim Import gepflegt (Foxtag-
-- Spalte LETZTE PRÜFUNG); danach setzt es die jeweils letzte Prüfung. naechste_pruefung_am und austausch_faellig_am
-- rechnet der Server (wartung/faelligkeit.py) – nie von Hand.
ALTER TABLE komponente ADD COLUMN letzte_pruefung_am TEXT;
CREATE INDEX komponente_faellig ON komponente (naechste_pruefung_am, austausch_faellig_am)
    WHERE geloescht = 0 AND status = 'verbaut';
