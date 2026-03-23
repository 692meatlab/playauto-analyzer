# -*- coding: utf-8 -*-
"""플레이오토 주문/매출 데이터 분석 모듈"""

import pandas as pd
import json
import requests
import base64
from io import StringIO
from datetime import datetime, date, timezone, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# KST 타임존
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """현재 시간을 KST로 반환"""
    return datetime.now(KST)


def today_kst() -> date:
    """오늘 날짜를 KST로 반환"""
    return datetime.now(KST).date()


class GitHubStorage:
    """GitHub 저장소 기반 데이터 저장"""

    def __init__(self, token: str, repo: str, branch: str = "main"):
        self.token = token
        self.repo = repo  # "username/repo-name"
        self.branch = branch
        self.api_base = "https://api.github.com"
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def _get_file(self, path: str) -> Optional[dict]:
        """GitHub에서 파일 정보 가져오기"""
        url = f"{self.api_base}/repos/{self.repo}/contents/{path}?ref={self.branch}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return None

    def read_json(self, path: str) -> Optional[dict]:
        """GitHub에서 JSON 파일 읽기"""
        file_info = self._get_file(path)
        if file_info and 'content' in file_info:
            content = base64.b64decode(file_info['content']).decode('utf-8')
            return json.loads(content)
        return None

    def read_csv(self, path: str) -> Optional[pd.DataFrame]:
        """GitHub에서 CSV 파일 읽기 (1MB 초과 파일은 download_url 사용)"""
        file_info = self._get_file(path)
        if not file_info:
            return None

        # content가 있고 비어있지 않으면 직접 디코딩
        content_b64 = file_info.get('content', '')
        if content_b64 and len(content_b64) > 0:
            content = base64.b64decode(content_b64).decode('utf-8')
            return pd.read_csv(StringIO(content))

        # 1MB 초과 파일은 download_url 사용
        download_url = file_info.get('download_url')
        if download_url:
            response = requests.get(download_url)
            if response.status_code == 200:
                return pd.read_csv(StringIO(response.text))

        return None

    def write_file(self, path: str, content: str, message: str = "Update data") -> bool:
        """GitHub에 파일 쓰기"""
        url = f"{self.api_base}/repos/{self.repo}/contents/{path}"

        # 기존 파일 SHA 확인 (업데이트 시 필요)
        existing = self._get_file(path)
        sha = existing.get('sha') if existing else None

        # Base64 인코딩
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        data = {
            "message": message,
            "content": content_b64,
            "branch": self.branch
        }
        if sha:
            data["sha"] = sha

        response = requests.put(url, headers=self.headers, json=data)
        return response.status_code in [200, 201]

    def write_json(self, path: str, data: dict, message: str = "Update data") -> bool:
        """GitHub에 JSON 파일 쓰기"""
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return self.write_file(path, content, message)

    def write_csv(self, path: str, df: pd.DataFrame, message: str = "Update data") -> bool:
        """GitHub에 CSV 파일 쓰기"""
        content = df.to_csv(index=False)
        return self.write_file(path, content, message)

    def delete_file(self, path: str, message: str = "Delete data") -> bool:
        """GitHub에서 파일 삭제"""
        existing = self._get_file(path)
        if not existing:
            return True

        url = f"{self.api_base}/repos/{self.repo}/contents/{path}"
        data = {
            "message": message,
            "sha": existing['sha'],
            "branch": self.branch
        }
        response = requests.delete(url, headers=self.headers, json=data)
        return response.status_code == 200


class OrderAnalyzer:
    """플레이오토 주문/매출 데이터 분석기"""

    # 사업장 분류 기준 (계정 기반)
    BUSINESS_RULES = {
        '육구이': ['692meatlab', '692'],
        '우주인': ['kms', 'sosin']
    }

    # 데이터 저장 경로 (로컬)
    DATA_DIR = Path.home() / 'playauto-analyzer-data'
    DATA_FILE = DATA_DIR / 'order_data.pkl'
    META_FILE = DATA_DIR / 'order_metadata.json'

    # GitHub 저장 경로
    GITHUB_DATA_FILE = "data/order_data.csv"
    GITHUB_META_FILE = "data/metadata.json"

    def __init__(self, github_token: str = None, github_repo: str = None):
        self.data: Dict[str, pd.DataFrame] = {}
        self.metadata: Dict[str, dict] = {}
        self.combined_df: Optional[pd.DataFrame] = None

        # GitHub 저장소 설정
        self.github: Optional[GitHubStorage] = None
        if github_token and github_repo:
            self.github = GitHubStorage(github_token, github_repo)

        # 로컬 디렉토리 생성 (로컬 모드일 때만)
        if not self.github:
            self.DATA_DIR.mkdir(exist_ok=True)

        self._load_saved_data()

    def _load_saved_data(self):
        """저장된 데이터 로드"""
        if self.github:
            self._load_from_github()
        else:
            self._load_from_local()

    def _load_from_github(self):
        """GitHub에서 데이터 로드"""
        try:
            # 메타데이터 로드
            meta = self.github.read_json(self.GITHUB_META_FILE)
            if meta:
                self.metadata = meta

            # 데이터 로드
            df = self.github.read_csv(self.GITHUB_DATA_FILE)
            if df is not None and not df.empty:
                # 날짜 컬럼 변환
                if '날짜' in df.columns:
                    df['날짜'] = pd.to_datetime(df['날짜']).dt.date
                if '출고날짜' in df.columns:
                    df['출고날짜'] = pd.to_datetime(df['출고날짜']).dt.date
                if '결제일시' in df.columns:
                    df['결제일시'] = pd.to_datetime(df['결제일시'])
                if '출고일시' in df.columns:
                    df['출고일시'] = pd.to_datetime(df['출고일시'])
                if '취소여부' in df.columns:
                    df['취소여부'] = df['취소여부'].astype(bool)

                self.combined_df = df
                for period in df['기간'].unique():
                    self.data[period] = df[df['기간'] == period].copy()
        except Exception as e:
            print(f"GitHub 데이터 로드 실패: {e}")

    def _load_from_local(self):
        """로컬에서 데이터 로드"""
        if self.DATA_FILE.exists():
            try:
                self.combined_df = pd.read_pickle(self.DATA_FILE)
                if self.combined_df is not None and not self.combined_df.empty:
                    for period in self.combined_df['기간'].unique():
                        self.data[period] = self.combined_df[self.combined_df['기간'] == period].copy()
            except Exception as e:
                print(f"주문 데이터 로드 실패: {e}")
                self.combined_df = None

        if self.META_FILE.exists():
            try:
                with open(self.META_FILE, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception:
                self.metadata = {}

    def _save_data(self):
        """데이터 저장"""
        if self.github:
            self._save_to_github()
        else:
            self._save_to_local()

    def _save_to_github(self):
        """GitHub에 데이터 저장"""
        try:
            # 메타데이터 저장
            self.github.write_json(self.GITHUB_META_FILE, self.metadata, "Update metadata")

            # 데이터 저장
            if self.combined_df is not None and not self.combined_df.empty:
                self.github.write_csv(self.GITHUB_DATA_FILE, self.combined_df, "Update order data")
        except Exception as e:
            print(f"GitHub 저장 실패: {e}")

    def _save_to_local(self):
        """로컬에 데이터 저장"""
        if self.combined_df is not None and not self.combined_df.empty:
            self.combined_df.to_pickle(self.DATA_FILE)

        with open(self.META_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2, default=str)

    def classify_business(self, account: str) -> str:
        """계정을 기준으로 사업장 분류"""
        if pd.isna(account):
            return '미분류'

        account_lower = str(account).lower()

        for keyword in self.BUSINESS_RULES['육구이']:
            if keyword.lower() in account_lower:
                return '육구이'

        for keyword in self.BUSINESS_RULES['우주인']:
            if keyword.lower() in account_lower:
                return '우주인'

        return '미분류'

    def load_excel(self, file) -> pd.DataFrame:
        """엑셀 파일 로드 및 처리 (날짜는 파일 내 컬럼에서 자동 추출)"""
        df = pd.read_excel(file)

        # ===== 전처리 Phase =====
        original_count = len(df)

        # 1. 컬럼명 통일 (쇼핑몰 -> 쇼핑몰명)
        if '쇼핑몰' in df.columns and '쇼핑몰명' not in df.columns:
            df = df.rename(columns={'쇼핑몰': '쇼핑몰명'})

        # 2. 중복 행 제거 (묶음번호 + SKU코드 기준)
        if '묶음번호' in df.columns and 'SKU코드' in df.columns:
            df = df.drop_duplicates(subset=['묶음번호', 'SKU코드'], keep='first')

        # 3. 금액 컬럼 결측치 처리
        if '금액' in df.columns:
            df['금액'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0).astype(int)

        # 4. 주문수량 결측치 처리
        if '주문수량' in df.columns:
            df['주문수량'] = pd.to_numeric(df['주문수량'], errors='coerce').fillna(0).astype(int)

        # 5. 이상치 처리 (음수 금액 → 0으로 처리, 취소/환불 건은 별도 처리)
        if '금액' in df.columns:
            df.loc[df['금액'] < 0, '금액'] = 0

        # 전처리 결과 기록
        cleaned_count = len(df)
        removed_count = original_count - cleaned_count

        # 결제완료일에서 날짜 추출 (매출 분석용)
        if '결제완료일' in df.columns:
            df['결제일시'] = pd.to_datetime(df['결제완료일'], errors='coerce')
            df['날짜'] = df['결제일시'].dt.date
        else:
            df['날짜'] = None

        # 출고완료일에서 날짜 추출 (출고 분석용)
        if '출고완료일' in df.columns:
            df['출고일시'] = pd.to_datetime(df['출고완료일'], errors='coerce')
            df['출고날짜'] = df['출고일시'].dt.date
        else:
            # 출고완료일이 없으면 결제완료일 사용
            df['출고날짜'] = df['날짜']

        # 사업장 분류 (계정 기준)
        if '계정' in df.columns:
            df['사업장'] = df['계정'].apply(self.classify_business)
        else:
            df['사업장'] = '미분류'

        # 취소/반품 여부 (주문수량 = 0)
        if '주문수량' in df.columns:
            df['취소여부'] = df['주문수량'] == 0
        else:
            df['취소여부'] = False

        # 파일 내 날짜 범위 자동 추출
        valid_dates = df[df['날짜'].notna()]['날짜']
        if len(valid_dates) > 0:
            min_date = pd.to_datetime(valid_dates.min())
            max_date = pd.to_datetime(valid_dates.max())
            start_str = min_date.strftime('%Y-%m-%d')
            end_str = max_date.strftime('%Y-%m-%d')
        else:
            start_str = now_kst().strftime('%Y-%m-%d')
            end_str = start_str

        # 기간 정보 추가
        df['기간'] = f"{start_str} ~ {end_str}"
        df['년월'] = pd.to_datetime(df['날짜']).dt.strftime('%Y-%m')

        # 데이터 저장
        period_key = df['기간'].iloc[0]
        self.data[period_key] = df

        # 메타데이터 저장
        file_name = file.name if hasattr(file, 'name') else str(file)

        # 통계 계산
        total_orders = df['묶음번호'].nunique() if '묶음번호' in df.columns else len(df)
        total_revenue = df['금액'].sum() if '금액' in df.columns else 0
        cancel_count = df['취소여부'].sum()

        self.metadata[period_key] = {
            'file_name': file_name,
            'start_date': start_str,
            'end_date': end_str,
            'row_count': len(df),
            'original_row_count': original_count,
            'removed_duplicates': removed_count,
            'order_count': int(total_orders),
            'total_revenue': int(total_revenue),
            'cancel_count': int(cancel_count),
            'loaded_at': now_kst().strftime('%Y-%m-%d %H:%M:%S')
        }

        self._update_combined()
        self._save_data()

        return df

    def _update_combined(self):
        """통합 데이터프레임 업데이트"""
        if self.data:
            self.combined_df = pd.concat(self.data.values(), ignore_index=True)
        else:
            self.combined_df = None

    def delete_period(self, period: str) -> bool:
        """특정 기간 데이터 삭제"""
        if period in self.data:
            del self.data[period]
            if period in self.metadata:
                del self.metadata[period]
            self._update_combined()
            self._save_data()
            return True
        return False

    def clear_all_data(self):
        """모든 데이터 삭제"""
        self.data = {}
        self.metadata = {}
        self.combined_df = None

        if self.github:
            # GitHub에서 삭제
            self.github.delete_file(self.GITHUB_DATA_FILE, "Clear all data")
            self.github.delete_file(self.GITHUB_META_FILE, "Clear metadata")
        else:
            # 로컬에서 삭제
            if self.DATA_FILE.exists():
                self.DATA_FILE.unlink()
            if self.META_FILE.exists():
                self.META_FILE.unlink()

    def get_loaded_periods(self) -> List[dict]:
        """로드된 기간 목록 반환"""
        periods = []
        for period, meta in self.metadata.items():
            periods.append({
                '기간': period,
                '파일명': meta.get('file_name', ''),
                '건수': meta.get('row_count', 0),
                '주문수': meta.get('order_count', 0),
                '매출': meta.get('total_revenue', 0),
                '취소': meta.get('cancel_count', 0),
                '로드일시': meta.get('loaded_at', '')
            })
        return sorted(periods, key=lambda x: x['기간'], reverse=True)

    # ===== 날짜 범위 관련 (매출용: 결제완료일 기준) =====

    def get_date_range(self) -> tuple:
        """매출 분석용 날짜 범위 반환 (결제완료일 기준)"""
        if self.combined_df is None or self.combined_df.empty:
            return None, None

        df = self.combined_df[self.combined_df['날짜'].notna()]
        if df.empty:
            return None, None

        min_date = pd.to_datetime(df['날짜']).min()
        max_date = pd.to_datetime(df['날짜']).max()
        return min_date, max_date

    def filter_by_date_range(self, start: date, end: date, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """매출 분석용 날짜 범위 필터링 (결제완료일 기준)"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        data_copy = data.copy()
        data_copy['날짜_dt'] = pd.to_datetime(data_copy['날짜'])
        mask = (data_copy['날짜_dt'].dt.date >= start) & (data_copy['날짜_dt'].dt.date <= end)
        return data_copy[mask].drop(columns=['날짜_dt'])

    # ===== 날짜 범위 관련 (출고용: 출고완료일 기준) =====

    def get_shipment_date_range(self) -> tuple:
        """출고 분석용 날짜 범위 반환 (출고완료일 기준)"""
        if self.combined_df is None or self.combined_df.empty:
            return None, None

        df = self.combined_df[self.combined_df['출고날짜'].notna()]
        if df.empty:
            return None, None

        min_date = pd.to_datetime(df['출고날짜']).min()
        max_date = pd.to_datetime(df['출고날짜']).max()
        return min_date, max_date

    def filter_by_shipment_date_range(self, start: date, end: date, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """출고 분석용 날짜 범위 필터링 (출고완료일 기준)"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        data_copy = data.copy()
        data_copy['출고날짜_dt'] = pd.to_datetime(data_copy['출고날짜'])
        mask = (data_copy['출고날짜_dt'].dt.date >= start) & (data_copy['출고날짜_dt'].dt.date <= end)
        return data_copy[mask].drop(columns=['출고날짜_dt'])

    def filter_by_business(self, business: str, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """사업장별 필터링"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        if business == '전체':
            return data.copy()
        return data[data['사업장'] == business].copy()

    # ===== 분석 메서드 =====

    def _get_shop_col(self, df: pd.DataFrame) -> str:
        """쇼핑몰 컬럼명 반환 (쇼핑몰명 또는 쇼핑몰)"""
        if '쇼핑몰명' in df.columns:
            return '쇼핑몰명'
        elif '쇼핑몰' in df.columns:
            return '쇼핑몰'
        return '쇼핑몰명'  # 기본값

    def get_summary_stats(self, df: Optional[pd.DataFrame] = None) -> Dict:
        """요약 통계"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return {
                '총 매출': 0,
                '판매건수': 0,
                '판매수량': 0,
                '취소건수': 0,
                '취소율': 0
            }

        # 정상 주문 (취소 아닌 것)
        normal = data[~data['취소여부']]
        cancelled = data[data['취소여부']]

        total_revenue = int(normal['금액'].sum()) if '금액' in normal.columns else 0
        order_count = normal['묶음번호'].nunique() if '묶음번호' in normal.columns else len(normal)
        qty_sum = int(normal['주문수량'].sum()) if '주문수량' in normal.columns else 0
        cancel_count = len(cancelled)
        total_count = len(data)
        cancel_rate = round(cancel_count / total_count * 100, 1) if total_count > 0 else 0

        return {
            '총 매출': total_revenue,
            '판매건수': int(order_count),
            '판매수량': qty_sum,
            '취소건수': cancel_count,
            '취소율': cancel_rate
        }

    def analyze_by_business(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """사업장별 분석"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        # 정상 주문만
        normal = data[~data['취소여부']]

        result = normal.groupby('사업장').agg({
            '금액': 'sum',
            '주문수량': 'sum',
            '묶음번호': 'nunique',
            'SKU상품명': 'nunique'
        }).reset_index()

        result.columns = ['사업장', '매출', '판매수량', '판매건수', '상품종류']

        # 취소 건수
        cancel_df = data[data['취소여부']].groupby('사업장').size().reset_index(name='취소건수')
        result = result.merge(cancel_df, on='사업장', how='left').fillna(0)
        result['취소건수'] = result['취소건수'].astype(int)

        total = result['매출'].sum()
        result['매출비율(%)'] = (result['매출'] / total * 100).round(1) if total > 0 else 0
        result = result.sort_values('매출', ascending=False)

        return result

    def analyze_by_shop(self, df: Optional[pd.DataFrame] = None, by_business: bool = True) -> pd.DataFrame:
        """쇼핑몰별 분석"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        normal = data[~data['취소여부']]
        shop_col = self._get_shop_col(normal)

        if by_business:
            result = normal.groupby(['사업장', shop_col]).agg({
                '금액': 'sum',
                '주문수량': 'sum',
                '묶음번호': 'nunique'
            }).reset_index()
            result.columns = ['사업장', '쇼핑몰명', '매출', '판매수량', '판매건수']
        else:
            result = normal.groupby(shop_col).agg({
                '금액': 'sum',
                '주문수량': 'sum',
                '묶음번호': 'nunique'
            }).reset_index()
            result.columns = ['쇼핑몰명', '매출', '판매수량', '판매건수']

        result = result.sort_values('매출', ascending=False)
        total = result['매출'].sum()
        result['매출비율(%)'] = (result['매출'] / total * 100).round(1) if total > 0 else 0

        return result

    def analyze_by_product(self, df: Optional[pd.DataFrame] = None, top_n: int = 30) -> pd.DataFrame:
        """상품별 분석"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        normal = data[~data['취소여부']]
        shop_col = self._get_shop_col(normal)

        result = normal.groupby(['사업장', 'SKU코드', 'SKU상품명']).agg({
            '금액': 'sum',
            '주문수량': 'sum',
            '묶음번호': 'nunique',
            shop_col: lambda x: ', '.join(sorted(x.unique()))
        }).reset_index()

        result.columns = ['사업장', 'SKU코드', '상품명', '매출', '판매수량', '판매건수', '판매채널']
        result = result.sort_values('매출', ascending=False)
        result['순위'] = range(1, len(result) + 1)
        result = result[['순위', '사업장', '상품명', '매출', '판매수량', '판매건수', '판매채널']]

        return result.head(top_n)

    def analyze_daily(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """일별 매출 분석 (결제완료일 기준)"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        normal = data[~data['취소여부']]

        result = normal.groupby('날짜').agg({
            '금액': 'sum',
            '주문수량': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()

        result.columns = ['날짜', '매출', '판매수량', '판매건수']
        result = result.sort_values('날짜')

        return result

    def analyze_daily_shipment(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """일별 출고 분석 (출고완료일 기준)"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        normal = data[~data['취소여부']]
        # 출고날짜가 있는 것만 (출고 완료된 건)
        normal = normal[normal['출고날짜'].notna()]

        if normal.empty:
            return pd.DataFrame()

        result = normal.groupby('출고날짜').agg({
            '주문수량': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()

        result.columns = ['날짜', '출고수량', '출고건수']
        result = result.sort_values('날짜')

        return result

    def analyze_cancellations(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """취소/반품 분석"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        cancelled = data[data['취소여부']]
        if cancelled.empty:
            return pd.DataFrame()

        shop_col = self._get_shop_col(cancelled)
        # 금액 컬럼이 없을 수 있으므로 실결제금액 사용
        amount_col = '금액' if '금액' in cancelled.columns else '금액'

        result = cancelled.groupby(['사업장', shop_col, 'SKU상품명']).agg({
            amount_col: 'sum',
            '묶음번호': 'nunique'
        }).reset_index()

        result.columns = ['사업장', '쇼핑몰명', '상품명', '취소금액', '취소건수']
        result = result.sort_values('취소건수', ascending=False)

        return result

    def compare_periods(self, base_start: date, base_end: date,
                        compare_start: date, compare_end: date) -> Dict:
        """기간 비교"""
        if self.combined_df is None or self.combined_df.empty:
            return {}

        base_df = self.filter_by_date_range(base_start, base_end)
        compare_df = self.filter_by_date_range(compare_start, compare_end)

        base_stats = self.get_summary_stats(base_df)
        compare_stats = self.get_summary_stats(compare_df)

        diff_revenue = base_stats['총 매출'] - compare_stats['총 매출']
        if compare_stats['총 매출'] > 0:
            change_rate = (diff_revenue / compare_stats['총 매출'] * 100)
        else:
            change_rate = 0

        return {
            'base': {'stats': base_stats},
            'compare': {'stats': compare_stats},
            'diff_revenue': diff_revenue,
            'change_rate': round(change_rate, 1)
        }

    def compare_shipment_periods(self, base_start: date, base_end: date,
                                  compare_start: date, compare_end: date) -> Dict:
        """출고 기간 비교 (출고완료일 기준)"""
        if self.combined_df is None or self.combined_df.empty:
            return {}

        base_df = self.filter_by_shipment_date_range(base_start, base_end)
        compare_df = self.filter_by_shipment_date_range(compare_start, compare_end)

        base_stats = self.get_summary_stats(base_df)
        compare_stats = self.get_summary_stats(compare_df)

        diff_qty = base_stats['판매수량'] - compare_stats['판매수량']
        if compare_stats['판매수량'] > 0:
            change_rate = (diff_qty / compare_stats['판매수량'] * 100)
        else:
            change_rate = 0

        return {
            'base': {'stats': base_stats},
            'compare': {'stats': compare_stats},
            'diff_qty': diff_qty,
            'change_rate': round(change_rate, 1)
        }
