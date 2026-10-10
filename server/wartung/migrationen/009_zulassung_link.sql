-- Zulassungs-/Prüfnummer je Komponente (Vorbild Foxtag) und Link an der Wohnung (Gruppe)
ALTER TABLE komponente ADD COLUMN zulassungsnummer TEXT NOT NULL DEFAULT '';
ALTER TABLE gruppe ADD COLUMN link TEXT NOT NULL DEFAULT '';
