"""Run Alembic without treating macOS AppleDouble sidecars as Python migrations."""
from pathlib import Path
import shutil
import sys
import tempfile
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    target = sys.argv[2] if len(sys.argv) > 2 else "head"
    if action not in {"upgrade", "downgrade"}:
        raise SystemExit("Usage: python migrate.py [upgrade|downgrade] [revision]")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("version_path_separator", "os")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    with tempfile.TemporaryDirectory(prefix="inteam-migrations-") as temporary:
        for path in (ROOT / "alembic/versions").glob("*.py"):
            if not path.name.startswith("._"):
                shutil.copyfile(path, Path(temporary) / path.name)
        config.set_main_option("version_locations", temporary)
        getattr(command, action)(config, target)


if __name__ == "__main__":
    main()
