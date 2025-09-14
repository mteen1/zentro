"""zentro models."""

import pkgutil
from pathlib import Path


app_names = [
    "db",
    "project_manager",
]


def load_all_models() -> None:
    """Load all models from this folder."""
    # Load models from zentro.db.models
    db_models_dir = Path(__file__).resolve().parent
    for module_info in pkgutil.walk_packages(
        path=[str(db_models_dir)],
        prefix="zentro.db.models.",
    ):
        if not module_info.name.endswith('__init__'):
            __import__(module_info.name)

    # Load models from other app modules
    project_root = Path(__file__).resolve().parent.parent.parent
    for app in app_names:
        app_models_path = project_root / app / "models"
        print(f"app models path is {app_models_path}")
        if app_models_path.exists():
            for module_info in pkgutil.walk_packages(
                path=[str(app_models_path)],
                prefix=f"zentro.{app}.models.",
            ):
                if not module_info.name.endswith('__init__'):
                    __import__(module_info.name)
