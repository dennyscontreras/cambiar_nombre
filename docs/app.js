// ====== CONFIGURA AQUÍ TU BACKEND ======
const API_BASE = "https://cambiar-nombre.onrender.com"; // tu URL de Render
// =======================================

const $ = (id) => document.getElementById(id);
const err = $("err"), summary = $("summary"), msg = $("msg"), upMsg = $("upMsg"), grid = $("preview");

async function postJSON(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
async function postForm(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
function card(item) {
  return `
    <article class="card img-card">
      <a href="${API_BASE}${item.url}" target="_blank" rel="noopener">
        <img loading="lazy" src="${API_BASE}${item.url}" alt="${item.name}" />
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
function selectedNames() {
  return Array.from(document.querySelectorAll(".sel:checked")).map(x => x.dataset.name);
}

// 1) Subir
$("btnUpload").addEventListener("click", async () => {
  err.textContent = ""; upMsg.textContent = "Subiendo…";
  try {
    const files = $("files").files;
    if (!files || files.length === 0) { upMsg.textContent = "Selecciona archivos"; return; }
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    fd.append("subcarpeta", $("subUp").value);

    const res = await postForm("/api/upload", fd);
    upMsg.textContent = `OK: ${res.saved.length} archivo(s) en ${res.folder}`;
  } catch (e) {
    upMsg.textContent = ""; err.textContent = "Error al subir: " + e.message;
  }
});

// 2) Vista previa
$("btnList").addEventListener("click", async () => {
  err.textContent = ""; msg.textContent = ""; grid.innerHTML = "Cargando…";
  $("btnRename").disabled = true;

  const payload = {
    subcarpeta: $("sub").value,
    clase: $("clase").value,
    fecha: $("fecha").value.trim(),
    lote: $("lote").value.trim(),
    angulo: $("angulo").value.trim(),
  };

  try {
    const data = await postJSON("/api/list", payload);
    if (data.count === 0) {
      grid.innerHTML = "<p>No hay imágenes en esa subcarpeta. Sube primero 👆</p>";
      summary.textContent = "";
      return;
    }
    grid.innerHTML = `
      <div class="toolbar">
        <button id="selAll" type="button">Seleccionar todo</button>
        <button id="selNone" type="button">Quitar selección</button>
      </div>
      <div class="cards">${data.items.map(card).join("")}</div>
    `;
    summary.textContent = `Carpeta: ${data.folder} | Imágenes: ${data.count}`;
    $("btnRename").disabled = false;

    $("selAll").onclick  = () => document.querySelectorAll(".sel").forEach(chk => chk.checked = true);
    $("selNone").onclick = () => document.querySelectorAll(".sel").forEach(chk => chk.checked = false);
  } catch (e) {
    grid.innerHTML = ""; err.textContent = "Error al listar: " + e.message;
  }
});

// 3) Renombrar
$("btnRename").addEventListener("click", async () => {
  err.textContent = ""; msg.textContent = "Renombrando…";
  const selected = selectedNames();
  if (selected.length === 0) { msg.textContent = ""; alert("Selecciona al menos una imagen."); return; }

  const payload = {
    subcarpeta: $("sub").value,
    clase: $("clase").value,
    fecha: $("fecha").value.trim(),
    lote: $("lote").value.trim(),
    angulo: $("angulo").value.trim(),
    selected
  };

  try {
    const res = await postJSON("/api/rename-selected", payload);
    msg.textContent = `OK: ${res.renamed} | Omitidas: ${res.skipped} | Errores: ${res.errors}`;
    $("btnList").click(); // refrescar preview
  } catch (e) {
    msg.textContent = ""; err.textContent = "Error al renombrar: " + e.message;
  }
});
