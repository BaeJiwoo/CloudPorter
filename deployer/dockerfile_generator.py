import json
from pathlib import Path


def generate_fastapi_dockerfile(
    app_path,
    entrypoint,
    container_port
):
    path = Path(app_path)

    dockerfile_content = f"""FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "{entrypoint}", "--host", "0.0.0.0", "--port", "{container_port}"]
"""

    dockerfile_path = path / "Dockerfile"

    dockerfile_path.write_text(
        dockerfile_content,
        encoding="utf-8"
    )

    return dockerfile_path


def generate_express_dockerfile(app_path, container_port):
    path = Path(app_path)
    install = "npm ci" if (path / "package-lock.json").is_file() else "npm install"
    content = f"""FROM node:22-slim

WORKDIR /app
COPY package*.json ./
RUN {install} --include=dev
COPY . .
ENV PORT={container_port}
CMD ["npm", "start"]
"""
    dockerfile = path / "Dockerfile"
    dockerfile.write_text(content, encoding="utf-8")
    return dockerfile


def generate_aspnetcore_dockerfile(app_path, analysis, container_port):
    path = Path(app_path)
    version = analysis["dotnet_version"]
    publish = json.dumps(["dotnet", "publish", analysis["project_file"],
                          "-c", "Release", "-o", "/out", "--no-self-contained",
                          "/p:UseAppHost=false"])
    command = json.dumps(["dotnet", analysis["entrypoint"]])
    content = f"""FROM mcr.microsoft.com/dotnet/sdk:{version} AS build
WORKDIR /src
COPY . .
RUN {publish}

FROM mcr.microsoft.com/dotnet/aspnet:{version}
WORKDIR /app
COPY --from=build /out .
ENV ASPNETCORE_URLS=http://0.0.0.0:{container_port}
CMD {command}
"""
    dockerfile = path / "Dockerfile"
    dockerfile.write_text(content, encoding="utf-8")
    return dockerfile


def generate_dockerfile(app_path, analysis, container_port):
    framework = analysis["framework"]
    if framework == "fastapi":
        if not analysis["entrypoint"]:
            raise ValueError("FastAPI entry point could not be detected")
        return generate_fastapi_dockerfile(app_path, analysis["entrypoint"], container_port)
    if framework == "express":
        if not analysis.get("start_command"):
            raise ValueError("Express requires scripts.start in package.json")
        return generate_express_dockerfile(app_path, container_port)
    if framework == "aspnetcore":
        return generate_aspnetcore_dockerfile(app_path, analysis, container_port)
    raise ValueError(f"Unsupported framework: {framework}")
