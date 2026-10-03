import argparse
import json
import shutil
import socket
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deployer"))
import deploy


def check_sample(name):
    identifier = f"mini-deployer-test-{uuid.uuid4().hex[:12]}"
    deploy.IMAGE_NAME = identifier
    deploy.CURRENT_CONTAINER = f"{identifier}-current"
    deploy.CANDIDATE_CONTAINER = f"{identifier}-candidate"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="mini-deployer-") as directory:
        app_path = Path(directory) / name
        shutil.copytree(ROOT / name, app_path, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", "node_modules", "bin", "obj", ".git"))
        try:
            if not deploy.deploy(app_path, port, 8080, "http", "/health"):
                raise RuntimeError(f"Deployment failed: {name}")
            for endpoint, expected in (("/", {"message": "Hello Deploy"}),
                                       ("/health", {"status": "ok"})):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{endpoint}", timeout=5) as response:
                    if json.load(response) != expected:
                        raise AssertionError(f"Unexpected response: {name}{endpoint}")
            request = urllib.request.Request(f"http://127.0.0.1:{port}/echo",
                data=b'{"message":"smoke"}', headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                if json.load(response) != {"received": "smoke"}:
                    raise AssertionError(f"Unexpected echo response: {name}")
            print(f"PASS: {name}", flush=True)
        finally:
            for container in (deploy.CANDIDATE_CONTAINER, deploy.CURRENT_CONTAINER):
                deploy.remove_container(container)
            result = deploy.run_docker(["image", "rm", identifier])
            if result.returncode:
                print(f"Test image cleanup failed: {result.stderr}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", nargs="*", default=[
        "sample-app", "sample-express-app", "sample-aspnetcore-app"])
    args = parser.parse_args()
    allowed = {"sample-app", "sample-express-app", "sample-aspnetcore-app"}
    if any(name not in allowed for name in args.samples):
        parser.error("Choose sample-app, sample-express-app or sample-aspnetcore-app")
    for sample in args.samples:
        check_sample(sample)
