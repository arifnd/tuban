// Self-hosted vendor libraries bundled by esbuild so the CSP can drop all
// third-party script origins and inline-script allowances.
import Alpine from "alpinejs";
import Chart from "chart.js/auto";
import DOMPurify from "dompurify";
import htmx from "htmx.org";
import { marked } from "marked";

window.htmx = htmx;
window.Alpine = Alpine;
window.Chart = Chart;
window.marked = marked;
window.DOMPurify = DOMPurify;

Alpine.start();
