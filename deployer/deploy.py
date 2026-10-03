import argparse
import subprocess
import time
import urllib.request
import socket
import sys
from pathlib import Path

from analyzer import analyze_project
from dockerfile_generator import generate_dockerfile

IMAGE_NAME = "sample-app"
CURRENT_CONTAINER = "sample-app-current"
CANDIDATE_CONTAINER = "sample-app-candidate"


def port_number(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def run_docker(arguments):
    try:
        return subprocess.run(
            ["docker", *arguments], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(["docker", *arguments], 1, "", str(error))


def tcp_health_check(port):
    for attempt in range(5):
        try:
            with socket.create_connection(
                ("127.0.0.1", port),
                timeout=2
            ):
                print("TCP health check success")
                return True

        except OSError as error:
            print(f"TCP health check retry {attempt + 1}/5")
            print(f"Reason: {error}")

        time.sleep(1)

    print("TCP health check failed")
    return False

def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex(("127.0.0.1", port))
        return result != 0

def find_available_port(start_port):
    port = start_port

    while port <= 65535:
        if is_port_available(port):
            return port

        port += 1

    return None

def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "app_path",
        help="Path to the web application"
    )

    parser.add_argument(
        "--port",
        type=port_number,
        default=8000,
        help="Host port for the deployed application"
    )

    parser.add_argument(
        "--health-path",
        default="/health",
        help="Health check endpoint"
    )

    parser.add_argument(
        "--container-port",
        type=port_number,
        default=8000,
        help="Port used inside the container"
    )

    parser.add_argument(
        "--health-mode",
        choices=["http", "root", "tcp"],
        default="http",
        help="Health check mode"
    )

    return parser.parse_args()

def resolve_app_path(app_path):
    path = Path(app_path).resolve()

    if not path.exists():
        print(f"App path does not exist: {path}")
        return None

    if not path.is_dir():
        print(f"App path is not a directory: {path}")
        return None

    return path

def build_image(app_path):
    print("\n[1] Building Docker image...")

    result = run_docker(
        [
            "build",
            "-t",
            IMAGE_NAME,
            str(app_path)
        ]
    )

    if result.returncode == 0:
        print("Docker image build success")
        return True

    print("Docker image build failed")
    print(result.stderr)
    return False

def remove_container(container_name):
    result = run_docker(
        [
            "rm",
            "-f",
            container_name
        ]
    )

    if result.returncode == 0:
        print(f"Container removed: {container_name}")
        return True

    if "No such container" in result.stderr:
        return True

    print(f"Failed to remove container: {container_name}")
    print(result.stderr)
    return False

def run_candidate(candidate_port, container_port):
    print("\n[2] Starting candidate container...")

    if not remove_container(CANDIDATE_CONTAINER):
        print("Candidate cleanup failed")
        return False

    result = run_docker(
        [
            "run",
            "-d",
            "-p",
            f"{candidate_port}:{container_port}",
            "--name",
            CANDIDATE_CONTAINER,
            IMAGE_NAME
        ]
    )

    if result.returncode == 0:
        print(f"Candidate started: localhost:{candidate_port}")
        return True

    print("Candidate container start failed")
    print(result.stderr)
    return False

def http_health_check(port, health_path):
    url = f"http://127.0.0.1:{port}{health_path}"

    print(f"\nHealth checking {url}")

    for attempt in range(5):
        try:
            with urllib.request.urlopen(
                url,
                timeout=2
            ) as response:
                if response.status == 200:
                    print("HTTP health check success")
                    return True

        except Exception as error:
            print(f"HTTP health check retry {attempt + 1}/5")
            print(f"Reason: {error}")

        time.sleep(1)

    print("HTTP health check failed")
    return False

def health_check(
    port,
    health_mode,
    health_path
):
    if health_mode == "tcp":
        return tcp_health_check(port)

    if health_mode == "root":
        return http_health_check(
            port,
            "/"
        )

    return http_health_check(
        port,
        health_path
    )

def run_current(current_port, container_port):
    print("\n[4] Starting current container...")

    result = run_docker(
        [
            "run",
            "-d",
            "-p",
            f"{current_port}:{container_port}",
            "--name",
            CURRENT_CONTAINER,
            IMAGE_NAME
        ]
    )

    if result.returncode == 0:
        print(f"Current container started: localhost:{current_port}")
        return True

    print("Current container start failed")
    print(result.stderr)
    return False

def deploy(
    app_path,
    current_port,
    container_port,
    health_mode,
    health_path
):

    candidate_port = find_available_port(current_port + 1)

    if candidate_port is None:
        print("No available candidate port found")
        return False

    print("==============================")
    print(" Mini Deployer")
    print("==============================")

    try:
        analysis = analyze_project(app_path)
    except (OSError, ValueError) as error:
        print(f"Project analysis failed: {error}")
        return False

    print("\n[0] Project Analysis")
    print(f"Language: {analysis['language']}")
    print(f"Framework: {analysis['framework']}")
    print(f"Dependency: {analysis['dependency_file']}")
    print(f"Entry Point: {analysis['entrypoint']}")
    print(f"Start Command: {analysis['start_command']}")
    print(f"Current host port: {current_port}")
    print(f"Candidate host port: {candidate_port}")
    print(f"Container port: {container_port}")

    if analysis["language"] is None:
        print("Unsupported project: language could not be detected")
        return False

    try:
        dockerfile_path = generate_dockerfile(app_path, analysis, container_port)
    except (OSError, ValueError) as error:
        print(f"Dockerfile generation failed: {error}")
        return False

    print(f"Dockerfile generated: {dockerfile_path}")

    if not build_image(app_path):
        print("\nDeployment aborted: build failed")
        return False

    if not run_candidate(
        candidate_port,
        container_port
    ):
        print("\nDeployment aborted: candidate start failed")
        return False

    if not health_check(
        candidate_port,
        health_mode,
        health_path
    ):
        print("\nCandidate is unhealthy")
        print("Keeping existing service")
        remove_container(CANDIDATE_CONTAINER)
        return False

    print("\nCandidate is healthy")
    print("\nReplacing current service...")

    if not remove_container(CURRENT_CONTAINER):
        print("Deployment aborted: current container removal failed")
        return False

    if not remove_container(CANDIDATE_CONTAINER):
        print("Deployment aborted: candidate container removal failed")
        return False

    if not run_current(
        current_port,
        container_port
    ):
        print("\nDeployment failed during final start")
        return False

    if health_check(
        current_port,
        health_mode,
        health_path
    ):
        print("\n==============================")
        print(" Deployment Success")
        print("==============================")
        print(f"http://127.0.0.1:{current_port}")
        return True
    else:
        print("\nFinal health check failed")
        print("Deployment failed")
        return False

def main():
    args = parse_arguments()
    app_path = resolve_app_path(args.app_path)
    if app_path is None:
        return 1
    success = deploy(app_path, args.port, args.container_port,
                     args.health_mode, args.health_path)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
