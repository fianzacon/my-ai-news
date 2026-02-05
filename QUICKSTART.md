# 🚀 GCP 클라우드 배포 - 빠른 시작 가이드

## ✅ 사전 체크리스트

- [ ] GCP 계정 생성 완료
- [ ] GCP 프로젝트 생성 완료 (프로젝트 ID 메모)
- [ ] Google Cloud SDK 설치 완료
- [ ] Docker Desktop 설치 완료
- [ ] `.env` 파일 확인 (GOOGLE_API_KEY, WEBEX_BOT_TOKEN, WEBEX_ROOM_ID)

---

## 📝 Step 1: GCP 초기 설정 (최초 1회만)

### 1-1. Google Cloud SDK 설치
https://cloud.google.com/sdk/docs/install 에서 다운로드 후 설치

### 1-2. GCP 인증
```powershell
gcloud auth login
gcloud auth application-default login
```

### 1-3. Docker 인증
```powershell
gcloud auth configure-docker
```

---

## 🚀 Step 2: 배포 실행 (2분 소요)

### Windows PowerShell에서 실행:

```powershell
cd C:\Users\user\Documents\test

# 프로젝트 ID를 실제 값으로 변경!
.\deploy.ps1 -ProjectId "your-gcp-project-id"
```

**예시**:
```powershell
.\deploy.ps1 -ProjectId "lotte-ai-news-12345"
```

---

## ⏰ Step 3: 스케줄러 설정 (1분 소요)

```powershell
# 프로젝트 ID를 실제 값으로 변경!
.\setup-scheduler.ps1 -ProjectId "your-gcp-project-id"
```

---

## ✅ Step 4: 테스트 실행

### 즉시 실행 테스트:
```powershell
gcloud scheduler jobs run ai-news-daily-730am --location asia-northeast3
```

### 로그 확인:
```powershell
# 실시간 로그 스트림
gcloud logs tail --format json

# 최근 50줄 로그
gcloud logs read --limit 50
```

### Webex 메시지 확인:
- 실행 후 약 90분 뒤 Webex Space에 메시지 도착
- 정확히 9:00 AM에 도착해야 함

---

## 🎯 완료!

이제 다음이 자동으로 작동합니다:

✅ **매일 아침 7:30 AM** → 파이프라인 자동 실행
✅ **83분 처리** → 뉴스 수집, 분석, 필터링
✅ **9:00 AM 정각** → Webex 메시지 전송

**PC 꺼져도, 정전되어도, 재부팅해도 관계없이 실행됩니다!**

---

## 🔧 유지보수 명령어

### 배포 업데이트 (코드 수정 후):
```powershell
.\deploy.ps1 -ProjectId "your-project-id"
```

### 스케줄 일시 중지:
```powershell
gcloud scheduler jobs pause ai-news-daily-730am --location asia-northeast3
```

### 스케줄 재개:
```powershell
gcloud scheduler jobs resume ai-news-daily-730am --location asia-northeast3
```

### 다음 실행 시간 확인:
```powershell
gcloud scheduler jobs describe ai-news-daily-730am --location asia-northeast3
```

---

## 💰 예상 비용

- **Cloud Run**: 월 $3-5 (실행 시간만 과금)
- **Cloud Scheduler**: $0.10/월
- **총**: **월 $3-5** (약 4,000-7,000원)

---

## 🆘 문제 해결

### 문제: "gcloud: command not found"
→ Google Cloud SDK 재설치 필요

### 문제: "Permission denied"
→ 프로젝트 Owner 권한 확인 필요

### 문제: "Docker daemon not running"
→ Docker Desktop 실행 필요

### 문제: Webex 메시지가 안 옴
→ 로그 확인:
```powershell
gcloud logs read --limit 100 --format json
```

---

## 📞 지원

- GCP 콘솔: https://console.cloud.google.com
- 로그 뷰어: https://console.cloud.google.com/logs
- Cloud Run: https://console.cloud.google.com/run

문제 발생 시 로그를 확인하거나 GCP 콘솔에서 상태를 체크하세요!
