# -*- coding: utf-8 -*-
"""
플레이오토 주문 데이터 자동 수집기

사용법:
    python playauto_collector.py

기능:
    1. 플레이오토 로그인
    2. 수집 버튼 클릭
    3. 주문 데이터 엑셀 다운로드
    4. GitHub에 자동 업로드
"""

import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import pandas as pd
import requests
import base64
import json
import time

from config import (
    PLAYAUTO_ID, PLAYAUTO_PW,
    GITHUB_TOKEN, GITHUB_REPO,
    PLAYAUTO_LOGIN_URL, PLAYAUTO_ORDER_URL,
    DOWNLOAD_DIR, LOG_DIR,
    PAGE_TIMEOUT, DOWNLOAD_TIMEOUT
)

# KST 타임존
KST = timezone(timedelta(hours=9))

def now_kst():
    return datetime.now(KST)

# 로깅 설정
log_file = LOG_DIR / f"collector_{now_kst().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PlayautoCollector:
    """플레이오토 데이터 수집기"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.page = None
        self.downloaded_file = None

    def run(self):
        """전체 수집 프로세스 실행"""
        logger.info("=" * 50)
        logger.info("플레이오토 데이터 수집 시작")
        logger.info(f"시작 시간: {now_kst().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 50)

        try:
            with sync_playwright() as p:
                # 브라우저 시작
                self.browser = p.chromium.launch(
                    headless=self.headless,
                    args=['--lang=ko-KR']
                )
                context = self.browser.new_context(
                    accept_downloads=True,
                    locale='ko-KR'
                )
                self.page = context.new_page()
                self.page.set_default_timeout(PAGE_TIMEOUT * 1000)

                # 1. 로그인
                if not self.login():
                    raise Exception("로그인 실패")

                # 2. 팝업 처리 (공지/광고 팝업 닫기)
                self.handle_popups()

                # 3. 수집 버튼 클릭
                if not self.click_collect():
                    logger.warning("수집 버튼을 찾지 못했거나 이미 수집됨")

                # 4. 주문 페이지로 이동
                if not self.go_to_orders():
                    raise Exception("주문 페이지 이동 실패")

                # 5. 엑셀 다운로드
                if not self.download_excel():
                    raise Exception("엑셀 다운로드 실패")

                # 6. GitHub 업로드
                if not self.upload_to_github():
                    raise Exception("GitHub 업로드 실패")

                logger.info("=" * 50)
                logger.info("데이터 수집 완료!")
                logger.info("=" * 50)
                return True

        except Exception as e:
            logger.error(f"수집 실패: {e}")
            return False

        finally:
            if self.browser:
                self.browser.close()

    def handle_popups(self) -> None:
        """로그인 후 공지/광고 팝업 처리.

        플레이오토 팝업 패턴:
        - "다음" 버튼을 끝까지 클릭해야 "닫기"가 활성화됨
        - iframe 또는 일반 DOM 팝업 모두 처리
        """
        logger.info("팝업 확인 중...")
        self.page.wait_for_timeout(2000)  # 팝업 로딩 대기

        iterations = 0
        max_iterations = 30  # 최대 반복 (무한루프 방지)

        while iterations < max_iterations:
            iterations += 1
            action_taken = False

            # 메인 페이지 + 모든 iframe 순서로 검색
            contexts = [self.page] + [f for f in self.page.frames if f != self.page.main_frame]

            for ctx in contexts:
                # 1순위: "다음" 버튼 (팝업 단계 진행)
                for selector in [
                    "button:has-text('다음')",
                    "a:has-text('다음')",
                    "input[value='다음']",
                ]:
                    try:
                        btn = ctx.locator(selector).first
                        if btn.is_visible(timeout=300) and btn.is_enabled():
                            btn.click()
                            logger.info(f"팝업 '다음' 클릭 ({iterations}번째)")
                            self.page.wait_for_timeout(600)
                            action_taken = True
                            break
                    except Exception:
                        pass
                if action_taken:
                    break

                # 2순위: 활성화된 "닫기"/"확인" 버튼
                for selector in [
                    "button:has-text('닫기')",
                    "a:has-text('닫기')",
                    "button:has-text('확인')",
                    "a:has-text('확인')",
                    "button:has-text('오늘하루 보지않기')",
                    "a:has-text('오늘하루 보지않기')",
                    ".popup-close",
                    ".modal-close",
                    "[class*='btn-close']",
                ]:
                    try:
                        btn = ctx.locator(selector).first
                        if btn.is_visible(timeout=300) and btn.is_enabled():
                            btn.click()
                            logger.info(f"팝업 닫기 완료 ({iterations}번째)")
                            self.page.wait_for_timeout(600)
                            action_taken = True
                            break
                    except Exception:
                        pass
                if action_taken:
                    break

            # 팝업이 더 이상 없으면 종료
            if not action_taken:
                logger.info(f"팝업 처리 완료 (총 {iterations - 1}회 처리)")
                break

        if iterations >= max_iterations:
            logger.warning("팝업 처리 최대 반복 도달, 스크린샷 저장")
            self.page.screenshot(path=str(LOG_DIR / "popup_timeout.png"))

    def login(self) -> bool:
        """플레이오토 로그인"""
        logger.info("로그인 시도...")

        try:
            self.page.goto(PLAYAUTO_LOGIN_URL)
            self.page.wait_for_load_state('networkidle')
            time.sleep(2)  # Angular 렌더링 대기

            # 아이디 입력 (다양한 선택자 시도)
            id_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="이메일"]',
                'input[placeholder*="아이디"]',
                '#email',
                '#userId',
                'input[type="text"]'
            ]

            id_input = None
            for selector in id_selectors:
                try:
                    id_input = self.page.wait_for_selector(selector, timeout=3000)
                    if id_input:
                        break
                except:
                    continue

            if not id_input:
                logger.error("아이디 입력 필드를 찾을 수 없습니다")
                # 페이지 스크린샷 저장
                self.page.screenshot(path=str(LOG_DIR / "login_page.png"))
                return False

            id_input.fill(PLAYAUTO_ID)
            logger.info("아이디 입력 완료")

            # 비밀번호 입력
            pw_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password'
            ]

            pw_input = None
            for selector in pw_selectors:
                try:
                    pw_input = self.page.wait_for_selector(selector, timeout=3000)
                    if pw_input:
                        break
                except:
                    continue

            if not pw_input:
                logger.error("비밀번호 입력 필드를 찾을 수 없습니다")
                return False

            pw_input.fill(PLAYAUTO_PW)
            logger.info("비밀번호 입력 완료")

            # 로그인 버튼 클릭
            login_selectors = [
                'button[type="submit"]',
                'button:has-text("Sign In")',
                'button:has-text("로그인")',
                'input[type="submit"]',
                '.login-btn',
                '#loginBtn'
            ]

            for selector in login_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=2000)
                    if btn:
                        btn.click()
                        break
                except:
                    continue

            # 로그인 성공 확인
            time.sleep(3)
            self.page.wait_for_load_state('networkidle')

            # URL 변경 확인 (로그인 페이지에서 벗어났는지)
            if 'login' not in self.page.url.lower():
                logger.info("로그인 성공!")
                return True
            else:
                logger.error("로그인 실패 - 여전히 로그인 페이지")
                self.page.screenshot(path=str(LOG_DIR / "login_failed.png"))
                return False

        except Exception as e:
            logger.error(f"로그인 중 오류: {e}")
            self.page.screenshot(path=str(LOG_DIR / "login_error.png"))
            return False

    def click_collect(self) -> bool:
        """수집 버튼 클릭"""
        logger.info("수집 버튼 찾는 중...")

        try:
            collect_selectors = [
                'button:has-text("수집")',
                'a:has-text("수집")',
                '.collect-btn',
                '[data-action="collect"]',
                'button:has-text("주문수집")',
                'button:has-text("데이터 수집")'
            ]

            for selector in collect_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=5000)
                    if btn and btn.is_visible():
                        btn.click()
                        logger.info("수집 버튼 클릭 완료")
                        time.sleep(5)  # 수집 완료 대기
                        return True
                except:
                    continue

            logger.info("수집 버튼을 찾지 못함 (이미 수집되었거나 버튼 없음)")
            return False

        except Exception as e:
            logger.warning(f"수집 버튼 클릭 중 오류: {e}")
            return False

    def go_to_orders(self) -> bool:
        """주문 목록 페이지로 이동"""
        logger.info("주문 목록 페이지로 이동...")

        try:
            self.page.goto(PLAYAUTO_ORDER_URL)
            self.page.wait_for_load_state('networkidle')
            time.sleep(3)

            logger.info(f"현재 URL: {self.page.url}")
            return True

        except Exception as e:
            logger.error(f"주문 페이지 이동 실패: {e}")
            return False

    def download_excel(self) -> bool:
        """엑셀 파일 다운로드"""
        logger.info("엑셀 다운로드 시도...")

        try:
            # 엑셀 다운로드 버튼 찾기
            excel_selectors = [
                'button:has-text("엑셀")',
                'button:has-text("Excel")',
                'button:has-text("다운로드")',
                'a:has-text("엑셀")',
                '.excel-download',
                '[data-action="excel"]',
                'button:has-text("내보내기")',
                'button[title*="엑셀"]'
            ]

            download_btn = None
            for selector in excel_selectors:
                try:
                    download_btn = self.page.wait_for_selector(selector, timeout=3000)
                    if download_btn and download_btn.is_visible():
                        break
                    download_btn = None
                except:
                    continue

            if not download_btn:
                logger.error("엑셀 다운로드 버튼을 찾을 수 없습니다")
                self.page.screenshot(path=str(LOG_DIR / "excel_btn_not_found.png"))
                return False

            # 다운로드 이벤트 대기
            with self.page.expect_download(timeout=DOWNLOAD_TIMEOUT * 1000) as download_info:
                download_btn.click()
                logger.info("다운로드 버튼 클릭")

            download = download_info.value

            # 파일 저장
            timestamp = now_kst().strftime('%Y%m%d_%H%M%S')
            filename = f"playauto_orders_{timestamp}.xlsx"
            save_path = DOWNLOAD_DIR / filename
            download.save_as(save_path)

            self.downloaded_file = save_path
            logger.info(f"다운로드 완료: {save_path}")
            return True

        except PlaywrightTimeout:
            logger.error("다운로드 시간 초과")
            return False
        except Exception as e:
            logger.error(f"다운로드 중 오류: {e}")
            self.page.screenshot(path=str(LOG_DIR / "download_error.png"))
            return False

    def upload_to_github(self) -> bool:
        """GitHub에 데이터 업로드"""
        logger.info("GitHub 업로드 시작...")

        if not self.downloaded_file or not self.downloaded_file.exists():
            logger.error("업로드할 파일이 없습니다")
            return False

        try:
            # 엑셀 파일 읽기
            df = pd.read_excel(self.downloaded_file)
            logger.info(f"데이터 로드: {len(df)} 행")

            # CSV로 변환
            csv_content = df.to_csv(index=False)

            # GitHub API로 업로드
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }

            # 기존 파일 SHA 가져오기
            file_path = "data/order_data.csv"
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

            resp = requests.get(url, headers=headers)
            sha = resp.json().get('sha') if resp.status_code == 200 else None

            # 파일 업로드
            content_b64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
            data = {
                "message": f"자동 업데이트: {now_kst().strftime('%Y-%m-%d %H:%M')}",
                "content": content_b64,
                "branch": "main"
            }
            if sha:
                data["sha"] = sha

            resp = requests.put(url, headers=headers, json=data)

            if resp.status_code in [200, 201]:
                logger.info("GitHub 업로드 성공!")
                return True
            else:
                logger.error(f"GitHub 업로드 실패: {resp.status_code} - {resp.text}")
                return False

        except Exception as e:
            logger.error(f"GitHub 업로드 중 오류: {e}")
            return False


def main():
    """메인 실행 함수"""
    # 설정 검증
    if not PLAYAUTO_ID or not PLAYAUTO_PW:
        logger.error("PLAYAUTO_ID, PLAYAUTO_PW 환경변수를 설정하세요")
        logger.error(".env 파일에 다음 내용 추가:")
        logger.error("  PLAYAUTO_ID=your_email")
        logger.error("  PLAYAUTO_PW=your_password")
        sys.exit(1)

    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN 환경변수를 설정하세요")
        sys.exit(1)

    # 수집기 실행
    collector = PlayautoCollector(headless=True)
    success = collector.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
