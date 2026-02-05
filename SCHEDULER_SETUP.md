# Windows Task Scheduler 설정 가이드 (매일 9시 자동 실행)

## 🔧 1단계: Webex Bot 설정

### Webex Bot 생성
1. https://developer.webex.com/ 접속
2. "Start Building Apps" 클릭
3. "Create a Bot" 선택
4. Bot 정보 입력:
   - Bot name: AI News Intelligence Bot
   - Bot username: ai-news-bot (unique)
   - Icon: 선택
5. **Bot Access Token 복사** (한 번만 표시됨!)

### Webex Room ID 확인
1. Webex Teams 앱 실행
2. 메시지를 받을 Space/Room 선택
3. Space 이름 옆 점 3개(...) 클릭
4. "Copy Space Link" 클릭
5. URL에서 Room ID 추출:
   ```
   https://web.webex.com/meet/ROOM_ID
   ```

### .env 파일 설정
```bash
cd C:\Users\user\Documents\test
notepad .env
```

추가할 내용:
```
WEBEX_BOT_TOKEN=your_bot_token_here
WEBEX_ROOM_ID=your_room_id_here
```

---

## 🧪 2단계: 테스트 실행

### 수동 테스트
```powershell
cd C:\Users\user\Documents\test
python run_pipeline_scheduled.py
```

예상 결과:
- ✅ Pipeline 실행 완료
- ✅ Webex로 메시지 전송
- ✅ Space에 뉴스 메시지 도착

---

## ⏰ 3단계: Windows Task Scheduler 설정

### 방법 1: GUI로 설정

1. **작업 스케줄러 실행**
   - Win + R → `taskschd.msc` → Enter

2. **새 작업 만들기**
   - 오른쪽: "작업 만들기..." 클릭

3. **일반 탭**
   - 이름: `AI News Pipeline - Daily 9AM`
   - 설명: `롯데멤버스 AI 뉴스 파이프라인 (매일 9시 실행)`
   - ✅ `가장 높은 수준의 권한으로 실행` 체크
   - ✅ `사용자의 로그온 여부에 관계없이 실행` 선택

4. **트리거 탭**
   - "새로 만들기..." 클릭
   - 작업 시작: `일정에 따라`
   - 설정:
     - 매일
     - 시작: `오전 7:30:00`  ⚠️ 중요: 파이프라인 실행 시간 ~83분 고려
     - 반복 간격: (비활성화)
     - 사용: ✅ 체크
   - 확인 클릭
   
   **참고**: 파이프라인 완료 후 9시에 Webex 메시지 전송하려면 7:30 실행 필요

5. **동작 탭**
   - "새로 만들기..." 클릭
   - 동작: `프로그램 시작`
   - 프로그램/스크립트:
     ```
     C:\Program Files\Python313\python.exe
     ```
   - 인수 추가:
     ```
     run_pipeline_scheduled.py
     ```
   - 시작 위치:
     ```
     C:\Users\user\Documents\test
     ```
   - 확인 클릭

6. **조건 탭**
   - ✅ `작업을 실행하기 위해 깨우기` 체크 (PC 절전 모드에서도 실행)
   - ❌ `컴퓨터의 전원이 AC 전원일 때만 작업 시작` 체크 해제

7. **설정 탭**
   - ✅ `요청 시 작업 실행 허용` 체크
   - ✅ `작업이 실패하면 다시 시작 간격`: `1분` / `3회`
   - 확인 클릭

8. **암호 입력**
   - Windows 로그인 암호 입력
   - 확인

---

### 방법 2: PowerShell로 설정 (고급)

```powershell
# 관리자 권한 PowerShell 실행

$action = New-ScheduledTaskAction `
    -Execute "C:\Program Files\Python313\python.exe" `
    -Argument "run_pipeline_scheduled.py" `
    -WorkingDirectory "C:\Users\user\Documents\test"

$trigger = New-ScheduledTaskTrigger -Daily -At 7:30am

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName "AI News Pipeline - Daily 7:30AM (9AM Delivery)" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "롯데멤버스 AI 뉴스 파이프라인 (7:30 시작, 9시 전송 목표)"`
```

---

## ✅ 4단계: 작업 확인 및 테스트

### 수동 실행 테스트
1. 작업 스케줄러에서 생성한 작업 선택
2. 오른쪽: "실행" 클릭
3. 결과 확인:
   - 마지막 실행 결과: `0x0` (성공)
   - Webex Space에 메시지 도착 확인

### 로그 확인
```powershell
cd C:\Users\user\Documents\test
notepad pipeline_scheduled.log
```

### 작업 삭제 (필요 시)
```powershell
Unregister-ScheduledTask -TaskName "AI News Pipeline - Daily 9AM" -Confirm:$false
```

---

## 🔒 보안 고려사항

### .env 파일 보호
```powershell
# .env 파일 권한 설정 (본인만 읽기 가능)
icacls .env /inheritance:r
icacls .env /grant:r "$env:USERNAME:(R)"
```

### Bot Token 보안
- ⚠️ Bot Token은 절대 공유하지 말 것
- ⚠️ GitHub에 커밋하지 말 것 (.gitignore 확인)
- ⚠️ 주기적으로 Token 재생성 권장 (6개월마다)

---

## 🎯 전송 모드 선택

### Batch 모드 (기본, 권장)
- 모든 뉴스를 1개의 메시지로 전송
- Webex Space가 깨끗하게 유지됨
- 수정: `run_pipeline_scheduled.py` 파일에서 `batch_mode='batch'`

### Single 모드
- 각 뉴스를 개별 메시지로 전송
- 메시지가 많을 경우 Space가 복잡해질 수 있음
- 수정: `run_pipeline_scheduled.py` 파일에서 `batch_mode='single'`

---

## 📊 모니터링

### 일일 실행 확인
```powershell
# 최근 7일간 실행 로그
Get-Content pipeline_scheduled.log -Tail 500 | Select-String "SCHEDULED EXECUTION"
```

### 오류 확인
```powershell
# 오류 로그만 필터
Get-Content pipeline_scheduled.log | Select-String "ERROR|FAILED"
```

---

## 🆘 문제 해결

### 작업이 실행되지 않음
1. 작업 스케줄러 → 작업 기록 확인
2. Python 경로 확인:
   ```powershell
   where.exe python
   ```
3. .env 파일 경로 확인
4. 관리자 권한으로 실행 여부 확인

### Webex 전송 실패
1. Bot Token 유효성 확인:
   ```powershell
   curl -H "Authorization: Bearer YOUR_TOKEN" https://webexapis.com/v1/people/me
   ```
2. Room ID 정확성 확인
3. Bot이 Space에 초대되었는지 확인

### PC 절전 모드에서 실행 안 됨
- 작업 조건 탭 → "작업을 실행하기 위해 깨우기" 체크

---

## 📧 알림 설정 (선택)

### 실행 실패 시 이메일 알림
작업 스케줄러 → 동작 탭 → 새로 만들기 → 전자 메일 보내기
(Windows Server만 지원 - Windows 10/11은 PowerShell 스크립트로 구현 필요)

---

**설정 완료!** 🎉
이제 매일 오전 9시에 자동으로 AI 뉴스가 Webex로 전송됩니다.
