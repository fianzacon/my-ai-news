# 🚀 Cloud Run Jobs 배포 퀵스타트

## Cloud Run Jobs란?

**Cloud Run Jobs**는 완료 후 종료되는 배치 작업에 최적화된 서비스입니다.

### Cloud Run Services vs Jobs 비교

| 기능 | Services | Jobs |
|------|----------|------|
| **실행 방식** | 항상 실행 (HTTP 엔드포인트) | 트리거 시 실행, 완료 후 종료 |
| **최대 타임아웃** | 60분 (3600초) | 24시간 (86400초) |
| **과금 방식** | 항상 실행 중 과금 | 실행 시간만 과금 |
| **적합한 용도** | API 서버, 웹 애플리케이션 | 배치 작업, 스케줄 작업, 데이터 처리 |
| **HTTP 엔드포인트** | ✅ 있음 | ❌ 없음 (내부 실행만) |

### 우리 파이프라인에 Jobs를 선택한 이유

1. **83분 실행 시간** → Services의 60분 제한 초과
2. **매일 1회 실행** → 항상 실행될 필요 없음 (비용 절감)
3. **완료 보장** → 24시간 타임아웃으로 안정적 실행
4. **스케줄링 최적화** → Cloud Scheduler와 완벽한 통합

---

## 📋 배포 3단계

### 1️⃣ 환경 변수 준비

`.env` 파일에 다음 내용 입력:
```
GOOGLE_API_KEY=your_gemini_api_key
WEBEX_BOT_TOKEN=your_bot_token
WEBEX_ROOM_ID=your_room_id
```

### 2️⃣ 배포 실행 (3분)

```powershell
cd C:\Users\user\Documents\test
.\deploy.ps1 -ProjectId "lotte-ai-news"
```

**실행 내용:**
- Docker 이미지 빌드 (2-3분)
- Container Registry 푸시
- Cloud Run Jobs 생성 (2시간 타임아웃)

### 3️⃣ 스케줄러 설정 (1분)

```powershell
.\setup-scheduler.ps1 -ProjectId "lotte-ai-news"
```

**실행 내용:**
- Service Account 생성
- IAM 권한 부여
- 매일 7:30 AM 실행 스케줄 생성

---

## ✅ 배포 확인

### 즉시 테스트 실행
```powershell
gcloud run jobs execute ai-news-pipeline --region asia-northeast3
```

### 실행 상태 확인
```powershell
# 최근 실행 목록
gcloud run jobs executions list --job ai-news-pipeline --region asia-northeast3

# 로그 실시간 확인
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ai-news-pipeline" --limit 50 --format json
```

### GCP Console에서 확인
- **Jobs 대시보드**: https://console.cloud.google.com/run/jobs?project=lotte-ai-news
- **실행 기록**: 각 실행의 상태, 시간, 로그 확인
- **Scheduler**: https://console.cloud.google.com/cloudscheduler?project=lotte-ai-news

---

## 🔍 차이점 요약

### 기존 deploy.ps1 (Services - 실패)
```powershell
gcloud run deploy ai-news-pipeline `
    --timeout 90m  # ❌ 60분 초과로 실패
    --no-allow-unauthenticated
```

### 새로운 deploy.ps1 (Jobs - 성공)
```powershell
gcloud run jobs deploy ai-news-pipeline `
    --task-timeout 2h  # ✅ 24시간까지 가능
    --max-retries 1    # 실패 시 1회 재시도
```

### 기존 setup-scheduler.ps1 (Services 트리거)
```powershell
--uri $SERVICE_URL  # HTTP 엔드포인트 호출
--oidc-service-account-email
```

### 새로운 setup-scheduler.ps1 (Jobs 트리거)
```powershell
--uri "https://asia-northeast3-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$ProjectId/jobs/ai-news-pipeline:run"
--oauth-service-account-email  # Jobs API 호출
```

---

## 💡 주요 명령어

### Jobs 관리
```powershell
# Job 목록
gcloud run jobs list --region asia-northeast3

# Job 상세 정보
gcloud run jobs describe ai-news-pipeline --region asia-northeast3

# Job 삭제
gcloud run jobs delete ai-news-pipeline --region asia-northeast3
```

### 실행 관리
```powershell
# 수동 실행
gcloud run jobs execute ai-news-pipeline --region asia-northeast3

# 실행 목록
gcloud run jobs executions list --job ai-news-pipeline --region asia-northeast3

# 특정 실행 삭제
gcloud run jobs executions delete EXECUTION_NAME --region asia-northeast3
```

### 로그 확인
```powershell
# 최근 로그
gcloud logging read "resource.type=cloud_run_job" --limit 100

# 특정 Job 로그
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ai-news-pipeline" --limit 50
```

---

## 🎯 예상 결과

### 정상 실행 시나리오

1. **7:30 AM**: Cloud Scheduler가 Job 트리거
2. **7:30-8:50 AM**: 파이프라인 실행 (뉴스 수집, 필터링, 분석)
3. **8:50-9:00 AM**: 9시까지 대기
4. **9:00 AM**: Webex Space에 메시지 전송
5. **9:00 AM**: Job 완료 및 종료

### 비용
- **일 1회 실행 × 90분 = 월 45시간**
- **약 $3-5/월** (기존 Services 대비 30-50% 절감)

---

## ⚠️ 문제 해결

### Job 실행 실패 시
```powershell
# 최근 실행 확인
gcloud run jobs executions list --job ai-news-pipeline --region asia-northeast3

# 실패한 실행의 로그 확인
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ai-news-pipeline AND severity>=ERROR" --limit 20
```

### Scheduler 트리거 안될 시
```powershell
# Scheduler 상태 확인
gcloud scheduler jobs describe ai-news-daily-730am --location asia-northeast3

# 수동 트리거 테스트
gcloud scheduler jobs run ai-news-daily-730am --location asia-northeast3
```

### 권한 오류 시
```powershell
# IAM 권한 재설정
gcloud run jobs add-iam-policy-binding ai-news-pipeline `
    --region asia-northeast3 `
    --member "serviceAccount:cloud-scheduler-invoker@lotte-ai-news.iam.gserviceaccount.com" `
    --role "roles/run.invoker"
```

---

## 📚 참고 문서

- [Cloud Run Jobs 공식 문서](https://cloud.google.com/run/docs/create-jobs)
- [Cloud Scheduler 문서](https://cloud.google.com/scheduler/docs)
- [Cloud Run 가격](https://cloud.google.com/run/pricing)
