# backend/api.py
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# 👇 IMPORT RELATIVO (necesita backend/__init__.py vacío)
from .renamer_core import (
    RenameParams, build_plan, execute_plan,
    resolve_subfolder, list_images
)

# ---------- Paths ----------
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

# ---------- App ----------
app = Flask(__name__)
CORS(app)

@app.get("/")
def root():
    return jsonify({
        "status": "ok",
        "message": "Cambiar Nombre API (Render)",
        "endpoints": ["/api/upload", "/api/list", "/api/rename-selected", "/api/image?path=<rel>"]
    })

@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "work_dir": str(WORK_DIR)})

# ---------- Upload ----------
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
        stem, suf = dst.stem, dst.suffix
        k = 1
        while dst.exists():
            dst = target_folder / f"{stem}({k}){suf}"
            k += 1
        f.save(dst)
        saved.append({"name": dst.name, "rel_path": f"{target_folder.name}/{dst.name}"})
    return jsonify({"ok": True, "folder": str(target_folder), "saved": saved})

# ---------- List/preview ----------
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
    items = [{
        "name": f.name,
        "proposed": plan.get(f.name, f.name),
        "url": f"/api/image?path={folder.name}/{f.name}"
    } for f in imgs]
    return jsonify({"folder": str(folder), "count": len(items), "items": items})

# ---------- Serve image ----------
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

# ---------- Rename selected ----------
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
