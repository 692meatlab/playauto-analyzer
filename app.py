# -*- coding: utf-8 -*-
"""
플레이오토 판매 데이터 분석기
- 매출/출고/취소 통합 분석 + AI 코멘트
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta, timezone
from io import BytesIO

from analyzers import OrderAnalyzer

# KST 타임존
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """현재 시간을 KST로 반환"""
    return datetime.now(KST)


def today_kst() -> date:
    """오늘 날짜를 KST로 반환"""
    return datetime.now(KST).date()


# ===== 페이지 설정 =====
st.set_page_config(
    page_title="플레이오토 판매 분석기",
    page_icon="📊",
    layout="wide"
)

# 스타일
st.markdown("""
<meta name="google" content="notranslate">
<style>
    [data-testid="stFileUploader"] section > div:first-child { display: none; }
    [data-testid="stFileUploader"] section > button { display: none; }
    [data-testid="stFileUploader"] small { display: none; }
    [data-testid="stFileUploader"] section {
        border: 2px dashed #ccc;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        background: #fafafa;
    }
    .business-card {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .yukgui { background: linear-gradient(135deg, #FFE5E5, #FFF5F5); border-left: 4px solid #FF6B6B; }
    .woojuin { background: linear-gradient(135deg, #E5F9F6, #F5FFFD); border-left: 4px solid #4ECDC4; }
    .menu-header { font-size: 12px; color: #888; margin-top: 20px; margin-bottom: 5px; }
    .date-basis { font-size: 11px; color: #888; padding: 3px 8px; background: #f0f0f0; border-radius: 4px; display: inline-block; margin-bottom: 5px; }
    .insight-box { background: #f8f9fa; border-left: 4px solid #3498db; padding: 12px 15px; margin: 10px 0; border-radius: 0 8px 8px 0; }
    .insight-title { font-weight: bold; color: #2c3e50; margin-bottom: 5px; }
    .insight-text { color: #555; font-size: 14px; line-height: 1.6; }
    .alert-box { background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 15px; margin: 10px 0; border-radius: 0 8px 8px 0; }
    .alert-danger { background: #f8d7da; border-left: 4px solid #dc3545; }
    .goal-progress { margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

# 사업장 색상
BUSINESS_COLORS = {'육구이': '#FF6B6B', '우주인': '#4ECDC4', '미분류': '#888888'}
WEEKDAY_NAMES = ['월', '화', '수', '목', '금', '토', '일']


def get_shop_col(df: pd.DataFrame) -> str:
    if '쇼핑몰명' in df.columns:
        return '쇼핑몰명'
    elif '쇼핑몰' in df.columns:
        return '쇼핑몰'
    return '쇼핑몰명'


@st.cache_resource(show_spinner="데이터 로딩 중...")
def _create_analyzer() -> OrderAnalyzer:
    """OrderAnalyzer 인스턴스 생성 (캐시됨)"""
    github_token = None
    github_repo = None

    try:
        if hasattr(st, 'secrets'):
            if "GITHUB_TOKEN" in st.secrets:
                github_token = st.secrets["GITHUB_TOKEN"]
            if "GITHUB_REPO" in st.secrets:
                github_repo = st.secrets["GITHUB_REPO"]
    except Exception:
        pass

    return OrderAnalyzer(
        github_token=github_token,
        github_repo=github_repo
    )


def get_analyzer() -> OrderAnalyzer:
    """캐시된 OrderAnalyzer 반환 (데이터 없으면 자동 재로드)"""
    analyzer = _create_analyzer()

    # 캐시된 analyzer에 데이터가 없지만 파일은 존재하는 경우 → 캐시 클리어 후 재로드
    if analyzer.combined_df is None or analyzer.combined_df.empty:
        if analyzer.DATA_FILE.exists():
            _create_analyzer.clear()
            analyzer = _create_analyzer()

    return analyzer


def clear_analyzer_cache():
    """데이터 변경 시 캐시 클리어"""
    _create_analyzer.clear()


def force_reload_data():
    """강제로 데이터 재로드 (사이드바 버튼용)"""
    _create_analyzer.clear()
    st.rerun()


def to_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='분석결과')
    return output.getvalue()


def render_insight(title: str, text: str, alert_type: str = "info"):
    """분석 인사이트 박스 렌더링"""
    if alert_type == "warning":
        st.markdown(f"""
        <div class="alert-box">
            <div class="insight-title">⚠️ {title}</div>
            <div class="insight-text">{text}</div>
        </div>
        """, unsafe_allow_html=True)
    elif alert_type == "danger":
        st.markdown(f"""
        <div class="alert-box alert-danger">
            <div class="insight-title">🚨 {title}</div>
            <div class="insight-text">{text}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="insight-box">
            <div class="insight-title">💡 {title}</div>
            <div class="insight-text">{text}</div>
        </div>
        """, unsafe_allow_html=True)


def generate_dashboard_insights(rev_stats, ship_stats, rev_biz, prev_stats, cancel_df):
    """대시보드 인사이트 생성"""
    insights = []

    # 매출 트렌드
    if prev_stats and prev_stats['총 매출'] > 0:
        change = ((rev_stats['총 매출'] - prev_stats['총 매출']) / prev_stats['총 매출'] * 100)
        if change > 10:
            insights.append(("매출 상승세", f"전기간 대비 매출이 {change:.1f}% 증가했습니다. 현재 성장 추세를 유지하세요.", "info"))
        elif change < -10:
            insights.append(("매출 하락 주의", f"전기간 대비 매출이 {abs(change):.1f}% 감소했습니다. 원인 분석이 필요합니다.", "warning"))

    # 사업장 비중
    if len(rev_biz) > 0:
        top_biz = rev_biz.iloc[0]
        insights.append(("주력 사업장", f"{top_biz['사업장']}이(가) 전체 매출의 {top_biz['매출비율(%)']}%를 차지합니다.", "info"))

    # 취소율
    if rev_stats['취소율'] > 5:
        insights.append(("취소율 주의", f"취소율이 {rev_stats['취소율']}%로 높습니다. 취소 원인을 파악해보세요.", "warning"))
    elif rev_stats['취소율'] <= 2:
        insights.append(("취소율 양호", f"취소율이 {rev_stats['취소율']}%로 안정적입니다.", "info"))

    # 취소 집중 채널
    if cancel_df is not None and len(cancel_df) > 0:
        top_cancel_shop = cancel_df.groupby('쇼핑몰명')['취소건수'].sum().idxmax()
        top_cancel_cnt = cancel_df.groupby('쇼핑몰명')['취소건수'].sum().max()
        if top_cancel_cnt >= 3:
            insights.append(("취소 집중 채널", f"{top_cancel_shop}에서 취소가 {top_cancel_cnt}건으로 가장 많습니다.", "warning"))

    return insights


def generate_shop_insights(merged, biz_name):
    """쇼핑몰별 분석 인사이트 생성"""
    insights = []

    if len(merged) == 0:
        return insights

    # 매출 1위 채널
    top_shop = merged.iloc[0]
    insights.append(("주력 채널", f"{top_shop['쇼핑몰명']}이(가) 매출 {top_shop['매출']:,}원으로 1위입니다. ({top_shop['매출비율(%)']}%)", "info"))

    # 채널 집중도
    if len(merged) >= 2:
        top2_ratio = merged.head(2)['매출비율(%)'].sum()
        if top2_ratio > 80:
            insights.append(("채널 집중도 높음", f"상위 2개 채널이 매출의 {top2_ratio:.1f}%를 차지합니다. 채널 다각화를 고려해보세요.", "warning"))

    # 객단가 분석
    if '객단가' in merged.columns:
        avg_aov = merged['객단가'].mean()
        high_aov = merged[merged['객단가'] > avg_aov * 1.3]
        low_aov = merged[merged['객단가'] < avg_aov * 0.7]
        if len(high_aov) > 0:
            top_aov = high_aov.iloc[0]
            insights.append(("고객단가 채널", f"{top_aov['쇼핑몰명']}의 객단가가 {top_aov['객단가']:,}원으로 높습니다. 프리미엄 상품 확대를 고려하세요.", "info"))
        if len(low_aov) > 0:
            low_shop = low_aov.iloc[0]
            insights.append(("저객단가 주의", f"{low_shop['쇼핑몰명']}의 객단가가 {low_shop['객단가']:,}원으로 낮습니다. 세트상품이나 업셀링 전략을 고려하세요.", "warning"))

    # 취소 많은 채널
    if '취소건수' in merged.columns:
        high_cancel = merged[merged['취소건수'] >= 3]
        if len(high_cancel) > 0:
            for _, row in high_cancel.iterrows():
                insights.append(("취소 주의 채널", f"{row['쇼핑몰명']}에서 취소가 {row['취소건수']}건 발생했습니다.", "warning"))

    return insights


def generate_product_insights(product_df, cancel_top):
    """상품별 분석 인사이트 생성"""
    insights = []

    if len(product_df) == 0:
        return insights

    # 베스트셀러
    top = product_df.iloc[0]
    insights.append(("베스트셀러", f"'{top['상품명'][:20]}...'이(가) 매출 {top['매출']:,}원으로 1위입니다.", "info"))

    # 상위 5개 집중도
    if len(product_df) >= 5:
        top5_revenue = product_df.head(5)['매출'].sum()
        total_revenue = product_df['매출'].sum()
        top5_ratio = (top5_revenue / total_revenue * 100) if total_revenue > 0 else 0
        if top5_ratio > 70:
            insights.append(("상품 집중도", f"상위 5개 상품이 매출의 {top5_ratio:.1f}%를 차지합니다.", "info"))

    # 객단가 분석
    if '객단가' in product_df.columns and len(product_df) >= 3:
        avg_aov = product_df['객단가'].mean()
        high_aov_products = product_df[product_df['객단가'] > avg_aov * 1.5].head(3)
        if len(high_aov_products) > 0:
            top_aov = high_aov_products.iloc[0]
            insights.append(("고단가 상품", f"'{top_aov['상품명'][:20]}...'의 객단가가 {top_aov['객단가']:,}원으로 높습니다. 프리미엄 라인으로 육성을 고려하세요.", "info"))

    # 취소 많은 상품
    if cancel_top is not None and len(cancel_top) > 0:
        worst = cancel_top.iloc[0]
        if worst['취소건수'] >= 3:
            insights.append(("취소 주의 상품", f"'{worst['상품명'][:20]}...'의 취소가 {worst['취소건수']}건으로 많습니다. 상품 상태나 배송 문제를 확인하세요.", "warning"))

    return insights


def analyze_weekday_pattern_revenue(df, by_business=False):
    """요일별 매출 패턴 분석 (결제완료일 기준)"""
    if df is None or len(df) == 0:
        return None, None

    df_copy = df.copy()
    df_copy['요일'] = pd.to_datetime(df_copy['날짜']).dt.dayofweek

    normal = df_copy[~df_copy['취소여부']]

    if by_business:
        weekday_stats = normal.groupby(['사업장', '요일']).agg({
            '금액': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        weekday_stats.columns = ['사업장', '요일', '금액', '주문건수']
    else:
        weekday_stats = normal.groupby('요일').agg({
            '금액': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        weekday_stats.columns = ['요일', '금액', '주문건수']

    weekday_stats['요일명'] = weekday_stats['요일'].apply(lambda x: WEEKDAY_NAMES[x])
    weekday_stats = weekday_stats.sort_values('요일')

    # 인사이트
    if not by_business:
        best_day = weekday_stats.loc[weekday_stats['금액'].idxmax()]
        worst_day = weekday_stats.loc[weekday_stats['금액'].idxmin()]
        insight = f"주문이 가장 많은 요일은 {best_day['요일명']}요일({best_day['금액']:,}원, {best_day['주문건수']}건)이고, 가장 적은 요일은 {worst_day['요일명']}요일({worst_day['금액']:,}원)입니다."
    else:
        insight = None

    return weekday_stats, insight


def analyze_weekday_pattern_shipment(df, by_business=False):
    """요일별 출고 패턴 분석 (출고완료일 기준)"""
    if df is None or len(df) == 0:
        return None, None

    df_copy = df.copy()
    # 출고완료일이 있는 건만 (실제 출고된 건)
    df_copy = df_copy[df_copy['출고날짜'].notna()]
    if len(df_copy) == 0:
        return None, None

    df_copy['요일'] = pd.to_datetime(df_copy['출고날짜']).dt.dayofweek

    normal = df_copy[~df_copy['취소여부']]

    if by_business:
        weekday_stats = normal.groupby(['사업장', '요일']).agg({
            '주문수량': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        weekday_stats.columns = ['사업장', '요일', '출고수량', '출고건수']
    else:
        weekday_stats = normal.groupby('요일').agg({
            '주문수량': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        weekday_stats.columns = ['요일', '출고수량', '출고건수']

    weekday_stats['요일명'] = weekday_stats['요일'].apply(lambda x: WEEKDAY_NAMES[x])
    weekday_stats = weekday_stats.sort_values('요일')

    # 인사이트
    if not by_business and len(weekday_stats) > 0:
        best_day = weekday_stats.loc[weekday_stats['출고수량'].idxmax()]
        # 주말(토:5, 일:6) 출고 여부 확인
        weekend_shipment = weekday_stats[weekday_stats['요일'].isin([5, 6])]['출고수량'].sum()

        if weekend_shipment == 0:
            insight = f"출고가 가장 많은 요일은 {best_day['요일명']}요일({best_day['출고수량']:,}개)입니다. 주말에는 출고가 없습니다."
        else:
            insight = f"출고가 가장 많은 요일은 {best_day['요일명']}요일({best_day['출고수량']:,}개)입니다."
    else:
        insight = None

    return weekday_stats, insight


def generate_time_promotion_recommendations(hourly_stats, biz_name="전체"):
    """시간대별 프로모션 추천 (축산 MD 전문가 관점)"""
    if hourly_stats is None or len(hourly_stats) == 0:
        return []

    recommendations = []

    # 시간대별 매출 비중 계산
    total_revenue = hourly_stats['금액'].sum()
    if total_revenue == 0:
        return []

    hourly_stats = hourly_stats.copy()
    hourly_stats['비중'] = (hourly_stats['금액'] / total_revenue * 100).round(1)

    # 시간대 그룹핑
    def get_hour(time_str):
        return int(time_str.split(':')[0])

    hourly_stats['시'] = hourly_stats['시간대'].apply(get_hour)

    # 시간대별 집계
    morning = hourly_stats[(hourly_stats['시'] >= 6) & (hourly_stats['시'] < 11)]['금액'].sum()
    lunch = hourly_stats[(hourly_stats['시'] >= 11) & (hourly_stats['시'] < 14)]['금액'].sum()
    afternoon = hourly_stats[(hourly_stats['시'] >= 14) & (hourly_stats['시'] < 18)]['금액'].sum()
    dinner = hourly_stats[(hourly_stats['시'] >= 18) & (hourly_stats['시'] < 21)]['금액'].sum()
    night = hourly_stats[(hourly_stats['시'] >= 21) | (hourly_stats['시'] < 6)]['금액'].sum()

    time_segments = {
        '오전(6-11시)': morning,
        '점심(11-14시)': lunch,
        '오후(14-18시)': afternoon,
        '저녁(18-21시)': dinner,
        '심야(21시-6시)': night
    }

    # 피크 시간대 찾기
    peak_segment = max(time_segments, key=time_segments.get)
    peak_revenue = time_segments[peak_segment]
    peak_ratio = (peak_revenue / total_revenue * 100) if total_revenue > 0 else 0

    # 피크 시간대별 추천
    if '점심' in peak_segment:
        recommendations.append({
            'type': 'peak',
            'title': '점심시간 집중 공략',
            'time': '11:00 ~ 14:00',
            'strategy': '간편식/밀키트 프로모션',
            'detail': '직장인 점심시간 주문이 많습니다. 빠른 조리가 가능한 양념육, 1인분 스테이크, 밀키트 상품을 메인으로 노출하세요.',
            'ad_type': '카카오 비즈보드, 네이버 타임보드 (11시~13시 집중)'
        })
    elif '저녁' in peak_segment:
        recommendations.append({
            'type': 'peak',
            'title': '저녁시간 집중 공략',
            'time': '18:00 ~ 21:00',
            'strategy': '가족 식사용 대용량 프로모션',
            'detail': '퇴근 후 저녁 준비를 위한 주문이 많습니다. 가족용 대용량, 구이류, 찌개용 고기를 메인으로 노출하세요.',
            'ad_type': '인스타그램/페이스북 피드 광고 (18시~20시), 유튜브 범퍼 광고'
        })
    elif '오후' in peak_segment:
        recommendations.append({
            'type': 'peak',
            'title': '오후시간 집중 공략',
            'time': '14:00 ~ 18:00',
            'strategy': '내일 배송 예약 프로모션',
            'detail': '여유있게 쇼핑하는 고객이 많습니다. 프리미엄 상품, 선물세트, 대용량 할인을 노출하세요.',
            'ad_type': '네이버 쇼핑 검색광고, 쿠팡 CPC 광고'
        })
    elif '오전' in peak_segment:
        recommendations.append({
            'type': 'peak',
            'title': '오전시간 집중 공략',
            'time': '06:00 ~ 11:00',
            'strategy': '당일배송/새벽배송 강조',
            'detail': '출근 전이나 오전에 미리 주문하는 계획적인 고객입니다. 당일배송, 정기구독 상품을 강조하세요.',
            'ad_type': '카카오톡 채널 메시지 (오전 8시 발송), 앱푸시'
        })
    elif '심야' in peak_segment:
        recommendations.append({
            'type': 'peak',
            'title': '심야시간 집중 공략',
            'time': '21:00 ~ 06:00',
            'strategy': '충동구매 유도 프로모션',
            'detail': '야식, 술안주 수요가 있습니다. 소포장 안주류, 즉석 조리 상품, 한정 타임딜을 운영하세요.',
            'ad_type': '인스타그램 스토리 광고, 유튜브 인스트림 (심야 시간대)'
        })

    # 비피크 시간대 활성화 추천
    min_segment = min(time_segments, key=time_segments.get)
    min_revenue = time_segments[min_segment]

    if min_revenue < peak_revenue * 0.3:  # 피크 대비 30% 미만이면 추천
        recommendations.append({
            'type': 'opportunity',
            'title': f'{min_segment} 매출 활성화 기회',
            'time': min_segment,
            'strategy': '타임특가/한정할인 운영',
            'detail': f'{min_segment}의 매출이 저조합니다. 이 시간대 한정 특가를 운영하여 트래픽을 분산시키고 매출을 늘려보세요.',
            'ad_type': '앱푸시 알림, 카카오톡 알림톡 (해당 시간 30분 전 발송)'
        })

    # 피크 시간 30분 전 광고 추천
    top_time = hourly_stats.loc[hourly_stats['금액'].idxmax()]['시간대']
    recommendations.append({
        'type': 'timing',
        'title': '광고 타이밍 최적화',
        'time': f'{top_time} 피크 30분 전',
        'strategy': '피크 시간 선점 광고',
        'detail': f'주문이 가장 많은 {top_time} 시간대 30분 전에 광고를 집중 노출하여 구매 전환을 높이세요.',
        'ad_type': '리타겟팅 광고, 장바구니 리마인드 푸시'
    })

    return recommendations


def generate_seasonal_recommendations(df, biz_name="전체"):
    """월별/계절별 프로모션 추천 (축산 MD 전문가 관점)"""
    if df is None or len(df) == 0:
        return [], None

    df_copy = df.copy()
    df_copy['월'] = pd.to_datetime(df_copy['날짜']).dt.month
    df_copy['년월'] = pd.to_datetime(df_copy['날짜']).dt.strftime('%Y-%m')

    normal = df_copy[~df_copy['취소여부']]

    # 월별 집계
    monthly = normal.groupby('월').agg({
        '금액': 'sum',
        '묶음번호': 'nunique'
    }).reset_index()
    monthly.columns = ['월', '매출', '주문건수']

    if len(monthly) < 2:
        return [], None

    # 계절 분류
    def get_season(month):
        if month in [3, 4, 5]:
            return '봄'
        elif month in [6, 7, 8]:
            return '여름'
        elif month in [9, 10, 11]:
            return '가을'
        else:
            return '겨울'

    monthly['계절'] = monthly['월'].apply(get_season)

    # 계절별 집계
    seasonal = monthly.groupby('계절').agg({
        '매출': 'sum',
        '주문건수': 'sum'
    }).reset_index()

    recommendations = []

    # 사업장별 계절 전략
    if biz_name == '육구이':
        # 육구이: 신선함 강조, 한돈/내장 취급, 평달 단품 매출 중요
        season_strategies = {
            '봄': {
                'products': '캠핑용 삼겹살/목살, 한돈 양념구이, 신선 내장(등골, 막창)',
                'events': '벚꽃시즌, 어린이날, 어버이날, 삼삼데이',
                'strategy': '🥩 캠핑/나들이 시즌 - 한돈 양념육 + 신선내장 세트 구성'
            },
            '여름': {
                'products': '삼겹살, 목살, 항정살, 신선 등골/막창, 캠핑 BBQ세트',
                'events': '휴가철, 복날, 캠핑시즌',
                'strategy': '🥩 복날 특수 + 캠핑 시즌, 신선내장 타임특가로 차별화'
            },
            '가을': {
                'products': '한우 선물세트 + 한돈 실속세트, 내장 마니아 세트',
                'events': '추석, 김장철, 한우데이',
                'strategy': '🥩 추석 선물세트 + 평달 인기 단품 묶음 구성으로 객단가 UP'
            },
            '겨울': {
                'products': '곰탕/설렁탕용, 국거리, 설 선물세트, 신선 내장',
                'events': '설날, 연말연시, 크리스마스',
                'strategy': '🥩 설 선물세트 + 국물요리용 단품 크로스셀링'
            }
        }
    elif biz_name == '우주인':
        # 우주인: 프리미엄 선물세트 전문, 명절 집중, 고급 이미지
        season_strategies = {
            '봄': {
                'products': '프리미엄 한우 스테이크, 어버이날 감사 선물세트',
                'events': '어버이날, 스승의날',
                'strategy': '🚀 VIP 고객 유지 + 기업 대량구매 영업, 프리미엄 이미지 유지'
            },
            '여름': {
                'products': '프리미엄 한우 구이세트 (소량), VIP 단품',
                'events': '휴가철, 복날',
                'strategy': '🚀 비수기 - 프리미엄 소량 상품으로 VIP 고객 유지, 추석 사전예약 준비'
            },
            '가을': {
                'products': '프리미엄 한우 선물세트 (추석 대목!), 1++ 등심/채끝 세트',
                'events': '추석 (연매출 최대 대목)',
                'strategy': '🚀 ★추석 올인★ 사전예약 필수, 고급 포장 강조, 기업 대량구매 공략'
            },
            '겨울': {
                'products': '설 프리미엄 선물세트, VIP 한우 세트',
                'events': '설날, 연말연시 (연매출 최대 대목)',
                'strategy': '🚀 ★설날 올인★ 추석과 함께 연매출 핵심! 고급 이미지 극대화'
            }
        }
    else:
        # 전체 (일반 전략)
        season_strategies = {
            '봄': {
                'products': '나들이용 도시락 세트, 캠핑용 양념육, 피크닉 밀키트',
                'events': '벚꽃시즌, 어린이날, 어버이날',
                'strategy': '야외활동 증가에 맞춘 휴대 간편 상품 강화'
            },
            '여름': {
                'products': '삼겹살, 목살, 캠핑용 숯불구이 세트, 냉동 보관 대용량',
                'events': '휴가철, 복날, 캠핑시즌',
                'strategy': 'BBQ/캠핑 시즌 마케팅, 복날 특수 (삼계탕용, 보양식)'
            },
            '가을': {
                'products': '프리미엄 한우, 선물세트, 구이용 고급 부위',
                'events': '추석, 김장철',
                'strategy': '명절 선물세트 사전예약, 프리미엄 라인업 강화'
            },
            '겨울': {
                'products': '국거리, 찌개용, 샤브샤브, 설 선물세트',
                'events': '설날, 연말연시, 크리스마스',
                'strategy': '따뜻한 국물요리 수요 공략, 설 선물세트 마케팅'
            }
        }

    # 현재 월 확인
    current_month = now_kst().month
    current_season = get_season(current_month)
    next_month = (current_month % 12) + 1
    next_season = get_season(next_month)

    # 현재 시즌 추천
    if current_season in season_strategies:
        s = season_strategies[current_season]
        recommendations.append({
            'type': 'current_season',
            'title': f'현재 시즌 ({current_season}) 전략',
            'products': s['products'],
            'events': s['events'],
            'strategy': s['strategy']
        })

    # 다음 시즌 준비 추천
    if next_season != current_season and next_season in season_strategies:
        s = season_strategies[next_season]
        recommendations.append({
            'type': 'next_season',
            'title': f'다음 시즌 ({next_season}) 준비',
            'products': s['products'],
            'events': s['events'],
            'strategy': f'지금부터 {next_season} 시즌 상품 기획 및 재고 확보 필요'
        })

    # 데이터 기반 추천 (월별 데이터가 충분할 때)
    if len(monthly) >= 3:
        best_month = monthly.loc[monthly['매출'].idxmax()]
        worst_month = monthly.loc[monthly['매출'].idxmin()]

        recommendations.append({
            'type': 'data_insight',
            'title': '데이터 기반 인사이트',
            'detail': f"매출이 가장 높은 달은 {int(best_month['월'])}월({best_month['매출']:,}원)이고, 가장 낮은 달은 {int(worst_month['월'])}월({worst_month['매출']:,}원)입니다.",
            'strategy': f"{int(worst_month['월'])}월 매출 보완을 위한 특별 프로모션을 기획하세요."
        })

    return recommendations, monthly


def generate_channel_strategies(df, biz_name="전체"):
    """채널별(쇼핑몰별) 프로모션 전략 (축산 MD 전문가 관점)"""

    # 채널별 마케팅 전략 (전문가 지식)
    channel_strategies = {
        '스마트스토어': {
            'name': '네이버 스마트스토어',
            'icon': '🟢',
            'strength': '검색 유입, 네이버페이, 리뷰 마케팅',
            'target': '검색 기반 신규 고객, 가격 비교 고객',
            'promotion': [
                '네이버 쇼핑 검색광고 (SA) 집중',
                '브랜드검색 광고로 브랜드명 선점',
                '리뷰 이벤트로 상품평 확보 (텍스트+포토)',
                '네이버 라이브커머스 활용',
                '톡톡 친구 추가 할인 프로모션'
            ],
            'tip': '상품명에 키워드 최적화 필수 (예: 한우 등심 1++ 구이용 300g)'
        },
        '쿠팡': {
            'name': '쿠팡',
            'icon': '🟠',
            'strength': '로켓배송, 충성 고객, 대량 구매',
            'target': '로켓와우 회원, 편의성 중시 고객',
            'promotion': [
                '로켓그로스 입점으로 로켓배송 뱃지 획득',
                '골드박스/빅딜 프로모션 참여',
                '쿠팡 라이브 방송 활용',
                '묶음배송 할인으로 객단가 상승',
                '리뷰 작성 유도 (쿠팡 상위노출 핵심)'
            ],
            'tip': '로켓배송 필수! 일반배송은 노출 불리'
        },
        'G마켓': {
            'name': 'G마켓/옥션',
            'icon': '🔴',
            'strength': '스마일클럽, 빅스마일데이, 슈퍼딜',
            'target': '할인/적립금 민감 고객, 40-50대',
            'promotion': [
                '빅스마일데이 행사 필수 참여',
                '슈퍼딜/타임딜 등록',
                '스마일클럽 전용 할인가 설정',
                'G마켓/옥션 동시 노출로 효율 극대화',
                '스마일페이 결제 추가 할인'
            ],
            'tip': '빅스마일데이 기간에 매출 집중 - 사전 재고 확보 필수'
        },
        '11번가': {
            'name': '11번가',
            'icon': '🟣',
            'strength': 'SK페이, 아마존 글로벌, 라이브11',
            'target': 'SKT 고객, 젊은 층',
            'promotion': [
                '십일절(11절) 행사 참여',
                'SK페이 추가 할인 프로모션',
                '라이브11 방송으로 실시간 판매',
                '타임딜/오늘의 발견 노출',
                '아마존 글로벌 셀링 연계'
            ],
            'tip': 'SKT 멤버십 연계 프로모션 효과적'
        },
        '카카오': {
            'name': '카카오쇼핑/톡스토어',
            'icon': '🟡',
            'strength': '카카오톡 기반, 선물하기, 바이럴',
            'target': '선물 수요, MZ세대, 카카오 헤비유저',
            'promotion': [
                '카카오 선물하기 입점 (명절 필수)',
                '톡딜 참여로 바이럴 유도',
                '카카오톡 채널 친구 모집',
                '비즈보드 광고 (카카오톡 노출)',
                '이모티콘 증정 이벤트'
            ],
            'tip': '선물하기는 명절/기념일 매출 핵심 채널'
        },
        '위메프': {
            'name': '위메프',
            'icon': '🔵',
            'strength': '특가 이미지, 원더배송',
            'target': '특가/최저가 추구 고객',
            'promotion': [
                '투데이특가/슈퍼특가 등록',
                '원더배송 활용',
                '타임특가로 트래픽 유도',
                '위메프데이 참여'
            ],
            'tip': '최저가 경쟁력 확보 시 효과적'
        },
        '티몬': {
            'name': '티몬',
            'icon': '🔵',
            'strength': '타임커머스, 티몬데이',
            'target': '특가/타임딜 선호 고객',
            'promotion': [
                '티몬데이 프로모션 참여',
                '슈퍼마트 입점',
                '타임특가 등록'
            ],
            'tip': '티몬데이 기간 집중 프로모션'
        },
        '인터파크': {
            'name': '인터파크',
            'icon': '🟤',
            'strength': '종합몰, 올인원 쇼핑',
            'target': '종합 쇼핑 고객',
            'promotion': [
                '카테고리 기획전 참여',
                '인터파크 멤버십 연계 할인'
            ],
            'tip': '식품 카테고리 기획전 노출 중요'
        }
    }

    if df is None or len(df) == 0:
        return [], channel_strategies

    # 데이터에서 쇼핑몰별 매출 분석
    shop_col = get_shop_col(df)
    normal = df[~df['취소여부']]

    if biz_name != "전체":
        normal = normal[normal['사업장'] == biz_name]

    if len(normal) == 0:
        return [], channel_strategies

    shop_stats = normal.groupby(shop_col).agg({
        '금액': 'sum',
        '묶음번호': 'nunique',
        '주문수량': 'sum'
    }).reset_index()
    shop_stats.columns = ['쇼핑몰', '매출', '주문건수', '판매수량']
    shop_stats['객단가'] = (shop_stats['매출'] / shop_stats['주문건수']).fillna(0).astype(int)
    shop_stats = shop_stats.sort_values('매출', ascending=False)

    total_revenue = shop_stats['매출'].sum()
    shop_stats['매출비중'] = (shop_stats['매출'] / total_revenue * 100).round(1)

    recommendations = []

    # 상위 채널 분석
    for idx, row in shop_stats.head(5).iterrows():
        shop_name = row['쇼핑몰']

        # 채널 매칭
        matched_strategy = None
        for key, strategy in channel_strategies.items():
            if key.lower() in shop_name.lower() or shop_name.lower() in key.lower():
                matched_strategy = strategy
                break

        # 스마트스토어 변형 체크
        if matched_strategy is None and ('스토어' in shop_name or 'naver' in shop_name.lower()):
            matched_strategy = channel_strategies.get('스마트스토어')

        # 쿠팡 변형 체크
        if matched_strategy is None and ('coupang' in shop_name.lower() or '쿠팡' in shop_name):
            matched_strategy = channel_strategies.get('쿠팡')

        recommendations.append({
            'shop': shop_name,
            'revenue': row['매출'],
            'ratio': row['매출비중'],
            'orders': row['주문건수'],
            'aov': row['객단가'],
            'strategy': matched_strategy
        })

    return recommendations, channel_strategies


def analyze_hourly_pattern(df, by_business=False):
    """시간대별 매출 패턴 분석 (30분 단위, 결제완료일 기준)"""
    if df is None or len(df) == 0:
        return None, None

    df_copy = df.copy()
    # 결제일시에서 시간 추출
    df_copy['결제일시'] = pd.to_datetime(df_copy['결제일시'], errors='coerce')
    df_copy = df_copy[df_copy['결제일시'].notna()]

    if len(df_copy) == 0:
        return None, None

    # 30분 단위 시간대 생성
    df_copy['시'] = df_copy['결제일시'].dt.hour
    df_copy['분'] = df_copy['결제일시'].dt.minute
    df_copy['시간대'] = df_copy['시'].astype(str).str.zfill(2) + ':' + ((df_copy['분'] // 30) * 30).astype(str).str.zfill(2)

    normal = df_copy[~df_copy['취소여부']]

    if by_business:
        hourly_stats = normal.groupby(['사업장', '시간대']).agg({
            '금액': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        hourly_stats.columns = ['사업장', '시간대', '금액', '주문건수']
    else:
        hourly_stats = normal.groupby('시간대').agg({
            '금액': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        hourly_stats.columns = ['시간대', '금액', '주문건수']

    hourly_stats = hourly_stats.sort_values('시간대')

    # 인사이트
    if not by_business and len(hourly_stats) > 0:
        # 피크 시간대 분석 (상위 5개) - 직렬 나열용 데이터
        top5 = hourly_stats.nlargest(5, '금액')[['시간대', '금액', '주문건수']].reset_index(drop=True)
        top5['순위'] = range(1, len(top5) + 1)
        insight = top5  # DataFrame 반환
    else:
        insight = None

    return hourly_stats, insight


def main():
    # 첫 실행 시 캐시 강제 클리어 (데이터 로드 보장)
    if 'cache_cleared' not in st.session_state:
        _create_analyzer.clear()
        st.session_state.cache_cleared = True

    analyzer = get_analyzer()

    with st.sidebar:
        st.title("📊 플레이오토 분석기")
        st.markdown("---")

        if 'current_page' not in st.session_state:
            st.session_state.current_page = '대시보드'

        # 목표 설정
        if 'monthly_goal' not in st.session_state:
            st.session_state.monthly_goal = 0

        # 분석 메뉴
        st.markdown('<p class="menu-header">📈 분석</p>', unsafe_allow_html=True)

        menus = ['대시보드', '쇼핑몰별', '상품별', '기간비교']
        icons = {'대시보드': '📊', '쇼핑몰별': '🏪', '상품별': '📦', '기간비교': '📈'}

        for menu in menus:
            is_selected = st.session_state.current_page == menu
            btn_type = "primary" if is_selected else "secondary"
            if st.button(f"{icons[menu]} {menu}", key=f"menu_{menu}", use_container_width=True, type=btn_type):
                st.session_state.current_page = menu
                st.rerun()

        # 프로모션 메뉴
        st.markdown("---")
        st.markdown('<p class="menu-header">🎁 프로모션</p>', unsafe_allow_html=True)

        promo_menus = ['프로모션 플래너', '준비 체크리스트', '경쟁사 분석']
        promo_icons = {'프로모션 플래너': '📋', '준비 체크리스트': '✅', '경쟁사 분석': '🔍'}

        for menu in promo_menus:
            is_selected = st.session_state.current_page == menu
            btn_type = "primary" if is_selected else "secondary"
            if st.button(f"{promo_icons[menu]} {menu}", key=f"menu_{menu}", use_container_width=True, type=btn_type):
                st.session_state.current_page = menu
                st.rerun()

        # 관리 메뉴
        st.markdown("---")
        st.markdown('<p class="menu-header">⚙️ 관리</p>', unsafe_allow_html=True)

        manage_menus = ['데이터 업로드', '저장된 데이터']
        manage_icons = {'데이터 업로드': '📤', '저장된 데이터': '📋'}

        for menu in manage_menus:
            is_selected = st.session_state.current_page == menu
            btn_type = "primary" if is_selected else "secondary"
            if st.button(f"{manage_icons[menu]} {menu}", key=f"menu_{menu}", use_container_width=True, type=btn_type):
                st.session_state.current_page = menu
                st.rerun()

        # 데이터 새로고침 버튼
        if st.button("🔄 데이터 새로고침", key="reload_data", use_container_width=True):
            force_reload_data()

        # 목표 설정
        st.markdown("---")
        st.markdown('<p class="menu-header">🎯 월 목표</p>', unsafe_allow_html=True)
        goal = st.number_input("월 매출 목표 (원)", min_value=0, step=1000000,
                               value=st.session_state.monthly_goal, key="goal_input", label_visibility="collapsed")
        st.session_state.monthly_goal = goal

        # 요약 + 목표 달성률
        st.markdown("---")
        periods = analyzer.get_loaded_periods()
        if periods and analyzer.combined_df is not None:
            stats = analyzer.get_summary_stats()
            st.caption(f"💰 매출: {stats['총 매출']:,}원")

            # 목표 달성률
            if st.session_state.monthly_goal > 0:
                achievement = (stats['총 매출'] / st.session_state.monthly_goal * 100)
                color = "#2ecc71" if achievement >= 100 else ("#f39c12" if achievement >= 70 else "#e74c3c")
                st.markdown(f"""
                <div class="goal-progress">
                    <div style="font-size:12px; color:#888;">목표 달성률</div>
                    <div style="font-size:18px; font-weight:bold; color:{color};">{achievement:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(min(achievement / 100, 1.0))

            st.caption(f"📦 출고: {stats['판매수량']:,}개")
            st.caption(f"🔄 취소: {stats['취소건수']}건 ({stats['취소율']}%)")

    # 메인 영역
    current_page = st.session_state.current_page
    has_data = analyzer.combined_df is not None and len(analyzer.combined_df) > 0

    if current_page == '데이터 업로드':
        render_upload_page(analyzer)
    elif current_page == '저장된 데이터':
        render_data_list_page(analyzer)
    elif current_page == '프로모션 플래너':
        render_promotion_planner(analyzer)
    elif current_page == '준비 체크리스트':
        render_preparation_checklist(analyzer)
    elif current_page == '경쟁사 분석':
        render_competitor_analysis(analyzer)
    elif not has_data:
        render_empty_state()
    elif current_page == '대시보드':
        render_dashboard(analyzer)
    elif current_page == '쇼핑몰별':
        render_shop_analysis(analyzer)
    elif current_page == '상품별':
        render_product_analysis(analyzer)
    elif current_page == '기간비교':
        render_period_comparison(analyzer)
    else:
        render_dashboard(analyzer)


def render_date_filter(analyzer: OrderAnalyzer, key_prefix: str = "", default_mode: str = "당월"):
    """기간 필터"""
    min_date, max_date = analyzer.get_date_range()

    if min_date is None:
        st.warning("날짜 데이터가 없습니다.")
        return None, None

    min_dt = min_date.date() if hasattr(min_date, 'date') else min_date
    max_dt = max_date.date() if hasattr(max_date, 'date') else max_date

    # 위젯 키와 세션 상태 키 통일
    start_key = f"{key_prefix}_date_start"
    end_key = f"{key_prefix}_date_end"

    # 초기값 설정
    if start_key not in st.session_state:
        if default_mode == "당월":
            month_start = max_dt.replace(day=1)
            st.session_state[start_key] = max(min_dt, month_start)
        else:
            st.session_state[start_key] = min_dt
    if end_key not in st.session_state:
        st.session_state[end_key] = max_dt

    # 버튼 클릭 처리 (date_input 렌더링 전에 처리)
    col1, col2, col3 = st.columns([1, 1, 2])

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        qcols = st.columns(5)
        with qcols[0]:
            if st.button("전일", key=f"{key_prefix}_q1", use_container_width=True):
                st.session_state[start_key] = max_dt
                st.session_state[end_key] = max_dt
                st.rerun()
        with qcols[1]:
            if st.button("7일", key=f"{key_prefix}_q2", use_container_width=True):
                st.session_state[start_key] = max(min_dt, max_dt - timedelta(days=6))
                st.session_state[end_key] = max_dt
                st.rerun()
        with qcols[2]:
            if st.button("당월", key=f"{key_prefix}_q5", use_container_width=True):
                month_start = max_dt.replace(day=1)
                st.session_state[start_key] = max(min_dt, month_start)
                st.session_state[end_key] = max_dt
                st.rerun()
        with qcols[3]:
            if st.button("30일", key=f"{key_prefix}_q3", use_container_width=True):
                st.session_state[start_key] = max(min_dt, max_dt - timedelta(days=29))
                st.session_state[end_key] = max_dt
                st.rerun()
        with qcols[4]:
            if st.button("전체", key=f"{key_prefix}_q4", use_container_width=True):
                st.session_state[start_key] = min_dt
                st.session_state[end_key] = max_dt
                st.rerun()

    with col1:
        start = st.date_input("시작일", min_value=min_dt, max_value=max_dt, key=start_key)

    with col2:
        end = st.date_input("종료일", min_value=min_dt, max_value=max_dt, key=end_key)

    return start, end


def render_empty_state():
    st.title("📊 플레이오토 판매 분석기")
    st.info("👈 사이드바의 **데이터 업로드**에서 주문 데이터 파일을 업로드하세요.")

    st.markdown("---")
    st.markdown("### 📌 사용 방법")
    st.markdown("""
    1. **데이터 업로드** 메뉴에서 플레이오토 주문 데이터 파일 업로드
    2. 업로드 완료 후 분석 메뉴에서 매출/출고 현황 확인
    3. 사이드바에서 **월 매출 목표**를 설정하면 달성률을 확인할 수 있습니다
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="business-card yukgui">
            <b>🥩 육구이</b><br>
            <small>계정: 692meatlab, 692</small>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="business-card woojuin">
            <b>🚀 우주인</b><br>
            <small>계정: sosin, kms</small>
        </div>
        """, unsafe_allow_html=True)


def render_upload_page(analyzer: OrderAnalyzer):
    st.title("📤 데이터 업로드")
    st.markdown("플레이오토에서 다운로드한 **주문 데이터** 파일을 업로드하세요.")

    with st.expander("📍 플레이오토 다운로드 경로", expanded=False):
        st.markdown("""
        **주문 데이터 파일 위치:**

        `메뉴` → `주문` → `전체주문조회` → `통합엑셀다운` → **엑셀다운** 버튼 클릭
        """)

    st.markdown("""
    <div style="background:#f0f2f6; padding:15px; border-radius:8px; text-align:center; margin:15px 0;">
        <p style="margin:0; color:#555;">📂 아래 영역을 클릭하여 파일을 선택하세요</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader("파일 선택", type=['xlsx', 'xls'], label_visibility="collapsed", key="file_uploader")

    if uploaded_file:
        st.success(f"📄 선택된 파일: **{uploaded_file.name}**")

        with st.expander("📋 데이터 미리보기", expanded=False):
            preview_df = pd.read_excel(uploaded_file)
            st.dataframe(preview_df.head(5), use_container_width=True)
            st.caption(f"전체 {len(preview_df)}건 중 5건 미리보기")
            uploaded_file.seek(0)

        if st.button("📥 데이터 추가", type="primary", use_container_width=True):
            with st.spinner("데이터를 처리하는 중..."):
                try:
                    df = analyzer.load_excel(uploaded_file)
                    stats = analyzer.get_summary_stats(df)
                    period = df['기간'].iloc[0] if '기간' in df.columns else ''
                    st.success(f"✅ **{len(df)}건** 데이터 추가! (기간: {period})")
                    st.info(f"💰 매출: {stats['총 매출']:,}원 | 📦 출고: {stats['판매수량']:,}개 | 🔄 취소: {stats['취소건수']}건")
                    st.balloons()
                    st.session_state.analyzer = analyzer
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")


def render_data_list_page(analyzer: OrderAnalyzer):
    st.title("📋 저장된 데이터")

    periods = analyzer.get_loaded_periods()
    if not periods:
        st.warning("저장된 데이터가 없습니다.")
        return

    total_revenue = sum(p['매출'] for p in periods)
    st.info(f"📊 총 **{len(periods)}개 기간** | 💰 **{total_revenue:,}원** 매출")

    for i, p in enumerate(periods):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(f"**📅 {p['기간']}**")
            fname = p['파일명']
            st.caption(f"파일: {fname[:40]}..." if len(fname) > 40 else f"파일: {fname}")
        with col2:
            st.markdown(f"**{p['매출']:,}원**")
            st.caption(f"주문: {p['주문수']:,}건 | 취소: {p['취소']}건")
        with col3:
            if st.button("🗑️ 삭제", key=f"del_{i}", use_container_width=True):
                analyzer.delete_period(p['기간'])
                clear_analyzer_cache()
                st.rerun()
        st.markdown("---")

    if st.button("🗑️ 전체 삭제", type="secondary"):
        analyzer.clear_all_data()
        clear_analyzer_cache()
        st.rerun()


def render_dashboard(analyzer: OrderAnalyzer):
    """통합 대시보드"""
    st.title("📊 대시보드")

    st.markdown("### 📅 조회 기간")
    start, end = render_date_filter(analyzer, "dash", default_mode="당월")

    if start is None:
        return

    revenue_df = analyzer.filter_by_date_range(start, end)
    shipment_df = analyzer.filter_by_shipment_date_range(start, end)

    if (revenue_df is None or len(revenue_df) == 0) and (shipment_df is None or len(shipment_df) == 0):
        st.warning("선택한 기간에 데이터가 없습니다.")
        return

    st.caption(f"📊 조회: {start} ~ {end}")

    # 사업장 선택 (상단에 하나만)
    st.markdown("### 🏢 사업장 선택")
    biz_col1, biz_col2, biz_col3 = st.columns(3)
    if 'selected_business' not in st.session_state:
        st.session_state.selected_business = '전체'

    with biz_col1:
        if st.button("📊 전체", key="biz_all", use_container_width=True,
                     type="primary" if st.session_state.selected_business == '전체' else "secondary"):
            st.session_state.selected_business = '전체'
            st.rerun()
    with biz_col2:
        if st.button("🥩 육구이", key="biz_yukgui", use_container_width=True,
                     type="primary" if st.session_state.selected_business == '육구이' else "secondary"):
            st.session_state.selected_business = '육구이'
            st.rerun()
    with biz_col3:
        if st.button("🚀 우주인", key="biz_woojuin", use_container_width=True,
                     type="primary" if st.session_state.selected_business == '우주인' else "secondary"):
            st.session_state.selected_business = '우주인'
            st.rerun()

    selected_biz = st.session_state.selected_business
    biz_color = BUSINESS_COLORS.get(selected_biz, '#9b59b6')

    # 선택된 사업장으로 데이터 필터링
    if selected_biz != '전체':
        revenue_df = analyzer.filter_by_business(selected_biz, revenue_df)
        shipment_df = analyzer.filter_by_business(selected_biz, shipment_df)

    st.markdown("---")

    rev_stats = analyzer.get_summary_stats(revenue_df) if revenue_df is not None else {'총 매출': 0, '판매건수': 0, '판매수량': 0, '취소건수': 0, '취소율': 0}
    ship_stats = analyzer.get_summary_stats(shipment_df) if shipment_df is not None else {'판매수량': 0}

    # 전기간 대비
    days_diff = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days_diff - 1)
    prev_rev_df = analyzer.filter_by_date_range(prev_start, prev_end)
    prev_stats = analyzer.get_summary_stats(prev_rev_df) if prev_rev_df is not None and len(prev_rev_df) > 0 else None

    # 전체 현황
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        delta = None
        if prev_stats and prev_stats['총 매출'] > 0:
            delta = f"{((rev_stats['총 매출'] - prev_stats['총 매출']) / prev_stats['총 매출'] * 100):+.1f}%"
        st.metric("💰 매출", f"{rev_stats['총 매출']:,}원", delta=delta)
    with col2:
        delta = None
        if prev_stats and prev_stats['판매건수'] > 0:
            delta = f"{((rev_stats['판매건수'] - prev_stats['판매건수']) / prev_stats['판매건수'] * 100):+.1f}%"
        st.metric("🛒 주문건수", f"{rev_stats['판매건수']:,}건", delta=delta)
    with col3:
        st.metric("📦 출고수량", f"{ship_stats['판매수량']:,}개")
    with col4:
        st.metric("🔄 취소", f"{rev_stats['취소건수']}건")
    with col5:
        st.metric("📉 취소율", f"{rev_stats['취소율']}%")

    if prev_stats:
        st.caption(f"💡 전기간 대비 ({prev_start} ~ {prev_end})")

    # 분석 인사이트
    rev_biz = analyzer.analyze_by_business(revenue_df) if revenue_df is not None and len(revenue_df) > 0 else pd.DataFrame()
    cancel_df = analyzer.analyze_cancellations(revenue_df) if revenue_df is not None else None

    insights = generate_dashboard_insights(rev_stats, ship_stats, rev_biz, prev_stats, cancel_df)
    if insights:
        st.markdown("### 💡 분석 코멘트")
        for title, text, alert_type in insights:
            render_insight(title, text, alert_type)

    st.markdown("---")

    # 사업장별 현황
    st.markdown("### 🏢 사업장별 현황")

    ship_biz = analyzer.analyze_by_business(shipment_df) if shipment_df is not None and len(shipment_df) > 0 else pd.DataFrame()

    if len(rev_biz) > 0:
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            for _, row in rev_biz.iterrows():
                biz = row['사업장']
                color_class = 'yukgui' if biz == '육구이' else ('woojuin' if biz == '우주인' else '')
                emoji = '🥩' if biz == '육구이' else ('🚀' if biz == '우주인' else '❓')

                ship_qty = 0
                if len(ship_biz) > 0:
                    ship_row = ship_biz[ship_biz['사업장'] == biz]
                    if len(ship_row) > 0:
                        ship_qty = ship_row.iloc[0]['판매수량']

                st.markdown(f"""
                <div class="business-card {color_class}">
                    <b>{emoji} {biz}</b><br>
                    💰 매출: <b>{row['매출']:,}원</b> ({row['매출비율(%)']}%)<br>
                    📦 출고: <b>{ship_qty:,}개</b> | 🔄 취소: {row['취소건수']}건
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown('<span class="date-basis">💰 매출 기준: 결제완료일</span>', unsafe_allow_html=True)
            fig = px.pie(rev_biz, values='매출', names='사업장', color='사업장',
                         color_discrete_map=BUSINESS_COLORS, hole=0.4)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(showlegend=False, height=220, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            if len(ship_biz) > 0:
                st.markdown('<span class="date-basis">📦 출고 기준: 출고완료일</span>', unsafe_allow_html=True)
                fig = px.pie(ship_biz, values='판매수량', names='사업장', color='사업장',
                             color_discrete_map=BUSINESS_COLORS, hole=0.4)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(showlegend=False, height=220, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 일별 추이
    st.markdown("### 📈 일별 추이")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<span class="date-basis">💰 매출 기준: 결제완료일</span>', unsafe_allow_html=True)
        daily_rev = analyzer.analyze_daily(revenue_df) if revenue_df is not None else pd.DataFrame()
        if len(daily_rev) > 0:
            fig = px.line(daily_rev, x='날짜', y='매출', markers=True)
            fig.update_layout(height=280, margin=dict(t=10))
            fig.update_traces(line_color='#FF6B6B')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<span class="date-basis">📦 출고 기준: 출고완료일</span>', unsafe_allow_html=True)
        daily_ship = analyzer.analyze_daily_shipment(shipment_df) if shipment_df is not None else pd.DataFrame()
        if len(daily_ship) > 0:
            fig = px.line(daily_ship, x='날짜', y='출고수량', markers=True)
            fig.update_layout(height=280, margin=dict(t=10))
            fig.update_traces(line_color='#4ECDC4')
            st.plotly_chart(fig, use_container_width=True)

    # 요일별 패턴
    st.markdown("---")
    st.markdown(f"### 📅 요일별 패턴 {'(' + selected_biz + ')' if selected_biz != '전체' else ''}")
    st.markdown('<span class="date-basis">💰 매출/주문: 결제완료일 기준</span> <span class="date-basis">📦 출고: 출고완료일 기준</span>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        weekday_rev, rev_insight = analyze_weekday_pattern_revenue(revenue_df)
        if weekday_rev is not None and len(weekday_rev) > 0:
            fig = px.bar(weekday_rev, x='요일명', y='금액', text=weekday_rev['금액'].apply(lambda x: f'{x:,}'),
                         color_discrete_sequence=[biz_color])
            fig.update_traces(textposition='outside')
            fig.update_layout(height=280, title=f"💰 요일별 매출", xaxis_title="", yaxis_title="", yaxis_rangemode='tozero')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("매출 데이터가 없습니다.")

    with col2:
        weekday_ship, ship_insight = analyze_weekday_pattern_shipment(shipment_df)
        if weekday_ship is not None and len(weekday_ship) > 0:
            fig = px.bar(weekday_ship, x='요일명', y='출고수량', text='출고수량',
                         color_discrete_sequence=[biz_color])
            fig.update_traces(textposition='outside')
            fig.update_layout(height=280, title="📦 요일별 출고", xaxis_title="", yaxis_title="", yaxis_rangemode='tozero')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("출고 데이터가 없습니다.")

    # 인사이트
    if rev_insight:
        render_insight(f"{selected_biz} 요일별 주문 패턴", rev_insight, "info")
    if ship_insight:
        render_insight(f"{selected_biz} 요일별 출고 패턴", ship_insight, "info")

    # 시간대별 패턴
    # 시간대별 패턴
    st.markdown("---")
    st.markdown(f"### 🕐 시간대별 주문 패턴 (30분 단위) {'(' + selected_biz + ')' if selected_biz != '전체' else ''}")
    st.markdown('<span class="date-basis">💰 결제완료일시 기준</span>', unsafe_allow_html=True)

    hourly_stats, hourly_top5 = analyze_hourly_pattern(revenue_df)

    if hourly_stats is not None and len(hourly_stats) > 0:
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = px.bar(hourly_stats, x='시간대', y='금액',
                         text=hourly_stats['금액'].apply(lambda x: f'{x:,}' if x > 0 else ''),
                         color_discrete_sequence=[biz_color])
            fig.update_traces(textposition='outside', textfont_size=8)
            fig.update_layout(height=350, title="💰 시간대별 매출", xaxis_title="시간대", yaxis_title="매출(원)",
                              xaxis_tickangle=-45, yaxis_rangemode='tozero')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown(f"#### 🏆 피크 시간대 TOP 5")
            if hourly_top5 is not None and len(hourly_top5) > 0:
                for _, row in hourly_top5.iterrows():
                    st.markdown(f"""
                    <div style="background:#f8f9fa; padding:8px 12px; margin:5px 0; border-radius:6px; border-left:3px solid {biz_color};">
                        <b>{row['순위']}위</b> {row['시간대']} — <b>{row['금액']:,}원</b> ({row['주문건수']}건)
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("시간대별 데이터가 없습니다.")

    # 프로모션 추천
    st.markdown("---")
    st.markdown("### 🎯 프로모션 추천 (축산 MD 전문가 분석)")

    promo_tabs = st.tabs(["⏰ 시간대별 전략", "🗓️ 시즌별 전략", "🏪 채널별 전략"])

    with promo_tabs[0]:
        st.markdown(f'<span class="date-basis">💡 {selected_biz} | {start} ~ {end} 주문 패턴 기반 추천</span>', unsafe_allow_html=True)

        # 시간대별 추천 (선택된 사업장 + 조회 기간 기준)
        time_recommendations = generate_time_promotion_recommendations(hourly_stats, selected_biz)

        if time_recommendations:
            for rec in time_recommendations:
                if rec['type'] == 'peak':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #e8f5e9, #f1f8e9); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid {biz_color};">
                        <div style="font-weight:bold; color:#2e7d32; font-size:16px;">🎯 {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>시간대:</b> {rec['time']}<br>
                            <b>전략:</b> {rec['strategy']}<br>
                            <b>상세:</b> {rec['detail']}<br>
                            <b>추천 광고:</b> {rec['ad_type']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif rec['type'] == 'opportunity':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #fff3e0, #ffe0b2); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #ff9800;">
                        <div style="font-weight:bold; color:#e65100; font-size:16px;">💡 {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>시간대:</b> {rec['time']}<br>
                            <b>전략:</b> {rec['strategy']}<br>
                            <b>상세:</b> {rec['detail']}<br>
                            <b>추천 광고:</b> {rec['ad_type']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif rec['type'] == 'timing':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #e3f2fd, #bbdefb); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid {biz_color};">
                        <div style="font-weight:bold; color:#1565c0; font-size:16px;">⏱️ {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>타이밍:</b> {rec['time']}<br>
                            <b>전략:</b> {rec['strategy']}<br>
                            <b>상세:</b> {rec['detail']}<br>
                            <b>추천 광고:</b> {rec['ad_type']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # 사업장 특화 전략 (선택된 사업장에 따라)
            if selected_biz == '육구이':
                st.markdown("""
                <div style="background:linear-gradient(135deg, #FFE5E5, #FFF5F5); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #FF6B6B;">
                    <div style="font-weight:bold; color:#c0392b; font-size:16px;">🥩 육구이 (도축장집아들들) 특화 전략</div>
                    <div style="color:#555; margin:8px 0;">
                        <b>브랜드 이미지:</b> 신선함 · 친근함 · 도축장 직송<br>
                        <b>타겟 고객:</b> 신선한 고기를 원하는 고객, 내장류 마니아, 평달 단품 구매자<br>
                        <b>주력 상품:</b> 한우/한돈 단품, 등골·내장류, 명절 선물세트<br>
                        <b>차별점:</b> 도축장 직송으로 신선도 극대화 → 쉽게 부패하는 내장류 취급 가능<br>
                        <b>광고 메시지:</b> "도축장 직송", "오늘 잡은 고기", "신선내장 전문", "한돈도 있어요"
                    </div>
                    <div style="background:#fff; padding:10px; border-radius:6px; margin-top:10px;">
                        <b>💡 시즌별 전략:</b><br>
                        • <b>평달:</b> 단품 매출 강조, 내장류 타임특가, 한돈 프로모션<br>
                        • <b>명절:</b> 선물세트 + 평소 인기 단품 묶음 구성
                    </div>
                </div>
                """, unsafe_allow_html=True)
            elif selected_biz == '우주인':
                st.markdown("""
                <div style="background:linear-gradient(135deg, #E5F9F6, #F5FFFD); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #4ECDC4;">
                    <div style="font-weight:bold; color:#16a085; font-size:16px;">🚀 우주인 특화 전략</div>
                    <div style="color:#555; margin:8px 0;">
                        <b>브랜드 이미지:</b> 프리미엄 · 고급스러움 · 선물 전문<br>
                        <b>타겟 고객:</b> 고급 선물세트 구매자, 품격있는 선물을 원하는 고객<br>
                        <b>주력 상품:</b> 프리미엄 한우 선물세트 (명절 시즌 집중)<br>
                        <b>차별점:</b> 고급 포장 · 프리미엄 이미지 → 받는 분이 감동하는 선물<br>
                        <b>광고 메시지:</b> "프리미엄 한우", "격이 다른 선물", "고급 포장", "VIP 선물"
                    </div>
                    <div style="background:#fff; padding:10px; border-radius:6px; margin-top:10px;">
                        <b>💡 시즌별 전략:</b><br>
                        • <b>명절 (설/추석):</b> 연매출 대부분 집중! 사전예약 필수, 고급 이미지 극대화<br>
                        • <b>평달:</b> VIP 고객 유지, 기업 대량 구매 타겟, 프리미엄 단품 소량 운영
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("시간대별 데이터가 부족합니다. 더 많은 데이터를 업로드하면 추천이 생성됩니다.")

    with promo_tabs[1]:
        st.markdown(f'<span class="date-basis">💡 {selected_biz} | {start} ~ {end} 시즌별 마케팅 전략</span>', unsafe_allow_html=True)

        season_recommendations, monthly_data = generate_seasonal_recommendations(revenue_df, selected_biz)

        if season_recommendations:
            for rec in season_recommendations:
                if rec['type'] == 'current_season':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #e8f5e9, #c8e6c9); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #4caf50;">
                        <div style="font-weight:bold; color:#2e7d32; font-size:16px;">🌟 {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>추천 상품:</b> {rec['products']}<br>
                            <b>주요 이벤트:</b> {rec['events']}<br>
                            <b>전략:</b> {rec['strategy']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif rec['type'] == 'next_season':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #e3f2fd, #bbdefb); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #2196f3;">
                        <div style="font-weight:bold; color:#1565c0; font-size:16px;">📅 {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>준비할 상품:</b> {rec['products']}<br>
                            <b>예정 이벤트:</b> {rec['events']}<br>
                            <b>전략:</b> {rec['strategy']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                elif rec['type'] == 'data_insight':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #fff8e1, #ffecb3); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #ffc107;">
                        <div style="font-weight:bold; color:#f57f17; font-size:16px;">📊 {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            {rec['detail']}<br>
                            <b>전략:</b> {rec['strategy']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # 월별 차트 (데이터가 있을 때)
            if monthly_data is not None and len(monthly_data) >= 2:
                st.markdown("#### 📈 월별 매출 추이")
                monthly_data['월명'] = monthly_data['월'].astype(str) + '월'
                fig = px.bar(monthly_data, x='월명', y='매출',
                             text=monthly_data['매출'].apply(lambda x: f'{x:,}'),
                             color_discrete_sequence=['#8e44ad'])
                fig.update_traces(textposition='outside')
                fig.update_layout(height=300, xaxis_title="", yaxis_title="매출(원)", yaxis_rangemode='tozero')
                st.plotly_chart(fig, use_container_width=True)

        # 축산 MD 연간 캘린더
        with st.expander("📅 축산 MD 연간 마케팅 캘린더 (주차별)", expanded=False):
            # 월별 탭
            cal_tabs = st.tabs(["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"])

            weekly_calendar = {
                "1월": [
                    {"주차": "1주", "날짜": "1/1", "이벤트": "🎍 신정", "유형": "공휴일", "추천상품": "파티용 고기, 구이 세트", "마케팅팁": "새해맞이 홈파티 수요"},
                    {"주차": "1주", "날짜": "1/14", "이벤트": "📔 다이어리데이", "유형": "민간", "추천상품": "정기구독 상품", "마케팅팁": "새해 다짐과 연계한 건강식 프로모션"},
                    {"주차": "2~3주", "날짜": "설연휴", "이벤트": "🧧 설날 (음력)", "유형": "명절", "추천상품": "한우 선물세트, 프리미엄 등심/갈비", "마케팅팁": "★필수★ 연중 최대 대목! 2주 전부터 사전예약, 선물포장 강조"},
                    {"주차": "4주", "날짜": "1/24", "이벤트": "🥩 한우데이", "유형": "민간", "추천상품": "한우 전품목", "마케팅팁": "★필수★ 한우 특가전, 등급별 프로모션, 1++ 강조"},
                ],
                "2월": [
                    {"주차": "2주", "날짜": "2/14", "이벤트": "💝 발렌타인데이", "유형": "민간", "추천상품": "스테이크, 커플 세트", "마케팅팁": "로맨틱 디너 세트, 프리미엄 포장"},
                    {"주차": "3주", "날짜": "2월 중", "이벤트": "🎓 졸업시즌", "유형": "시즌", "추천상품": "파티용 세트, 축하 선물", "마케팅팁": "졸업 축하 기획전"},
                    {"주차": "4주", "날짜": "2/29", "이벤트": "🍖 육류의날 (2/9)", "유형": "민간", "추천상품": "고기 전품목", "마케팅팁": "29(육류) 할인 이벤트"},
                ],
                "3월": [
                    {"주차": "1주", "날짜": "3/3", "이벤트": "🥓 삼삼데이 (삼겹살데이)", "유형": "민간", "추천상품": "삼겹살, 목살, 항정살", "마케팅팁": "★필수★ 삼겹살 특가, 3+3 증정, 33% 할인"},
                    {"주차": "1주", "날짜": "3/1", "이벤트": "🇰🇷 삼일절", "유형": "공휴일", "추천상품": "가족 식사용", "마케팅팁": "연휴 집밥 프로모션"},
                    {"주차": "2주", "날짜": "3/14", "이벤트": "🍬 화이트데이", "유형": "민간", "추천상품": "스테이크, 고급 부위", "마케팅팁": "답례 선물세트, 커플 프로모션"},
                    {"주차": "3~4주", "날짜": "3월 중순", "이벤트": "🌸 봄나들이 시즌", "유형": "시즌", "추천상품": "캠핑용 양념육, 소풍 밀키트", "마케팅팁": "피크닉/캠핑 패키지 출시"},
                ],
                "4월": [
                    {"주차": "1주", "날짜": "4/4", "이벤트": "🥩 양념육데이 (사사데이)", "유형": "민간", "추천상품": "양념 삼겹살, 양념 갈비", "마케팅팁": "양념육 특가, 4+4 행사"},
                    {"주차": "1~2주", "날짜": "4월 초", "이벤트": "🌸 벚꽃시즌", "유형": "시즌", "추천상품": "바베큐 세트, 도시락용", "마케팅팁": "꽃놀이 패키지, 야외용 강조"},
                    {"주차": "2주", "날짜": "4/14", "이벤트": "🖤 블랙데이", "유형": "민간", "추천상품": "1인분 스테이크, 혼밥용", "마케팅팁": "솔로를 위한 혼밥 프로모션"},
                    {"주차": "3주", "날짜": "4/19", "이벤트": "🥩 한우 등심데이 (4/19)", "유형": "민간", "추천상품": "한우 등심", "마케팅팁": "등심 특가전"},
                ],
                "5월": [
                    {"주차": "1주", "날짜": "5/5", "이벤트": "👶 어린이날", "유형": "공휴일", "추천상품": "가족 파티세트, 아이용 떡갈비", "마케팅팁": "가족 나들이 패키지"},
                    {"주차": "2주", "날짜": "5/8", "이벤트": "💐 어버이날", "유형": "기념일", "추천상품": "한우 선물세트, 프리미엄 세트", "마케팅팁": "★필수★ 효도 선물 마케팅, 감사 카드"},
                    {"주차": "2주", "날짜": "5/14", "이벤트": "🌹 로즈데이", "유형": "민간", "추천상품": "스테이크, 와인 페어링 세트", "마케팅팁": "로맨틱 디너 연계"},
                    {"주차": "3주", "날짜": "5/15", "이벤트": "👨‍🏫 스승의날", "유형": "기념일", "추천상품": "감사 선물세트", "마케팅팁": "소포장 선물 세트"},
                    {"주차": "4주", "날짜": "5월 말", "이벤트": "👨‍👩‍👧‍👦 가정의달 마무리", "유형": "시즌", "추천상품": "가족 모임용 대용량", "마케팅팁": "가정의달 감사 이벤트"},
                ],
                "6월": [
                    {"주차": "1주", "날짜": "6/6", "이벤트": "🎖️ 현충일", "유형": "공휴일", "추천상품": "가족 식사용", "마케팅팁": "연휴 집밥 프로모션"},
                    {"주차": "2주", "날짜": "6/9", "이벤트": "🍗 닭고기데이 (육구데이)", "유형": "민간", "추천상품": "닭고기, 삼계탕용", "마케팅팁": "69(육구) 치킨/닭 프로모션"},
                    {"주차": "2주", "날짜": "6/14", "이벤트": "💋 키스데이", "유형": "민간", "추천상품": "커플 디너 세트", "마케팅팁": "데이트용 프리미엄 세트"},
                    {"주차": "3~4주", "날짜": "6월 말", "이벤트": "☀️ 초복 준비", "유형": "시즌", "추천상품": "삼계탕용 닭, 보양식 재료", "마케팅팁": "★필수★ 복날 사전예약 시작"},
                ],
                "7월": [
                    {"주차": "1~2주", "날짜": "7월 중순", "이벤트": "🔥 초복", "유형": "명절", "추천상품": "삼계탕용, 보신탕용, 보양식", "마케팅팁": "★필수★ 복날 특수, 보양식 마케팅"},
                    {"주차": "2주", "날짜": "7/14", "이벤트": "💍 실버데이", "유형": "민간", "추천상품": "커플 세트", "마케팅팁": "커플 프로모션"},
                    {"주차": "2~3주", "날짜": "7월 중순", "이벤트": "🏖️ 휴가철 시작", "유형": "시즌", "추천상품": "캠핑용 대용량, BBQ 세트", "마케팅팁": "캠핑/바베큐 패키지 강화"},
                    {"주차": "3~4주", "날짜": "7월 하순", "이벤트": "🔥 중복", "유형": "명절", "추천상품": "삼계탕, 보양식", "마케팅팁": "복날 연속 마케팅"},
                ],
                "8월": [
                    {"주차": "1주", "날짜": "8월 초", "이벤트": "🔥 말복", "유형": "명절", "추천상품": "삼계탕, 보양식 마무리", "마케팅팁": "마지막 복날 프로모션"},
                    {"주차": "1주", "날짜": "8/8", "이벤트": "🐝 벌집 삼겹살데이", "유형": "민간", "추천상품": "벌집 삼겹살", "마케팅팁": "88 할인, 벌집 삼겹살 특가"},
                    {"주차": "2주", "날짜": "8/14", "이벤트": "💚 그린데이", "유형": "민간", "추천상품": "건강식, 샐러드용 닭가슴살", "마케팅팁": "건강한 데이트 콘셉트"},
                    {"주차": "2주", "날짜": "8/15", "이벤트": "🇰🇷 광복절", "유형": "공휴일", "추천상품": "가족 모임용", "마케팅팁": "연휴 가족 식사 프로모션"},
                    {"주차": "3~4주", "날짜": "8월 말", "이벤트": "🍂 추석 준비", "유형": "시즌", "추천상품": "추석 선물세트", "마케팅팁": "★필수★ 추석 선물세트 사전예약 시작"},
                ],
                "9월": [
                    {"주차": "1~2주", "날짜": "추석연휴", "이벤트": "🌕 추석", "유형": "명절", "추천상품": "한우 선물세트, LA갈비, 프리미엄 세트", "마케팅팁": "★필수★ 명절 최대 대목, 2주전 마케팅 집중"},
                    {"주차": "2주", "날짜": "9/9", "이벤트": "🍗 구구데이 (닭고기데이)", "유형": "민간", "추천상품": "닭고기 전품목", "마케팅팁": "99 치킨/닭 특가"},
                    {"주차": "2주", "날짜": "9/14", "이벤트": "📸 포토데이", "유형": "민간", "추천상품": "SNS용 예쁜 패키지", "마케팅팁": "인스타그래머블 패키지"},
                    {"주차": "3~4주", "날짜": "9월 하순", "이벤트": "🍂 가을 캠핑", "유형": "시즌", "추천상품": "캠핑용 구이 세트", "마케팅팁": "단풍철 캠핑 수요 공략"},
                ],
                "10월": [
                    {"주차": "1주", "날짜": "10/3", "이벤트": "🇰🇷 개천절", "유형": "공휴일", "추천상품": "가족 식사용", "마케팅팁": "연휴 프로모션"},
                    {"주차": "1주", "날짜": "10/9", "이벤트": "🇰🇷 한글날", "유형": "공휴일", "추천상품": "가족 모임용", "마케팅팁": "연휴 집밥 프로모션"},
                    {"주차": "2주", "날짜": "10/14", "이벤트": "🍷 와인데이", "유형": "민간", "추천상품": "스테이크, 와인 페어링", "마케팅팁": "와인과 어울리는 고기 추천"},
                    {"주차": "3주", "날짜": "10월 중순", "이벤트": "🍂 단풍철", "유형": "시즌", "추천상품": "캠핑용 양념육", "마케팅팁": "가을 캠핑 패키지"},
                    {"주차": "4주", "날짜": "10/31", "이벤트": "🎃 할로윈", "유형": "민간", "추천상품": "파티용 세트, 바베큐", "마케팅팁": "할로윈 파티 프로모션"},
                ],
                "11월": [
                    {"주차": "1주", "날짜": "11/1", "이벤트": "🥬 김장철 시작", "유형": "시즌", "추천상품": "수육용 돼지고기, 보쌈용", "마케팅팁": "★필수★ 김장 보쌈 프로모션"},
                    {"주차": "2주", "날짜": "11/11", "이벤트": "🥢 빼빼로데이", "유형": "민간", "추천상품": "막대 모양 육포, 스틱 간식", "마케팅팁": "빼빼로 콘셉트 상품"},
                    {"주차": "2주", "날짜": "11/14", "이벤트": "🎬 무비데이", "유형": "민간", "추천상품": "안주용, 영화관람 세트", "마케팅팁": "영화보며 먹을 안주 추천"},
                    {"주차": "3~4주", "날짜": "11월 넷째주", "이벤트": "🛒 블랙프라이데이", "유형": "민간", "추천상품": "전품목", "마케팅팁": "★필수★ 연중 최대 할인, 대량구매 유도"},
                    {"주차": "4주", "날짜": "11월 말", "이벤트": "🎄 연말 준비", "유형": "시즌", "추천상품": "파티용, 크리스마스 세트", "마케팅팁": "연말연시 사전예약 시작"},
                ],
                "12월": [
                    {"주차": "1주", "날짜": "12월 초", "이벤트": "🎄 크리스마스 준비", "유형": "시즌", "추천상품": "파티용 스테이크, 로스트", "마케팅팁": "크리스마스 예약 프로모션"},
                    {"주차": "2주", "날짜": "12/14", "이벤트": "🤗 허그데이", "유형": "민간", "추천상품": "따뜻한 국물용 고기", "마케팅팁": "따뜻한 겨울 음식 연계"},
                    {"주차": "3주", "날짜": "12/22", "이벤트": "❄️ 동지", "유형": "명절", "추천상품": "동지팥죽용, 보양식", "마케팅팁": "겨울 보양식 프로모션"},
                    {"주차": "4주", "날짜": "12/25", "이벤트": "🎄 크리스마스", "유형": "공휴일", "추천상품": "파티용 스테이크, 립, 로스트비프", "마케팅팁": "★필수★ 홈파티 시즌, 프리미엄 강조"},
                    {"주차": "4주", "날짜": "12/31", "이벤트": "🎆 송년회/연말", "유형": "시즌", "추천상품": "모임용 대용량, 파티세트", "마케팅팁": "송년회 단체 주문 프로모션"},
                ],
            }

            for i, month in enumerate(["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]):
                with cal_tabs[i]:
                    cal_df = pd.DataFrame(weekly_calendar[month])
                    # 필수 이벤트 강조
                    st.dataframe(
                        cal_df.style.apply(
                            lambda x: ['background-color: #fff3cd' if '★필수★' in str(v) else '' for v in x],
                            axis=1
                        ),
                        use_container_width=True,
                        hide_index=True
                    )

            st.markdown("""
            ---
            **범례:**
            - 🔴 **★필수★** (노란 배경): 축산 MD 필수 대응 - 절대 놓치면 안되는 이벤트
              - **설날/추석**: 연간 매출의 60% 이상 차지하는 최대 대목
              - **한우데이**: 한우 업계 공식 기념일
              - **삼삼데이**: 삼겹살 연중 최대 판매일
              - **복날**: 보양식 수요 폭발
              - **블랙프라이데이/크리스마스**: 연말 대형 프로모션
            - **민간**: SNS/입소문 기념일 (14일 시리즈 등)
            - **공휴일**: 국가 공휴일
            - **명절**: 전통 명절
            - **시즌**: 계절/시즌 이벤트
            """)

    with promo_tabs[2]:
        st.markdown(f'<span class="date-basis">💡 {selected_biz} | {start} ~ {end} 채널별 맞춤 전략</span>', unsafe_allow_html=True)

        channel_recommendations, all_strategies = generate_channel_strategies(revenue_df, selected_biz)

        if channel_recommendations:
            st.markdown("#### 📊 내 채널별 맞춤 전략")
            st.caption("매출 데이터를 기반으로 상위 채널에 맞는 전략을 추천합니다.")

            for rec in channel_recommendations:
                strategy = rec['strategy']
                if strategy:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #f5f5f5, #eeeeee); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #666;">
                        <div style="font-weight:bold; font-size:18px; margin-bottom:10px;">
                            {strategy['icon']} {rec['shop']}
                            <span style="font-size:14px; color:#666; margin-left:10px;">
                                매출 {rec['revenue']:,}원 ({rec['ratio']}%) | 객단가 {rec['aov']:,}원
                            </span>
                        </div>
                        <div style="color:#555; margin:8px 0;">
                            <b>강점:</b> {strategy['strength']}<br>
                            <b>타겟:</b> {strategy['target']}<br>
                            <b>💡 TIP:</b> {strategy['tip']}
                        </div>
                        <div style="margin-top:10px;">
                            <b>추천 프로모션:</b>
                            <ul style="margin:5px 0; padding-left:20px;">
                    """, unsafe_allow_html=True)
                    for promo in strategy['promotion'][:4]:
                        st.markdown(f"<li>{promo}</li>", unsafe_allow_html=True)
                    st.markdown("</ul></div></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:#f9f9f9; padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #999;">
                        <div style="font-weight:bold; font-size:16px;">
                            🏪 {rec['shop']}
                            <span style="font-size:14px; color:#666; margin-left:10px;">
                                매출 {rec['revenue']:,}원 ({rec['ratio']}%) | 객단가 {rec['aov']:,}원
                            </span>
                        </div>
                        <div style="color:#888; margin-top:5px;">해당 채널의 상세 전략 정보가 없습니다.</div>
                    </div>
                    """, unsafe_allow_html=True)

        # 전체 채널 전략 가이드
        with st.expander("📚 전체 채널 마케팅 가이드", expanded=False):
            for key, strategy in all_strategies.items():
                st.markdown(f"""
                **{strategy['icon']} {strategy['name']}**
                - 강점: {strategy['strength']}
                - 타겟: {strategy['target']}
                - TIP: {strategy['tip']}
                """)
                st.markdown("---")

        # 사업장별 채널 전략 차이 (전체 선택시에만 표시)
        if selected_biz == "전체":
            st.markdown("#### 🔍 사업장별 주력 채널 비교")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**🥩 육구이**")
                육구이_recs, _ = generate_channel_strategies(revenue_df, "육구이")
                if 육구이_recs:
                    for rec in 육구이_recs[:3]:
                        st.markdown(f"- {rec['shop']}: {rec['revenue']:,}원 ({rec['ratio']}%)")
                else:
                    st.info("데이터가 없습니다.")

            with col2:
                st.markdown("**🚀 우주인**")
                우주인_recs, _ = generate_channel_strategies(revenue_df, "우주인")
                if 우주인_recs:
                    for rec in 우주인_recs[:3]:
                        st.markdown(f"- {rec['shop']}: {rec['revenue']:,}원 ({rec['ratio']}%)")
                else:
                    st.info("데이터가 없습니다.")

    # 다운로드
    st.markdown("---")
    if len(rev_biz) > 0:
        export_df = rev_biz.copy()
        if len(ship_biz) > 0:
            export_df = export_df.merge(ship_biz[['사업장', '판매수량']], on='사업장', how='left', suffixes=('', '_출고'))
            export_df = export_df.rename(columns={'판매수량_출고': '출고수량'})

        st.download_button(
            "📥 대시보드 데이터 다운로드",
            data=to_excel(export_df),
            file_name=f"대시보드_{start}_{end}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


def render_shop_analysis(analyzer: OrderAnalyzer):
    """쇼핑몰별 분석"""
    st.title("🏪 쇼핑몰별 분석")

    st.markdown("### 📅 조회 기간")
    start, end = render_date_filter(analyzer, "shop")

    if start is None:
        return

    revenue_df = analyzer.filter_by_date_range(start, end)
    shipment_df = analyzer.filter_by_shipment_date_range(start, end)

    if revenue_df is None or len(revenue_df) == 0:
        st.warning("선택한 기간에 데이터가 없습니다.")
        return

    st.caption(f"📊 조회: {start} ~ {end}")

    st.markdown("""
    <div style="display:flex; gap:10px; margin:10px 0;">
        <span class="date-basis">💰 매출: 결제완료일 기준</span>
        <span class="date-basis">📦 출고: 출고완료일 기준</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    biz_tabs = st.tabs(["🥩 육구이", "🚀 우주인"])

    for tab_idx, (tab, biz_name) in enumerate(zip(biz_tabs, ['육구이', '우주인'])):
        with tab:
            biz_rev_df = analyzer.filter_by_business(biz_name, revenue_df)
            biz_ship_df = analyzer.filter_by_business(biz_name, shipment_df) if shipment_df is not None else pd.DataFrame()

            if biz_rev_df is None or len(biz_rev_df) == 0:
                st.warning(f"{biz_name} 데이터가 없습니다.")
                continue

            shop_rev = analyzer.analyze_by_shop(biz_rev_df, by_business=False)

            shop_col = get_shop_col(biz_ship_df) if len(biz_ship_df) > 0 else '쇼핑몰명'
            if len(biz_ship_df) > 0:
                normal_ship = biz_ship_df[~biz_ship_df['취소여부']]
                shop_ship = normal_ship.groupby(shop_col)['주문수량'].sum().reset_index()
                shop_ship.columns = ['쇼핑몰명', '출고수량']
            else:
                shop_ship = pd.DataFrame(columns=['쇼핑몰명', '출고수량'])

            cancelled = biz_rev_df[biz_rev_df['취소여부']]
            if len(cancelled) > 0:
                shop_col_cancel = get_shop_col(cancelled)
                shop_cancel = cancelled.groupby(shop_col_cancel).size().reset_index(name='취소건수')
                shop_cancel.columns = ['쇼핑몰명', '취소건수']
            else:
                shop_cancel = pd.DataFrame(columns=['쇼핑몰명', '취소건수'])

            if shop_rev is None or len(shop_rev) == 0:
                continue

            merged = shop_rev.merge(shop_ship, on='쇼핑몰명', how='left').fillna(0)
            merged = merged.merge(shop_cancel, on='쇼핑몰명', how='left').fillna(0)
            merged['출고수량'] = merged['출고수량'].astype(int)
            merged['취소건수'] = merged['취소건수'].astype(int)
            # 객단가 계산 (매출 / 판매건수)
            merged['객단가'] = (merged['매출'] / merged['판매건수']).fillna(0).astype(int)

            # 인사이트
            insights = generate_shop_insights(merged, biz_name)
            if insights:
                st.markdown("#### 💡 분석 코멘트")
                for title, text, alert_type in insights:
                    render_insight(title, text, alert_type)

            # 차트
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(merged, x='쇼핑몰명', y='매출', text=merged['매출'].apply(lambda x: f'{x:,}'),
                             color_discrete_sequence=[BUSINESS_COLORS[biz_name]])
                fig.update_traces(textposition='outside')
                fig.update_layout(height=300, showlegend=False, title="💰 매출", yaxis_rangemode='tozero')
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(merged, x='쇼핑몰명', y='출고수량', text='출고수량',
                             color_discrete_sequence=[BUSINESS_COLORS[biz_name]])
                fig.update_traces(textposition='outside')
                fig.update_layout(height=300, showlegend=False, title="📦 출고수량", yaxis_rangemode='tozero')
                st.plotly_chart(fig, use_container_width=True)

            # 테이블
            st.dataframe(merged[['쇼핑몰명', '매출', '출고수량', '판매건수', '객단가', '취소건수', '매출비율(%)']].style.format({
                '매출': '{:,}원', '출고수량': '{:,}', '판매건수': '{:,}', '객단가': '{:,}원', '취소건수': '{:,}', '매출비율(%)': '{:.1f}%'
            }), use_container_width=True, hide_index=True)

            # 쇼핑몰별 상품 상세
            st.markdown("#### 📦 쇼핑몰별 상품 상세")
            for _, shop_row in merged.iterrows():
                shop_name = shop_row['쇼핑몰명']
                shop_revenue = shop_row['매출']
                shop_qty = shop_row['출고수량']
                shop_cancel_cnt = shop_row['취소건수']
                shop_aov = shop_row['객단가']

                shop_col_name = get_shop_col(biz_rev_df)
                shop_data = biz_rev_df[biz_rev_df[shop_col_name] == shop_name]
                normal_data = shop_data[~shop_data['취소여부']]
                top_products = normal_data.groupby(['SKU코드', 'SKU상품명']).agg({
                    '금액': 'sum',
                    '주문수량': 'sum',
                    '묶음번호': 'nunique'
                }).reset_index().sort_values('금액', ascending=False)

                cancel_label = f" | 🔄 취소 {shop_cancel_cnt}건" if shop_cancel_cnt > 0 else ""
                with st.expander(f"🏪 **{shop_name}** — 💰 {shop_revenue:,}원 | 📦 {shop_qty:,}개 | 💳 객단가 {shop_aov:,}원{cancel_label}", expanded=False):
                    if len(top_products) > 0:
                        top_products.columns = ['SKU코드', '상품명', '매출', '출고수량', '판매건수']
                        top_products['객단가'] = (top_products['매출'] / top_products['판매건수']).fillna(0).astype(int)
                        top_products['순위'] = range(1, len(top_products) + 1)
                        top_products = top_products[['순위', '상품명', '매출', '출고수량', '판매건수', '객단가']]
                        st.dataframe(
                            top_products.style.format({'매출': '{:,}원', '출고수량': '{:,}', '판매건수': '{:,}', '객단가': '{:,}원'}),
                            use_container_width=True, hide_index=True
                        )

            st.download_button(
                f"📥 {biz_name} 데이터 다운로드", data=to_excel(merged),
                file_name=f"쇼핑몰별_{biz_name}_{start}_{end}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_shop_{biz_name}"
            )


def render_product_analysis(analyzer: OrderAnalyzer):
    """상품별 분석"""
    st.title("📦 상품별 분석")

    st.markdown("### 📅 조회 기간")
    start, end = render_date_filter(analyzer, "prod")

    if start is None:
        return

    revenue_df = analyzer.filter_by_date_range(start, end)

    if revenue_df is None or len(revenue_df) == 0:
        st.warning("선택한 기간에 데이터가 없습니다.")
        return

    st.caption(f"📊 조회: {start} ~ {end}")

    st.markdown("""
    <div style="display:flex; gap:10px; margin:10px 0;">
        <span class="date-basis">💰 매출: 결제완료일 기준</span>
        <span class="date-basis">📦 출고: 결제완료일 기준 (주문수량)</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 필터
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        biz_option = st.radio("사업장", ["전체", "육구이", "우주인"], horizontal=True, key="prod_biz")
    with col2:
        top_n = st.slider("표시 수", 10, 100, 30, key="prod_n")
    with col3:
        search_term = st.text_input("🔍 상품 검색", placeholder="상품명 입력...", key="prod_search")

    target_df = revenue_df.copy()
    if biz_option != "전체":
        target_df = analyzer.filter_by_business(biz_option, revenue_df)

    # 상품 검색 필터
    if search_term:
        target_df = target_df[target_df['SKU상품명'].str.contains(search_term, case=False, na=False)]
        if len(target_df) == 0:
            st.warning(f"'{search_term}' 검색 결과가 없습니다.")
            return

    normal = target_df[~target_df['취소여부']]
    cancelled = target_df[target_df['취소여부']]

    product_df = normal.groupby(['사업장', 'SKU코드', 'SKU상품명']).agg({
        '금액': 'sum',
        '주문수량': 'sum',
        '묶음번호': 'nunique'
    }).reset_index()
    product_df.columns = ['사업장', 'SKU코드', '상품명', '매출', '출고수량', '판매건수']
    # 객단가 계산
    product_df['객단가'] = (product_df['매출'] / product_df['판매건수']).fillna(0).astype(int)

    if len(cancelled) > 0:
        cancel_prod = cancelled.groupby(['SKU코드']).size().reset_index(name='취소건수')
        product_df = product_df.merge(cancel_prod, on='SKU코드', how='left').fillna(0)
        product_df['취소건수'] = product_df['취소건수'].astype(int)
    else:
        product_df['취소건수'] = 0

    product_df = product_df.sort_values('매출', ascending=False).head(top_n)
    product_df['순위'] = range(1, len(product_df) + 1)
    product_df = product_df[['순위', '사업장', '상품명', '매출', '출고수량', '판매건수', '객단가', '취소건수']]

    if len(product_df) == 0:
        st.warning("데이터가 없습니다.")
        return

    # 취소 많은 상품
    cancel_top = product_df[product_df['취소건수'] > 0].sort_values('취소건수', ascending=False).head(5) if product_df['취소건수'].sum() > 0 else None

    # 인사이트
    insights = generate_product_insights(product_df, cancel_top)
    if insights:
        st.markdown("### 💡 분석 코멘트")
        for title, text, alert_type in insights:
            render_insight(title, text, alert_type)

    st.markdown("---")

    st.dataframe(product_df.style.format({
        '매출': '{:,}원', '출고수량': '{:,}', '판매건수': '{:,}', '객단가': '{:,}원', '취소건수': '{:,}'
    }), use_container_width=True, hide_index=True, height=400)

    # 차트
    chart_df = product_df.head(15)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(chart_df, x='상품명', y='매출', text=chart_df['매출'].apply(lambda x: f'{x:,}'),
                     color='사업장', color_discrete_map=BUSINESS_COLORS)
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45, height=400, showlegend=False, title="💰 매출 TOP 15", yaxis_rangemode='tozero')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(chart_df, x='상품명', y='출고수량', text='출고수량',
                     color='사업장', color_discrete_map=BUSINESS_COLORS)
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45, height=400, showlegend=False, title="📦 출고 TOP 15", yaxis_rangemode='tozero')
        st.plotly_chart(fig, use_container_width=True)

    # 취소 많은 상품
    if cancel_top is not None and len(cancel_top) > 0:
        st.markdown("#### 🔄 취소 많은 상품")
        fig = px.bar(cancel_top, x='상품명', y='취소건수', text='취소건수',
                     color='사업장', color_discrete_map=BUSINESS_COLORS)
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45, height=300, showlegend=False, yaxis_rangemode='tozero')
        st.plotly_chart(fig, use_container_width=True)

    st.download_button("📥 상품별 데이터 다운로드", data=to_excel(product_df),
                       file_name=f"상품별_{start}_{end}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def render_period_comparison(analyzer: OrderAnalyzer):
    """기간 비교"""
    st.title("📈 기간 비교")

    min_date, max_date = analyzer.get_date_range()

    if min_date is None:
        st.warning("비교할 데이터가 없습니다.")
        return

    max_dt = max_date.date() if hasattr(max_date, 'date') else max_date
    min_dt = min_date.date() if hasattr(min_date, 'date') else min_date

    periods = analyzer.get_loaded_periods()
    if periods:
        st.info(f"📊 저장된 데이터: {', '.join([p['기간'] for p in periods])}")

    st.markdown("""
    <div style="display:flex; gap:10px; margin:10px 0;">
        <span class="date-basis">💰 매출: 결제완료일 기준</span>
        <span class="date-basis">📦 출고: 출고완료일 기준</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📅 비교 기간 선택")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🎯 기준 기간")
        bc1, bc2 = st.columns(2)
        with bc1:
            base_start = st.date_input("시작", value=min_dt, key="cmp_bs")
        with bc2:
            base_end = st.date_input("종료", value=max_dt, key="cmp_be")

    with col2:
        st.markdown("#### 📊 비교 기간")
        cc1, cc2 = st.columns(2)
        with cc1:
            comp_start = st.date_input("시작", value=min_dt, key="cmp_cs")
        with cc2:
            comp_end = st.date_input("종료", value=max_dt, key="cmp_ce")

    if st.button("📊 비교 분석", type="primary", use_container_width=True):
        base_rev = analyzer.filter_by_date_range(base_start, base_end)
        comp_rev = analyzer.filter_by_date_range(comp_start, comp_end)
        base_ship = analyzer.filter_by_shipment_date_range(base_start, base_end)
        comp_ship = analyzer.filter_by_shipment_date_range(comp_start, comp_end)

        if base_rev is None or len(base_rev) == 0:
            st.warning("기준 기간에 데이터가 없습니다.")
            return

        base_rev_stats = analyzer.get_summary_stats(base_rev)
        comp_rev_stats = analyzer.get_summary_stats(comp_rev) if comp_rev is not None else {'총 매출': 0, '판매건수': 0, '판매수량': 0, '취소건수': 0}
        base_ship_stats = analyzer.get_summary_stats(base_ship) if base_ship is not None else {'판매수량': 0}
        comp_ship_stats = analyzer.get_summary_stats(comp_ship) if comp_ship is not None else {'판매수량': 0}

        st.markdown("---")

        # 인사이트
        rev_diff = base_rev_stats['총 매출'] - comp_rev_stats['총 매출']
        rev_rate = round((rev_diff / comp_rev_stats['총 매출'] * 100), 1) if comp_rev_stats['총 매출'] > 0 else 0

        if rev_rate > 10:
            render_insight("매출 성장", f"기준 기간 매출이 비교 기간 대비 {rev_rate}% 증가했습니다. 성장 요인을 파악하여 유지하세요.", "info")
        elif rev_rate < -10:
            render_insight("매출 감소 주의", f"기준 기간 매출이 비교 기간 대비 {abs(rev_rate)}% 감소했습니다. 원인 분석이 필요합니다.", "warning")

        st.markdown("### 📈 전체 비교 결과")

        ship_diff = base_ship_stats['판매수량'] - comp_ship_stats['판매수량']
        ship_rate = round((ship_diff / comp_ship_stats['판매수량'] * 100), 1) if comp_ship_stats['판매수량'] > 0 else 0
        cancel_diff = base_rev_stats['취소건수'] - comp_rev_stats['취소건수']

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**🎯 기준**: {base_start} ~ {base_end}")
            st.metric("💰 매출", f"{base_rev_stats['총 매출']:,}원")
            st.metric("📦 출고", f"{base_ship_stats['판매수량']:,}개")
            st.metric("🔄 취소", f"{base_rev_stats['취소건수']}건")
        with col2:
            st.markdown(f"**📊 비교**: {comp_start} ~ {comp_end}")
            st.metric("💰 매출", f"{comp_rev_stats['총 매출']:,}원")
            st.metric("📦 출고", f"{comp_ship_stats['판매수량']:,}개")
            st.metric("🔄 취소", f"{comp_rev_stats['취소건수']}건")
        with col3:
            st.markdown("**📈 증감**")
            st.metric("💰 매출", f"{rev_diff:+,}원", delta=f"{rev_rate:+.1f}%")
            st.metric("📦 출고", f"{ship_diff:+,}개", delta=f"{ship_rate:+.1f}%")
            st.metric("🔄 취소", f"{cancel_diff:+,}건")

        # ========== 사업장별 비교 ==========
        st.markdown("---")
        st.markdown("### 🏢 사업장별 비교")

        base_biz = analyzer.analyze_by_business(base_rev)
        comp_biz = analyzer.analyze_by_business(comp_rev) if comp_rev is not None and len(comp_rev) > 0 else pd.DataFrame()

        if len(base_biz) > 0:
            if len(comp_biz) > 0:
                biz_merged = base_biz.merge(comp_biz, on='사업장', suffixes=('_기준', '_비교'), how='outer').fillna(0)
            else:
                biz_merged = base_biz.copy()
                biz_merged['매출_기준'] = biz_merged['매출']
                biz_merged['매출_비교'] = 0
                biz_merged['판매수량_기준'] = biz_merged['판매수량']
                biz_merged['판매수량_비교'] = 0
                biz_merged['취소건수_기준'] = biz_merged['취소건수']
                biz_merged['취소건수_비교'] = 0

            biz_merged['매출증감'] = biz_merged['매출_기준'] - biz_merged['매출_비교']
            biz_merged['매출증감율'] = ((biz_merged['매출증감'] / biz_merged['매출_비교']) * 100).replace([float('inf'), -float('inf')], 0).fillna(0).round(1)
            biz_merged['출고증감'] = biz_merged['판매수량_기준'] - biz_merged['판매수량_비교']
            biz_merged['취소증감'] = biz_merged['취소건수_기준'] - biz_merged['취소건수_비교']

            # 사업장별 인사이트
            for _, row in biz_merged.iterrows():
                biz = row['사업장']
                biz_rev_rate = row['매출증감율']
                if biz_rev_rate > 20:
                    render_insight(f"{biz} 성장", f"{biz} 매출이 {biz_rev_rate}% 증가했습니다.", "info")
                elif biz_rev_rate < -20:
                    render_insight(f"{biz} 하락 주의", f"{biz} 매출이 {abs(biz_rev_rate)}% 감소했습니다.", "warning")

            disp = biz_merged[['사업장', '매출_기준', '매출_비교', '매출증감', '매출증감율', '판매수량_기준', '판매수량_비교', '출고증감']]
            disp.columns = ['사업장', '매출(기준)', '매출(비교)', '매출증감', '증감율(%)', '출고(기준)', '출고(비교)', '출고증감']

            st.dataframe(disp.style.format({
                '매출(기준)': '{:,.0f}원', '매출(비교)': '{:,.0f}원', '매출증감': '{:+,.0f}원', '증감율(%)': '{:+.1f}%',
                '출고(기준)': '{:,.0f}개', '출고(비교)': '{:,.0f}개', '출고증감': '{:+,.0f}개'
            }), use_container_width=True, hide_index=True)

            col1, col2 = st.columns(2)
            with col1:
                fig = go.Figure()
                for biz in biz_merged['사업장']:
                    row = biz_merged[biz_merged['사업장'] == biz].iloc[0]
                    fig.add_trace(go.Bar(name=f'{biz} (기준)', x=[biz], y=[row['매출_기준']],
                                         marker_color=BUSINESS_COLORS.get(biz, '#888'),
                                         text=[f"{int(row['매출_기준']):,}"], textposition='outside'))
                    fig.add_trace(go.Bar(name=f'{biz} (비교)', x=[biz], y=[row['매출_비교']],
                                         marker_color=BUSINESS_COLORS.get(biz, '#888'), opacity=0.5,
                                         text=[f"{int(row['매출_비교']):,}"], textposition='outside'))
                fig.update_layout(barmode='group', height=300, title="💰 매출 비교", showlegend=False, yaxis_rangemode='tozero')
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = go.Figure()
                for biz in biz_merged['사업장']:
                    row = biz_merged[biz_merged['사업장'] == biz].iloc[0]
                    fig.add_trace(go.Bar(name=f'{biz} (기준)', x=[biz], y=[row['판매수량_기준']],
                                         marker_color=BUSINESS_COLORS.get(biz, '#888'),
                                         text=[f"{int(row['판매수량_기준']):,}"], textposition='outside'))
                    fig.add_trace(go.Bar(name=f'{biz} (비교)', x=[biz], y=[row['판매수량_비교']],
                                         marker_color=BUSINESS_COLORS.get(biz, '#888'), opacity=0.5,
                                         text=[f"{int(row['판매수량_비교']):,}"], textposition='outside'))
                fig.update_layout(barmode='group', height=300, title="📦 출고 비교", showlegend=False, yaxis_rangemode='tozero')
                st.plotly_chart(fig, use_container_width=True)

        # ========== 쇼핑몰별 비교 ==========
        st.markdown("---")
        st.markdown("### 🏪 쇼핑몰별 비교")

        shop_col = get_shop_col(base_rev)

        # 기준 기간 쇼핑몰 분석
        base_normal = base_rev[~base_rev['취소여부']]
        base_shop = base_normal.groupby(['사업장', shop_col]).agg({
            '금액': 'sum',
            '주문수량': 'sum',
            '묶음번호': 'nunique'
        }).reset_index()
        base_shop.columns = ['사업장', '쇼핑몰명', '매출_기준', '출고_기준', '건수_기준']

        # 비교 기간 쇼핑몰 분석
        if comp_rev is not None and len(comp_rev) > 0:
            comp_normal = comp_rev[~comp_rev['취소여부']]
            comp_shop_col = get_shop_col(comp_rev)
            comp_shop = comp_normal.groupby(['사업장', comp_shop_col]).agg({
                '금액': 'sum',
                '주문수량': 'sum',
                '묶음번호': 'nunique'
            }).reset_index()
            comp_shop.columns = ['사업장', '쇼핑몰명', '매출_비교', '출고_비교', '건수_비교']
        else:
            comp_shop = pd.DataFrame(columns=['사업장', '쇼핑몰명', '매출_비교', '출고_비교', '건수_비교'])

        shop_merged = base_shop.merge(comp_shop, on=['사업장', '쇼핑몰명'], how='outer').fillna(0)
        shop_merged['매출증감'] = shop_merged['매출_기준'] - shop_merged['매출_비교']
        shop_merged['매출증감율'] = ((shop_merged['매출증감'] / shop_merged['매출_비교']) * 100).replace([float('inf'), -float('inf')], 0).fillna(0).round(1)
        shop_merged['출고증감'] = shop_merged['출고_기준'] - shop_merged['출고_비교']
        shop_merged = shop_merged.sort_values('매출_기준', ascending=False)

        # 성장/하락 채널 분류
        growing_shops = shop_merged[shop_merged['매출증감율'] > 20].head(5)
        declining_shops = shop_merged[shop_merged['매출증감율'] < -20].head(5)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📈 성장 채널 TOP 5")
            if len(growing_shops) > 0:
                for _, row in growing_shops.iterrows():
                    st.markdown(f"- **{row['사업장']} - {row['쇼핑몰명']}**: +{row['매출증감율']:.1f}% ({row['매출증감']:+,.0f}원)")
                render_insight("성장 채널 전략", "성장 채널의 성공 요인을 분석하고, 다른 채널에도 적용해보세요.", "info")
            else:
                st.info("20% 이상 성장한 채널이 없습니다.")

        with col2:
            st.markdown("#### 📉 하락 채널 TOP 5")
            if len(declining_shops) > 0:
                for _, row in declining_shops.iterrows():
                    st.markdown(f"- **{row['사업장']} - {row['쇼핑몰명']}**: {row['매출증감율']:.1f}% ({row['매출증감']:+,.0f}원)")
                render_insight("하락 채널 대응", "하락 채널의 원인(경쟁사, 가격, 노출 등)을 파악하고 대응 전략을 수립하세요.", "warning")
            else:
                st.info("20% 이상 하락한 채널이 없습니다.")

        # 쇼핑몰별 상세 테이블
        with st.expander("📋 쇼핑몰별 상세 데이터", expanded=False):
            shop_disp = shop_merged[['사업장', '쇼핑몰명', '매출_기준', '매출_비교', '매출증감', '매출증감율', '출고_기준', '출고_비교', '출고증감']]
            shop_disp.columns = ['사업장', '쇼핑몰', '매출(기준)', '매출(비교)', '매출증감', '증감율(%)', '출고(기준)', '출고(비교)', '출고증감']
            st.dataframe(shop_disp.style.format({
                '매출(기준)': '{:,.0f}원', '매출(비교)': '{:,.0f}원', '매출증감': '{:+,.0f}원', '증감율(%)': '{:+.1f}%',
                '출고(기준)': '{:,.0f}개', '출고(비교)': '{:,.0f}개', '출고증감': '{:+,.0f}개'
            }), use_container_width=True, hide_index=True)

        # ========== 상품별 비교 ==========
        st.markdown("---")
        st.markdown("### 📦 상품별 비교")

        # 기준 기간 상품 분석
        base_prod = base_normal.groupby(['사업장', 'SKU코드', 'SKU상품명']).agg({
            '금액': 'sum',
            '주문수량': 'sum'
        }).reset_index()
        base_prod.columns = ['사업장', 'SKU코드', '상품명', '매출_기준', '출고_기준']

        # 비교 기간 상품 분석
        if comp_rev is not None and len(comp_rev) > 0:
            comp_prod = comp_normal.groupby(['사업장', 'SKU코드', 'SKU상품명']).agg({
                '금액': 'sum',
                '주문수량': 'sum'
            }).reset_index()
            comp_prod.columns = ['사업장', 'SKU코드', '상품명', '매출_비교', '출고_비교']
        else:
            comp_prod = pd.DataFrame(columns=['사업장', 'SKU코드', '상품명', '매출_비교', '출고_비교'])

        prod_merged = base_prod.merge(comp_prod, on=['사업장', 'SKU코드', '상품명'], how='outer').fillna(0)
        prod_merged['매출증감'] = prod_merged['매출_기준'] - prod_merged['매출_비교']
        prod_merged['매출증감율'] = ((prod_merged['매출증감'] / prod_merged['매출_비교']) * 100).replace([float('inf'), -float('inf')], 0).fillna(0).round(1)
        prod_merged['출고증감'] = prod_merged['출고_기준'] - prod_merged['출고_비교']

        # 성장/하락 상품 분류 (일정 매출 이상만)
        min_revenue = prod_merged['매출_기준'].quantile(0.3)  # 상위 70% 이상 매출 상품만
        significant_prods = prod_merged[prod_merged['매출_기준'] >= min_revenue]

        growing_prods = significant_prods[significant_prods['매출증감율'] > 30].sort_values('매출증감', ascending=False).head(5)
        declining_prods = significant_prods[significant_prods['매출증감율'] < -30].sort_values('매출증감').head(5)
        new_prods = prod_merged[(prod_merged['매출_비교'] == 0) & (prod_merged['매출_기준'] > 0)].sort_values('매출_기준', ascending=False).head(5)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🚀 성장 상품 TOP 5")
            if len(growing_prods) > 0:
                for _, row in growing_prods.iterrows():
                    prod_name = row['상품명'][:25] + "..." if len(row['상품명']) > 25 else row['상품명']
                    st.markdown(f"- **{row['사업장']}** {prod_name}: +{row['매출증감율']:.0f}%")
                render_insight("주력 상품 육성", "성장 상품을 메인으로 프로모션하고 재고를 충분히 확보하세요.", "info")
            else:
                st.info("30% 이상 성장한 상품이 없습니다.")

        with col2:
            st.markdown("#### 📉 하락 상품 TOP 5")
            if len(declining_prods) > 0:
                for _, row in declining_prods.iterrows():
                    prod_name = row['상품명'][:25] + "..." if len(row['상품명']) > 25 else row['상품명']
                    st.markdown(f"- **{row['사업장']}** {prod_name}: {row['매출증감율']:.0f}%")
                render_insight("하락 상품 대응", "가격 경쟁력, 상품 품질, 시즌성 여부를 확인하세요. 지속 하락시 상품 리뉴얼이나 대체 상품을 검토하세요.", "warning")
            else:
                st.info("30% 이상 하락한 상품이 없습니다.")

        # 신규 상품
        if len(new_prods) > 0:
            st.markdown("#### 🆕 신규 상품 (기준 기간 신규 판매)")
            for _, row in new_prods.iterrows():
                prod_name = row['상품명'][:30] + "..." if len(row['상품명']) > 30 else row['상품명']
                st.markdown(f"- **{row['사업장']}** {prod_name}: {row['매출_기준']:,.0f}원")

        # 상품별 상세 테이블
        with st.expander("📋 상품별 상세 데이터 (매출 TOP 30)", expanded=False):
            prod_disp = prod_merged.sort_values('매출_기준', ascending=False).head(30)
            prod_disp = prod_disp[['사업장', '상품명', '매출_기준', '매출_비교', '매출증감', '매출증감율', '출고_기준', '출고_비교', '출고증감']]
            prod_disp.columns = ['사업장', '상품명', '매출(기준)', '매출(비교)', '매출증감', '증감율(%)', '출고(기준)', '출고(비교)', '출고증감']
            st.dataframe(prod_disp.style.format({
                '매출(기준)': '{:,.0f}원', '매출(비교)': '{:,.0f}원', '매출증감': '{:+,.0f}원', '증감율(%)': '{:+.1f}%',
                '출고(기준)': '{:,.0f}개', '출고(비교)': '{:,.0f}개', '출고증감': '{:+,.0f}개'
            }), use_container_width=True, hide_index=True)

        # ========== MD 전략 제안 ==========
        st.markdown("---")
        st.markdown("### 🎯 MD 전략 제안")

        md_insights = []

        # 주력 채널 분석
        top_shops = shop_merged.sort_values('매출_기준', ascending=False).head(3)
        if len(top_shops) > 0:
            top_shop_names = [f"{r['사업장']}-{r['쇼핑몰명']}" for _, r in top_shops.iterrows()]
            md_insights.append(f"**주력 채널**: {', '.join(top_shop_names)} — 이 채널들의 매출 비중이 높습니다. 안정적 운영과 함께 프로모션을 집중하세요.")

        # 성장 기회 채널
        if len(growing_shops) > 0:
            growth_names = [f"{r['사업장']}-{r['쇼핑몰명']}" for _, r in growing_shops.head(2).iterrows()]
            md_insights.append(f"**성장 기회**: {', '.join(growth_names)} — 급성장 중인 채널입니다. 상품 라인업 확대와 마케팅 강화를 검토하세요.")

        # 보완 필요 채널
        if len(declining_shops) > 0:
            decline_names = [f"{r['사업장']}-{r['쇼핑몰명']}" for _, r in declining_shops.head(2).iterrows()]
            md_insights.append(f"**보완 필요**: {', '.join(decline_names)} — 매출 하락 중입니다. 가격, 노출, 경쟁사 현황을 점검하세요.")

        # 주력 상품
        top_prods = prod_merged.sort_values('매출_기준', ascending=False).head(3)
        if len(top_prods) > 0:
            top_prod_names = [r['상품명'][:15] for _, r in top_prods.iterrows()]
            md_insights.append(f"**베스트셀러**: {', '.join(top_prod_names)} — 재고 확보와 품질 관리에 집중하세요.")

        # 성장 상품
        if len(growing_prods) > 0:
            growth_prod_names = [r['상품명'][:15] for _, r in growing_prods.head(2).iterrows()]
            md_insights.append(f"**성장 상품**: {', '.join(growth_prod_names)} — 다른 채널로의 확장을 검토하세요.")

        for insight in md_insights:
            st.markdown(f"- {insight}")

        # 다운로드
        st.markdown("---")
        if len(biz_merged) > 0:
            st.download_button(
                "📥 기간비교 데이터 다운로드",
                data=to_excel(shop_merged),
                file_name=f"기간비교_{base_start}_{base_end}_vs_{comp_start}_{comp_end}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


def render_promotion_planner(analyzer: OrderAnalyzer):
    """프로모션 플래너"""
    st.title("📋 프로모션 플래너")
    st.markdown("이벤트 선택부터 할인율, 마진 계산, 예상 매출까지 한 번에 기획하세요.")

    # 세션 상태 초기화
    if 'promo_events' not in st.session_state:
        st.session_state.promo_events = []

    # 이벤트 캘린더 데이터
    events_calendar = {
        '1월': [
            {'name': '신정', 'date': '1/1', 'type': '공휴일', 'priority': '보통'},
            {'name': '설날', 'date': '1월말~2월초', 'type': '명절', 'priority': '★필수★'},
        ],
        '2월': [
            {'name': '발렌타인데이', 'date': '2/14', 'type': '기념일', 'priority': '보통'},
            {'name': '육고기데이', 'date': '2/9', 'type': '민간기념일', 'priority': '추천'},
        ],
        '3월': [
            {'name': '삼삼데이', 'date': '3/3', 'type': '민간기념일', 'priority': '추천'},
            {'name': '화이트데이', 'date': '3/14', 'type': '기념일', 'priority': '보통'},
            {'name': '한우데이', 'date': '3/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '4월': [
            {'name': '블랙데이', 'date': '4/14', 'type': '기념일', 'priority': '보통'},
            {'name': '한우데이', 'date': '4/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '5월': [
            {'name': '어린이날', 'date': '5/5', 'type': '공휴일', 'priority': '추천'},
            {'name': '어버이날', 'date': '5/8', 'type': '기념일', 'priority': '추천'},
            {'name': '스승의날', 'date': '5/15', 'type': '기념일', 'priority': '보통'},
            {'name': '한우데이', 'date': '5/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '6월': [
            {'name': '현충일', 'date': '6/6', 'type': '공휴일', 'priority': '보통'},
            {'name': '육고기데이', 'date': '6/9', 'type': '민간기념일', 'priority': '추천'},
            {'name': '한우데이', 'date': '6/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '7월': [
            {'name': '초복', 'date': '7월중순', 'type': '절기', 'priority': '★필수★'},
            {'name': '중복', 'date': '7월말', 'type': '절기', 'priority': '★필수★'},
            {'name': '한우데이', 'date': '7/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '8월': [
            {'name': '말복', 'date': '8월초', 'type': '절기', 'priority': '★필수★'},
            {'name': '광복절', 'date': '8/15', 'type': '공휴일', 'priority': '보통'},
            {'name': '한우데이', 'date': '8/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '9월': [
            {'name': '추석', 'date': '9월중순', 'type': '명절', 'priority': '★필수★'},
            {'name': '한우데이', 'date': '9/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
            {'name': '구구데이', 'date': '9/9', 'type': '민간기념일', 'priority': '추천'},
        ],
        '10월': [
            {'name': '한글날', 'date': '10/9', 'type': '공휴일', 'priority': '보통'},
            {'name': '빼빼로데이', 'date': '10/11', 'type': '기념일', 'priority': '보통'},
            {'name': '한우데이', 'date': '10/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '11월': [
            {'name': '빼빼로데이', 'date': '11/11', 'type': '기념일', 'priority': '보통'},
            {'name': '블랙프라이데이', 'date': '11월말', 'type': '세일', 'priority': '추천'},
            {'name': '한우데이', 'date': '11/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
        '12월': [
            {'name': '크리스마스', 'date': '12/25', 'type': '공휴일', 'priority': '추천'},
            {'name': '연말/송년', 'date': '12월말', 'type': '시즌', 'priority': '추천'},
            {'name': '한우데이', 'date': '12/9,19,29', 'type': '민간기념일', 'priority': '★필수★'},
        ],
    }

    # ===== 1. 이벤트 선택 =====
    st.markdown("### 📅 1. 이벤트 선택")

    col1, col2 = st.columns([1, 2])
    with col1:
        selected_month = st.selectbox("월 선택", list(events_calendar.keys()), key="promo_month")

    with col2:
        month_events = events_calendar.get(selected_month, [])
        event_options = [f"{e['name']} ({e['date']}) - {e['priority']}" for e in month_events]
        event_options.append("직접 입력")
        selected_event = st.selectbox("이벤트 선택", event_options, key="promo_event")

    if selected_event == "직접 입력":
        custom_event = st.text_input("이벤트명 입력", key="custom_event")
        custom_date = st.text_input("날짜 입력 (예: 3/15)", key="custom_date")
        event_name = custom_event
        event_date = custom_date
    else:
        idx = event_options.index(selected_event)
        if idx < len(month_events):
            event_name = month_events[idx]['name']
            event_date = month_events[idx]['date']
        else:
            event_name = ""
            event_date = ""

    # ===== 2. 상품 및 할인 설정 =====
    st.markdown("### 💰 2. 상품 및 할인 설정")

    col1, col2, col3 = st.columns(3)
    with col1:
        product_name = st.text_input("상품명", value="", key="promo_product")
        original_price = st.number_input("정상가 (원)", min_value=0, step=1000, value=50000, key="promo_price")

    with col2:
        discount_rate = st.slider("할인율 (%)", min_value=0, max_value=50, value=10, key="promo_discount")
        sale_price = int(original_price * (1 - discount_rate / 100))
        st.metric("판매가", f"{sale_price:,}원", f"-{discount_rate}%")

    with col3:
        cost_price = st.number_input("원가 (원)", min_value=0, step=1000, value=30000, key="promo_cost")
        margin = sale_price - cost_price
        margin_rate = (margin / sale_price * 100) if sale_price > 0 else 0
        color = "#2ecc71" if margin_rate >= 20 else ("#f39c12" if margin_rate >= 10 else "#e74c3c")
        st.markdown(f"""
        <div style="background:#f8f9fa; padding:10px; border-radius:8px; text-align:center;">
            <div style="font-size:12px; color:#888;">마진</div>
            <div style="font-size:20px; font-weight:bold; color:{color};">{margin:,}원 ({margin_rate:.1f}%)</div>
        </div>
        """, unsafe_allow_html=True)

    # ===== 3. 예상 매출 시뮬레이션 =====
    st.markdown("### 📊 3. 예상 매출 시뮬레이션")

    col1, col2, col3 = st.columns(3)
    with col1:
        expected_qty = st.number_input("예상 판매수량", min_value=0, step=10, value=100, key="promo_qty")
    with col2:
        expected_revenue = sale_price * expected_qty
        st.metric("예상 매출", f"{expected_revenue:,}원")
    with col3:
        expected_profit = margin * expected_qty
        st.metric("예상 순이익", f"{expected_profit:,}원")

    # 할인율별 시뮬레이션
    st.markdown("#### 📈 할인율별 예상 수익 비교")
    sim_data = []
    for dr in [0, 5, 10, 15, 20, 25, 30]:
        sp = int(original_price * (1 - dr / 100))
        mg = sp - cost_price
        mr = (mg / sp * 100) if sp > 0 else 0
        # 할인율이 높을수록 판매량 증가 가정 (10% 할인당 20% 판매량 증가)
        qty_multiplier = 1 + (dr / 10 * 0.2)
        est_qty = int(expected_qty * qty_multiplier)
        est_rev = sp * est_qty
        est_profit = mg * est_qty
        sim_data.append({
            '할인율': f'{dr}%',
            '판매가': sp,
            '마진': mg,
            '마진율': f'{mr:.1f}%',
            '예상판매량': est_qty,
            '예상매출': est_rev,
            '예상순이익': est_profit
        })

    sim_df = pd.DataFrame(sim_data)
    st.dataframe(sim_df.style.format({
        '판매가': '{:,}원', '마진': '{:,}원', '예상판매량': '{:,}개',
        '예상매출': '{:,}원', '예상순이익': '{:,}원'
    }), use_container_width=True, hide_index=True)

    # 최적 할인율 추천
    optimal = sim_df.loc[sim_df['예상순이익'].idxmax()]
    st.success(f"💡 **추천 할인율**: {optimal['할인율']} (예상 순이익 {optimal['예상순이익']:,}원)")

    # ===== 4. 프로모션 저장 =====
    st.markdown("### 💾 4. 프로모션 저장")

    if st.button("📌 이 프로모션 저장", key="save_promo"):
        promo = {
            'event_name': event_name,
            'event_date': event_date,
            'product_name': product_name,
            'original_price': original_price,
            'discount_rate': discount_rate,
            'sale_price': sale_price,
            'cost_price': cost_price,
            'margin': margin,
            'margin_rate': margin_rate,
            'expected_qty': expected_qty,
            'expected_revenue': expected_revenue,
            'expected_profit': expected_profit
        }
        st.session_state.promo_events.append(promo)
        st.success(f"'{event_name} - {product_name}' 프로모션이 저장되었습니다!")

    # 저장된 프로모션 목록
    if st.session_state.promo_events:
        st.markdown("#### 📋 저장된 프로모션")
        for i, promo in enumerate(st.session_state.promo_events):
            with st.expander(f"🎯 {promo['event_name']} - {promo['product_name']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**이벤트**: {promo['event_name']} ({promo['event_date']})")
                    st.write(f"**상품**: {promo['product_name']}")
                with col2:
                    st.write(f"**정상가**: {promo['original_price']:,}원")
                    st.write(f"**할인율**: {promo['discount_rate']}%")
                    st.write(f"**판매가**: {promo['sale_price']:,}원")
                with col3:
                    st.write(f"**마진**: {promo['margin']:,}원 ({promo['margin_rate']:.1f}%)")
                    st.write(f"**예상매출**: {promo['expected_revenue']:,}원")
                    st.write(f"**예상순이익**: {promo['expected_profit']:,}원")

                if st.button(f"🗑️ 삭제", key=f"del_promo_{i}"):
                    st.session_state.promo_events.pop(i)
                    st.rerun()


def render_preparation_checklist(analyzer: OrderAnalyzer):
    """준비 체크리스트"""
    st.title("✅ 준비 체크리스트")
    st.markdown("프로모션 D-Day까지 단계별 준비 사항을 체크하세요.")

    # 세션 상태 초기화
    if 'checklist_items' not in st.session_state:
        st.session_state.checklist_items = {}

    # 이벤트 유형별 체크리스트 템플릿
    checklist_templates = {
        '명절 (설날/추석)': {
            'D-30': [
                '명절 선물세트 구성 확정',
                '포장재/박스 디자인 확정',
                '예상 판매량 기반 원육 발주',
                '명절 특가 상품 선정',
            ],
            'D-14': [
                '상품 페이지 업데이트 (명절 테마)',
                '할인율 및 판매가 최종 확정',
                '광고 소재 제작 완료',
                '재고 입고 확인',
                '택배사 물량 사전 협의',
                '카카오 선물하기 입점 확인',
            ],
            'D-7': [
                '광고 집행 시작 (검색광고, SNS)',
                '스마트스토어/쿠팡 프로모션 등록',
                '포장 인력 확보',
                '고객 CS 응대 매뉴얼 준비',
                '배송 마감일 공지 준비',
            ],
            'D-3': [
                '최종 재고 점검',
                '포장 라인 가동 준비',
                '배송 마감일 D-2 공지',
                '광고 예산 추가 투입 검토',
            ],
            'D-Day': [
                '실시간 주문 모니터링',
                '재고 소진 상품 품절 처리',
                '긴급 CS 대응',
                '당일 출고 마감 관리',
            ],
            'D+1': [
                '미출고 주문 확인 및 출고',
                '반품/교환 처리 준비',
                '프로모션 성과 중간 점검',
            ],
        },
        '복날 (초복/중복/말복)': {
            'D-14': [
                '복날 특가 상품 선정 (소고기, 보양식)',
                '복날 기획전 페이지 준비',
                '예상 판매량 기반 재고 확보',
            ],
            'D-7': [
                '복날 프로모션 등록 (각 채널)',
                '광고 소재 제작 및 집행',
                'SNS 복날 이벤트 공지',
                '배송 스케줄 확정',
            ],
            'D-3': [
                '최종 재고 점검',
                '포장/출고 인력 확보',
                '당일 배송 가능 지역 확인',
            ],
            'D-Day': [
                '실시간 주문 대응',
                '당일 출고 마감 관리',
                '품절 상품 즉시 처리',
            ],
        },
        '일반 프로모션': {
            'D-7': [
                '할인 상품 및 할인율 확정',
                '상품 페이지 업데이트',
                '광고 소재 제작',
                '재고 확인',
            ],
            'D-3': [
                '프로모션 등록 (각 채널)',
                '광고 집행 시작',
                'SNS 홍보',
            ],
            'D-Day': [
                '실시간 매출 모니터링',
                '재고 관리',
                'CS 대응',
            ],
        },
        '한우데이 (9,19,29일)': {
            'D-7': [
                '한우데이 특가 상품 선정',
                '한우 인증 마크 확인',
                '상품 페이지 한우데이 배너 추가',
                '예상 판매량 기반 재고 확보',
            ],
            'D-3': [
                '프로모션 등록 (스마트스토어, 쿠팡 등)',
                '광고 소재 제작 및 집행',
                '한우데이 해시태그 이벤트 준비',
            ],
            'D-Day': [
                '한우데이 프로모션 활성화',
                '실시간 매출 모니터링',
                '재고 소진시 품절 처리',
                '다음 한우데이 (10일 후) 사전 예고',
            ],
        },
    }

    # 이벤트 유형 선택
    col1, col2 = st.columns([1, 2])
    with col1:
        event_type = st.selectbox("이벤트 유형", list(checklist_templates.keys()), key="checklist_type")
    with col2:
        event_name = st.text_input("이벤트명 (메모용)", value="", placeholder="예: 2024 설날 프로모션", key="checklist_name")

    # 체크리스트 표시
    template = checklist_templates[event_type]
    checklist_key = f"{event_type}_{event_name}"

    if checklist_key not in st.session_state.checklist_items:
        st.session_state.checklist_items[checklist_key] = {day: {item: False for item in items} for day, items in template.items()}

    st.markdown("---")

    # D-Day 기준 색상
    day_colors = {
        'D-30': '#9b59b6',
        'D-14': '#3498db',
        'D-7': '#2ecc71',
        'D-3': '#f39c12',
        'D-Day': '#e74c3c',
        'D+1': '#95a5a6',
    }

    # 진행률 계산
    total_items = sum(len(items) for items in template.values())
    checked_items = sum(
        sum(1 for checked in st.session_state.checklist_items[checklist_key][day].values() if checked)
        for day in template.keys()
    )
    progress = checked_items / total_items if total_items > 0 else 0

    st.markdown(f"### 📊 전체 진행률: {progress * 100:.0f}%")
    st.progress(progress)

    # 단계별 체크리스트
    for day, items in template.items():
        color = day_colors.get(day, '#888')
        day_checked = sum(1 for item in items if st.session_state.checklist_items[checklist_key][day].get(item, False))
        day_total = len(items)
        day_progress = day_checked / day_total if day_total > 0 else 0

        with st.expander(f"📌 {day} ({day_checked}/{day_total} 완료)", expanded=(day_progress < 1)):
            st.markdown(f"""
            <div style="height:4px; background:{color}; border-radius:2px; margin-bottom:10px;"></div>
            """, unsafe_allow_html=True)

            for item in items:
                checked = st.checkbox(
                    item,
                    value=st.session_state.checklist_items[checklist_key][day].get(item, False),
                    key=f"check_{checklist_key}_{day}_{item}"
                )
                st.session_state.checklist_items[checklist_key][day][item] = checked

    # 추가 체크리스트 항목
    st.markdown("---")
    st.markdown("### ➕ 항목 추가")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        add_day = st.selectbox("단계", list(template.keys()), key="add_day")
    with col2:
        new_item = st.text_input("새 항목", placeholder="추가할 체크리스트 항목", key="new_item")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ 추가", key="add_item"):
            if new_item:
                if add_day not in st.session_state.checklist_items[checklist_key]:
                    st.session_state.checklist_items[checklist_key][add_day] = {}
                st.session_state.checklist_items[checklist_key][add_day][new_item] = False
                st.success(f"'{new_item}' 항목이 {add_day}에 추가되었습니다.")
                st.rerun()

    # 리셋 버튼
    st.markdown("---")
    if st.button("🔄 체크리스트 초기화", key="reset_checklist"):
        st.session_state.checklist_items[checklist_key] = {day: {item: False for item in items} for day, items in template.items()}
        st.success("체크리스트가 초기화되었습니다.")
        st.rerun()


def render_competitor_analysis(analyzer: OrderAnalyzer):
    """경쟁사 분석"""
    st.title("🔍 경쟁사 분석")
    st.markdown("경쟁사 가격과 프로모션을 모니터링하고 전략을 수립하세요.")

    # 세션 상태 초기화
    if 'competitors' not in st.session_state:
        st.session_state.competitors = []
    if 'competitor_products' not in st.session_state:
        st.session_state.competitor_products = []

    # ===== 1. 경쟁사 등록 =====
    st.markdown("### 🏢 1. 경쟁사 등록")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_competitor = st.text_input("경쟁사명", placeholder="예: ○○축산, △△정육", key="new_competitor")
    with col2:
        competitor_channels = st.multiselect(
            "주요 판매 채널",
            ['스마트스토어', '쿠팡', 'G마켓', '11번가', '카카오', '위메프', '티몬', '자사몰', '기타'],
            key="competitor_channels"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ 등록", key="add_competitor"):
            if new_competitor:
                st.session_state.competitors.append({
                    'name': new_competitor,
                    'channels': competitor_channels
                })
                st.success(f"'{new_competitor}' 경쟁사가 등록되었습니다.")
                st.rerun()

    # 등록된 경쟁사 목록
    if st.session_state.competitors:
        st.markdown("#### 📋 등록된 경쟁사")
        for i, comp in enumerate(st.session_state.competitors):
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                st.write(f"**{comp['name']}**")
            with col2:
                st.write(", ".join(comp['channels']) if comp['channels'] else "채널 미등록")
            with col3:
                if st.button("🗑️", key=f"del_comp_{i}"):
                    st.session_state.competitors.pop(i)
                    st.rerun()

    st.markdown("---")

    # ===== 2. 상품별 가격 비교 =====
    st.markdown("### 💵 2. 상품별 가격 비교")

    if not st.session_state.competitors:
        st.info("먼저 경쟁사를 등록해주세요.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            product_name = st.text_input("상품명", placeholder="예: 한우 등심 1++", key="price_product")
        with col2:
            my_price = st.number_input("우리 가격 (원)", min_value=0, step=1000, value=0, key="my_price")
        with col3:
            competitor_select = st.selectbox(
                "경쟁사",
                [c['name'] for c in st.session_state.competitors],
                key="price_competitor"
            )
        with col4:
            competitor_price = st.number_input("경쟁사 가격 (원)", min_value=0, step=1000, value=0, key="competitor_price")

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("📊 가격 추가", key="add_price"):
                if product_name and my_price > 0 and competitor_price > 0:
                    st.session_state.competitor_products.append({
                        'product': product_name,
                        'my_price': my_price,
                        'competitor': competitor_select,
                        'competitor_price': competitor_price,
                        'diff': my_price - competitor_price,
                        'diff_rate': ((my_price - competitor_price) / competitor_price * 100) if competitor_price > 0 else 0,
                        'date': now_kst().strftime('%Y-%m-%d')
                    })
                    st.success("가격 정보가 추가되었습니다.")
                    st.rerun()

        # 가격 비교 테이블
        if st.session_state.competitor_products:
            st.markdown("#### 📈 가격 비교 현황")

            price_df = pd.DataFrame(st.session_state.competitor_products)

            # 가격 경쟁력 색상
            def price_color(row):
                if row['diff'] < 0:
                    return '🟢 저렴'  # 우리가 저렴
                elif row['diff'] == 0:
                    return '🟡 동일'
                else:
                    return '🔴 비쌈'  # 우리가 비쌈

            price_df['경쟁력'] = price_df.apply(price_color, axis=1)

            st.dataframe(
                price_df[['date', 'product', 'my_price', 'competitor', 'competitor_price', 'diff', 'diff_rate', '경쟁력']].rename(columns={
                    'date': '조사일',
                    'product': '상품명',
                    'my_price': '우리가격',
                    'competitor': '경쟁사',
                    'competitor_price': '경쟁사가격',
                    'diff': '가격차이',
                    'diff_rate': '차이율(%)'
                }).style.format({
                    '우리가격': '{:,}원',
                    '경쟁사가격': '{:,}원',
                    '가격차이': '{:+,}원',
                    '차이율(%)': '{:+.1f}%'
                }),
                use_container_width=True,
                hide_index=True
            )

            # 요약 분석
            st.markdown("#### 💡 가격 경쟁력 분석")
            cheaper = len(price_df[price_df['diff'] < 0])
            same = len(price_df[price_df['diff'] == 0])
            expensive = len(price_df[price_df['diff'] > 0])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🟢 우리가 저렴", f"{cheaper}개 상품")
            with col2:
                st.metric("🟡 가격 동일", f"{same}개 상품")
            with col3:
                st.metric("🔴 우리가 비쌈", f"{expensive}개 상품")

            if expensive > 0:
                expensive_products = price_df[price_df['diff'] > 0].sort_values('diff', ascending=False)
                st.warning(f"⚠️ 가격 경쟁력 보완 필요: {', '.join(expensive_products['product'].head(3).tolist())}")

                render_insight(
                    "가격 대응 전략",
                    "1) 가격 인하가 어려우면 구성 변경(증량, 사은품)으로 가치 제안\n"
                    "2) 프리미엄 포지셔닝 강화 (품질, 원산지, 등급 강조)\n"
                    "3) 묶음 할인으로 객단가 유지하면서 경쟁력 확보",
                    "warning"
                )

    st.markdown("---")

    # ===== 3. 경쟁사 프로모션 모니터링 =====
    st.markdown("### 📢 3. 경쟁사 프로모션 모니터링")

    if 'competitor_promos' not in st.session_state:
        st.session_state.competitor_promos = []

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        promo_competitor = st.selectbox(
            "경쟁사",
            [c['name'] for c in st.session_state.competitors] if st.session_state.competitors else ['(경쟁사 먼저 등록)'],
            key="promo_competitor"
        )
    with col2:
        promo_type = st.selectbox("프로모션 유형", ['할인', '쿠폰', '적립금', '증정', '무료배송', '기타'], key="promo_type")
    with col3:
        promo_detail = st.text_input("프로모션 내용", placeholder="예: 전품목 20% 할인", key="promo_detail")
    with col4:
        promo_channel = st.selectbox("채널", ['스마트스토어', '쿠팡', 'G마켓', '11번가', '카카오', '기타'], key="promo_channel")

    if st.button("📌 프로모션 기록", key="add_promo_record"):
        if promo_competitor and promo_detail:
            st.session_state.competitor_promos.append({
                'date': now_kst().strftime('%Y-%m-%d'),
                'competitor': promo_competitor,
                'type': promo_type,
                'detail': promo_detail,
                'channel': promo_channel
            })
            st.success("경쟁사 프로모션이 기록되었습니다.")
            st.rerun()

    if st.session_state.competitor_promos:
        st.markdown("#### 📋 경쟁사 프로모션 기록")
        promo_df = pd.DataFrame(st.session_state.competitor_promos)
        promo_df = promo_df.sort_values('date', ascending=False)
        promo_df.columns = ['날짜', '경쟁사', '유형', '내용', '채널']
        st.dataframe(promo_df, use_container_width=True, hide_index=True)

        # 프로모션 유형 분석
        st.markdown("#### 📊 경쟁사 프로모션 패턴")
        type_counts = pd.DataFrame(st.session_state.competitor_promos)['type'].value_counts()
        fig = px.pie(values=type_counts.values, names=type_counts.index, title="프로모션 유형 분포")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ===== 4. 대응 전략 제안 =====
    st.markdown("### 🎯 4. 대응 전략 제안")

    if st.session_state.competitor_products or st.session_state.competitor_promos:
        strategies = []

        # 가격 기반 전략
        if st.session_state.competitor_products:
            price_df = pd.DataFrame(st.session_state.competitor_products)
            avg_diff_rate = price_df['diff_rate'].mean()

            if avg_diff_rate > 10:
                strategies.append({
                    'title': '가격 경쟁력 강화 필요',
                    'detail': '평균적으로 경쟁사 대비 10% 이상 비쌉니다. 원가 절감, 마진 조정, 또는 가치 제안 강화가 필요합니다.',
                    'type': 'warning'
                })
            elif avg_diff_rate < -10:
                strategies.append({
                    'title': '가격 경쟁력 우위',
                    'detail': '가격 경쟁력이 있습니다. 이를 마케팅 포인트로 적극 활용하세요. "최저가 보장" 등의 문구 활용을 권장합니다.',
                    'type': 'info'
                })

        # 프로모션 기반 전략
        if st.session_state.competitor_promos:
            promo_df = pd.DataFrame(st.session_state.competitor_promos)
            recent_promos = promo_df[promo_df['date'] >= (now_kst() - timedelta(days=7)).strftime('%Y-%m-%d')]

            if len(recent_promos) > 3:
                strategies.append({
                    'title': '경쟁 심화 대응',
                    'detail': f'최근 7일간 {len(recent_promos)}건의 경쟁사 프로모션이 감지되었습니다. 차별화된 프로모션 또는 고객 충성도 강화 전략이 필요합니다.',
                    'type': 'warning'
                })

            # 할인 프로모션이 많으면
            discount_count = len(promo_df[promo_df['type'] == '할인'])
            if discount_count > len(promo_df) * 0.5:
                strategies.append({
                    'title': '가격 경쟁 회피 전략',
                    'detail': '경쟁사들이 가격 할인 위주로 프로모션하고 있습니다. 가격 경쟁 대신 품질/서비스 차별화(빠른배송, 친절CS, 품질보증)로 포지셔닝하세요.',
                    'type': 'info'
                })

        if strategies:
            for strategy in strategies:
                render_insight(strategy['title'], strategy['detail'], strategy['type'])
        else:
            st.info("더 많은 경쟁사 데이터를 수집하면 전략 제안이 가능합니다.")
    else:
        st.info("경쟁사 가격 또는 프로모션 데이터를 입력하면 대응 전략을 제안해드립니다.")


if __name__ == "__main__":
    main()
