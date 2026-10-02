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