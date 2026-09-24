// Shared UI behaviour: CSRF for HTMX, web confirm dialogs, toasts.

document.addEventListener("htmx:configRequest", function (event) {
  var token = window.csrfToken ? window.csrfToken() : "";
  if (token) {
    event.detail.headers["X-CSRF-Token"] = token;
  }
});

function labels() {
  return window.APP_LABELS || {};
}

function showConfirmDialog(message, confirmLabel, danger) {
  return new Promise(function (resolve) {
    var root = document.getElementById("modal-root");
    if (!root) {
      resolve(window.confirm(message));
      return;
    }

    var overlay = document.createElement("div");
    overlay.className = "fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4";

    var card = document.createElement("div");
    card.className = "w-full max-w-sm rounded-lg bg-white p-6 shadow-xl dark:bg-slate-800 dark:shadow-black/40";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");

    var text = document.createElement("p");
    text.className = "text-sm text-slate-700 dark:text-slate-200";
    text.textContent = message;

    var actions = document.createElement("div");
    actions.className = "mt-5 flex justify-end gap-2";

    var cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "btn btn-secondary";
    cancelButton.textContent = labels().cancel || "Cancel";

    var confirmButton = document.createElement("button");
    confirmButton.type = "button";
    confirmButton.className = "btn " + (danger === false ? "btn-primary" : "btn-danger");
    confirmButton.textContent = confirmLabel || labels().confirm || "Confirm";

    actions.appendChild(cancelButton);
    actions.appendChild(confirmButton);
    card.appendChild(text);
    card.appendChild(actions);
    overlay.appendChild(card);

    var settled = false;
    function close(result) {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey);
      overlay.remove();
      resolve(result);
    }
    function onKey(event) {
      if (event.key === "Escape") close(false);
    }

    cancelButton.addEventListener("click", function () {
      close(false);
    });
    confirmButton.addEventListener("click", function () {
      close(true);
    });
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) close(false);
    });
    document.addEventListener("keydown", onKey);

    root.appendChild(overlay);
    confirmButton.focus();
  });
}

document.addEventListener("submit", function (event) {
  var form = event.target;
  if (!form || !form.getAttribute) return;
  var message = form.getAttribute("data-confirm");
  if (!message || form.dataset.confirmed === "true") return;
  event.preventDefault();
  showConfirmDialog(message, form.getAttribute("data-confirm-label")).then(function (confirmed) {
    if (!confirmed) return;
    form.dataset.confirmed = "true";
    if (form.requestSubmit) {
      form.requestSubmit();
    } else {
      form.submit();
    }
  });
});

// Route HTMX-triggered confirmations through the same web dialog.
document.addEventListener("htmx:confirm", function (event) {
  var elt = event.detail.elt;
  if (!elt || !elt.hasAttribute || !elt.hasAttribute("data-confirm")) return;
  event.preventDefault();
  showConfirmDialog(elt.getAttribute("data-confirm"), elt.getAttribute("data-confirm-label")).then(function (confirmed) {
    if (confirmed) event.detail.issueRequest(true);
  });
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
