import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployer"))
from dockerfile_generator import generate_dockerfile


class DockerfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def generate(self, analysis):
        return generate_dockerfile(self.path, analysis, 8123).read_text(encoding="utf-8")

    def test_fastapi_command(self):
        content = self.generate({"framework": "fastapi", "entrypoint": "api:app"})
        command = json.loads(content.split("CMD ")[1])
        self.assertEqual(command, ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8123"])

    def test_express_install_policy_and_port(self):
        analysis = {"framework": "express", "start_command": "node App.js"}
        content = self.generate(analysis)
        self.assertIn("RUN npm install --include=dev", content)
        (self.path / "package-lock.json").write_text("{}")
        content = self.generate(analysis)
        self.assertIn("RUN npm ci --include=dev", content)
        self.assertIn("ENV PORT=8123", content)
        self.assertEqual(json.loads(content.split("CMD ")[1]), ["npm", "start"])

    def test_dotnet_publish_and_runtime_match(self):
        content = self.generate({"framework": "aspnetcore", "dotnet_version": "10.0",
                                 "project_file": "My Web.csproj", "entrypoint": "Api.dll"})
        self.assertIn("sdk:10.0 AS build", content)
        self.assertIn("aspnet:10.0", content)
        publish = json.loads(next(line[4:] for line in content.splitlines() if line.startswith("RUN ")))
        self.assertEqual(publish[2], "My Web.csproj")
        self.assertIn("ASPNETCORE_URLS=http://0.0.0.0:8123", content)
        self.assertEqual(json.loads(content.split("CMD ")[1]), ["dotnet", "Api.dll"])

    def test_invalid_analysis_does_not_overwrite_dockerfile(self):
        dockerfile = self.path / "Dockerfile"
        dockerfile.write_text("original")
        for analysis in ({"framework": "unknown"}, {"framework": "fastapi", "entrypoint": None},
                         {"framework": "express", "start_command": None}):
            with self.assertRaises(ValueError):
                self.generate(analysis)
            self.assertEqual(dockerfile.read_text(), "original")
