-- Stammtechniker je Anlage (Vorbelegung beim Planen, Filter in der Anlagenliste)
ALTER TABLE anlage ADD COLUMN stammtechniker_id TEXT REFERENCES nutzer (id);
