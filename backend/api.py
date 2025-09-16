from pathlib import Path
from datetime import timedelta, datetime
from io import BytesIO
import zipfile

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import relativo (backend/__init__.py debe existir y estar vacío)
from .renamer_core import (
    RenameParams, build_plan, execute_plan,
    resolve_subfolder, list_images
)

# -------------------- Paths --------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
WORK_DIR = (PROJECT_ROOT / "uploads").resolve()
WORK_DIR.mkdir(parents=True, exist_ok=True)


def _safe_under_work_dir(p: Path) -> bool:
    try:
        rp = p.resolve()
    except Exception:
        return False
    return WORK_DIR == rp or WORK_DIR in rp.parents


def _ensure_rel_path(rel: str) -> Path:
    if not rel or rel.strip() == "":
        raise ValueError("ruta vacía")
    if ":" in rel or rel.startswith("/") or rel.startswith("\\"):
        raise ValueError("ruta absoluta no permitida")
    rel = rel.replace("\\", "/")
    parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    return WORK_DIR.joinpath(*parts)


# -------------------- App & CORS --------------------
app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"],
    max_age=timedelta(hours=1),
)


# -------------------- Endpoints --------------------
@app.get("/")
def root():
    return jsonify({
        "status": "ok",
        "message": "Cambiar Nombre API (Render)",
        "endpoints": [
            "/api/upload",
            "/api/list",
            "/api/rename-selected",
            "/api/image?path=<rel>",
            "/api/download-selected",
            "/api/download-all?subcarpeta=Util|No_util"
        ],
        "work_dir": str(WORK_DIR)
    })


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "work_dir": str(WORK_DIR)})


# --------- Subir ----------
@app.post("/api/upload")
def upload_files():
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

        # Evitar colisiones
        stem, suf = dst.stem, dst.suffix
        k = 1
        while dst.exists():
            dst = target_folder / f"{stem}({k}){suf}"
            k += 1

        f.save(dst)
        saved.append({"name": dst.name, "rel_path": f"{target_folder.name}/{dst.name}"})

    return jsonify({"ok": True, "folder": str(target_folder), "saved": saved})


# --------- Listar / Preview ----------
@app.post("/api/list")
def api_list():
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
        return jsonify({"folder": str(folder), "count": 0, "items": []})

    imgs = list_images(folder)
    plan = {item.src.name: item.dst.name for item in build_plan(params)}

    items = []
    for f in imgs:
        rel = f"{folder.name}/{f.name}"
        items.append({
            "name": f.name,
            "proposed": plan.get(f.name, f.name),
            "url": f"/api/image?path={rel}"
        })

    return jsonify({"folder": str(folder), "count": len(items), "items": items})


# --------- Servir imagen ----------
@app.get("/api/image")
def api_image():
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


# --------- Renombrar seleccionadas ----------
@app.post("/api/rename-selected")
def api_rename_selected():
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


# --------- Descargas (ZIP) ----------
def _zip_bytes(pairs):
    """
    pairs: lista de tuplas (Path absoluto, nombre dentro del zip)
    """
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arcname in pairs:
            if abs_path.exists() and abs_path.is_file():
                zf.write(abs_path, arcname)
    bio.seek(0)
    return bio


@app.post("/api/download-selected")
def download_selected():
    data = request.get_json(force=True)
    sub = data.get("subcarpeta", "Util")
    selected = list(data.get("selected") or [])
    folder = resolve_subfolder(WORK_DIR, sub)
    if not folder.exists():
        return ("Not Found", 404)

    pairs = []
    for name in selected:
        p = folder / name
        if _safe_under_work_dir(p) and p.exists():
            pairs.append((p, name))

    if not pairs:
        return jsonify({"ok": False, "error": "No hay archivos válidos para descargar"}), 400

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = f"{sub}_seleccionadas_{stamp}.zip"
    bio = _zip_bytes(pairs)
    return send_file(bio, download_name=fname, as_attachment=True, mimetype="application/zip")


@app.get("/api/download-all")
def download_all():
    sub = request.args.get("subcarpeta", "Util")
    folder = resolve_subfolder(WORK_DIR, sub)
    if not folder.exists():
        return ("Not Found", 404)

    files = list_images(folder)
    if not files:
        return jsonify({"ok": False, "error": "No hay imágenes"}), 400

    pairs = [(p, p.name) for p in files if _safe_under_work_dir(p)]
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = f"{sub}_completo_{stamp}.zip"
    bio = _zip_bytes(pairs)
    return send_file(bio, download_name=fname, as_attachment=True, mimetype="application/zip")
