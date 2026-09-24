// Renders Chart.js charts declared with data-* attributes.
// Chart.js is loaded from a CDN on pages that need it.

window.renderCharts = function () {
  if (typeof window.Chart === "undefined") return;
  document.querySelectorAll("[data-chart]").forEach(function (canvas) {
    var labels = JSON.parse(canvas.getAttribute("data-labels") || "[]");
    var values = JSON.parse(canvas.getAttribute("data-values") || "[]");
    var type = canvas.getAttribute("data-chart") || "line";
    var brand = "#16a34a";
    new window.Chart(canvas, {
      type: type,
      data: {
        labels: labels,
        datasets: [{ label: canvas.getAttribute("data-label") || "", data: values, borderColor: brand, backgroundColor: brand + "33", fill: type === "line", tension: 0.3 }],
      },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
    });
  });
};

if (document.readyState !== "loading") {
  window.renderCharts();
} else {
  document.addEventListener("DOMContentLoaded", window.renderCharts);
}
