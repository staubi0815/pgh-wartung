// Kleine Helfer für alle Seiten (eigene Datei, weil die Sicherheitsregeln eingebettetes JavaScript verbieten).
// Formulare mit data-frage fragen vor dem Absenden nach (z. B. Löschen).
document.addEventListener("submit", function (e) {
  var frage = e.target.getAttribute("data-frage");
  if (frage && !window.confirm(frage)) {
    e.preventDefault();
  }
});
