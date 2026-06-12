"""Runtime helpers for the KETCHUP real bridge.

KETCHUP (the ``ktools`` package) ships no PyPI release — upstream is run by
inserting its ``src`` directory onto ``sys.path``.  We mirror that here: the
package vendors a copy of the ``ktools`` source under ``third_party/`` (so the
bridge is offline-reproducible) and exposes a single :func:`ensure_ketchup`
entry point that makes it importable and returns the resolved paths the
bridge needs.

If the vendored copy is missing (e.g. a slimmed-down wheel), ``ensure_ketchup``
falls back to cloning the upstream repository into a user cache directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

UPSTREAM_URL = "https://github.com/maranasgroup/KETCHUP.git"

# repo root = parent of the pbg_ketchup package directory
_PKG_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_DIR.parent


def _candidate_ktools_roots() -> list[Path]:
    """Directories that may contain an importable ``ktools`` package."""
    roots = [
        _REPO_ROOT / "third_party",                       # vendored (preferred)
        _REPO_ROOT / "third_party" / "KETCHUP" / "KETCHUP_main" / "src",
    ]
    cache = Path(os.environ.get("KETCHUP_CACHE",
                                Path.home() / ".cache" / "pbg-ketchup"))
    roots.append(cache / "KETCHUP" / "KETCHUP_main" / "src")
    return roots


def _clone_upstream(cache: Path) -> Path:
    import subprocess

    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / "KETCHUP"
    if not (dest / "KETCHUP_main" / "src" / "ktools").is_dir():
        subprocess.run(
            ["git", "clone", "--depth", "1", UPSTREAM_URL, str(dest)],
            check=True,
        )
    return dest / "KETCHUP_main" / "src"


def ensure_ketchup() -> Path:
    """Make ``ktools`` importable and return the directory it lives under.

    Raises
    ------
    RuntimeError
        If ``ktools`` can be neither located in a vendored/cache location nor
        cloned from upstream.
    """
    for root in _candidate_ktools_roots():
        if (root / "ktools").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return root

    # last resort: clone upstream into the cache
    cache = Path(os.environ.get("KETCHUP_CACHE",
                                Path.home() / ".cache" / "pbg-ketchup"))
    try:
        root = _clone_upstream(cache)
    except Exception as exc:  # pragma: no cover - network dependent
        raise RuntimeError(
            "ktools (KETCHUP) source not found in vendored 'third_party/' and "
            f"could not clone {UPSTREAM_URL}: {exc}"
        ) from exc
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def solver_options_file() -> str:
    """Path to the vendored ipopt options file (tolerances, max_iter)."""
    return str(_REPO_ROOT / "third_party" / "ipopt.opt")


def dataset_dir(model_name: str) -> Path:
    """Directory holding the K-FIT model/mechanism/data xlsx for ``model_name``.

    Looks under the repo's ``datasets/<model_name>/`` first; honours
    ``KETCHUP_DATASETS`` as an override root.
    """
    override = os.environ.get("KETCHUP_DATASETS")
    base = Path(override) if override else (_REPO_ROOT / "datasets")
    return base / model_name


# Canonical K-FIT filename triples for the (static) models shipped here.
BUNDLED_MODELS = {
    "k-ecoli74": {
        "filename_model": "k-ecoli74_model.xlsx",
        "filename_mechanism": "k-ecoli74_mechanism.xlsx",
        "filename_data": "k-ecoli74_data.xlsx",
    },
    "k-ecoli307": {
        "filename_model": "k-ecoli307_model.xlsx",
        "filename_mechanism": "k-ecoli307_mechanism.xlsx",
        "filename_data": "k-ecoli307_data.xlsx",
    },
}

# Dynamic (time-series) cell-free models from the KETCHUP time-series paper
# (Hu, Jilani, Olson & Maranas, PLOS Comput Biol 2025). Each fits an enzyme's
# kinetic parameters to a measured NADH(t) trajectory via the 'strainer'
# time-course data format and a custom rate law.
BUNDLED_DYNAMIC_MODELS = {
    "FDH": {  # formate dehydrogenase: NAD+ + HCOO- -> CO2 + NADH
        "filename_model": "FDH_model.xlsx",
        "filename_mechanism": "FDH_mechanism.xlsx",
        "filename_data": "FDH_dataset_series_A1.xlsx",
        "target_species": "nadh",
        "strainer_header": {
            "t_0": ["fdh", "23bdo", "actn", "nad", "formate", "nadh", "co2"],
            "time": ["nadh"],
            "type": ["e", "c", "c", "c", "c", "c", "c", "c"],
            "status": ["i", "g", "g", "i", "i", "i", "i", "d"],
        },
    },
    "BDH": {  # 2,3-butanediol dehydrogenase: acetoin + NADH -> 23BD + NAD+
        "filename_model": "BDH_model.xlsx",
        "filename_mechanism": "BDH_mechanism.xlsx",
        "filename_data": "BDH_dataset_series_Z1.xlsx",
        "target_species": "nadh",
        "strainer_header": {
            "t_0": ["bdh", "23bdo", "actn", "nad", "formate", "nadh", "pyr"],
            "time": ["nadh"],
            "type": ["e", "c", "c", "c", "c", "c", "c", "c"],
            "status": ["i", "g", "g", "i", "i", "i", "i", "d"],
        },
    },
}
