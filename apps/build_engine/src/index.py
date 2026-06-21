from clone import clone_repo
from detect import detect
from builder import build
import shutil
import os
import stat


def remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_pipeline(project_id: str, repo_url: str, docker_username: str) -> dict:
    repo_path = None

    try:
        print(f"[1/3] Cloning {repo_url}...")
        repo_path = clone_repo(project_id, repo_url)

        print("[2/3] Detecting framework...")
        detected = detect(repo_path)

        print(f"      → {detected['framework']} on port {detected['port']}")

        print("[3/3] Building and pushing image...")

        image_repository = f"{docker_username}/{project_id}"

        build_result = build(
            repo_path=repo_path,
            detection=detected,
            image_repository=image_repository,
            tag="latest",
        )

        print(f"      → pushed {build_result['image']}")

        return {
            "image_tag": build_result["image"],
            "image": build_result["image"],
            "framework": detected["framework"],
            "port": detected["port"],
            "start_command": detected.get("start_command"),
            "build_command": detected.get("build_command"),
        }

    except Exception as e:
        print(f"Pipeline failed: {e}")
        raise

    finally:
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path, onerror=remove_readonly)
            print(f"Cleaned up {repo_path}")


if __name__ == "__main__":
    result = run_pipeline(
        project_id="test-123",
        repo_url="https://github.com/BStok/deployment-test-repo",
        docker_username="sanyagupta",
    )
    print(result)