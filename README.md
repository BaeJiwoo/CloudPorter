<p align="center">
  <img src="assets/CloudPorter_Logo.png" alt="CloudPorter 로고" width="320" />
</p>

<h1 align="center">CloudPorter</h1>

<p align="center">웹 애플리케이션의 개발 환경을 자동으로 확인하고, 그에 맞게 배포하는 도구</p>

## 프로젝트 도입 배경

- 게임 API 서버 개발 과정에서 배포 자동화와 CI/CD의 필요성을 느껴 프로젝트를 기획함.

## 개발 목표

- 개발 환경과 서비스 엔트리 포인트를 자동으로 분석함.
- Docker 이미지 빌드 및 컨테이너 배포를 자동화함.
- Health Check로 서비스의 정상 동작을 확인함.
- CI/CD 파이프라인을 연동함.
- DB 저장 공간과 서버 상태를 보고함.
- 이상 감지 시 이슈를 자동으로 등록함.

## 현재 지원 범위

로컬 Docker 기반의 단일 앱 배포 프로토타입입니다. 위 개발 목표 중 Cloud, CI/CD,
DB 보고, 자동 이슈 등록은 아직 구현하지 않았습니다.

| 앱 | 분석 기준 | 실행 방식 |
| --- | --- | --- |
| FastAPI | 최상위 requirements.txt와 Python 파일의 FastAPI() 대입 | Python 3.12 + Uvicorn |
| Express | package.json의 dependencies/devDependencies에 express, scripts.start 필수 | Node 22 + npm start |
| ASP.NET Core | 최상위 .csproj 하나, Microsoft.NET.Sdk.Web, net8.0/net9.0/net10.0 | SDK로 publish 후 ASP.NET 런타임에서 DLL 실행 |

Express는 PORT 환경변수를 읽고 0.0.0.0에 바인딩해야 합니다. package-lock.json이
있으면 npm ci, 없으면 npm install을 사용합니다. devDependencies의 Express와
시작 스크립트를 지원하기 위해 개발 의존성도 설치합니다. 별도 npm build 단계는 없습니다.

ASP.NET Core는 프로젝트에 직접 선언된 단일 TargetFramework와 선택적인 AssemblyName을
읽습니다. 조건부 속성, 다중 대상 프레임워크, 외부 프로젝트 참조, Directory.Build.props에서
상속되는 설정, Windows 전용 앱은 현재 지원 범위 밖입니다. HTTP 바인딩은
ASPNETCORE_URLS로 지정하므로 앱에서 주소를 별도로 강제하지 않아야 합니다.
HTTPS 인증서 설정은 포함하지 않습니다.

## 실행

Python 3.10 이상과 Linux 컨테이너 모드의 Docker Desktop/Engine이 필요합니다.
배포 자체에는 호스트의 Node.js나 .NET SDK가 필요하지 않습니다.
저장소 루트에서 Docker Engine 연결을 먼저 확인합니다.

```text
docker info
```

아래 명령 중 원하는 앱 하나를 실행합니다. 이미지와 컨테이너 이름이 공유되므로
다른 샘플을 배포하면 이전 샘플을 교체합니다. 동시에 실행하는 명령이 아닙니다.

```text
python deployer/deploy.py sample-app --port 9000 --container-port 8080
python deployer/deploy.py sample-express-app --port 9000 --container-port 8080
python deployer/deploy.py sample-aspnetcore-app --port 9000 --container-port 8080
```

성공하면 http://127.0.0.1:9000 에 접속할 수 있습니다. 세 샘플 모두
GET /, GET /health, POST /echo를 제공합니다. echo의 요청 본문은
`{"message":"hello"}`이며 응답은 `{"received":"hello"}`입니다.

| 옵션 | 기본값 | 용도 |
| --- | --- | --- |
| app_path | 필수 | 배포할 프로젝트 디렉터리 |
| --port | 8000 | Current Host Port (Candidate 탐색을 위해 65534 이하 권장) |
| --container-port | 8000 | 앱 내부 포트 |
| --health-mode | http | http: 지정 경로, root: /, tcp: 연결 확인 |
| --health-path | /health | http 모드의 검사 경로. /로 시작하는 경로 사용 |

성공 종료 코드는 0, 배포 실패는 1, 잘못된 CLI 입력은 2입니다.
Docker 명령의 제한 시간은 각각 600초입니다.

## 코드 안내

| 파일 | 역할 |
| --- | --- |
| deployer/analyzer.py | 프로젝트 종류, 실행 정보 분석. 잘못된 설정은 ValueError로 전달 |
| deployer/dockerfile_generator.py | 프레임워크별 Dockerfile 생성과 선택 |
| deployer/deploy.py | CLI, Docker 명령, Health Check, Candidate/Current 교체 |
| sample-app/ | FastAPI 샘플 |
| sample-express-app/ | PORT 환경변수를 사용하는 Express 샘플 |
| sample-aspnetcore-app/ | .NET 10 Minimal API 샘플 |
| tests/test_*.py | Docker 없이 분석·생성·배포 실패 흐름 검증 |
| tests/docker_smoke.py | 임시 복사본과 고유 컨테이너 이름으로 실제 배포·HTTP 검증 |

배포 흐름: 경로 확인 → Candidate Port 선택 → 분석 → Dockerfile 생성 → 빌드
→ Candidate 실행·검증 → Current 삭제 → Candidate 삭제 → Current 재실행·검증.

## 검증

외부 테스트 라이브러리 설치 없이 실행합니다.

```text
python -B -m unittest discover -s tests -v
```

Docker가 실행 중이면 실제 빌드부터 GET /, GET /health, POST /echo까지 검사합니다.
기존 sample-app-current와 다른 이름을 사용하며, 테스트 컨테이너와 이미지 태그를
종료 시 정리합니다. 내려받은 베이스 이미지와 빌드 캐시는 남을 수 있습니다.

```text
python -u -B tests/docker_smoke.py
python -u -B tests/docker_smoke.py sample-aspnetcore-app
```

## 현재 한계

- 배포 대상의 기존 Dockerfile을 덮어씁니다. 사용자 정의 파일은 먼저 보관하세요.
- 고정 이미지·컨테이너 이름을 사용하므로 한 번에 앱 하나만 배포합니다.
- Candidate 실패 시 Current는 유지하지만, 교체 후 실패에 대한 Rollback은 없습니다.
- 교체 시 다운타임이 있고 포트 탐색은 포트를 예약하지 않습니다.
- HTTP 검사는 200 응답, TCP 검사는 연결 성공만 확인합니다. 재시도는 5회입니다.
- FastAPI 분석은 최상위 Python 파일의 단순 FastAPI() 대입만 지원합니다.
- 여러 생태계 파일이 함께 있으면 requirements.txt → package.json → .csproj 순서로 분석합니다.
- Cloud Adapter, AWS/GCP 배포, Web UI, AI 분석은 다음 범위입니다.

구현 참고: [npm ci](https://docs.npmjs.com/cli/commands/npm-ci/),
[.NET Docker 소개](https://learn.microsoft.com/en-us/dotnet/core/docker/).
