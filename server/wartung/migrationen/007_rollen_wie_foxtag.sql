-- 007: Standardrollen heißen und wirken wie bei Foxtag (docs/06). Nur Standardrollen (feste Kennung) werden angefasst.
UPDATE rolle SET name = 'Planen und Daten pflegen',
    beschreibung = 'Stammdaten, Aufträge, Mängel, Berichte, Rechnungsentwürfe, Katalog, Import und Export. Nicht in die App.',
    version = version + 1, geaendert_am = strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')
WHERE kennung = 'buero';
UPDATE rolle SET name = 'Techniker ohne Webzugang',
    version = version + 1, geaendert_am = strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')
WHERE kennung = 'techniker_app';

-- Foxtag: Planen und Daten pflegen erstellt keine Auswertungen (Rechtetabelle Foxtag: Mitarbeiterverwaltung nur Administration)
DELETE FROM rolle_recht WHERE recht = 'auswertungen' AND rolle_id IN (SELECT id FROM rolle WHERE kennung = 'buero');
