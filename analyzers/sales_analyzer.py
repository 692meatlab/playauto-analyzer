# -*- coding: utf-8 -*-
"""플레이오토 판매 데이터 분석 모듈"""

import pandas as pd
import json
import os
from datetime import datetime, date, timezone, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# KST 타임존
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """현재 시간을 KST로 반환"""
    return datetime.now(KST)


class SalesAnalyzer:
    """플레이오토 SKU 판매 데이터 분석기"""

    # 사업장 분류 기준
    BUSINESS_RULES = {
        '육구이': ['692', 'meatlab'],
        '우주인': ['kms', 'sosin']
    }

    # 데이터 저장 경로
    DATA_DIR = Path.home() / 'playauto-analyzer-data'
    DATA_FILE = DATA_DIR / 'sales_data.pkl'
    META_FILE = DATA_DIR / 'metadata.json'

    def __init__(self):
        self.data: Dict[str, pd.DataFrame] = {}  # 기간별 데이터
        self.metadata: Dict[str, dict] = {}  # 파일 메타정보
        self.combined_df: Optional[pd.DataFrame] = None

        # 저장소 초기화
        self.DATA_DIR.mkdir(exist_ok=True)

        # 저장된 데이터 로드
        self._load_saved_data()

    def _load_saved_data(self):
        """저장된 데이터 로드"""
        if self.DATA_FILE.exists():
            try:
                self.combined_df = pd.read_pickle(self.DATA_FILE)
                # 기간별로 분리
                if self.combined_df is not None and not self.combined_df.empty:
                    for period in self.combined_df['기간'].unique():
                        self.data[period] = self.combined_df[self.combined_df['기간'] == period].copy()
            except Exception as e:
                print(f"데이터 로드 실패: {e}")
                self.combined_df = None

        if self.META_FILE.exists():
            try:
                with open(self.META_FILE, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception:
                self.metadata = {}

    def _save_data(self):
        """데이터 저장"""
        if self.combined_df is not None and not self.combined_df.empty:
            self.combined_df.to_pickle(self.DATA_FILE)

        with open(self.META_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2, default=str)

    def classify_business(self, id_value: str) -> str:
        """ID를 기준으로 사업장 분류"""
        if pd.isna(id_value):
            return '미분류'

        id_lower = str(id_value).lower()

        for keyword in self.BUSINESS_RULES['육구이']:
            if keyword.lower() in id_lower:
                return '육구이'

        return '우주인'

    def load_excel(
        self,
        file,
        start_date: datetime,
        end_date: datetime,
        sheet_name: str = 'SKU별 쇼핑몰 판매 리스트'
    ) -> pd.DataFrame:
        """엑셀 파일 로드 및 날짜 정보 추가"""
        df = pd.read_excel(file, sheet_name=sheet_name)

        # 날짜 정보 추가
        df['시작일'] = start_date
        df['종료일'] = end_date
        df['기간'] = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
        df['년월'] = start_date.strftime('%Y-%m')
        df['년'] = start_date.year
        df['월'] = start_date.month
        df['일'] = start_date.day

        # 사업장 분류
        df['사업장'] = df['ID'].apply(self.classify_business)

        # 데이터 저장
        period_key = df['기간'].iloc[0]

        # 중복 체크 (같은 기간 데이터가 있으면 덮어쓰기)
        if period_key in self.data:
            # 기존 데이터 제거 후 추가
            self.data[period_key] = df
        else:
            self.data[period_key] = df

        # 메타데이터 저장
        file_name = file.name if hasattr(file, 'name') else str(file)
        self.metadata[period_key] = {
            'file_name': file_name,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'row_count': len(df),
            'loaded_at': now_kst().strftime('%Y-%m-%d %H:%M:%S')
        }

        # 통합 데이터 업데이트 및 저장
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
                '로드일시': meta.get('loaded_at', '')
            })
        return sorted(periods, key=lambda x: x['기간'], reverse=True)

    def get_date_range(self) -> tuple:
        """데이터의 날짜 범위 반환"""
        if self.combined_df is None or self.combined_df.empty:
            return None, None

        min_date = self.combined_df['시작일'].min()
        max_date = self.combined_df['종료일'].max()
        return min_date, max_date

    def filter_by_date_range(self, start: date, end: date, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """날짜 범위로 필터링"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        mask = (data['시작일'].dt.date >= start) & (data['종료일'].dt.date <= end)
        return data[mask].copy()

    def filter_by_business(self, business: str, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """사업장별 필터링"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        if business == '전체':
            return data.copy()
        return data[data['사업장'] == business].copy()

    # ===== 분석 메서드 =====

    def analyze_by_business(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """사업장별 요약"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        result = data.groupby('사업장').agg({
            'SKU 총 출고수량': 'sum',
            'SKU상품명': 'nunique',
            '쇼핑몰명': 'nunique'
        }).reset_index()

        result.columns = ['사업장', '총 출고수량', '상품 종류', '채널 수']
        total = result['총 출고수량'].sum()
        result['비율(%)'] = (result['총 출고수량'] / total * 100).round(1)
        result = result.sort_values('총 출고수량', ascending=False)

        return result

    def analyze_by_shop(self, df: Optional[pd.DataFrame] = None, by_business: bool = True) -> pd.DataFrame:
        """쇼핑몰별 분석 (사업장별 구분)"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        if by_business:
            result = data.groupby(['사업장', '쇼핑몰명']).agg({
                'SKU 총 출고수량': 'sum',
                'SKU상품명': 'nunique'
            }).reset_index()
            result.columns = ['사업장', '쇼핑몰명', '출고수량', '상품 종류']
        else:
            result = data.groupby('쇼핑몰명').agg({
                'SKU 총 출고수량': 'sum',
                'SKU상품명': 'nunique'
            }).reset_index()
            result.columns = ['쇼핑몰명', '출고수량', '상품 종류']

        result = result.sort_values('출고수량', ascending=False)
        total = result['출고수량'].sum()
        result['비율(%)'] = (result['출고수량'] / total * 100).round(1)

        return result

    def analyze_by_product(self, df: Optional[pd.DataFrame] = None, top_n: int = 20, by_business: bool = True) -> pd.DataFrame:
        """상품별 분석 (사업장별 구분)"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return pd.DataFrame()

        if by_business:
            result = data.groupby(['사업장', 'SKU코드', 'SKU상품명']).agg({
                'SKU 총 출고수량': 'sum',
                '쇼핑몰명': lambda x: ', '.join(sorted(x.unique()))
            }).reset_index()
            result.columns = ['사업장', 'SKU코드', '상품명', '출고수량', '판매채널']
        else:
            result = data.groupby(['SKU코드', 'SKU상품명']).agg({
                'SKU 총 출고수량': 'sum',
                '쇼핑몰명': lambda x: ', '.join(sorted(x.unique()))
            }).reset_index()
            result.columns = ['SKU코드', '상품명', '출고수량', '판매채널']

        result = result.sort_values('출고수량', ascending=False)
        result['순위'] = range(1, len(result) + 1)

        # 컬럼 순서 조정
        if by_business:
            result = result[['순위', '사업장', 'SKU코드', '상품명', '출고수량', '판매채널']]
        else:
            result = result[['순위', 'SKU코드', '상품명', '출고수량', '판매채널']]

        return result.head(top_n)

    def get_summary_stats(self, df: Optional[pd.DataFrame] = None) -> Dict:
        """요약 통계"""
        data = df if df is not None else self.combined_df
        if data is None or data.empty:
            return {'총 출고수량': 0, '상품 종류': 0, '채널 수': 0}

        return {
            '총 출고수량': int(data['SKU 총 출고수량'].sum()),
            '상품 종류': data['SKU상품명'].nunique(),
            '채널 수': data['쇼핑몰명'].nunique(),
            '데이터 건수': len(data)
        }

    def compare_periods(self, base_start: date, base_end: date, compare_start: date, compare_end: date) -> Dict:
        """기간 비교 분석"""
        if self.combined_df is None or self.combined_df.empty:
            return {}

        base_df = self.filter_by_date_range(base_start, base_end)
        compare_df = self.filter_by_date_range(compare_start, compare_end)

        base_stats = self.get_summary_stats(base_df)
        compare_stats = self.get_summary_stats(compare_df)

        # 증감 계산
        diff = base_stats['총 출고수량'] - compare_stats['총 출고수량']
        if compare_stats['총 출고수량'] > 0:
            change_rate = (diff / compare_stats['총 출고수량'] * 100)
        else:
            change_rate = 0

        return {
            'base': {
                'period': f"{base_start} ~ {base_end}",
                'stats': base_stats,
                'by_business': self.analyze_by_business(base_df).to_dict('records'),
                'by_shop': self.analyze_by_shop(base_df).to_dict('records')
            },
            'compare': {
                'period': f"{compare_start} ~ {compare_end}",
                'stats': compare_stats,
                'by_business': self.analyze_by_business(compare_df).to_dict('records'),
                'by_shop': self.analyze_by_shop(compare_df).to_dict('records')
            },
            'diff': diff,
            'change_rate': round(change_rate, 1)
        }
