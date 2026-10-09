// Kleine Helfer für alle Seiten (eigene Datei, weil die Sicherheitsregeln eingebettetes JavaScript verbieten).
// Formulare mit data-frage fragen vor dem Absenden nach (z. B. Löschen).
document.addEventListener("submit", function (e) {
  var frage = e.target.getAttribute("data-frage");
  if (frage && !window.confirm(frage)) {
    e.preventDefault();
  }
});

// Felder mit data-nur-fuer="<wert>" nur zeigen, wenn die Auswahl #importart diesen Wert hat (ohne JS: alle sichtbar).
function nurPassendeFelder() {
  var auswahl = document.getElementById("importart");
  if (!auswahl) { return; }
  document.querySelectorAll("[data-nur-fuer]").forEach(function (feld) {
    feld.hidden = feld.getAttribute("data-nur-fuer") !== auswahl.value;
  });
}
document.addEventListener("change", function (e) {
  if (e.target.id === "importart") { nurPassendeFelder(); }
});
document.addEventListener("DOMContentLoaded", nurPassendeFelder);
