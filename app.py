# -*- coding: utf-8 -*-
"""
플레이오토 판매 데이터 분석기
- 매출/출고/취소 통합 분석 + AI 코멘트
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from io import BytesIO

from analyzers import OrderAnalyzer


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


def get_analyzer() -> OrderAnalyzer:
    if 'analyzer' not in st.session_state:
        # GitHub 저장소 설정 확인
        github_token = None
        github_repo = None

        try:
            if hasattr(st, 'secrets'):
                github_token = st.secrets.get("GITHUB_TOKEN", None)
                github_repo = st.secrets.get("GITHUB_REPO", None)
        except Exception:
            pass

        st.session_state.analyzer = OrderAnalyzer(
            github_token=github_token,
            github_repo=github_repo
        )
    return st.session_state.analyzer


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

    # 축산물 계절별 추천 (하드코딩된 전문가 지식)
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
    current_month = datetime.now().month
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

    start_key = f"{key_prefix}_filter_start"
    end_key = f"{key_prefix}_filter_end"

    if start_key not in st.session_state:
        if default_mode == "당월":
            month_start = max_dt.replace(day=1)
            st.session_state[start_key] = max(min_dt, month_start)
        else:
            st.session_state[start_key] = min_dt
    if end_key not in st.session_state:
        st.session_state[end_key] = max_dt

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        start = st.date_input("시작일", value=st.session_state[start_key],
                              min_value=min_dt, max_value=max_dt, key=f"{key_prefix}_date_start")
        st.session_state[start_key] = start

    with col2:
        end = st.date_input("종료일", value=st.session_state[end_key],
                            min_value=min_dt, max_value=max_dt, key=f"{key_prefix}_date_end")
        st.session_state[end_key] = end

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
                st.session_state.analyzer = analyzer
                st.rerun()
        st.markdown("---")

    if st.button("🗑️ 전체 삭제", type="secondary"):
        analyzer.clear_all_data()
        st.session_state.analyzer = analyzer
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
    st.markdown("### 📅 요일별 패턴")
    st.markdown('<span class="date-basis">💰 매출/주문: 결제완료일 기준</span> <span class="date-basis">📦 출고: 출고완료일 기준</span>', unsafe_allow_html=True)

    # 사업장별 요일 패턴
    weekday_rev_biz, _ = analyze_weekday_pattern_revenue(revenue_df, by_business=True)
    weekday_ship_biz, _ = analyze_weekday_pattern_shipment(shipment_df, by_business=True)

    biz_tabs = st.tabs(["🥩 육구이", "🚀 우주인", "📊 전체"])

    for tab_idx, (tab, biz_name) in enumerate(zip(biz_tabs, ['육구이', '우주인', '전체'])):
        with tab:
            col1, col2 = st.columns(2)

            with col1:
                if biz_name == '전체':
                    weekday_rev, _ = analyze_weekday_pattern_revenue(revenue_df)
                    if weekday_rev is not None and len(weekday_rev) > 0:
                        fig = px.bar(weekday_rev, x='요일명', y='금액', text=weekday_rev['금액'].apply(lambda x: f'{x:,}'),
                                     color_discrete_sequence=['#3498db'])
                        fig.update_traces(textposition='outside')
                        fig.update_layout(height=280, title="💰 요일별 매출", xaxis_title="", yaxis_title="")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    if weekday_rev_biz is not None:
                        biz_data = weekday_rev_biz[weekday_rev_biz['사업장'] == biz_name]
                        if len(biz_data) > 0:
                            fig = px.bar(biz_data, x='요일명', y='금액', text=biz_data['금액'].apply(lambda x: f'{x:,}'),
                                         color_discrete_sequence=[BUSINESS_COLORS.get(biz_name, '#3498db')])
                            fig.update_traces(textposition='outside')
                            fig.update_layout(height=280, title=f"💰 {biz_name} 요일별 매출", xaxis_title="", yaxis_title="")
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info(f"{biz_name} 매출 데이터가 없습니다.")

            with col2:
                if biz_name == '전체':
                    weekday_ship, _ = analyze_weekday_pattern_shipment(shipment_df)
                    if weekday_ship is not None and len(weekday_ship) > 0:
                        fig = px.bar(weekday_ship, x='요일명', y='출고수량', text='출고수량',
                                     color_discrete_sequence=['#2ecc71'])
                        fig.update_traces(textposition='outside')
                        fig.update_layout(height=280, title="📦 요일별 출고", xaxis_title="", yaxis_title="")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("출고 데이터가 없습니다.")
                else:
                    if weekday_ship_biz is not None:
                        biz_ship_data = weekday_ship_biz[weekday_ship_biz['사업장'] == biz_name]
                        if len(biz_ship_data) > 0:
                            fig = px.bar(biz_ship_data, x='요일명', y='출고수량', text='출고수량',
                                         color_discrete_sequence=[BUSINESS_COLORS.get(biz_name, '#2ecc71')])
                            fig.update_traces(textposition='outside')
                            fig.update_layout(height=280, title=f"📦 {biz_name} 요일별 출고", xaxis_title="", yaxis_title="")
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info(f"{biz_name} 출고 데이터가 없습니다.")

            # 각 탭별 인사이트
            if biz_name == '전체':
                _, rev_insight = analyze_weekday_pattern_revenue(revenue_df)
                _, ship_insight = analyze_weekday_pattern_shipment(shipment_df)
                if rev_insight:
                    render_insight("전체 요일별 주문 패턴", rev_insight, "info")
                if ship_insight:
                    render_insight("전체 요일별 출고 패턴", ship_insight, "info")
            else:
                # 사업장별 인사이트 생성
                if weekday_rev_biz is not None:
                    biz_rev_data = weekday_rev_biz[weekday_rev_biz['사업장'] == biz_name]
                    if len(biz_rev_data) > 0:
                        best_rev_day = biz_rev_data.loc[biz_rev_data['금액'].idxmax()]
                        worst_rev_day = biz_rev_data.loc[biz_rev_data['금액'].idxmin()]
                        rev_insight = f"{biz_name} 주문이 가장 많은 요일은 {best_rev_day['요일명']}요일({best_rev_day['금액']:,}원)이고, 가장 적은 요일은 {worst_rev_day['요일명']}요일({worst_rev_day['금액']:,}원)입니다."
                        render_insight(f"{biz_name} 요일별 주문 패턴", rev_insight, "info")

                if weekday_ship_biz is not None:
                    biz_ship_data = weekday_ship_biz[weekday_ship_biz['사업장'] == biz_name]
                    if len(biz_ship_data) > 0:
                        best_ship_day = biz_ship_data.loc[biz_ship_data['출고수량'].idxmax()]
                        weekend_ship = biz_ship_data[biz_ship_data['요일'].isin([5, 6])]['출고수량'].sum()
                        if weekend_ship == 0:
                            ship_insight = f"{biz_name} 출고가 가장 많은 요일은 {best_ship_day['요일명']}요일({best_ship_day['출고수량']:,}개)입니다. 주말에는 출고가 없습니다."
                        else:
                            ship_insight = f"{biz_name} 출고가 가장 많은 요일은 {best_ship_day['요일명']}요일({best_ship_day['출고수량']:,}개)입니다."
                        render_insight(f"{biz_name} 요일별 출고 패턴", ship_insight, "info")

    # 시간대별 패턴
    st.markdown("---")
    st.markdown("### 🕐 시간대별 주문 패턴 (30분 단위)")
    st.markdown('<span class="date-basis">💰 결제완료일시 기준</span>', unsafe_allow_html=True)

    hourly_biz, _ = analyze_hourly_pattern(revenue_df, by_business=True)

    time_tabs = st.tabs(["🥩 육구이", "🚀 우주인", "📊 전체"])

    for tab_idx, (tab, biz_name) in enumerate(zip(time_tabs, ['육구이', '우주인', '전체'])):
        with tab:
            if biz_name == '전체':
                hourly_stats, hourly_top5 = analyze_hourly_pattern(revenue_df)
                if hourly_stats is not None and len(hourly_stats) > 0:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        fig = px.bar(hourly_stats, x='시간대', y='금액',
                                     text=hourly_stats['금액'].apply(lambda x: f'{x:,}' if x > 0 else ''),
                                     color_discrete_sequence=['#9b59b6'])
                        fig.update_traces(textposition='outside', textfont_size=8)
                        fig.update_layout(height=350, title="💰 시간대별 매출", xaxis_title="시간대", yaxis_title="매출(원)",
                                          xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)
                    with col2:
                        st.markdown("#### 🏆 피크 시간대 TOP 5")
                        if hourly_top5 is not None and len(hourly_top5) > 0:
                            for _, row in hourly_top5.iterrows():
                                st.markdown(f"""
                                <div style="background:#f8f9fa; padding:8px 12px; margin:5px 0; border-radius:6px; border-left:3px solid #9b59b6;">
                                    <b>{row['순위']}위</b> {row['시간대']} — <b>{row['금액']:,}원</b> ({row['주문건수']}건)
                                </div>
                                """, unsafe_allow_html=True)
                else:
                    st.info("시간대별 데이터가 없습니다.")
            else:
                if hourly_biz is not None:
                    biz_hourly = hourly_biz[hourly_biz['사업장'] == biz_name]
                    if len(biz_hourly) > 0:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            fig = px.bar(biz_hourly, x='시간대', y='금액',
                                         text=biz_hourly['금액'].apply(lambda x: f'{x:,}' if x > 0 else ''),
                                         color_discrete_sequence=[BUSINESS_COLORS.get(biz_name, '#9b59b6')])
                            fig.update_traces(textposition='outside', textfont_size=8)
                            fig.update_layout(height=350, title=f"💰 {biz_name} 시간대별 매출", xaxis_title="시간대", yaxis_title="매출(원)",
                                              xaxis_tickangle=-45)
                            st.plotly_chart(fig, use_container_width=True)
                        with col2:
                            st.markdown(f"#### 🏆 {biz_name} 피크 시간대 TOP 5")
                            top5 = biz_hourly.nlargest(5, '금액')[['시간대', '금액', '주문건수']].reset_index(drop=True)
                            top5['순위'] = range(1, len(top5) + 1)
                            biz_color = BUSINESS_COLORS.get(biz_name, '#9b59b6')
                            for _, row in top5.iterrows():
                                st.markdown(f"""
                                <div style="background:#f8f9fa; padding:8px 12px; margin:5px 0; border-radius:6px; border-left:3px solid {biz_color};">
                                    <b>{row['순위']}위</b> {row['시간대']} — <b>{row['금액']:,}원</b> ({row['주문건수']}건)
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info(f"{biz_name} 시간대별 데이터가 없습니다.")

    # 프로모션 추천
    st.markdown("---")
    st.markdown("### 🎯 프로모션 추천 (축산 MD 전문가 분석)")

    promo_tabs = st.tabs(["⏰ 시간대별 전략", "🗓️ 시즌별 전략"])

    with promo_tabs[0]:
        st.markdown('<span class="date-basis">💡 주문 패턴 기반 광고/프로모션 타이밍 추천</span>', unsafe_allow_html=True)

        # 전체 시간대별 추천
        hourly_all, _ = analyze_hourly_pattern(revenue_df)
        time_recommendations = generate_time_promotion_recommendations(hourly_all, "전체")

        if time_recommendations:
            for rec in time_recommendations:
                if rec['type'] == 'peak':
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #e8f5e9, #f1f8e9); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #4caf50;">
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
                    <div style="background:linear-gradient(135deg, #e3f2fd, #bbdefb); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #2196f3;">
                        <div style="font-weight:bold; color:#1565c0; font-size:16px;">⏱️ {rec['title']}</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>타이밍:</b> {rec['time']}<br>
                            <b>전략:</b> {rec['strategy']}<br>
                            <b>상세:</b> {rec['detail']}<br>
                            <b>추천 광고:</b> {rec['ad_type']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # 사업장별 차이점
            hourly_육구이, _ = analyze_hourly_pattern(analyzer.filter_by_business('육구이', revenue_df))
            hourly_우주인, _ = analyze_hourly_pattern(analyzer.filter_by_business('우주인', revenue_df))

            if hourly_육구이 is not None and len(hourly_육구이) > 0 and hourly_우주인 is not None and len(hourly_우주인) > 0:
                peak_육구이 = hourly_육구이.loc[hourly_육구이['금액'].idxmax()]['시간대']
                peak_우주인 = hourly_우주인.loc[hourly_우주인['금액'].idxmax()]['시간대']

                if peak_육구이 != peak_우주인:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg, #fce4ec, #f8bbd9); padding:15px; margin:10px 0; border-radius:10px; border-left:4px solid #e91e63;">
                        <div style="font-weight:bold; color:#c2185b; font-size:16px;">🔍 사업장별 피크 시간 차이</div>
                        <div style="color:#555; margin:8px 0;">
                            <b>육구이:</b> {peak_육구이} 피크 → 해당 시간에 육구이 상품 집중 노출<br>
                            <b>우주인:</b> {peak_우주인} 피크 → 해당 시간에 우주인 상품 집중 노출<br>
                            <b>전략:</b> 사업장별 타겟 고객층이 다르므로 광고 시간대를 분리 운영하세요.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("시간대별 데이터가 부족합니다. 더 많은 데이터를 업로드하면 추천이 생성됩니다.")

    with promo_tabs[1]:
        st.markdown('<span class="date-basis">💡 축산물 시즌별 마케팅 전략</span>', unsafe_allow_html=True)

        season_recommendations, monthly_data = generate_seasonal_recommendations(revenue_df)

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
                fig.update_layout(height=300, xaxis_title="", yaxis_title="매출(원)")
                st.plotly_chart(fig, use_container_width=True)

        # 축산 MD 연간 캘린더
        with st.expander("📅 축산 MD 연간 마케팅 캘린더", expanded=False):
            calendar_data = [
                {'월': '1월', '이벤트': '설날 선물세트', '주력상품': '한우 선물세트, 프리미엄 등심', '비고': '설 2주전부터 마케팅 집중'},
                {'월': '2월', '이벤트': '발렌타인데이, 졸업시즌', '주력상품': '스테이크, 파티용 세트', '비고': '소포장 프리미엄 상품'},
                {'월': '3월', '이벤트': '봄나들이 시즌', '주력상품': '캠핑용 양념육, 도시락 세트', '비고': '휴대 간편 상품 강화'},
                {'월': '4월', '이벤트': '벚꽃시즌, 피크닉', '주력상품': '바베큐 세트, 소풍용 밀키트', '비고': '야외용 패키지 기획'},
                {'월': '5월', '이벤트': '어린이날, 어버이날', '주력상품': '가족 파티 세트, 선물용', '비고': '가정의 달 선물 마케팅'},
                {'월': '6월', '이벤트': '초복 준비', '주력상품': '삼계탕용, 보양식', '비고': '복날 사전예약 시작'},
                {'월': '7월', '이벤트': '복날, 휴가철', '주력상품': '삼겹살, 캠핑용 대용량', '비고': '복날 특수, 캠핑 시즌'},
                {'월': '8월', '이벤트': '휴가철, 말복', '주력상품': 'BBQ 세트, 냉동 대용량', '비고': '여름 보양식 마케팅'},
                {'월': '9월', '이벤트': '추석', '주력상품': '한우 선물세트, 프리미엄 갈비', '비고': '추석 2주전 마케팅 집중'},
                {'월': '10월', '이벤트': '가을 캠핑', '주력상품': '캠핑용 구이 세트', '비고': '단풍철 캠핑 수요'},
                {'월': '11월', '이벤트': '김장철, 블프', '주력상품': '수육용, 블프 특가', '비고': '김장 보쌈 수요, 연말 준비'},
                {'월': '12월', '이벤트': '연말, 크리스마스', '주력상품': '파티용 스테이크, 로스트', '비고': '연말 홈파티 수요'}
            ]
            calendar_df = pd.DataFrame(calendar_data)
            st.dataframe(calendar_df, use_container_width=True, hide_index=True)

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
                fig.update_layout(height=300, showlegend=False, title="💰 매출")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(merged, x='쇼핑몰명', y='출고수량', text='출고수량',
                             color_discrete_sequence=[BUSINESS_COLORS[biz_name]])
                fig.update_traces(textposition='outside')
                fig.update_layout(height=300, showlegend=False, title="📦 출고수량")
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
        fig.update_layout(xaxis_tickangle=-45, height=400, showlegend=False, title="💰 매출 TOP 15")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(chart_df, x='상품명', y='출고수량', text='출고수량',
                     color='사업장', color_discrete_map=BUSINESS_COLORS)
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45, height=400, showlegend=False, title="📦 출고 TOP 15")
        st.plotly_chart(fig, use_container_width=True)

    # 취소 많은 상품
    if cancel_top is not None and len(cancel_top) > 0:
        st.markdown("#### 🔄 취소 많은 상품")
        fig = px.bar(cancel_top, x='상품명', y='취소건수', text='취소건수',
                     color='사업장', color_discrete_map=BUSINESS_COLORS)
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_tickangle=-45, height=300, showlegend=False)
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
                fig.update_layout(barmode='group', height=300, title="💰 매출 비교", showlegend=False)
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
                fig.update_layout(barmode='group', height=300, title="📦 출고 비교", showlegend=False)
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


if __name__ == "__main__":
    main()
