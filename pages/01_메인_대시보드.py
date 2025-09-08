import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="경영 대시보드", layout="wide")
st.title("📊 경영 대시보드")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# 빠른 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_dashboard_data(df):
    # 날짜 처리
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df = df.dropna(subset=['정비일자'])
        df['년월'] = df['정비일자'].dt.to_period('M')
        df['년'] = df['정비일자'].dt.year
        df['월'] = df['정비일자'].dt.month
    
    # 수리비 처리
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    return df

df = prepare_dashboard_data(df)

if df.empty:
    st.error("처리 가능한 데이터가 없습니다.")
    st.stop()

# 사이드바 설정 (간소화)
st.sidebar.header("📊 분석 설정")

# 기간 선택
available_months = sorted(df['년월'].dropna().unique(), reverse=True)
if not available_months:
    st.error("분석 가능한 데이터가 없습니다.")
    st.stop()

selected_month = st.sidebar.selectbox(
    "분석 기준 월", 
    available_months,
    format_func=lambda x: str(x)
)

# 비교 월 설정
compare_months = [m for m in available_months if m < selected_month]
compare_month = compare_months[0] if compare_months else None

# 현재 월과 비교 월 데이터
current_data = df[df['년월'] == selected_month]
prev_data = df[df['년월'] == compare_month] if compare_month else pd.DataFrame()

# 핵심 지표 계산
current_cases = len(current_data)
current_cost = current_data['수리비'].sum()
current_avg = current_cost / current_cases if current_cases > 0 else 0

prev_cases = len(prev_data) if not prev_data.empty else 0
prev_cost = prev_data['수리비'].sum() if not prev_data.empty else 0
prev_avg = prev_cost / prev_cases if prev_cases > 0 else 0

# 증감률 계산
case_change = ((current_cases - prev_cases) / prev_cases * 100) if prev_cases > 0 else 0
cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
avg_change = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0

# 상단 KPI
st.header(f"🎯 {selected_month} 핵심 지표")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if compare_month:
        st.metric("AS 건수", f"{current_cases:,}건", f"{case_change:+.1f}%")
    else:
        st.metric("AS 건수", f"{current_cases:,}건")

with col2:
    if compare_month:
        st.metric("총 수리비", f"{current_cost:,.0f}원", f"{cost_change:+.1f}%")
    else:
        st.metric("총 수리비", f"{current_cost:,.0f}원")

with col3:
    if compare_month:
        st.metric("건당 평균", f"{current_avg:,.0f}원", f"{avg_change:+.1f}%")
    else:
        st.metric("건당 평균", f"{current_avg:,.0f}원")

with col4:
    unique_equipment = current_data['관리번호'].nunique()
    st.metric("수리 장비", f"{unique_equipment}대")

# 알림
if current_avg > df['수리비'].mean() * 1.3:
    st.error(f"⚠️ 이번 달 평균 수리비가 전체 평균보다 {((current_avg/df['수리비'].mean()-1)*100):.1f}% 높습니다!")

st.markdown("---")

# 메인 분석
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 월별 트렌드 (최근 12개월)")
    
    # 월별 데이터 집계
    recent_months = available_months[:12]
    monthly_data = df[df['년월'].isin(recent_months)].groupby('년월').agg({
        '수리비': 'sum',
        '관리번호': 'count'
    }).reset_index()
    monthly_data['년월_str'] = monthly_data['년월'].astype(str)
    monthly_data = monthly_data.sort_values('년월')
    
    if not monthly_data.empty:
        fig = go.Figure()
        
        # 수리비 트렌드
        fig.add_trace(go.Scatter(
            x=monthly_data['년월_str'],
            y=monthly_data['수리비'],
            mode='lines+markers',
            name='월별 수리비',
            line=dict(color='#FF6B6B', width=3),
            yaxis='y'
        ))
        
        # AS 건수 (보조축)
        fig.add_trace(go.Scatter(
            x=monthly_data['년월_str'],
            y=monthly_data['관리번호'],
            mode='lines+markers',
            name='AS 건수',
            line=dict(color='#4ECDC4', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            height=400,
            yaxis=dict(title="수리비 (원)", side="left"),
            yaxis2=dict(title="AS 건수", side="right", overlaying="y"),
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🚨 주요 이슈")
    
    # 파트별 수리비 (상위 5개)
    if '정비자소속' in current_data.columns and not current_data.empty:
        part_costs = current_data.groupby('정비자소속')['수리비'].sum().nlargest(5)
        
        st.write("**💰 수리비 상위 파트:**")
        for idx, (part, cost) in enumerate(part_costs.items()):
            icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
            st.write(f"{icon} {part}: {cost:,.0f}원")
    
    # 업체별 수리비 (상위 5개)
    client_col = '현장명' if '현장명' in current_data.columns else '업체명'
    if client_col in current_data.columns and not current_data.empty:
        client_costs = current_data.groupby(client_col)['수리비'].sum().nlargest(5)
        
        st.write("**🏢 수리비 상위 업체:**")
        for idx, (client, cost) in enumerate(client_costs.items()):
            icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
            client_short = str(client)[:15] + "..." if len(str(client)) > 15 else str(client)
            st.write(f"{icon} {client_short}: {cost:,.0f}원")

# 하단 상세 분석
st.header("📋 상세 분석")

tab1, tab2, tab3 = st.tabs(["파트별", "업체별", "고장유형별"])

with tab1:
    if '정비자소속' in current_data.columns:
        part_analysis = current_data.groupby('정비자소속').agg({
            '관리번호': 'count',
            '수리비': ['sum', 'mean']
        })
        part_analysis.columns = ['건수', '총수리비', '평균수리비']
        part_analysis['효율성'] = part_analysis['건수'] / part_analysis['총수리비'] * 1000000
        part_analysis = part_analysis.sort_values('총수리비', ascending=False)
        
        st.dataframe(
            part_analysis.style.format({
                '총수리비': '{:,.0f}원',
                '평균수리비': '{:,.0f}원',
                '효율성': '{:.2f}'
            }),
            use_container_width=True
        )

with tab2:
    if client_col in current_data.columns:
        client_analysis = current_data.groupby(client_col).agg({
            '관리번호': 'count',
            '수리비': ['sum', 'mean']
        })
        client_analysis.columns = ['건수', '총수리비', '평균수리비']
        client_analysis = client_analysis.sort_values('총수리비', ascending=False).head(20)
        
        st.dataframe(
            client_analysis.style.format({
                '총수리비': '{:,.0f}원',
                '평균수리비': '{:,.0f}원'
            }),
            use_container_width=True
        )

with tab3:
    if '작업유형' in current_data.columns:
        fault_analysis = current_data.groupby('작업유형').agg({
            '관리번호': 'count',
            '수리비': 'sum'
        })
        fault_analysis.columns = ['건수', '총수리비']
        fault_analysis['비율'] = (fault_analysis['건수'] / fault_analysis['건수'].sum() * 100).round(1)
        fault_analysis = fault_analysis.sort_values('건수', ascending=False)
        
        st.dataframe(
            fault_analysis.style.format({
                '총수리비': '{:,.0f}원',
                '비율': '{:.1f}%'
            }),
            use_container_width=True
        )

# 액션 아이템
st.markdown("---")
st.header("📋 액션 아이템")

action_items = []

if current_cost > 10000000:
    action_items.append(f"💰 **고비용 주의**: 총 수리비 {current_cost:,.0f}원 → 비용 절감 방안 검토")

if case_change > 30:
    action_items.append(f"📈 **건수 급증**: 전월 대비 {case_change:.1f}% 증가 → 원인 분석 필요")

if avg_change > 25:
    action_items.append(f"⚠️ **단가 상승**: 건당 평균 {avg_change:.1f}% 상승 → 수리 품질 점검")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")
