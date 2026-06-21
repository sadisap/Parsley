# clone a project of medium size from a public github urlbut while /

import subprocess
import os
from pathlib import Path

BUILD_DIR = Path(os.getenv("BUILD_DIR", "apps/build-engine/builds"))
MAX_SIZE_MB = 500

def clone_repo(project_id: str, repo_url: str) -> Path:
    dest = BUILD_DIR / project_id

    if dest.exists():
        raise Exception(f"Build directory already exists for {project_id}")

    # Shallow clone — faster, no git history
    subprocess.run(
        ["git", "clone", "--depth=1", repo_url, str(dest)],
        check=True
    )

    # Size check
    size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        import shutil
        shutil.rmtree(dest)
        raise Exception(f"Repo too large: {size_mb:.1f}MB (max {MAX_SIZE_MB}MB)")

    return dest

