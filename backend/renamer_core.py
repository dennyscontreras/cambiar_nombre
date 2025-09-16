from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from typing import Iterable, List, Tuple

# Extensiones válidas (se conservan mayúsculas por compatibilidad, pero normalizamos a .lower())
VALID_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

# Mapeo de subcarpetas permitidas (sin acentos)
ALIASES = {
    "Util": {"Util", "UTIL", "util"},
    "No_util": {"No_util", "no_util", "NO_UTIL", "No util", "no util"},
}

# Regex típico de nombres que terminan con _NNN.ext (no lo usamos para empezar en 1, queda por compatibilidad)
RE_INDEX = re.compile(r".*?_(\d{3})\.[^.]+$", re.IGNORECASE)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_name(s: str) -> str:
    s = strip_accents(s)
    s = s.lower().replace("-", "_").replace(" ", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def resolve_subfolder(base: Path, user_input: str) -> Path:
    """
    Devuelve la ruta a la subcarpeta canónica dentro de 'base' sin acentos.
    Si no existe, la crea. Acepta 'Util' o 'No_util' (sin tilde).
    """
    base.mkdir(parents=True, exist_ok=True)
    target_norm = norm_name(user_input or "Util")

    # Resolver alias
    for canon, opts in ALIASES.items():
        if target_norm in {norm_name(o) for o in opts}:
            sub = canon
            break
    else:
        # por si ingresan algo distinto: devolvemos el nombre que pusieron
        sub = user_input

    folder = base / sub
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_images(folder: Path) -> List[Path]:
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix in VALID_EXTS],
        key=lambda p: p.name.lower()
    )


@dataclass
class RenameParams:
    base: Path
    subcarpeta: str
    clase: str       # UTIL | NO_UTIL
    fecha: str       # YYYYMMDD
    lote: str        # Lote01
    angulo: str      # Frontal / Sup / Ang45

    @property
    def folder(self) -> Path:
        return resolve_subfolder(self.base, self.subcarpeta)


@dataclass
class PlanItem:
    src: Path
    dst: Path


def build_plan(params: RenameParams) -> List[PlanItem]:
    """
    Construye el plan de renombrado empezando SIEMPRE en 1 (001), sin importar nombres previos.
    """
    folder = params.folder
    files = list_images(folder)

    plan: List[PlanItem] = []
    idx = 1  # <- siempre comenzamos en 1
    used_names = set()

    for src in files:
        ext = src.suffix.lower()
        new_name = f"{params.clase}_{params.fecha}_{params.lote}_{params.angulo}_{idx:03d}{ext}"

        # Si por alguna razón ya existe un archivo con ese nombre, avanza hasta encontrar hueco
        while new_name in used_names or (folder / new_name).exists():
            idx += 1
            new_name = f"{params.clase}_{params.fecha}_{params.lote}_{params.angulo}_{idx:03d}{ext}"

        dst = folder / new_name
        plan.append(PlanItem(src=src, dst=dst))
        used_names.add(new_name)
        idx += 1

    return plan


def execute_plan(plan: Iterable[PlanItem], only_names: Iterable[str] = None) -> Tuple[int, int, int]:
    """
    Ejecuta el plan de renombrado.
    - only_names: si se pasa, solo renombra aquellos cuyo src.name esté en esta lista.
    Devuelve (ok, err, skip).
    """
    ok = err = skip = 0
    only = set(only_names or [])

    for item in plan:
        if only and item.src.name not in only:
            skip += 1
            continue
        try:
            if item.src.name == item.dst.name:
                skip += 1
                continue
            item.src.rename(item.dst)
            ok += 1
        except Exception:
            err += 1

    return ok, err, skip
