// ====== CONFIGURA AQUÍ TU BACKEND ======
const API_BASE = "https://cambiar-nombre.onrender.com"; // <-- tu URL de Render
// =======================================

const $ = (id) => document.getElementById(id);
const err = $("err"), summary = $("summary"), msg = $("msg"), upMsg = $("upMsg"), grid = $("preview");

// Helpers fetch con mensajes de error detallados
async function postJSON(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body),
  });
  const txt = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${txt}`);
  return JSON.parse(txt);
}
async function postForm(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData });
  const txt = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${txt}`);
  return JSON.parse(txt);
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

async function downloadBlobToDisk(blob, suggestedName) {
  // Si el navegador soporta File System Access API, permitimos elegir ubicación
  if (window.showSaveFilePicker) {
    try {
      const handle = await showSaveFilePicker({
        suggestedName,
        types: [{ description: "ZIP file", accept: { "application/zip": [".zip"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    } catch (e) {
      console.warn("showSaveFilePicker cancelado o falló, usando enlace", e);
    }
  }
  // Fallback: descargar con un enlace invisible
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName || "descarga.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function downloadSelectedZip(subcarpeta, selected) {
  const res = await fetch(`${API_BASE}/api/download-selected`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subcarpeta, selected }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const name = `${subcarpeta}_seleccionadas.zip`;
  await downloadBlobToDisk(blob, name);
}

async function downloadAllZip(subcarpeta) {
  const res = await fetch(`${API_BASE}/api/download-all?subcarpeta=${encodeURIComponent(subcarpeta)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const name = `${subcarpeta}_completo.zip`;
  await downloadBlobToDisk(blob, name);
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
  $("btnDownloadSel").disabled = true;

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
    $("btnDownloadSel").disabled = false;

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

// 4) Descargas
$("btnDownloadSel").addEventListener("click", async () => {
  err.textContent = ""; msg.textContent = "Preparando ZIP…";
  try {
    const selected = selectedNames();
    if (selected.length === 0) {
      msg.textContent = ""; alert("Selecciona al menos una imagen.");
      return;
    }
    await downloadSelectedZip($("sub").value, selected);
    msg.textContent = "Descarga lista.";
  } catch (e) {
    msg.textContent = ""; err.textContent = "Error al descargar: " + e.message;
  }
});

$("btnDownloadAll").addEventListener("click", async () => {
  err.textContent = ""; msg.textContent = "Preparando ZIP…";
  try {
    await downloadAllZip($("sub").value);
    msg.textContent = "Descarga lista.";
  } catch (e) {
    msg.textContent = ""; err.textContent = "Error al descargar: " + e.message;
  }
});
