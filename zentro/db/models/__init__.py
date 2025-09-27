"""zentro models."""

import pkgutil
from pathlib import Path

from zentro.settings import settings


def load_all_models() -> None:
    """Load all models from this folder."""
    # Load models from zentro.db.models
    db_models_dir = Path(__file__).resolve().parent
    for module_info in pkgutil.walk_packages(
        path=[str(db_models_dir)],
        prefix="zentro.db.models.",
    ):
        if not module_info.name.endswith("__init__"):
            __import__(module_info.name)

    project_root = Path(__file__).resolve().parent.parent.parent
    for app in settings.app_names:
        models_file = project_root / app / "models.py"
        if models_file.exists():
            module_name = f"zentro.{app}.models"
            __import__(module_name)
