import ast
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def read_text_file(path):
    encodings = [
        "utf-8-sig",
        "utf-8",
        "utf-16",
        "cp949"
    ]

    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Cannot decode file: {path}")


def find_fastapi_entrypoint(path):
    for file in path.glob("*.py"):
        try:
            content = read_text_file(file)
            tree = ast.parse(content)
        except (SyntaxError, ValueError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue

            if not isinstance(node.value, ast.Call):
                continue

            function = node.value.func

            is_fastapi = (
                isinstance(function, ast.Name)
                and function.id == "FastAPI"
            )

            if not is_fastapi:
                continue

            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_name = file.stem
                    variable_name = target.id

                    return f"{module_name}:{variable_name}"

    return None

def analyze_python(requirements, result):
    result.update(language="python", dependency_file="requirements.txt")
    content = read_text_file(requirements).lower()

    if "fastapi" in content:
        result["framework"] = "fastapi"
        result["entrypoint"] = find_fastapi_entrypoint(requirements.parent)


def analyze_node(package_json, result):
    package = json.loads(read_text_file(package_json))
    if not isinstance(package, dict):
        raise ValueError("package.json must contain a JSON object")

    sections = {}
    for name in ("dependencies", "devDependencies", "scripts"):
        sections[name] = package.get(name, {})
        if not isinstance(sections[name], dict):
            raise ValueError(f"package.json: {name} must be an object")

    result.update(language="node", dependency_file="package.json")
    has_express = (
        "express" in sections["dependencies"]
        or "express" in sections["devDependencies"]
    )
    if has_express:
        result["framework"] = "express"
        start = sections["scripts"].get("start")
        if not isinstance(start, str) or not start.strip():
            raise ValueError("Express requires a non-empty scripts.start in package.json")
        result["start_command"] = start


def read_dotnet_properties(root):
    properties = {}
    for group in root.findall("PropertyGroup"):
        for child in group:
            if group.get("Condition") or child.get("Condition"):
                raise ValueError("Conditional .NET properties are not supported yet")
            properties[child.tag] = (child.text or "").strip()
    return properties


def analyze_dotnet(project_files, result):
    if len(project_files) != 1:
        raise ValueError("Use a directory containing exactly one .csproj file")

    project = project_files[0]
    try:
        root = ET.fromstring(read_text_file(project))
    except ET.ParseError as error:
        raise ValueError(f"Invalid project XML: {project.name}") from error

    result.update(language="dotnet", dependency_file=project.name)
    if root.get("Sdk") != "Microsoft.NET.Sdk.Web":
        return

    properties = read_dotnet_properties(root)
    target = properties.get("TargetFramework", "")
    if properties.get("TargetFrameworks") or not re.fullmatch(r"net(8|9|10)\.0", target):
        raise ValueError(
            "ASP.NET Core requires a single TargetFramework: net8.0, net9.0 or net10.0"
        )

    assembly = properties.get("AssemblyName", project.stem)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", assembly):
        raise ValueError(
            "Unsupported AssemblyName; use letters, digits, dots, hyphens or underscores"
        )

    result.update(
        framework="aspnetcore",
        entrypoint=f"{assembly}.dll",
        dotnet_version=target[3:],
        project_file=project.name,
    )


def analyze_project(app_path):
    path = Path(app_path)

    result = {
        "language": None,
        "framework": None,
        "dependency_file": None,
        "entrypoint": None,
        "start_command": None
    }

    requirements = path / "requirements.txt"
    package_json = path / "package.json"

    if requirements.exists():
        analyze_python(requirements, result)
    elif package_json.exists():
        analyze_node(package_json, result)
    else:
        project_files = sorted(path.glob("*.csproj"))
        if project_files:
            analyze_dotnet(project_files, result)

    return result

