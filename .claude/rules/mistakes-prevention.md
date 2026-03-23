# 실수 방지 규칙

## 경로
- 금지: Git/Docker/CI 파일에 절대 경로 → 대신: 상대 경로
- 금지: 로컬 전용 스크립트에 상대 경로 → 대신: 절대 경로

## Windows Batch
- 금지: `chcp 65001` 없이 한글 출력 → 대신: 파일 첫 줄에 `chcp 65001 >nul`

## 타임존
- 금지: `datetime.now()` → 대신: `datetime.now(KST)` 또는 `now_kst()`
- 금지: `date.today()` → 대신: `today_kst()`
- 금지: DB 저장 시 타임존 생략 → 대신: timezone-aware datetime 사용

## 비동기
- 금지: FastAPI 핸들러에서 `def` → 대신: `async def`
- 금지: `time.sleep()` → 대신: `await asyncio.sleep()`
- 금지: 동기 DB 드라이버 → 대신: asyncpg, databases 등 비동기 드라이버

## 보안
- 금지: 코드에 `"sk-..."`, `"ghp_..."` 등 키 문자열 → 대신: `os.environ["KEY"]`
- 금지: `.env` 파일 Git 커밋 → 대신: `.gitignore`에 `.env*` 패턴 등록
- 금지: `logger.info(f"token={token}")` → 대신: 민감값은 `***`로 마스킹

## 데이터베이스
- 금지: `SELECT *` → 대신: 필요한 컬럼만 명시
- 금지: `LIMIT` 없이 전체 조회 → 대신: 페이지네이션 적용
- 금지: 인덱스 없는 컬럼으로 WHERE (대용량) → 대신: 인덱스 생성 후 사용

<!-- 프로젝트별 실수 발생 시 아래에 추가 -->
