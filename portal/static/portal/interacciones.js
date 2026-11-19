(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Tema claro / oscuro
  $("#theme-toggle")?.addEventListener("click", () => {
    const oscuro = document.documentElement.dataset.theme !== "dark";
    document.documentElement.dataset.theme = oscuro ? "dark" : "light";
    try { localStorage.setItem("tema", oscuro ? "dark" : "light"); } catch (e) {}
    document.dispatchEvent(new Event("temacambiado"));
  });

  // Avisos: se cierran solos
  $$(".toasts .message").forEach((m) => {
    const cerrar = () => { m.classList.add("leaving"); setTimeout(() => m.remove(), 320); };
    $(".toast-x", m)?.addEventListener("click", cerrar);
    setTimeout(cerrar, 6000);
  });

  // Formulario de nuevo reporte
  const description = $("#id_descripcion");
  const count = $("#description-count");
  if (description && count) {
    const meter = $("#detail-meter"), hint = $("#detail-hint");
    const update = () => {
      const n = description.value.length;
      count.textContent = n + " / 2500";
      const palabras = description.value.trim().split(/\s+/).filter(Boolean).length;
      const pct = Math.min(100, palabras * 8);
      if (meter) { meter.style.width = pct + "%"; meter.style.background = pct < 32 ? "#c0392b" : pct < 64 ? "#e08a00" : "#2f8f4f"; }
      if (hint) hint.textContent = palabras === 0 ? "Cuanto más específico, más rápido se atiende."
        : palabras < 4 ? "Muy corto: añade qué falla y dónde."
        : palabras < 8 ? "Bien. Si puedes, indica desde cuándo y si hay riesgo."
        : "Buen nivel de detalle.";
    };
    description.addEventListener("input", update);
    $$(".chip[data-ejemplo]").forEach((b) => b.addEventListener("click", () => {
      description.value = b.dataset.ejemplo; description.focus(); update();
    }));
    update();
  }
  const file = $("#id_evidencia");
  const preview = $("#photo-preview");
  let previewUrl;
  const mostrar = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    preview.hidden = true; preview.removeAttribute("src");
    const selected = file.files[0];
    if (selected && ["image/jpeg", "image/png"].includes(selected.type) && selected.size <= 5 * 1024 * 1024) {
      previewUrl = URL.createObjectURL(selected); preview.src = previewUrl; preview.hidden = false;
    }
  };
  if (file && preview) {
    file.addEventListener("change", mostrar);
    const zona = $("#dropzone");
    ["dragenter", "dragover"].forEach((e) => zona?.addEventListener(e, (ev) => { ev.preventDefault(); zona.classList.add("over"); }));
    ["dragleave", "drop"].forEach((e) => zona?.addEventListener(e, (ev) => { ev.preventDefault(); zona.classList.remove("over"); }));
    zona?.addEventListener("drop", (ev) => { if (ev.dataTransfer.files.length) { file.files = ev.dataTransfer.files; mostrar(); } });
  }

  // Bandeja: filtros en vivo (sin recargar toda la página)
  const filtros = $("#filtros");
  const resultados = $("#resultados");
  if (filtros && resultados) {
    let timer, controlador;
    const cargar = async () => {
      const url = new URL(location.href);
      url.search = new URLSearchParams(new FormData(filtros)).toString();
      controlador?.abort(); controlador = new AbortController();
      resultados.classList.add("loading");
      try {
        const r = await fetch(url, { signal: controlador.signal, headers: { "X-Requested-With": "fetch" } });
        const doc = new DOMParser().parseFromString(await r.text(), "text/html");
        const nuevo = $("#resultados", doc);
        if (nuevo) { resultados.innerHTML = nuevo.innerHTML; const c = $(".count", doc); const actual = $(".list-heading .count"); if (c && actual) actual.textContent = c.textContent; history.replaceState(null, "", url); }
      } catch (e) { if (e.name !== "AbortError") filtros.submit(); }
      resultados.classList.remove("loading");
    };
    filtros.addEventListener("submit", (e) => { e.preventDefault(); cargar(); });
    $("input[name=q]", filtros)?.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(cargar, 300); });
    $$("select", filtros).forEach((s) => s.addEventListener("change", cargar));
  }

  // Panel: contadores animados y gráficas
  $$("[data-count]").forEach((el) => {
    const meta = parseFloat(el.dataset.count), dec = parseInt(el.dataset.dec || "0", 10);
    if (!isFinite(meta) || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t0 = performance.now(), dur = 700;
    const paso = (t) => { const k = Math.min(1, (t - t0) / dur); el.textContent = (meta * (1 - Math.pow(1 - k, 3))).toFixed(dec); if (k < 1) requestAnimationFrame(paso); };
    requestAnimationFrame(paso);
  });

  const datosEl = $("#datos-panel");
  if (datosEl) window.addEventListener("load", () => {
    if (!window.Chart) return;
    const D = JSON.parse(datosEl.textContent);
    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const charts = [];
    const crear = () => {
      charts.splice(0).forEach((c) => c.destroy());
      const ink = css("--muted"), grid = css("--line");
      Chart.defaults.font.family = '"Inter","Segoe UI",sans-serif'; Chart.defaults.color = ink;
      const ejes = { x: { grid: { display: false }, ticks: { maxRotation: 0 } }, y: { beginAtZero: true, grid: { color: grid }, ticks: { precision: 0 } } };
      const prio = [css("--c-inm"), css("--c-alta"), css("--c-media"), css("--c-baja")];
      const corto = function (v) { const l = this.getLabelForValue(v); return l.length > 24 ? l.slice(0, 23) + "…" : l; };
      charts.push(new Chart($("#ch-dias"), { type: "line", data: { labels: D.dias, datasets: [
        { label: "Todos", data: D.creados, borderColor: "#2f8f83", backgroundColor: "rgba(47,143,131,.16)", fill: true, tension: .35, pointRadius: 3 },
        { label: "Críticos", data: D.criticos, borderColor: css("--c-inm"), backgroundColor: "transparent", tension: .35, pointRadius: 3, borderDash: [5, 4] }] },
        options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: ejes, interaction: { mode: "index", intersect: false } } }));
      charts.push(new Chart($("#ch-prioridad"), { type: "doughnut", data: { labels: Object.keys(D.prioridad), datasets: [{ data: Object.values(D.prioridad), backgroundColor: prio, borderColor: css("--surface"), borderWidth: 3 }] },
        options: { maintainAspectRatio: false, cutout: "66%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } } } } }));
      const barra = (id, obj, color, horizontal) => charts.push(new Chart($(id), { type: "bar", data: { labels: Object.keys(obj), datasets: [{ data: Object.values(obj), backgroundColor: color, borderRadius: 6, maxBarThickness: 22 }] },
        options: { indexAxis: horizontal ? "y" : "x", maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: horizontal ? { x: ejes.y, y: { grid: { display: false }, ticks: { callback: corto } } } : { ...ejes, x: { grid: { display: false }, ticks: { autoSkip: false, maxRotation: 35, callback: corto } } } } }));
      barra("#ch-categorias", D.categorias, "#2f8f83", true);
      barra("#ch-zonas", D.zonas, css("--c-media"), true);
      barra("#ch-resp", D.responsables, css("--green"), true);
      barra("#ch-estados", D.estados, ["#e2a13a", "#9b6fcb", "#4aa0b8", css("--c-media"), "#3d9a66"], false);
    };
    crear();
    document.addEventListener("temacambiado", crear);
  });
})();
