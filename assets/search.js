/* All filtering stays in this browser; no network/search service is used. */
"use strict";
(() => {
  const payload = document.getElementById("search-data");
  if (!payload) {
    for (const link of document.querySelectorAll(".back, .brand, [data-language]")) {
      const target = new URL(link.getAttribute("href"), location.href);
      target.search = location.search;
      link.href = target.href;
    }
    return;
  }
  const { records, pageSize, words } = JSON.parse(payload.textContent);
  const form = document.getElementById("search-form");
  const query = document.getElementById("q");
  const filters = [...form.querySelectorAll("select")];
  const cards = [...document.querySelectorAll("[data-index]")];
  const pagination = document.getElementById("pagination");
  const normalize = value => value.normalize("NFKC").toLowerCase().replace(/ß/g, "ss").replace(/ς/g, "σ");
  let page = 1;
  let timer;
  function format(template, values) {
    return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key]));
  }
  function readURL() {
    const params = new URLSearchParams(location.search);
    query.value = params.get("q") || "";
    for (const select of filters) select.value = params.get(select.name) || "";
    const n = Number(params.get("page"));
    page = Number.isSafeInteger(n) && n > 0 ? n : 1;
  }
  function updateURL(push) {
    const url = new URL(location.href);
    url.search = "";
    if (query.value.trim()) url.searchParams.set("q", query.value.trim());
    for (const select of filters) if (select.value) url.searchParams.set(select.name, select.value);
    if (page > 1) url.searchParams.set("page", String(page));
    if (url.href !== location.href) history[push ? "pushState" : "replaceState"](null, "", url);
    for (const link of document.querySelectorAll("[data-language]")) {
      const target = new URL(link.getAttribute("href"), location.href);
      target.search = url.search;
      // Creator names can differ by display language; unknown values are ignored there.
      link.href = target.href;
    }
    for (const link of document.querySelectorAll(".resource h3 a")) {
      const target = new URL(link.getAttribute("href"), location.href);
      target.search = url.search;
      link.href = target.href;
    }
  }
  function render(push = false) {
    const tokens = normalize(query.value.trim()).split(/\s+/u).filter(Boolean);
    const matches = records.map((record, i) => ({ record, i })).filter(({record}) =>
      tokens.every(token => record.search.includes(token)) &&
      filters.every(select => !select.value || record[select.name].includes(select.value))
    );
    const pages = Math.max(1, Math.ceil(matches.length / pageSize));
    page = Math.min(Math.max(1, page), pages);
    const visible = new Set(matches.slice((page - 1) * pageSize, page * pageSize).map(({i}) => i));
    cards.forEach((card, i) => { card.hidden = !visible.has(i); });
    document.getElementById("count").textContent = format(words.found, { visible: matches.length, total: records.length });
    document.getElementById("empty").hidden = matches.length > 0;
    pagination.hidden = matches.length <= pageSize;
    document.getElementById("previous").disabled = page <= 1;
    document.getElementById("next").disabled = page >= pages;
    document.getElementById("page-status").textContent = format(words.page, { page, pages });
    updateURL(push);
  }
  form.addEventListener("submit", event => { event.preventDefault(); clearTimeout(timer); page = 1; render(true); });
  query.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; render(); }, 150); });
  filters.forEach(select => select.addEventListener("change", () => { clearTimeout(timer); page = 1; render(true); }));
  document.getElementById("reset").addEventListener("click", () => { clearTimeout(timer); form.reset(); page = 1; render(true); query.focus(); });
  for (const [id, delta] of [["previous", -1], ["next", 1]]) {
    document.getElementById(id).addEventListener("click", () => { page += delta; render(true); document.getElementById("results-title").scrollIntoView({block:"start"}); });
  }
  window.addEventListener("popstate", () => { clearTimeout(timer); readURL(); render(); });
  readURL();
  render();
})();
