const $ = (id) => document.getElementById(id);
const grid = $("grid"), summary = $("summary"), err = $("err");

function params() {
  return {
    base: $("base").value.trim(),
    subcarpeta: $("subcarpeta").value,
    clase: $("clase").value,
    fecha: $("fecha").value.trim(),
    lote: $("lote").value.trim(),
    angulo: $("angulo").value.trim()
  };
}

async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); if (j.error) msg += `: ${j.error}`; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

function card(item) {
  return `
    <article class="card">
      <a href="${item.url}" target="_blank" rel="noopener">
        <img src="${item.url}" alt="${item.name}" />
      </a>
      <div class="meta">
        <label class="chk">
          <input type="checkbox" class="sel" data-name="${item.name}"/>
          <span>${item.name}</span>
        </label>
        <div class="arrow">→</div>
        <div class="new">${item.proposed}</div>
      </div>
    </article>
  `;
}

function collectSelected() {
  return Array.from(document.querySelectorAll(".sel:checked")).map(x => x.dataset.name);
}

// Elegir carpeta
$("btn-pick").addEventListener("click", async () => {
  err.textContent = "";
  try {
    const { ok, base, error } = await post("/api/pick-base", {});
    if (ok && base) { $("base").value = base; }
    else { alert(error || "No se pudo abrir el selector de carpetas."); }
  } catch (e) { alert("No se pudo abrir el selector de carpetas. " + e.message); }
});

// Abrir carpeta
$("btn-open").addEventListener("click", async () => {
  const folder = $("base").value.trim();
  if (!folder) return;
  try { await post("/api/open-folder", { folder }); } catch {}
});

$("btn-list").addEventListener("click", async (e) => {
  e.preventDefault(); err.textContent = ""; grid.innerHTML = "Cargando vista previa…";
  $("btn-rename").disabled = true;
  try {
    const data = await post("/api/list", params());
    if (data.count === 0) { grid.innerHTML = "<p>No hay imágenes.</p>"; summary.textContent = ""; return; }
    grid.innerHTML = `
      <div class="toolbar">
        <button id="sel-all" type="button">Seleccionar todo</button>
        <button id="sel-none" type="button">Quitar selección</button>
      </div>
      <div class="cards">${data.items.map(card).join("")}</div>`;
    summary.textContent = `Carpeta: ${data.folder} | Imágenes: ${data.count}`;
    $("btn-rename").disabled = false;
    $("sel-all").onclick  = () => document.querySelectorAll(".sel").forEach(chk => chk.checked = true);
    $("sel-none").onclick = () => document.querySelectorAll(".sel").forEach(chk => chk.checked = false);
  } catch (e) { err.textContent = "Error: " + e.message; grid.innerHTML = ""; }
});

$("btn-rename").addEventListener("click", async (e) => {
  e.preventDefault(); err.textContent = "";
  const selected = collectSelected();
  if (selected.length === 0) { alert("Selecciona al menos una imagen."); return; }
  try {
    const data = await post("/api/rename-selected", {...params(), selected});
    alert(`Renombrados: ${data.renamed} | Omitidos: ${data.skipped} | Errores: ${data.errors}`);
    $("btn-list").click();
  } catch (e) { err.textContent = "Error: " + e.message; }
});
