import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployer"))
import deploy


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        (self.path / "package.json").write_text(json.dumps({
            "dependencies": {"express": "*"}, "scripts": {"start": "node app.js"}}))
        self.commands = []
        self.failed_command = None
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(deploy, "run_docker", side_effect=self.docker))
        self.stack.enter_context(patch.object(deploy, "find_available_port", return_value=9001))
        self.health = self.stack.enter_context(patch.object(deploy, "health_check", return_value=True))

    def docker(self, arguments):
        self.commands.append(arguments)
        failed = self.failed_command and self.failed_command(arguments)
        return subprocess.CompletedProcess(arguments, 1 if failed else 0, "id", "error" if failed else "")

    def run_deploy(self):
        return deploy.deploy(self.path, 9000, 8080, "http", "/health")

    def test_express_full_flow_and_ports(self):
        self.assertTrue(self.run_deploy())
        self.assertEqual([c[0] for c in self.commands], ["build", "rm", "run", "rm", "rm", "run"])
        self.assertIn("9001:8080", self.commands[2])
        self.assertIn("9000:8080", self.commands[-1])
        self.assertEqual([c.args[0] for c in self.health.call_args_list], [9001, 9000])
        self.assertIn("node:22-slim", (self.path / "Dockerfile").read_text())

    def test_fastapi_and_dotnet_use_same_flow(self):
        (self.path / "package.json").unlink()
        (self.path / "requirements.txt").write_text("fastapi\nuvicorn")
        (self.path / "app.py").write_text("app = FastAPI()")
        self.assertTrue(self.run_deploy())
        self.assertIn("python:3.12-slim", (self.path / "Dockerfile").read_text())
        (self.path / "requirements.txt").unlink()
        (self.path / "Web.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web">'
            '<PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
        self.assertTrue(self.run_deploy())
        self.assertIn("aspnet:10.0", (self.path / "Dockerfile").read_text())

    def test_unhealthy_candidate_keeps_current(self):
        self.health.return_value = False
        self.assertFalse(self.run_deploy())
        self.assertNotIn(["rm", "-f", deploy.CURRENT_CONTAINER], self.commands)
        self.assertEqual(self.commands[-1], ["rm", "-f", deploy.CANDIDATE_CONTAINER])

    def test_cleanup_failure_stops_following_commands(self):
        for container in (deploy.CANDIDATE_CONTAINER, deploy.CURRENT_CONTAINER):
            with self.subTest(container=container):
                self.commands.clear()
                self.failed_command = lambda args: args == ["rm", "-f", container]
                self.assertFalse(self.run_deploy())
                self.assertEqual(self.commands[-1], ["rm", "-f", container])

    def test_candidate_cleanup_after_validation_stops_current_start(self):
        self.failed_command = lambda args: args == ["rm", "-f", deploy.CANDIDATE_CONTAINER] and len(self.commands) == 5
        self.assertFalse(self.run_deploy())
        self.assertEqual(len(self.commands), 5)

    def test_final_health_failure(self):
        self.health.side_effect = [True, False]
        self.assertFalse(self.run_deploy())

    def test_build_failure_keeps_current(self):
        self.failed_command = lambda args: args[0] == "build"
        self.assertFalse(self.run_deploy())
        self.assertEqual(len(self.commands), 1)

    def test_invalid_project_does_not_call_docker(self):
        (self.path / "package.json").write_text("{broken")
        self.assertFalse(self.run_deploy())
        self.assertEqual(self.commands, [])

    def test_main_exit_status(self):
        args = argparse.Namespace(app_path=str(self.path), port=9000, container_port=8080,
                                  health_mode="http", health_path="/health")
        with patch.object(deploy, "parse_arguments", return_value=args):
            self.assertEqual(deploy.main(), 0)
            self.health.return_value = False
            self.assertEqual(deploy.main(), 1)


class DockerCommandTests(unittest.TestCase):
    def test_missing_docker_and_timeout_are_failures(self):
        for error in (FileNotFoundError("docker missing"), subprocess.TimeoutExpired("docker", 600)):
            with patch.object(deploy.subprocess, "run", side_effect=error):
                self.assertNotEqual(deploy.run_docker(["info"]).returncode, 0)

    def test_invalid_ports(self):
        for value in ("0", "65536", "abc"):
            with self.assertRaises(argparse.ArgumentTypeError):
                deploy.port_number(value)
