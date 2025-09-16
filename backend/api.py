# backend/api.py
from pathlib import Path
from datetime import timedelta

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# IMPORT RELATIVO (asegúrate de tener backend/__init__.py VACÍO)
from .renamer_core import (
    RenameParams, build_plan, execute_plan,
    resolve_subfolder, list_images
)

# --------------------------------------------------------------------------------------
# Paths (funciona igual en local y en Render)
# --------------------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

# Directorio de trabajo para archivos subidos (en Render es disco efímero)
WORK_DIR = (PROJECT_ROOT / "uploads").resolve()
WORK_DIR.mkdir(parents=True, exist_ok=True)


def _safe_under_work_dir(p: Path) -> bool:
    """Asegura que p esté dentro de WORK_DIR (evita path traversal)."""
    try:
        rp = p.resolve()
    except Exception:
        return False
    return WORK_DIR == rp or WORK_DIR in rp.parents


def _ensure_rel_path(rel: str) -> Path:
    """
    Acepta rutas relativas tipo 'Util/imagen.jpg' o 'No_util/imagen.png'.
    Rechaza absolutas y '../'.
    """
    if not rel or rel.strip() == "":
        raise ValueError("ruta vacía")
    if ":" in rel or rel.startswith("/") or rel.startswith("\\"):
        raise ValueError("ruta absoluta no permitida")
    rel = rel.replace("\\", "/")
    parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    return WORK_DIR.joinpath(*parts)


# --------------------------------------------------------------------------------------
# Flask app + CORS
# --------------------------------------------------------------------------------------
app = Flask(__name__)

# CORS explícito para frontends estáticos (GitHub Pages / Vercel / Netlify)
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"],
    max_age=timedelta(hours=1),
)


# --------------------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------------------
@app.get("/")
def root():
    """Home mínima para verificar despliegue."""
    return jsonify({
        "status": "ok",
        "message": "Cambiar Nombre API (Render)",
        "endpoints": [
            "/api/upload",
            "/api/list",
            "/api/rename-selected",
            "/api/image?path=<rel>"
        ],
        "work_dir": str(WORK_DIR)
    })


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "work_dir": str(WORK_DIR)})


# ----------------------------- SUBIR ARCHIVOS -----------------------------------------
@app.post("/api/upload")
def upload_files():
    """
    Subida vía multipart/form-data:
      - Campo 'files' (puede haber varios): files=@img1.jpg, files=@img2.png
      - Campo 'subcarpeta' (opcional): 'Util' o 'No_util' (por defecto 'Util').

    Guarda en WORK_DIR/<subcarpeta> y devuelve los nombres guardados.
    """
    sub = request.form.get("subcarpeta", "Util")
    target_folder = resolve_subfolder(WORK_DIR, sub)
    target_folder.mkdir(parents=True, exist_ok=True)

    files = request.files.getlist("files") or request.files.getlist("files[]")
    if not files:
        return jsonify({"ok": False, "error": "No files received"}), 400

    saved = []
    for f in files:
        filename = secure_filename(f.filename)
        if not filename:
            continue
        dst = target_folder / filename

        # Evitar colisiones: nombre (1), (2), ...
        stem, suf = dst.stem, dst.suffix
        k = 1
        while dst.exists():
            dst = target_folder / f"{stem}({k}){suf}"
            k += 1

        f.save(dst)
        saved.append({
            "name": dst.name,
            "rel_path": f"{target_folder.name}/{dst.name}"
        })

    return jsonify({"ok": True, "folder": str(target_folder), "saved": saved})


# ----------------------------- LISTA / PREVIEW ----------------------------------------
@app.post("/api/list")
def api_list():
    """
    JSON esperado:
      {
        "subcarpeta": "Util" | "No_util",
        "clase": "UTIL" | "NO_UTIL",
        "fecha": "YYYYMMDD",
        "lote": "Lote01",
        "angulo": "Frontal"
      }
    Trabaja SIEMPRE sobre WORK_DIR (donde guardó /api/upload).
    """
    data = request.get_json(force=True)
    sub = data.get("subcarpeta", "Util")

    params = RenameParams(
        base=WORK_DIR,
        subcarpeta=sub,
        clase=(data.get("clase") or "UTIL").strip().upper().replace(" ", "_"),
        fecha=(data.get("fecha") or "").strip(),
        lote=(data.get("lote") or "").strip(),
        angulo=(data.get("angulo") or "").replace(" ", "")
    )

    folder = resolve_subfolder(WORK_DIR, sub)
    if not folder.exists():
        # No hay nada subido todavía a esa subcarpeta
        return jsonify({"folder": str(folder), "count": 0, "items": []})

    imgs = list_images(folder)  # archivos válidos .jpg/.png etc.
    plan = {item.src.name: item.dst.name for item in build_plan(params)}

    items = []
    for f in imgs:
        rel = f"{folder.name}/{f.name}"  # relativo a WORK_DIR
        items.append({
            "name": f.name,
            "proposed": plan.get(f.name, f.name),
            "url": f"/api/image?path={rel}"
        })

    return jsonify({"folder": str(folder), "count": len(items), "items": items})


# ----------------------------- ENTREGAR IMAGEN ----------------------------------------
@app.get("/api/image")
def api_image():
    """
    Sirve una imagen por ruta relativa: ?path=Util/imagen.jpg
    Seguridad: solo dentro de WORK_DIR; rechaza absolutas y '..'.
    """
    rel = request.args.get("path", "")
    try:
        p = _ensure_rel_path(rel)
    except Exception as e:
        return (f"Bad Request: {e}", 400)

    if not _safe_under_work_dir(p):
        return ("Forbidden", 403)
    if not p.exists() or not p.is_file():
        return ("Not Found", 404)

    return send_file(p)


# ----------------------------- RENOMBRAR SELECCIONADAS --------------------------------
@app.post("/api/rename-selected")
def api_rename_selected():
    """
    JSON esperado:
      {
        "subcarpeta": "Util" | "No_util",
        "clase": "UTIL",
        "fecha": "20250818",
        "lote": "Lote01",
        "angulo": "Frontal",
        "selected": ["img1.jpg", "img2.png"]  # nombres tal como aparecen en /api/list
      }
    """
    data = request.get_json(force=True)
    sub = data.get("subcarpeta", "Util")
    selected = set(data.get("selected") or [])

    params = RenameParams(
        base=WORK_DIR,
        subcarpeta=sub,
        clase=(data.get("clase") or "UTIL").strip().upper().replace(" ", "_"),
        fecha=(data.get("fecha") or "").strip(),
        lote=(data.get("lote") or "").strip(),
        angulo=(data.get("angulo") or "").replace(" ", "")
    )

    plan = build_plan(params)
    ok, err, skip = execute_plan(plan, only_names=selected)

    return jsonify({"renamed": ok, "errors": err, "skipped": skip})
