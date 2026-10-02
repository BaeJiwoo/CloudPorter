import ast
from pathlib import Path


def read_text_file(path):
    encodings = [
        "utf-8",
        "utf-8-sig",
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

def analyze_project(app_path):
    path = Path(app_path)

    result = {
        "language": None,
        "framework": None,
        "dependency_file": None,
        "entrypoint": None
    }

    requirements = path / "requirements.txt"
    package_json = path / "package.json"

    if requirements.exists():
        result["language"] = "python"
        result["dependency_file"] = "requirements.txt"

        content = read_text_file(requirements).lower()

        if "fastapi" in content:
            result["framework"] = "fastapi"
            result["entrypoint"] = find_fastapi_entrypoint(path)

    elif package_json.exists():
        result["language"] = "node"
        result["dependency_file"] = "package.json"

        content = read_text_file(package_json).lower()

        if "express" in content:
            result["framework"] = "express"

    return result

# if __name__ == "__main__":
#    result = analyze_project("../sample-app")
#    print(result)