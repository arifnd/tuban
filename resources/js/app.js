// Shared UI behaviour: CSRF for HTMX, confirm dialogs, toasts.

document.addEventListener("htmx:configRequest", function (event) {
  var token = window.csrfToken ? window.csrfToken() : "";
  if (token) {
    event.detail.headers["X-CSRF-Token"] = token;
  }
});

document.addEventListener("submit", function (event) {
  var form = event.target;
  if (!form || !form.getAttribute) return;
  var message = form.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

window.toast = function (message, type) {
  var root = document.getElementById("toast-root");
  if (!root) return;
  var el = document.createElement("div");
  var tone = type === "error" ? "alert-error" : "alert-success";
  el.className = "alert " + tone + " shadow";
  el.textContent = message;
  root.appendChild(el);
  setTimeout(function () {
    el.remove();
  }, 4000);
};
