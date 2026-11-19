"use strict";
(() => {
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const root = document.documentElement;
const store = {get(k){try{return localStorage.getItem(k)}catch(e){return null}}, set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
const usd = n => "$" + Math.round(n).toLocaleString("en-US");
let csrf = "", user = null, meta = null, last = "";

/* ---- API helper: sends the CSRF token on every write; text is always inserted with textContent ---- */
async function api(path, {method = "GET", json, form} = {}) {
  const o = {method, headers: {}, credentials: "same-origin"};
  if (method !== "GET") o.headers["X-CSRF-Token"] = csrf;
  if (json) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(json); }
  if (form) o.body = form;
  const r = await fetch(path, o); let d = {};
  try { d = await r.json(); } catch (e) {}
  if (!r.ok) throw Object.assign(new Error(d.error || "Something went wrong. Please try again."), {errors: d.errors});
  return d;
}
const busy = (b, on) => { b.classList.toggle("busy", on); b.disabled = on; };

/* ---- 1 dark mode ---- */
const saved = store.get("theme"); if (saved === "dark" || saved === "light") root.dataset.theme = saved;
$("#theme").onclick = () => {
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark"; store.set("theme", root.dataset.theme);
};

/* ---- 5 mobile menu ---- */
const menu = $("#menu"), nav = $("#nav");
const setMenu = o => { nav.classList.toggle("open", o); menu.setAttribute("aria-expanded", String(o)); };
menu.onclick = () => setMenu(!nav.classList.contains("open"));
nav.addEventListener("click", e => { if (e.target.tagName === "A") setMenu(false); });
addEventListener("keydown", e => { if (e.key === "Escape") setMenu(false); });

/* ---- 8 progress bar, 4 back to top ---- */
const bar = $("#bar"), top2 = $("#top2");
function onScroll() { const h = root.scrollHeight - innerHeight; bar.style.transform = "scaleX(" + (h > 0 ? Math.min(scrollY / h, 1) : 0) + ")"; top2.hidden = scrollY < 400; }
addEventListener("scroll", onScroll, {passive: true}); onScroll();
top2.onclick = () => scrollTo({top: 0, behavior: "smooth"});

/* ---- 3 search ---- */
const items = $$(".searchable"), none = $("#none");
$("#q").addEventListener("input", e => {
  const q = e.target.value.trim().toLowerCase(); let hits = 0;
  items.forEach(el => { const m = !q || el.textContent.toLowerCase().includes(q); el.hidden = !m; if (m) hits++; if (el.tagName === "DETAILS") el.open = !!q && m; });
  none.hidden = hits > 0;
});

/* ---- 2 cookie banner ---- */
const cb = $("#cookie"); if (!store.get("consent")) cb.hidden = false;
cb.addEventListener("click", e => { const c = e.target.dataset.c; if (c) { store.set("consent", c); cb.hidden = true; } });

/* ---- 14 UTM tracking ---- */
const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
let utm = {}; const qs = new URLSearchParams(location.search);
UTM_KEYS.forEach(k => { const v = qs.get(k); if (v) utm[k] = v.slice(0, 100); });
try { if (Object.keys(utm).length) sessionStorage.setItem("utm", JSON.stringify(utm)); else utm = JSON.parse(sessionStorage.getItem("utm") || "{}"); } catch (e) {}
$("#utm").textContent = Object.keys(utm).length ? Object.entries(utm).map(([k, v]) => k + "=" + v).join(", ") : "none";

/* ---- 13 password visibility toggle ---- */
$("#pwt").onclick = e => { const i = $("#ap"), show = i.type === "password"; i.type = show ? "text" : "password"; e.currentTarget.textContent = show ? "Hide" : "Show"; e.currentTarget.setAttribute("aria-pressed", String(show)); };

/* ---- prediction form (built from /api/meta) ---- */
function buildForm() {
  const box = $("#fields"); box.textContent = "";
  meta.features.forEach(f => {
    const w = document.createElement("div"), l = document.createElement("label"), i = document.createElement("input"), e = document.createElement("p");
    l.htmlFor = "f-" + f.name; l.textContent = f.label;
    Object.assign(i, {id: "f-" + f.name, name: f.name, type: "number", min: f.min, max: f.max, step: f.step, value: f.default, inputMode: "decimal"});
    e.className = "err"; e.id = "e-f-" + f.name; e.setAttribute("role", "alert");
    w.append(l, i, e); box.append(w);
  });
  $("#cols").textContent = meta.features.map(f => f.name).join(",");
  const sel = $("#model"); sel.textContent = "";
  Object.keys(meta.models).forEach(k => { const o = document.createElement("option"); o.value = k; o.textContent = k === "baseline" ? "Baseline (Linear Regression)" : "Improved (Ridge + features)"; sel.append(o); });
}
function fieldErrors(errs) {
  meta.features.forEach(f => { const m = errs && errs[f.name]; $("#e-f-" + f.name).textContent = m || ""; $("#f-" + f.name).setAttribute("aria-invalid", String(!!m)); });
}
$("#pf").addEventListener("submit", async e => {
  e.preventDefault(); const btn = e.submitter || $("#pf button[type=submit]"), body = {model: $("#model").value}, msg = $("#pmsg");
  meta.features.forEach(f => { body[f.name] = $("#f-" + f.name).value === "" ? null : Number($("#f-" + f.name).value); });
  msg.textContent = ""; busy(btn, true); root.classList.add("loading");
  try {
    const d = await api("/api/predict", {method: "POST", json: body}); fieldErrors({});
    $("#price").textContent = usd(d.price);
    $("#margin").textContent = "Typical error of this model: about ±" + usd(d.error_margin) + (d.demo ? " (demo model)" : "");
    last = "Estimated median house value: " + usd(d.price) + " (±" + usd(d.error_margin) + ")";
    $("#result").hidden = false; if (d.saved) loadHistory();
  } catch (err) { fieldErrors(err.errors); msg.textContent = err.message; const bad = $("#pf [aria-invalid=true]"); if (bad) bad.focus(); }
  finally { busy(btn, false); root.classList.remove("loading"); }
});
$("#reset").onclick = () => { meta.features.forEach(f => { $("#f-" + f.name).value = f.default; }); fieldErrors({}); $("#pmsg").textContent = ""; };

/* ---- 9 copy button, print ---- */
$("#copy").onclick = async e => {
  const b = e.currentTarget;
  try { await navigator.clipboard.writeText(last); } catch (_) { const t = document.createElement("textarea"); t.value = last; document.body.append(t); t.select(); try { document.execCommand("copy"); } catch (__) {} t.remove(); }
  b.textContent = "Copied ✓"; setTimeout(() => { b.textContent = "Copy result"; }, 1600);
};
$("#print").onclick = () => print();

/* ---- batch CSV ---- */
$("#bgo").onclick = async e => {
  const btn = e.currentTarget, f = $("#file").files[0], msg = $("#bmsg"), tb = $("#btable"); msg.textContent = ""; tb.hidden = true;
  if (!f) { msg.textContent = "Choose a .csv file first."; return; }
  const fd = new FormData(); fd.append("file", f); busy(btn, true);
  try {
    const d = await api("/api/predict-batch", {method: "POST", form: fd}), body = tb.tBodies[0]; body.textContent = "";
    d.results.forEach(r => { const tr = body.insertRow(); tr.insertCell().textContent = r.row; tr.insertCell().textContent = r.price !== undefined ? usd(r.price) : r.error; });
    tb.hidden = false;
  } catch (err) { msg.textContent = err.message; } finally { busy(btn, false); }
};

/* ---- account + history ---- */
function renderUser() {
  $("#guest").hidden = !!user; $("#member").hidden = !user;
  if (user) $("#who").textContent = user.email + (user.role === "admin" ? " (admin)" : "");
  if (!user) { $("#htable").hidden = true; $("#hnote").hidden = false; $("#hnote").textContent = "Sign in to see your saved predictions."; }
}
async function loadHistory() {
  if (!user) return;
  const rows = await api("/api/history"), tb = $("#htable"), body = tb.tBodies[0]; body.textContent = "";
  rows.forEach(r => { const tr = body.insertRow(); tr.insertCell().textContent = new Date(r.created * 1000).toLocaleDateString();
    tr.insertCell().textContent = r.inputs.MedInc; tr.insertCell().textContent = r.inputs.Latitude + ", " + r.inputs.Longitude; tr.insertCell().textContent = usd(r.price); });
  tb.hidden = !rows.length; $("#hnote").hidden = !!rows.length; $("#hnote").textContent = "No saved predictions yet. Make one above.";
}
$("#af").addEventListener("submit", async e => {
  e.preventDefault(); const action = e.submitter && e.submitter.dataset.a, msg = $("#amsg"); msg.textContent = "";
  if (!action) return; busy(e.submitter, true);
  try { const d = await api("/api/" + action, {method: "POST", json: {email: $("#ae").value, password: $("#ap").value}});
    user = d.user; csrf = d.csrf; $("#ap").value = ""; renderUser(); loadHistory();
  } catch (err) { msg.textContent = err.message; } finally { busy(e.submitter, false); }
});
$("#logout").onclick = async () => { try { const d = await api("/api/logout", {method: "POST"}); csrf = d.csrf; user = null; renderUser(); } catch (e) { $("#amsg").textContent = e.message; } };

/* ---- 17 confirmation modal ---- */
const dlg = $("#dlg"); $("#clear").onclick = () => dlg.showModal();
dlg.addEventListener("close", async () => { if (dlg.returnValue === "yes") { try { await api("/api/history", {method: "DELETE"}); loadHistory(); } catch (e) {} } });

/* ---- 15 + 16 feedback form: success and error states ---- */
const cf = $("#cf");
cf.addEventListener("submit", async e => {
  e.preventDefault(); const btn = cf.querySelector("[type=submit]"); busy(btn, true); $("#cmsg").textContent = "";
  const d = Object.fromEntries(new FormData(cf)); d.utm = utm;
  try { await api("/api/feedback", {method: "POST", json: d}); cf.hidden = true; $("#ok").hidden = false; $("#ok").focus(); }
  catch (err) { const errs = err.errors || {};
    ["name", "email", "message"].forEach(k => { $("#e-" + k).textContent = errs[k] || ""; cf.elements[k].setAttribute("aria-invalid", String(!!errs[k])); });
    $("#cmsg").textContent = err.message; const bad = cf.querySelector("[aria-invalid=true]"); if (bad) bad.focus(); }
  finally { busy(btn, false); }
});
$("#again").onclick = () => { cf.reset(); cf.hidden = false; $("#ok").hidden = true; };

/* ---- start-up ---- */
(async () => {
  root.classList.add("loading");                            // 6 loading animation until the model info arrives
  try {
    const s = await api("/api/session"); csrf = s.csrf; user = s.user;
    meta = await api("/api/meta"); buildForm(); renderUser(); loadHistory();
    const m = meta.models.baseline, imp = meta.models.improved;
    $("#mstat").textContent = (meta.demo ? "Demo model · " : "") + "Baseline R² " + m.r2.toFixed(2) + " · typical error ±" + usd(m.mae * 100000);
    $("#acc").textContent = "On unseen test data the baseline model has a mean absolute error of about " + usd(m.mae * 100000) + " and an R² of " + m.r2.toFixed(2) + "." +
      (imp ? " The improved model reaches an R² of " + imp.r2.toFixed(2) + " (error about " + usd(imp.mae * 100000) + ")." : "");
    $("#trained").textContent = meta.trained_at || "recently"; if (meta.trained_at) $("#trained").dateTime = meta.trained_at;
    $("#demo").hidden = !meta.demo;
  } catch (e) { $("#mstat").textContent = "Could not load the model. Please refresh."; }
  setTimeout(() => root.classList.remove("loading"), 400);
})();
})();
