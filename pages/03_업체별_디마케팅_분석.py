import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="업체별 디마케팅 분석", layout="wide")
st.title("🏢 업체별 디마케팅 분석")

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# 현장명/업체명 컬럼 확인
client_col = None
if '현장명' in df.columns and df['현장명'].notna().any():
    client_col = '현장명'
elif '업체명' in df.columns and df['업체명'].notna().any():
    client_col = '업체명'
else:
    st.error("현장명 또는 업체명 컬럼이 없습니다.")
    st.stop()

# 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_client_data(df, client_col):
    # 업체명 정리
    df = df[df[client_col].notna()].copy()
    df['업체명'] = df[client_col].astype(str)
    
    # 수리비 처리
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    # 날짜 처리
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
    
    return df

df = prepare_client_data(df, client_col)

if df.empty:
    st.error("처리할 수 있는 데이터가 없습니다.")
    st.stop()

# 사이드바 설정
st.sidebar.header("🎯 분석 설정")

# 기간 필터
if '정비일자' in df.columns and df['정비일자'].notna().any():
    min_date = df['정비일자'].min().date()
    max_date = df['정비일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[(df['정비일자'].dt.date >= start_date) & 
                (df['정비일자'].dt.date <= end_date)]

# 최소 AS 건수 필터
min_cases = st.sidebar.slider("최소 AS 건수", 1, 20, 3)

# 업체별 통계 계산
client_stats = df.groupby('업체명').agg({
    '관리번호': 'count',
    '수리비': ['sum', 'mean'],
    '정비일자': ['min', 'max'] if '정비일자' in df.columns else lambda x: None
}).round(0)

if '정비일자' in df.columns:
    client_stats.columns = ['AS건수', '총수리비', '평균수리비', '첫수리일', '최근수리일']
else:
    client_stats.columns = ['AS건수', '총수리비', '평균수리비']

client_stats = client_stats.reset_index()
client_stats = client_stats[client_stats['AS건수'] >= min_cases]

if client_stats.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 위험도 점수 계산
@st.cache_data(show_spinner=False)
def calculate_risk_scores(client_stats):
    # 전체 평균 계산
    global_avg_cost = client_stats['평균수리비'].mean()
    global_avg_cases = client_stats['AS건수'].mean()
    
    # 정규화된 점수 계산
    client_stats['비용점수'] = client_stats['평균수리비'] / global_avg_cost
    client_stats['빈도점수'] = client_stats['AS건수'] / global_avg_cases
    
    # 종합 위험도 점수 (비용 70%, 빈도 30%)
    client_stats['위험도점수'] = (client_stats['비용점수'] * 0.7) + (client_stats['빈도점수'] * 0.3)
    
    return client_stats

client_stats = calculate_risk_scores(client_stats)

# 위험도 등급 분류
def get_risk_level(score):
    if score >= 2.5:
        return "🔴 HIGH", "매우 위험"
    elif score >= 1.8:
        return "🟠 MID-HIGH", "위험"
    elif score >= 1.3:
        return "🟡 MID", "주의"
    elif score >= 0.8:
        return "🟢 LOW", "양호"
    else:
        return "🔵 VERY LOW", "매우 양호"

client_stats['위험등급'], client_stats['위험설명'] = zip(*client_stats['위험도점수'].apply(get_risk_level))

# 전체 업체 현황
st.header("📊 전체 업체 현황")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 수리비 상위 업체 TOP 10")
    top_cost_clients = client_stats.nlargest(10, '총수리비')
    
    # 업체명 줄임
    top_cost_display = top_cost_clients.copy()
    top_cost_display['업체명_short'] = top_cost_display['업체명'].apply(
        lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
    )
    
    fig = px.bar(
        top_cost_display,
        x='총수리비',
        y='업체명_short',
        orientation='h',
        color='총수리비',
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📈 AS 건수 상위 업체 TOP 10")
    top_case_clients = client_stats.nlargest(10, 'AS건수')
    
    top_case_display = top_case_clients.copy()
    top_case_display['업체명_short'] = top_case_display['업체명'].apply(
        lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
    )
    
    fig2 = px.bar(
        top_case_display,
        x='AS건수',
        y='업체명_short',
        orientation='h',
        color='AS건수',
        color_continuous_scale='Blues'
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 위험도 분석
st.header("🚨 디마케팅 위험도 분석")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 업체별 위험도 매트릭스")
    
    client_display = client_stats.copy()
    client_display['업체명_short'] = client_display['업체명'].apply(
        lambda x: x[:15] + "..." if len(str(x)) > 15 else str(x)
    )
    
    fig = px.scatter(
        client_display,
        x='AS건수',
        y='총수리비',
        color='위험도점수',
        size='평균수리비',
        hover_name='업체명',
        hover_data=['위험등급'],
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 위험등급 분포")
    
    risk_counts = client_stats['위험등급'].value_counts()
    
    fig3 = px.pie(
        values=risk_counts.values,
        names=risk_counts.index,
        title="위험등급별 업체 수"
    )
    st.plotly_chart(fig3, use_container_width=True)

# 고위험 업체 상세 분석
st.header("🎯 디마케팅 검토 대상 업체")

risk_threshold = st.slider("위험도 점수 기준", 0.5, 5.0, 1.5, 0.1)
risky_clients = client_stats[client_stats['위험도점수'] >= risk_threshold].sort_values('위험도점수', ascending=False).head(10)

if len(risky_clients) == 0:
    st.info("선택한 기준에 해당하는 위험 업체가 없습니다.")
else:
    st.write(f"위험도 점수 {risk_threshold} 이상 업체: {len(risky_clients)}개")
    
    for idx, (_, client) in enumerate(risky_clients.iterrows()):
        risk_icon, risk_desc = get_risk_level(client['위험도점수'])
        
        client_name_display = str(client['업체명'])[:30] + "..." if len(str(client['업체명'])) > 30 else str(client['업체명'])
        
        with st.expander(f"{risk_icon} {client_name_display} (위험도: {client['위험도점수']:.2f})"):
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("총 수리비", f"{client['총수리비']:,.0f}원")
                st.metric("AS 건수", f"{client['AS건수']}건")
            
            with col2:
                st.metric("건당 평균 수리비", f"{client['평균수리비']:,.0f}원")
                st.metric("위험도 점수", f"{client['위험도점수']:.2f}")
            
            with col3:
                if '최근수리일' in client and pd.notna(client['최근수리일']):
                    st.metric("최근 수리일", client['최근수리일'].strftime('%Y-%m-%d'))
                st.metric("위험 등급", client['위험설명'])
            
            # 상세 분석
            client_detail = df[df['업체명'] == client['업체명']]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**🔧 주요 수리 유형**")
                if '작업유형' in client_detail.columns:
                    work_types = client_detail['작업유형'].value_counts().head(3)
                    for work, count in work_types.items():
                        st.write(f"• {work}: {count}건")
            
            with col2:
                st.write("**🚛 주요 장비 브랜드**")
                if '브랜드' in client_detail.columns:
                    brands = client_detail['브랜드'].value_counts().head(3)
                    for brand, count in brands.items():
                        st.write(f"• {brand}: {count}건")
            
            # 권고사항
            st.write("**💡 디마케팅 권고사항**")
            
            if client['위험도점수'] >= 3.0:
                st.error("🚨 **즉시 계약 검토 필요** - 매우 높은 위험도")
                st.write("- 계약 해지 또는 대폭적인 조건 변경 검토")
                st.write("- 수리비 상한선 설정 또는 유상 전환")
            elif client['위험도점수'] >= 2.0:
                st.warning("⚠️ **계약 조건 재협상 검토** - 높은 위험도")
                st.write("- 월 수리비 한도 설정")
                st.write("- 예방정비 교육으로 고장 빈도 감소")
            elif client['위험도점수'] >= 1.5:
                st.info("💡 **모니터링 강화** - 중간 위험도")
                st.write("- 정기적인 수리비 모니터링")
                st.write("- 고객 교육을 통한 예방정비 강화")
            else:
                st.success("✅ 현재 특별한 조치 불필요")

# 데이터 다운로드 - 엑셀 버전
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    # 위험도 분석 결과 다운로드
    excel_data = to_excel_download(client_stats, "업체별_위험도분석.xlsx")
    st.download_button(
        label="📊 위험도 분석 결과 다운로드 (Excel)",
        data=excel_data,
        file_name="업체별_위험도분석.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col2:
    # 상세 데이터 다운로드
    download_columns = ['업체명', '관리번호', '정비일자', '수리비', '작업유형', '브랜드']
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_excel = to_excel_download(detailed_data, "업체별_상세데이터.xlsx")
    st.download_button(
        label="📄 업체별 상세 데이터 다운로드 (Excel)",
        data=detailed_excel,
        file_name="업체별_상세데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
