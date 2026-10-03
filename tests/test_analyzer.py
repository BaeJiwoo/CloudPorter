import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployer"))
from analyzer import analyze_project


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def package(self, data):
        (self.path / "package.json").write_text(json.dumps(data), encoding="utf-8-sig")

    def test_express_dependencies_and_command_case(self):
        for section in ("dependencies", "devDependencies"):
            with self.subTest(section=section):
                self.package({section: {"express": "*"}, "scripts": {"start": "node App.js"}})
                result = analyze_project(self.path)
                self.assertEqual(result["framework"], "express")
                self.assertEqual(result["start_command"], "node App.js")

    def test_description_is_not_dependency(self):
        self.package({"description": "express"})
        self.assertIsNone(analyze_project(self.path)["framework"])

    def test_invalid_node_projects(self):
        for data in ([], {"scripts": None}, {"dependencies": {"express": "*"}},
                     {"dependencies": {"express": "*"}, "scripts": {"start": " "}}):
            with self.subTest(data=data):
                self.package(data)
                with self.assertRaises(ValueError):
                    analyze_project(self.path)

    def test_fastapi_utf16_requirements_and_bom_source(self):
        (self.path / "requirements.txt").write_text("fastapi", encoding="utf-16")
        (self.path / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()", encoding="utf-8-sig")
        self.assertEqual(analyze_project(self.path)["entrypoint"], "app:app")

    def project(self, target="net10.0", extra=""):
        (self.path / "Web.csproj").write_text(
            f'<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup>'
            f'<TargetFramework>{target}</TargetFramework>{extra}</PropertyGroup></Project>', encoding="utf-8")

    def test_dotnet_versions_and_assembly_name(self):
        for version in ("8.0", "9.0", "10.0"):
            self.project(f"net{version}", "<AssemblyName>Example.Api</AssemblyName>")
            result = analyze_project(self.path)
            self.assertEqual(result["framework"], "aspnetcore")
            self.assertEqual(result["dotnet_version"], version)
            self.assertEqual(result["entrypoint"], "Example.Api.dll")

    def test_unsupported_dotnet_target(self):
        self.project("net48")
        with self.assertRaises(ValueError):
            analyze_project(self.path)

    def test_ambiguous_projects(self):
        self.project()
        (self.path / "Other.csproj").write_text("<Project/>")
        with self.assertRaises(ValueError):
            analyze_project(self.path)
