# -*- coding: utf-8 -*-
"""플레이오토 자동화 설정"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 플레이오토 로그인 정보
PLAYAUTO_ID = os.getenv("PLAYAUTO_ID", "")
PLAYAUTO_PW = os.getenv("PLAYAUTO_PW", "")

# GitHub 설정
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "692meatlab/playauto-analyzer")

# 경로 설정
BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOG_DIR = BASE_DIR / "logs"

# 다운로드 폴더 생성
DOWNLOAD_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 플레이오토 URL
PLAYAUTO_LOGIN_URL = "https://app.playauto.io/login.html"
PLAYAUTO_ORDER_URL = "https://app.playauto.io/order/shipment/delivery_list"

# 타임아웃 설정 (초)
PAGE_TIMEOUT = 60
DOWNLOAD_TIMEOUT = 120
