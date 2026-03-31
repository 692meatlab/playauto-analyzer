# 플레이오토 자동 수집기

플레이오토에서 주문 데이터를 자동으로 수집하여 GitHub에 업로드합니다.

## 설치 방법

### 1. Python 패키지 설치

```bash
cd automation
pip install -r requirements.txt
playwright install chromium
```

### 2. 환경변수 설정

`.env.example`을 `.env`로 복사 후 수정:

```bash
copy .env.example .env
```

`.env` 파일 내용:
```
PLAYAUTO_ID=플레이오토_이메일
PLAYAUTO_PW=플레이오토_비밀번호
GITHUB_TOKEN=ghp_xxxxx
GITHUB_REPO=692meatlab/playauto-analyzer
```

### 3. 테스트 실행

```bash
python playauto_collector.py
```

### 4. 윈도우 스케줄러 등록

`install_schedule.bat`을 **관리자 권한**으로 실행

- 매일 오전 8시 자동 실행
- 작업 이름: `PlayautoCollector`

## 다른 PC에서 실행하기

1. 이 `automation` 폴더 전체 복사
2. Python 설치 (3.10 이상)
3. 위 설치 방법 1~4 동일하게 진행
4. `.env` 파일은 복사 안 되므로 새로 생성

## 파일 구조

```
automation/
├── config.py              # 설정
├── playauto_collector.py  # 메인 수집기
├── run_collector.bat      # 실행 배치 파일
├── install_schedule.bat   # 스케줄러 등록
├── requirements.txt       # Python 패키지
├── .env                   # 환경변수 (비밀)
├── .env.example           # 환경변수 예시
├── downloads/             # 다운로드 파일
└── logs/                  # 로그 파일
```

## 로그 확인

`logs/collector_YYYYMMDD.log` 파일에서 실행 기록 확인

## 문제 해결

### 로그인 실패
- `logs/login_failed.png` 스크린샷 확인
- ID/PW 확인
- 플레이오토 사이트 UI 변경 시 선택자 수정 필요

### 다운로드 실패
- `logs/excel_btn_not_found.png` 스크린샷 확인
- 플레이오토에 데이터가 있는지 확인

### 스케줄러 미실행
- 작업 스케줄러에서 `PlayautoCollector` 작업 상태 확인
- PC가 켜져 있어야 실행됨
