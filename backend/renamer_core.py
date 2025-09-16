# backend/renamer_core.py
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Optional, Set

# Ruta por defecto (ajústala si quieres otro valor inicial)
DEFAULT_BASE = Path(r"C:/Users/PC/Desktop/tesis/dataset")

# Extensiones válidas
VALID_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

# Detecta numeración final _NNN
PATRON = re.compile(r".*?_(\d{3})\.[^.]+$", re.IGNORECASE)

# Subcarpetas canónicas (sin tilde) pero aceptamos entradas con tildes o espacios
ALIASES = {
    "Util": {"util", "Util", "UTIL", "Útil", "útil"},
    "No_util": {
        "no util", "No util", "no_util", "No_util", "NO_UTIL",
        "No_útil", "no_útil"
    },
}

@dataclass
class RenameParams:
    base: Path
    subcarpeta: str      # "Util" | "No_util" (o variantes)
    clase: str           # "UTIL" | "NO_UTIL"
    fecha: str           # YYYYMMDD
    lote: str            # p.ej. Lote01
    angulo: str          # p.ej. Frontal | Sup | Ang45

@dataclass
class RenamePlanItem:
    src: Path
    dst: Path

# ---------------- Utilidades de normalización ---------------- #

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm_name(s: str) -> str:
    s = strip_accents(s).lower().replace("-", "_").replace(" ", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")

def _canon_from_input(user_input: str) -> str:
    n = norm_name(user_input)
    for canon, opts in ALIASES.items():
        if n in {norm_name(o) for o in opts}:
            return canon
    return user_input  # dejar tal cual si no coincide

# ---------------- Resolución de carpeta ---------------- #

def resolve_subfolder(base: Path, user_input: str) -> Path:
    """
    Soporta dos usos:
      1) base = ruta del dataset (padre)  + subcarpeta en 'user_input'
      2) base = ruta que YA es 'Util' o 'No_util' (con/sin tilde) -> se usa tal cual
    """
    base = base.resolve()

    # Caso 2: la propia base ya es una subcarpeta (util/no_util)
    last = norm_name(base.name)
    if last in {"util", "no_util"}:
        return base

    # Caso 1: partir del dataset padre y aplicar la subcarpeta elegida
    target = _canon_from_input(user_input)  # "Util" o "No_util" (canónico)
    if not base.exists():
        # dataset no existe: construir ruta directa
        return base / target

    # Buscar una carpeta hija que coincida por nombre normalizado
    for p in base.iterdir():
        if p.is_dir() and norm_name(p.name) == norm_name(target):
            return p

    # Si no existe, devolver la canónica a crear
    return base / target

# ---------------- Núcleo de renombrado ---------------- #

def list_images(folder: Path, valid_exts: Iterable[str] = None) -> List[Path]:
    valid = set(valid_exts or VALID_EXTS)
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix in valid]
    files.sort(key=lambda p: p.name.lower())
    return files

def build_plan(params: RenameParams) -> List[RenamePlanItem]:
    """
    Genera el plan de renombrado **reiniciando SIEMPRE en 001**.
    Si existe colisión con un nombre ya presente, avanza hasta encontrar el siguiente libre.
    """
    folder = resolve_subfolder(params.base, params.subcarpeta)
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)

    files = list_images(folder)
    plan: List[RenamePlanItem] = []

    # ¡Siempre empezar en 1!
    for i, src in enumerate(files, start=1):
        ext = src.suffix.lower()
        new_name = f"{params.clase}_{params.fecha}_{params.lote}_{params.angulo}_{i:03d}{ext}"
        dst = folder / new_name

        # Si ya existe ese destino, buscar el siguiente libre
        j = i
        while dst.exists():
            j += 1
            new_name = f"{params.clase}_{params.fecha}_{params.lote}_{params.angulo}_{j:03d}{ext}"
            dst = folder / new_name

        # Si ya está con el nombre final, no lo añadimos al plan
        if src.name == dst.name:
            continue

        plan.append(RenamePlanItem(src=src, dst=dst))

    return plan

def execute_plan(plan: Sequence[RenamePlanItem], only_names: Optional[Set[str]] = None) -> Tuple[int, int, int]:
    """
    Ejecuta el plan. Si only_names se pasa, solo renombra aquellos cuyo src.name esté en el conjunto.
    Devuelve (ok, err, skip).
    """
    ok = err = skip = 0
    for item in plan:
        if only_names is not None and item.src.name not in only_names:
            skip += 1
            continue
        if item.src.name == item.dst.name:
            skip += 1
            continue
        try:
            item.src.rename(item.dst)
            ok += 1
        except Exception:
            err += 1
    return ok, err, skip
