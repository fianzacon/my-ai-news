# AI 에이전트 실행 가이드

이 문서는 AI 에이전트를 실행하는 두 가지 방법을 안내합니다.
- **A. 기본 로컬 실행**: 데이터베이스 없이 간단하게 로컬 환경에서 에이전트를 실행합니다.
- **B. Cloud SQL 연동 실행**: Google Cloud SQL을 연동하 여 대화 기록을 영구 저장하고, 질문 추천 기능을 활성화합니다.

---

### 0단계: 사전 준비 (필수)

이 에이전트를 실행하기 전에, 먼저 Gemini API를 사용하기 위한 준비가 필요합니다.

#### 1. Gemini API 키 발급

Gemini API 키는 두 가지 방법으로 발급받을 수 있습니다.

**방법 1: Google AI Studio (가장 간단한 방법)**
[Google AI Studio](https://aistudio.google.com/app/apikey)에 방문하여 'Create API key' 버튼을 클릭하면 바로 키를 발급받을 수 있습니다.

**방법 2: Google Cloud Console (GCP 프로젝트 사용 시)**
Google Cloud 프로젝트와 연동하여 API 키를 관리하고 싶다면 다음 단계를 따르세요.
1.  [Google Cloud Console](https://console.cloud.google.com/)에 접속하여 원하는 프로젝트를 선택합니다.
2.  **Vertex AI API**를 검색하여 '사용 설정(Enable)'합니다.
3.  'API 및 서비스' > '사용자 인증 정보(Credentials)' 페이지로 이동합니다.
4.  상단의 '사용자 인증 정보 만들기(Create credentials)' > 'API 키(API key)'를 선택하여 키를 생성합니다.
    > **보안 권장 사항:** 생성된 API 키는 특정 API(Vertex AI API)만 호출할 수 있도록 제한합니다.

#### 2. Gemini CLI 설치 및 API 키 테스트 (선택 사항)

Python 환경과 별개로, 터미널에서 직접 Gemini 모델을 사용하고 싶다면 `gemini-cli`를 설치할 수 있습니다. 설치 후에는 `gemini` 명령어로 실행할 수 있으며, API 키가 올바르게 작동하는지 확인하는 데 유용합니다.

##### macOS (Homebrew 사용):
```bash
brew install gemini-cli
```

##### Windows (Scoop 또는 Chocolatey 사용):
Windows에서는 Scoop 또는 Chocolatey와 같은 패키지 매니저를 사용하여 설치할 수 있습니다. **만약 둘 다 설치되어 있지 않다면, 먼저 하나를 선택하여 설치해야 합니다.**

*   **Scoop으로 설치:**
    *   (Scoop이 설치되어 있지 않다면) PowerShell에서 다음 명령어로 설치:
        ```powershell
        Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
        irm get.scoop.sh | iex
        ```
    *   Scoop으로 `gemini-cli` 설치:
        ```bash
        scoop bucket add extras
        scoop install gemini-cli
        ```

*   **Chocolatey로 설치:**
    *   (Chocolatey가 설치되어 있지 않다면) [공식 홈페이지](https://chocolatey.org/install)의 안내에 따라 설치합니다.
    *   Chocolatey로 `gemini-cli` 설치:
        ```bash
        choco install gemini-cli
        ```

##### 설치 후 API 키 설정:
CLI를 사용하기 전에, API 키를 환경 변수로 설정해야 합니다.

*   **macOS 또는 Linux:**
    ```bash
    export GEMINI_API_KEY="YOUR_API_KEY"
    ```
*   **Windows (Command Prompt):**
    ```bash
    set GEMINI_API_KEY="YOUR_API_KEY"
    ```

##### 사용법:
`gemini`만 입력하면 대화형 세션이 시작되어, 여러 질문을 연속해서 할 수 있습니다.
```bash
gemini
```
(실행 후 프롬프트가 나타나면 질문을 입력하세요.)

#### 3. Google AI Python SDK 설치
다음 명령어를 사용하여 Gemini API와 상호작용할 수 있는 Python 라이브러리를 설치합니다.
```bash
pip install google-generativeai
```

#### 4. API 키 환경 변수 설정
애플리케이션을 실행할 터미널에서 아래 명령어를 실행하여 발급받은 API 키를 환경 변수로 설정합니다. 이 설정은 현재 터미널 세션에만 유효합니다.

##### macOS 또는 Linux:
```bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

##### Windows (Command Prompt):
```bash
set GEMINI_API_KEY="YOUR_API_KEY"
```

---

## A. 기본 로컬 실행 (데이터베이스 없음)

Docker나 외부 데이터베이스 없이 로컬 Python 환경에서 직접 AI 에이전트를 실행하는 가장 간단한 방법입니다.

### 1단계: 가상 환경 설정

프로젝트의 최상위 폴더에서 다음 명령어를 실행하여 Python 가상 환경을 만들고 활성화합니다.

#### macOS 또는 Linux:
```bash
# Python 3.11 버전으로 가상 환경 생성 권장
python3.11 -m venv venv
source venv/bin/activate
```

#### Windows:
```bash
# Python 3.11 버전으로 가상 환경 생성 권장
python -m venv venv
.\venv\Scripts\activate
```

### 2단계: 필수 라이브러리 설치 

`requirements.txt` 파일에 명시된 모든 필수 Python 라이브러리를 설치합니다.
```bash
pip install -r requirements.txt
```

### 3단계: API 키 설정

`.env.example` 파일을 복사하여 `.env` 파일을 생성하고, `YOUR_GOOGLE_API_KEY` 부분에 자신의 Google API 키를 입력합니다.
```bash
cp .env.example .env
```

### 4단계: 애플리케이션 실행

FastAPI 서버를 시작합니다.

```bash
uvicorn run_agent:app_fastapi --host 0.0.0.0 --port 8000 --reload
```

> **⚠️ 보안 경고:** 위 명령어는 개발 환경의 편의성을 위한 설정입니다. `--reload` 옵션과 `--host 0.0.0.0` 설정은 실제 운영 환경(Production)에서는 보안상 취약할 수 있으므로 사용하지 않는 것을 권장합니다. 운영 환경에서는 Gunicorn과 같은 WSGI 서버를 사용하고, Nginx를 리버스 프록시로 두어 HTTPS를 적용해야 합니다.

서버가 시작되면, 웹 브라우저에서 `http://localhost:8000` 주소로 접속하여 AI 에이전트를 사용할 수 있습니다.

---

## B. Cloud SQL 연동 실행 (대화 기록 및 추천 기능 활성화)

Google Cloud SQL (PostgreSQL)을 연동하여 대화 기록을 영구적으로 저장하고, 다른 사용자의 대화 기록을 바탕으로 질문을 추천하는 기능을 활성화합니다.

### 사전 준비

1.  **Google Cloud SDK 설치**: `gcloud` CLI가 설치되어 있어야 합니다. [설치 가이드](https://cloud.google.com/sdk/docs/install)를 참고하세요.
2.  **Cloud SQL 인스턴스**: GCP 프로젝트에 Cloud SQL for PostgreSQL 인스턴스가 준비되어 있어야 합니다.
3.  **Docker (선택 사항)**: Langfuse를 함께 사용하려면 Docker가 필요합니다.

### 1단계: 가상 환경 및 라이브러리 설치

위의 **A. 기본 로컬 실행**의 1, 2단계를 따라 가상 환경을 설정하고 라이브러리를 설치합니다.

### 2단계: 환경 변수 설정

`.env` 파일에 Cloud SQL 접속 정보를 추가로 입력해야 합니다.

```dotenv
# .env 파일

# Google API Key
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"

# Langfuse (선택 사항)
LANGFUSE_PUBLIC_KEY="..."
LANGFUSE_SECRET_KEY="..."
LANGFUSE_HOST="http://localhost:3000"

# Google Cloud SQL
INSTANCE_CONNECTION_NAME="<your-project-id>:<your-region>:<your-instance-id>"
DB_USER="<your-db-user>"
DB_PASS="<your-db-password>"
DB_NAME="<your-db-name>"
```
- `INSTANCE_CONNECTION_NAME`: Cloud SQL 인스턴스의 연결 이름입니다. (예: `my-project:asia-northeast3:my-instance`)
- `DB_USER`, `DB_PASS`, `DB_NAME`: Cloud SQL Console에서 확인한 데이터베이스 사용자, 비밀번호, 데이터베이스 이름입니다.

### 3단계: Cloud SQL 인증 프록시 실행

애플리케이션이 Cloud SQL에 안전하게 연결될 수 있도록 **별도의 터미널**에서 Cloud SQL 인증 프록시를 실행합니다.

```bash
# 1. (최초 한 번) gcloud 인증
gcloud auth application-default login

# 2. (최초 한 번) gcloud 프로젝트 설정
gcloud config set project <your-project-id>

> **⚠️ 보안 권장 사항:** `gcloud auth application-default login` 명령어는 개인 사용자 계정의 넓은 권한을 사용하므로, 실제 운영 환경에서는 보안상 위험할 수 있습니다. 운영 환경에서는 최소한의 권한(예: Cloud SQL Client)만 가진 별도의 서비스 계정(Service Account)을 생성하여 인증하는 것이 훨씬 안전합니다.

# 3. 프록시가 사용할 디렉토리 생성
mkdir -p /tmp/cloudsql

# 4. 프록시 실행 (애플리케이션 실행 내내 켜두어야 함)
cloud-sql-proxy <your-instance-connection-name> --unix-socket /tmp/cloudsql
```
"ready for new connections" 메시지가 나오면 성공입니다. 이 터미널은 그대로 둡니다.

### 4단계: 애플리케이션 실행

**새로운 터미널**을 열고, 가상 환경을 활성화한 뒤 FastAPI 서버를 시작합니다.
```bash
# 가상 환경 활성화
source venv/bin/activate

# 서버 실행
python run_agent.py
```
이제 `http://localhost:8000`으로 접속하면 모든 기능이 활성화된 에이전트를 사용할 수 있습니다.

### 추가된 기능

- **대화 기록 영구 저장**: 모든 대화가 Cloud SQL에 저장되어 서버를 재시작해도 유지됩니다.
- **질문 추천**: 다른 사용자들이 했던 질문들이 답변 하단에 추천 버튼으로 표시됩니다. (데이터베이스에 다른 사용자의 기록이 있어야 표시됩니다.)

---

## C. 전체 아키텍처

이 에이전트의 전체 아키텍처는 다음과 같습니다.

![AI Agent Architecture](./architect.png)

### 아키텍처 설명 요약

1.  **User Interaction**: 사용자가 웹 UI를 통해 질문을 제출합니다.
2.  **FastAPI Backend**:
    *   `/invoke` 엔드포인트가 요청을 받아 DB에서 이전 대화 기록을 조회합니다.
    *   LangGraph 에이전트를 백그라운드에서 실행시키고, 클라이언트에게는 즉시 `run_id`를 반환합니다.
    *   클라이언트는 이 `run_id`를 사용하여 `/stream-logs` 엔드포인트에 접속해 실시간 로그와 최종 결과를 받습니다.
3.  **LangGraph Agent**:
    *   **Intent Router**: 에이전트의 시작점입니다. 사용자의 의도를 '새로운 연구'와 '답변 수정'으로 분류합니다.
    *   **새로운 연구 경로**: `Researcher` (임베딩 생성 포함) → `Writer` → `Critique` → `Reviser` (필요시 반복) → `SetFinalOutput` → `Recommender` (벡터 검색으로 추천 생성) 순서로 실행됩니다.
    *   **답변 수정 경로**: `Refiner` 노드가 이전 답변을 사용자의 요청에 맞게 수정한 후 바로 종료됩니다.
4.  **External Services & Database**:
    *   에이전트의 모든 LLM 호출은 **Vertex AI**를 사용합니다.
    *   대화 기록 저장 및 벡터 검색은 **PostgreSQL (pgvector)** 데이터베이스에서 이루어집니다.
5.  **Observability**: 에이전트의 모든 실행 과정은 **Langfuse**를 통해 추적 및 기록됩니다.
