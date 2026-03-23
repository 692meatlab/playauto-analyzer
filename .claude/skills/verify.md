# /verify - 프로젝트 검증 실행

## 트리거
"검증", "verify", "테스트", "test", "린트", "lint"

## 프로젝트 감지 (위에서부터 우선)
| 파일 | 유형 |
|------|------|
| `pyproject.toml` | Python (Poetry) |
| `requirements.txt` (pyproject 없을 때) | Python (pip) |
| `package.json` + `next.config.*` | Next.js |
| `package.json` (next.config 없을 때) | Node.js |

## Python 실행 순서

| 단계 | 명령어 | 비고 |
|------|--------|------|
| 1. 린트 | `poetry run ruff check .` | --fix 시 `--fix` 추가 |
| 2. 포맷 | `poetry run ruff format .` | --fix 시만 실행 |
| 3. 타입 | `poetry run mypy src/ --ignore-missing-imports` | |
| 4. 테스트 | `poetry run pytest tests/ -v --cov=src` | 커버리지 80% 목표 |
| 5. 보안 | `poetry run bandit -r src/ -ll -q` | --detail 시만 |

pip 환경: `poetry run` 제거하고 직접 실행.

## Node.js 실행 순서

| 단계 | 명령어 | 비고 |
|------|--------|------|
| 1. 린트 | `npm run lint` | --fix 시 `-- --fix` 추가 |
| 2. 타입 | `npx tsc --noEmit` | |
| 3. 테스트 | `npm test -- --watchAll=false` | |
| 4. 빌드 | `npm run build` | |
| 5. 보안 | `npm audit` | --detail 시만 |

## 옵션

| 옵션 | 동작 |
|------|------|
| (없음) | 전체 검증 (보안 제외) |
| `--quick` | 린트만 실행 |
| `--fix` | 린트+포맷 자동수정 후 전체 실행 |
| `--detail` | 전체 + 보안검사 추가 |

## 보고 형식

```
## 검증 결과: PASSED / FAILED

| 단계 | 상태 | 상세 |
|------|------|------|
| 린트 | PASSED/FAILED | 에러 내용 또는 "통과" |
| 타입 | PASSED/FAILED | ... |
| 테스트 | PASSED/FAILED | N/N 통과, 커버리지 N% |
```

실패 시: 에러 메시지 + 파일:라인 포함 보고. 자동수정 가능하면 `--fix` 제안.

## 참고
스크립트: `scripts/verify_all.py` (Python) / `scripts/verify_all.js` (Node.js)
