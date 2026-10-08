-- 002: Einzelrechte und Rollen (mehrere Rollen je Nutzer), ersetzt nutzer.rolle. Siehe docs/06-foxtag-rollen-und-app.md.
-- Die Liste der gültigen Rechte steht im Code (wartung/rechte.py); die Rolle mit kennung 'admin' hat immer alle Rechte.

CREATE TABLE rolle (
    id              TEXT PRIMARY KEY,
    kennung         TEXT UNIQUE,                       -- feste Kennung der Standardrollen, eigene Rollen: NULL
    name            TEXT NOT NULL,
    beschreibung    TEXT NOT NULL DEFAULT '',
    reihenfolge     INTEGER NOT NULL DEFAULT 100,
    erstellt_am     TEXT NOT NULL,
    erstellt_von    TEXT,
    geaendert_am    TEXT,
    geaendert_von   TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    geloescht       INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX rolle_name ON rolle (name COLLATE NOCASE) WHERE geloescht = 0;

CREATE TABLE rolle_recht (
    rolle_id    TEXT NOT NULL REFERENCES rolle (id),
    recht       TEXT NOT NULL,
    PRIMARY KEY (rolle_id, recht)
) WITHOUT ROWID;

CREATE TABLE nutzer_rolle (
    nutzer_id   TEXT NOT NULL REFERENCES nutzer (id),
    rolle_id    TEXT NOT NULL REFERENCES rolle (id),
    PRIMARY KEY (nutzer_id, rolle_id)
) WITHOUT ROWID;
CREATE INDEX nutzer_rolle_rolle ON nutzer_rolle (rolle_id);

-- Standardrollen (feste IDs, damit sie auf allen Geräten gleich sind)
INSERT INTO rolle (id, kennung, name, beschreibung, reihenfolge, erstellt_am) VALUES
  ('bd796a74-fded-4d22-a08d-f48a3055a855', 'admin', 'Administration',
   'Alle Rechte, auch künftige. Nicht änderbar.', 10, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
  ('6d079dcc-ede0-41d3-9509-c755e69d9fc9', 'buero', 'Büro',
   'Stammdaten, Aufträge, Mängel, Berichte, Rechnungsentwürfe, Import und Export.', 20, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
  ('a12b44fb-e224-4fd2-ab76-b45fe14472a6', 'techniker', 'Techniker',
   'Aufträge in der App durchführen; Webseite nur für eigene Aufträge.', 30, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
  ('4cf3fa00-3877-4410-a278-1225521078d7', 'techniker_app', 'Techniker nur App',
   'Aufträge in der App durchführen, kein Zugang zur Webseite.', 40, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'));

INSERT INTO rolle_recht (rolle_id, recht)
SELECT '6d079dcc-ede0-41d3-9509-c755e69d9fc9', value FROM json_each('["web.zugang", "stammdaten.lesen",
  "stammdaten.bearbeiten", "auftraege.planen", "maengel.bearbeiten", "berichte.versenden", "rechnung.entwurf",
  "auswertungen", "import", "export", "verwaltung.katalog"]');
INSERT INTO rolle_recht (rolle_id, recht)
SELECT 'a12b44fb-e224-4fd2-ab76-b45fe14472a6', value FROM json_each('["web.zugang", "app.zugang", "app.auftraege",
  "app.stammdaten", "app.fotos"]');
INSERT INTO rolle_recht (rolle_id, recht)
SELECT '4cf3fa00-3877-4410-a278-1225521078d7', value FROM json_each('["app.zugang", "app.auftraege",
  "app.stammdaten", "app.fotos"]');

-- bisherige Einzelrolle übernehmen, dann Spalte entfernen
INSERT INTO nutzer_rolle (nutzer_id, rolle_id)
SELECT n.id, r.id FROM nutzer n JOIN rolle r ON r.kennung = n.rolle;
ALTER TABLE nutzer DROP COLUMN rolle;
