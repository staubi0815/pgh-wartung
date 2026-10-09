"""Probe-Import ins Foxtag-Testkonto: legt erfundene Testdaten in einer leeren Datenbank an und schreibt daraus den
Foxtag-Export (ZIP). Nur erfundene Daten – nie gegen die echte Datenbank laufen lassen.

Aufruf (aus server/):  ../.venv-test/bin/python werkzeuge/foxtag_probe.py <leerer Ordner> <ziel.zip>

Alle Nummern beginnen mit „PT-“, damit sie im Testkonto nicht mit vorhandenen Demo-Daten zusammenstoßen.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wartung import (anlagen, anlagenart, auftraege, auth, export, gruppen, komponenten, kunden,  # noqa: E402
                     objekte, rechte, typen)
from wartung.app import erzeuge_app  # noqa: E402

TECHNIKER_NUMMER = "PT-TECH-1"


def anlegen(con):
    rwm = anlagenart.holen("rauchwarnmelder")
    techniker_rolle = con.execute("SELECT id FROM rolle WHERE kennung = 'techniker'").fetchone()["id"]
    tech = auth.nutzer_anlegen(con, "Probe Techniker", "probe-techniker@example.org", [techniker_rolle], None,
                               personalnummer=TECHNIKER_NUMMER)
    assert auftraege.TECHNIKER_RECHT in rechte.rechte_von_nutzer(con, tech)

    k1 = kunden.anlegen(con, {"nummer": "PT-K1", "art": "hausverwaltung", "name": "Probe Hausverwaltung GmbH",
                              "zusatz": "z. Hd. Technik", "strasse": "Musterstraße 1", "plz": "01067",
                              "ort": "Dresden", "land": "DE", "notiz_intern": "Probe-Import, erfundene Daten"}, None)
    k2 = kunden.anlegen(con, {"nummer": "PT-K2", "art": "privat", "name": "Erika Probe", "strasse": "Beispielweg 7",
                              "plz": "90402", "ort": "Nürnberg", "land": "DE"}, None)
    kunden.kontakt_anlegen(con, k1, {"name": "Max Probe", "funktion": "Hausmeister", "telefon": "0351 123456",
                                     "mobil": "0170 1234567", "email": "hausmeister@example.org",
                                     "notiz": "Schlüssel im Büro"}, None)
    o1 = objekte.anlegen(con, k1, {"nummer": "PT-O1", "bezeichnung": "Wohnanlage Probe Süd", "strasse": "Teststraße 12",
                                   "plz": "01069", "ort": "Dresden", "land": "DE"}, None)
    o2 = objekte.anlegen(con, k2, {"nummer": "PT-O2", "bezeichnung": "Einfamilienhaus Probe",
                                   "adresse_wie_kunde": "1"}, None)
    a1 = anlagen.anlegen(con, o1, {"nummer": "PT-ANL-1", "anlagenart": "rauchwarnmelder", "verfahren": "A",
                                   "bezeichnung": "Haus A"}, None)
    a2 = anlagen.anlegen(con, o2, {"nummer": "PT-ANL-2", "anlagenart": "rauchwarnmelder", "verfahren": "A"}, None)

    def typ(bezeichnung, hersteller, modell):
        return typen.anlegen(con, {"anlagenart": "rauchwarnmelder", "bezeichnung": bezeichnung,
                                   "hersteller": hersteller, "modell": modell, "kategorie": "komponente",
                                   "funk": "keine", "batterie": "fest_10j", "aktiv": "1"}, None)
    ei650 = typ("Ei650", "Ei Electronics", "Ei650")
    genius = typ("Genius Plus", "Hekatron", "Genius Plus")

    def wohnung(anlage, nummer, lage, bewohner=""):
        return gruppen.holen(con, gruppen.anlegen(con, rwm, anlage, {"nummer": str(nummer), "bezeichnung": lage,
                                                                     "bewohner": bewohner, "zugang": "frei"}, None))

    def melder(g, nummer, raum, t, seriennummer, baujahr, letzte="", barcode=""):
        komponenten.anlegen(con, rwm, g, {"nummer": str(nummer), "komponententyp_id": t, "raum": raum,
                                          "seriennummer": seriennummer, "baujahr": str(baujahr),
                                          "letzte_pruefung_am": letzte, "inbetriebnahme_am": f"{baujahr}-03-01",
                                          "barcode": barcode}, None)
    w1 = wohnung(a1, 1, "EG links", "Musterfrau")
    melder(w1, 1, "Flur", ei650, "PT-SN-0001", 2021, "2025-10-20", "PT-QR-0001")
    melder(w1, 2, "Schlafzimmer", ei650, "PT-SN-0002", 2021, "2025-10-20")
    melder(w1, 3, "Kinderzimmer", genius, "PT-SN-0003", 2023, "2025-10-20")
    w2 = wohnung(a1, 2, "EG rechts")
    melder(w2, 1, "Flur", ei650, "PT-SN-0004", 2020, "2025-10-21")
    melder(w2, 2, "Schlafzimmer", ei650, "PT-SN-0005", 2020, "2025-10-21")
    w3 = wohnung(a2, 1, "Haus")
    melder(w3, 1, "Flur", genius, "PT-SN-0006", 2022)
    melder(w3, 2, "Schlafzimmer", genius, "PT-SN-0007", 2022)

    termin = date.today() + timedelta(days=14)
    auftraege.anlegen(con, anlagen.holen(con, a1), auftraege.FormularWerte(
        {"nummer": "PT-A-1", "auftragsart": "wartung", "datum": termin.isoformat(), "uhrzeit": "08:30",
         "hinweise": "Probe-Import: Schlüssel beim Hausmeister"}, [tech]), None)
    auftraege.anlegen(con, anlagen.holen(con, a2), auftraege.FormularWerte(
        {"nummer": "PT-A-2", "auftragsart": "installation", "datum": (termin + timedelta(days=1)).isoformat()},
        [tech]), None)


def main(ordner, ziel):
    ordner = Path(ordner)
    if (ordner / "wartung.db").exists():
        raise SystemExit("Der Ordner enthält schon eine Datenbank – bitte einen leeren Ordner angeben.")
    con = erzeuge_app(ordner).state.con
    anlegen(con)
    inhalt, anzahl = export.foxtag(con)
    Path(ziel).write_bytes(inhalt)
    for name, n in anzahl.items():
        print(f"{name}: {n}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
