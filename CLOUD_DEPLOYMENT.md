# GCP Cloud Run 배포 가이드

## 📋 사전 준비

### 1. GCP 계정 및 프로젝트 생성
1. https://console.cloud.google.com 접속
2. 프로젝트 생성 (예: `lotte-ai-news`)
3. 프로젝트 ID 복사 (예: `lotte-ai-news-12345`)

### 2. 필수 도구 설치

#### Windows 환경
```powershell
# Google Cloud SDK 설치
# https://cloud.google.com/sdk/docs/install 에서 다운로드

# 설치 후 인증
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Docker Desktop 설치
# https://www.docker.com/products/docker-desktop
```

#### 설치 확인
```powershell
gcloud --version
docker --version
```

---

## 🚀 배포 단계

### Step 1: 프로젝트 설정

```powershell
cd C:\Users\user\Documents\test

# 프로젝트 ID 설정 (deploy.sh, setup-scheduler.sh 파일 수정)
# PROJECT_ID="your-gcp-project-id" → PROJECT_ID="lotte-ai-news-12345"
```

### Step 2: 환경 변수 확인

`.env` 파일에 다음 변수가 있는지 확인:
```
GOOGLE_API_KEY=your_gemini_api_key
WEBEX_BOT_TOKEN=your_bot_token
WEBEX_ROOM_ID=your_room_id
```

### Step 3: Docker 이미지 빌드 및 Cloud Run Jobs 배포

```powershell
# GCP 인증
gcloud auth configure-docker

# 자동 배포 스크립트 실행 (권장)
.\deploy.ps1 -ProjectId YOUR_PROJECT_ID

# 또는 수동 배포
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ai-news-pipeline

# Cloud Run Jobs 배포 (24시간 타임아웃 지원)
gcloud run jobs deploy ai-news-pipeline `
  --image gcr.io/YOUR_PROJECT_ID/ai-news-pipeline `
  --region asia-northeast3 `
  --memory 2Gi `
  --cpu 2 `
  --task-timeout 2h `
  --max-retries 1 `
  --set-env-vars "GOOGLE_API_KEY=$env:GOOGLE_API_KEY,WEBEX_BOT_TOKEN=$env:WEBEX_BOT_TOKEN,WEBEX_ROOM_ID=$env:WEBEX_ROOM_ID"
```

**Cloud Run Jobs vs Services 차이:**
- **Jobs**: 완료 후 종료, 24시간 타임아웃, 스케줄 실행에 최적화
- **Services**: 항상 실행, HTTP 엔드포인트 제공, 60분 타임아웃 제한

### Step 4: Cloud Scheduler 설정 (매일 7:30 AM 자동 실행)

```powershell
# 자동 설정 스크립트 실행 (권장)
.\setup-scheduler.ps1 -ProjectId YOUR_PROJECT_ID

# 또는 수동 설정
# Service account 생성
gcloud iam service-accounts create cloud-scheduler-invoker `
  --display-name "Cloud Scheduler Invoker"

# 권한 부여 (Cloud Run Jobs 실행 권한)
gcloud run jobs add-iam-policy-binding ai-news-pipeline `
  --region asia-northeast3 `
  --member "serviceAccount:cloud-scheduler-invoker@YOUR_PROJECT_ID.iam.gserviceaccount.com" `
  --role "roles/run.invoker"

# Scheduler job 생성 (Cloud Run Jobs 트리거)
gcloud scheduler jobs create http ai-news-daily-730am `
  --location asia-northeast3 `
  --schedule "30 7 * * *" `
  --time-zone "Asia/Seoul" `
  --uri "https://asia-northeast3-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/ai-news-pipeline:run" `
  --http-method POST `
  --oauth-service-account-email "cloud-scheduler-invoker@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

---

## ✅ 배포 확인

### 1. 수동 테스트
```powershell
# Cloud Run Jobs 직접 실행
gcloud run jobs execute ai-news-pipeline --region asia-northeast3

# 실행 상태 확인
gcloud run jobs executions list --job ai-news-pipeline --region asia-northeast3

# 로그 확인 (실행 중)
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ai-news-pipeline" --limit 50 --format json
```

### 2. Scheduler 테스트
```powershell
# 즉시 실행
gcloud scheduler jobs run ai-news-daily-730am --location asia-northeast3

# 다음 실행 시간 확인
gcloud scheduler jobs describe ai-news-daily-730am --location asia-northeast3
```

### 3. Webex 메시지 확인
- 실행 후 약 90분 뒤 Webex Space에 메시지 도착 확인
- 정확히 9:00 AM에 도착해야 함

### 4. GCP Console 모니터링
- **Cloud Run Jobs**: https://console.cloud.google.com/run/jobs
- **Cloud Scheduler**: https://console.cloud.google.com/cloudscheduler
- **Logs**: https://console.cloud.google.com/logs

---

## 💰 비용 예상

### Cloud Run Jobs
- **실행 시간**: 90분/일 × 30일 = 45시간/월
- **메모리**: 2GB
- **CPU**: 2 vCPU
- **비용**: 약 $3-5/월 (실행 시간만 과금)

### Cloud Scheduler
- **비용**: $0.10/월 (첫 3개 무료)

### Cloud Build
- **빌드 시간**: 매 배포 시 1회 (무료 제한 120분/일)

### 총 예상 비용
- **월 $3-5** (약 4,000-7,000원)
- Cloud Run Services 대비 **30-50% 저렴** (항상 실행되지 않으므로)

---

## 🔧 유지보수

### 로그 확인
```powershell
# 최근 로그 보기
gcloud logging read "resource.type=cloud_run_job" --limit 100 --format "table(timestamp,severity,textPayload)"

# 특정 Job 로그
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ai-news-pipeline" --limit 50

# 특정 날짜 로그
gcloud logs read --format json --freshness 1d
```

### 코드 업데이트
```powershell
# 1. 코드 수정
# 2. 다시 빌드 및 배포
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ai-news-pipeline
gcloud run services update ai-news-pipeline --image gcr.io/YOUR_PROJECT_ID/ai-news-pipeline --region asia-northeast3
```

### 긴급 중지
```powershell
# Scheduler 일시 중지
gcloud scheduler jobs pause ai-news-daily-730am --location asia-northeast3

# 재개
gcloud scheduler jobs resume ai-news-daily-730am --location asia-northeast3
```

---

## 🆘 문제 해결

### 문제 1: "Permission denied" 오류
```powershell
# 권한 재설정
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID `
  --member "user:your-email@gmail.com" `
  --role "roles/owner"
```

### 문제 2: Timeout 오류
```powershell
# Timeout 증가 (최대 90분)
gcloud run services update ai-news-pipeline `
  --timeout 90m `
  --region asia-northeast3
```

### 문제 3: 메모리 부족
```powershell
# 메모리 증가
gcloud run services update ai-news-pipeline `
  --memory 4Gi `
  --region asia-northeast3
```

---

## 📞 지원

- GCP 콘솔: https://console.cloud.google.com
- Cloud Run 문서: https://cloud.google.com/run/docs
- 비용 계산기: https://cloud.google.com/products/calculator

---

## ✨ 장점 요약

✅ PC 꺼져도 매일 정확히 실행
✅ 정전, 재부팅 걱정 없음
✅ 원격에서 로그 확인 가능
✅ 자동 스케일링
✅ 99.9% 가동률 보장
✅ 실행 시간만 과금 (저렴)
