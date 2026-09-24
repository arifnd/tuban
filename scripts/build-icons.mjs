// Generates the self-hosted Lucide icon sprite and the Jinja icon macro.
//
//   node scripts/build-icons.mjs
//
// Outputs (both committed, since templates are the app source):
//   templates/partials/sprite.html  - hidden <svg> with <symbol id="icon-<name>">
//   templates/partials/icons.html   - {% macro icon(name, class) %} using <use>#icon-<name>
//
// The macro signature is unchanged, so existing icon("name", "class") call sites keep
// working. Stroke width is pinned to 1.5.

import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import config from "./icons.config.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ICONS_DIR = join(ROOT, "node_modules", "lucide-static", "icons");
const SPRITE_OUT = join(ROOT, "templates", "partials", "sprite.html");
const MACRO_OUT = join(ROOT, "templates", "partials", "icons.html");
const STROKE_WIDTH = "1.5";

function innerSvg(file) {
  const path = join(ICONS_DIR, `${file}.svg`);
  let raw;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    throw new Error(`Missing Lucide icon "${file}.svg" (check scripts/icons.config.mjs)`);
  }
  const match = raw.match(/<svg[^>]*>([\s\S]*)<\/svg>/);
  if (!match) {
    throw new Error(`Could not parse <svg> body from "${file}.svg"`);
  }
  return match[1].trim();
}

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(full);
    } else {
      yield full;
    }
  }
}

function assertNoUnknownIcons() {
  const used = new Set();
  for (const file of walk(join(ROOT, "templates"))) {
    if (!file.endsWith(".html")) continue;
    const text = readFileSync(file, "utf8");
    for (const match of text.matchAll(/icon\(\s*["']([a-z0-9-]+)["']/g)) {
      used.add(match[1]);
    }
  }
  const unknown = [...used].filter((name) => !(name in config));
  if (unknown.length) {
    throw new Error(`Templates reference icons missing from icons.config.mjs: ${unknown.sort().join(", ")}`);
  }
}

const symbols = Object.entries(config).map(
  ([name, file]) => `  <symbol id="icon-${name}" viewBox="0 0 24 24">${innerSvg(file)}</symbol>`,
);

const sprite = [
  '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">',
  ...symbols,
  "</svg>",
  "",
].join("\n");

const macro = `{% macro icon(name, class="w-5 h-5") -%}
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${STROKE_WIDTH}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="{{ class }}"><use href="#icon-{{ name }}"/></svg>
{%- endmacro %}
`;

assertNoUnknownIcons();
writeFileSync(SPRITE_OUT, sprite);
writeFileSync(MACRO_OUT, macro);
console.log(`Wrote ${Object.keys(config).length} icons to sprite.html and icons.html`);
