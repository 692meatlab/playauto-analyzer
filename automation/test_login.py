# -*- coding: utf-8 -*-
"""
플레이오토 로그인 테스트 스크립트
실행: python test_login.py
"""

import sys
import time
from playwright.sync_api import sync_playwright

# .env 파일에서 로드하거나 직접 입력
PLAYAUTO_ID = ""  # 여기에 이메일 입력
PLAYAUTO_PW = ""  # 여기에 비밀번호 입력

def test_login():
    print("플레이오토 로그인 테스트 시작...")
    print()

    if not PLAYAUTO_ID or not PLAYAUTO_PW:
        print("[오류] PLAYAUTO_ID, PLAYAUTO_PW를 입력하세요")
        print("test_login.py 파일을 열어 ID/PW를 입력하거나")
        print(".env 파일을 생성하세요")
        return False

    with sync_playwright() as p:
        # 브라우저 시작 (headless=False로 실제 화면 보기)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            # 로그인 페이지 이동
            print("1. 로그인 페이지 이동...")
            page.goto("https://app.playauto.io/login.html")
            page.wait_for_load_state('networkidle')
            time.sleep(3)

            # 페이지 요소 분석
            print("2. 페이지 요소 분석...")
            print()

            # input 요소 찾기
            inputs = page.query_selector_all('input')
            print(f"   input 요소 {len(inputs)}개 발견:")
            for i, inp in enumerate(inputs):
                inp_type = inp.get_attribute('type') or 'text'
                inp_name = inp.get_attribute('name') or ''
                inp_placeholder = inp.get_attribute('placeholder') or ''
                inp_id = inp.get_attribute('id') or ''
                print(f"   [{i}] type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

            print()

            # button 요소 찾기
            buttons = page.query_selector_all('button')
            print(f"   button 요소 {len(buttons)}개 발견:")
            for i, btn in enumerate(buttons):
                btn_text = btn.inner_text().strip()[:30]
                btn_type = btn.get_attribute('type') or ''
                btn_class = btn.get_attribute('class') or ''
                print(f"   [{i}] text='{btn_text}', type={btn_type}")

            print()
            print("3. 로그인 시도...")

            # 아이디 입력 시도
            id_input = page.query_selector('input[type="email"], input[type="text"]')
            if id_input:
                id_input.fill(PLAYAUTO_ID)
                print("   아이디 입력 완료")

            # 비밀번호 입력 시도
            pw_input = page.query_selector('input[type="password"]')
            if pw_input:
                pw_input.fill(PLAYAUTO_PW)
                print("   비밀번호 입력 완료")

            # 로그인 버튼 클릭
            login_btn = page.query_selector('button[type="submit"], button:has-text("Sign In"), button:has-text("로그인")')
            if login_btn:
                login_btn.click()
                print("   로그인 버튼 클릭")

            # 결과 대기
            time.sleep(5)
            page.wait_for_load_state('networkidle')

            print()
            print(f"4. 현재 URL: {page.url}")

            if 'login' not in page.url.lower():
                print()
                print("[성공] 로그인 성공!")

                # 10초간 화면 유지 (확인용)
                print()
                print("10초 후 브라우저 종료...")
                time.sleep(10)
                return True
            else:
                print()
                print("[실패] 로그인 실패 - 여전히 로그인 페이지")
                page.screenshot(path="login_failed.png")
                print("스크린샷 저장: login_failed.png")
                time.sleep(10)
                return False

        except Exception as e:
            print(f"[오류] {e}")
            page.screenshot(path="login_error.png")
            return False
        finally:
            browser.close()


if __name__ == "__main__":
    # .env 파일에서 로드 시도
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        if not PLAYAUTO_ID:
            PLAYAUTO_ID = os.getenv("PLAYAUTO_ID", "")
        if not PLAYAUTO_PW:
            PLAYAUTO_PW = os.getenv("PLAYAUTO_PW", "")
    except ImportError:
        pass

    success = test_login()
    sys.exit(0 if success else 1)
