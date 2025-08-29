# 1. 메인 대시보드 (경영진 중심)
# pages/01_경영_대시보드.py

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="경영 대시보드", layout="wide")
st.title("📊 경영 대시보드 - 실시간 AS 현황")

if 'df_maintenance' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df_maintenance

# 날짜 필터
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    # 기간 선택
    period_type = st.selectbox("분석 기간", ["월별", "분기별", "반기별"], key="period_main")
with col2:
    # 비교 기준 선택  
    compare_type = st.selectbox("비교 기준", ["전월 대비", "전년 동기 대비", "전분기 대비"], key="compare_main")
with col3:
    # 자동 새로고침
    auto_refresh = st.checkbox("자동 새로고침 (30초)")

# 핵심 KPI 영역
st.header("🎯 핵심 지표 (Key Performance Indicators)")

# 현재 월 vs 이전 기간 비교
current_month = datetime.now().replace(day=1)
prev_month = (current_month - timedelta(days=1)).replace(day=1)

current_data = df[df['정비일자'].dt.to_period('M') == pd.Timestamp(current_month).to_period('M')]
prev_data = df[df['정비일자'].dt.to_period('M') == pd.Timestamp(prev_month).to_period('M')]

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    current_cases = len(current_data)
    prev_cases = len(prev_data)
    case_change = ((current_cases - prev_cases) / prev_cases * 100) if prev_cases > 0 else 0
    
    st.metric("📋 이번달 AS 건수", 
             f"{current_cases:,}건", 
             f"{case_change:+.1f}%")

with col2:
    current_cost = current_data['수리비'].sum() if '수리비' in current_data.columns else 0
    prev_cost = prev_data['수리비'].sum() if '수리비' in prev_data.columns else 0
    cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
    
    st.metric("💰 이번달 수리비", 
             f"{current_cost:,.0f}원", 
             f"{cost_change:+.1f}%")

with col3:
    current_avg = current_cost / current_cases if current_cases > 0 else 0
    prev_avg = prev_cost / prev_cases if prev_cases > 0 else 0
    avg_change = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0
    
    st.metric("📊 건당 평균 수리비", 
             f"{current_avg:,.0f}원", 
             f"{avg_change:+.1f}%")

with col4:
    # 가장 문제가 되는 파트 찾기
    if '정비자소속' in current_data.columns:
        problem_parts = current_data.groupby('정비자소속')['수리비'].sum().nlargest(1)
        if not problem_parts.empty:
            worst_part = problem_parts.index[0]
            worst_cost = problem_parts.iloc[0]
            st.metric("⚠️ 최고비용 파트", 
                     worst_part, 
                     f"{worst_cost:,.0f}원")
        else:
            st.metric("⚠️ 최고비용 파트", "데이터 없음")
    else:
        st.metric("⚠️ 최고비용 파트", "데이터 없음")

with col5:
    # 가장 문제가 되는 업체 찾기  
    if '현장명' in current_data.columns:
        problem_clients = current_data.groupby('현장명')['수리비'].sum().nlargest(1)
        if not problem_clients.empty:
            worst_client = problem_clients.index[0]
            worst_client_cost = problem_clients.iloc[0]
            # 업체명만 표시 (너무 길면 줄임)
            display_name = worst_client[:10] + "..." if len(worst_client) > 10 else worst_client
            st.metric("🏢 최고비용 업체", 
                     display_name, 
                     f"{worst_client_cost:,.0f}원")
        else:
            st.metric("🏢 최고비용 업체", "데이터 없음")
    else:
        st.metric("🏢 최고비용 업체", "데이터 없음")

st.markdown("---")

# 상황실 스타일의 차트 영역
st.header("📈 실시간 트렌드 분석")

col1, col2 = st.columns(2)

with col1:
    st.subheader("월별 수리비 추이 (최근 12개월)")
    
    # 최근 12개월 데이터
    df['년월'] = df['정비일자'].dt.to_period('M')
    recent_months = sorted(df['년월'].dropna().unique())[-12:]
    
    monthly_analysis = df[df['년월'].isin(recent_months)].groupby('년월').agg({
        '수리비': 'sum',
        '관리번호': 'count'  # AS 건수
    }).reset_index()
    monthly_analysis['년월_str'] = monthly_analysis['년월'].astype(str)
    
    # Plotly 인터랙티브 차트
    fig = go.Figure()
    
    # 수리비 라인
    fig.add_trace(go.Scatter(
        x=monthly_analysis['년월_str'],
        y=monthly_analysis['수리비'],
        mode='lines+markers',
        name='월별 수리비',
        line=dict(color='#FF6B6B', width=3),
        marker=dict(size=8)
    ))
    
    # 평균선 추가
    avg_cost = monthly_analysis['수리비'].mean()
    fig.add_hline(y=avg_cost, line_dash="dash", line_color="gray", 
                  annotation_text=f"평균: {avg_cost:,.0f}원")
    
    fig.update_layout(
        title="최근 12개월 수리비 트렌드",
        xaxis_title="월",
        yaxis_title="수리비 (원)",
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("월별 AS 건수 추이 (최근 12개월)")
    
    # AS 건수 차트
    fig2 = go.Figure()
    
    fig2.add_trace(go.Bar(
        x=monthly_analysis['년월_str'],
        y=monthly_analysis['관리번호'],
        name='월별 AS 건수',
        marker_color='#4ECDC4'
    ))
    
    # 평균선 추가
    avg_cases = monthly_analysis['관리번호'].mean()
    fig2.add_hline(y=avg_cases, line_dash="dash", line_color="gray",
                   annotation_text=f"평균: {avg_cases:.0f}건")
    
    fig2.update_layout(
        title="최근 12개월 AS 건수 트렌드", 
        xaxis_title="월",
        yaxis_title="AS 건수",
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig2, use_container_width=True)

# 핵심 문제 영역 분석
st.header("🚨 주요 이슈 및 액션 포인트")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🔥 수리비 급증 파트 TOP 5")
    
    # 이번달 vs 지난달 파트별 비교
    if '정비자소속' in df.columns:
        current_part_cost = current_data.groupby('정비자소속')['수리비'].sum()
        prev_part_cost = prev_data.groupby('정비자소속')['수리비'].sum()
        
        # 증감률 계산
        part_comparison = pd.DataFrame({
            '이번달': current_part_cost,
            '지난달': prev_part_cost
        }).fillna(0)
        
        part_comparison['증감률'] = ((part_comparison['이번달'] - part_comparison['지난달']) / 
                                   part_comparison['지난달'].replace(0, 1) * 100)
        part_comparison['증감액'] = part_comparison['이번달'] - part_comparison['지난달']
        
        # 급증한 파트 TOP 5
        top_increases = part_comparison.nlargest(5, '증감률')
        
        for idx, (part, row) in enumerate(top_increases.iterrows()):
            if row['증감률'] > 20:  # 20% 이상 증가한 경우만
                color = "🔴" if row['증감률'] > 50 else "🟡"
                st.write(f"{color} **{part}**")
                st.write(f"   증감: +{row['증감률']:.1f}% (+{row['증감액']:,.0f}원)")
            else:
                break
    else:
        st.info("파트 정보가 없습니다.")

with col2:
    st.subheader("⚠️ 문제 업체 TOP 5")
    
    # 업체별 수리비 급증 분석
    if '현장명' in df.columns:
        current_client_cost = current_data.groupby('현장명')['수리비'].sum()
        prev_client_cost = prev_data.groupby('현장명')['수리비'].sum()
        
        client_comparison = pd.DataFrame({
            '이번달': current_client_cost,
            '지난달': prev_client_cost
        }).fillna(0)
        
        client_comparison['증감률'] = ((client_comparison['이번달'] - client_comparison['지난달']) / 
                                     client_comparison['지난달'].replace(0, 1) * 100)
        client_comparison['증감액'] = client_comparison['이번달'] - client_comparison['지난달']
        
        # 문제 업체 TOP 5 (수리비 절대액 기준)
        problem_clients = client_comparison.nlargest(5, '이번달')
        
        for idx, (client, row) in enumerate(problem_clients.iterrows()):
            if row['이번달'] > 1000000:  # 100만원 이상인 경우
                color = "🔴" if row['이번달'] > 5000000 else "🟡"
                client_short = client[:15] + "..." if len(client) > 15 else client
                st.write(f"{color} **{client_short}**")
                st.write(f"   수리비: {row['이번달']:,.0f}원")
                if row['지난달'] > 0:
                    st.write(f"   전월대비: {row['증감률']:+.1f}%")
    else:
        st.info("업체 정보가 없습니다.")

with col3:
    st.subheader("🔧 주요 고장 유형")
    
    # 이번달 주요 고장 유형 분석
    if '작업유형' in current_data.columns and '정비대상' in current_data.columns:
        current_faults = current_data.groupby(['작업유형', '정비대상']).agg({
            '수리비': 'sum',
            '관리번호': 'count'
        }).reset_index()
        
        current_faults['고장유형'] = current_faults['작업유형'] + ' > ' + current_faults['정비대상']
        top_faults = current_faults.nlargest(5, '수리비')
        
        for idx, row in top_faults.iterrows():
            cost_level = "🔴" if row['수리비'] > 2000000 else "🟡" if row['수리비'] > 1000000 else "🟢"
            st.write(f"{cost_level} **{row['고장유형']}**")
            st.write(f"   수리비: {row['수리비']:,.0f}원 ({row['관리번호']}건)")
    else:
        st.info("고장 유형 정보가 없습니다.")

# 액션 아이템 요약
st.markdown("---")
st.header("📋 이번 주 액션 아이템")

action_items = []

# 자동으로 액션 아이템 생성
if len(top_increases) > 0:
    worst_part = top_increases.index[0]
    worst_increase = top_increases.iloc[0]['증감률']
    if worst_increase > 30:
        action_items.append(f"🔥 **긴급**: {worst_part} 파트 수리비 {worst_increase:.1f}% 급증 → 원인 분석 및 대책 수립")

if len(problem_clients) > 0:
    worst_client = problem_clients.index[0]
    worst_cost = problem_clients.iloc[0]['이번달']
    if worst_cost > 3000000:
        client_short = worst_client[:20] + "..." if len(worst_client) > 20 else worst_client
        action_items.append(f"📞 **업체 미팅**: {client_short} (수리비 {worst_cost:,.0f}원) → 디마케팅 검토")

if case_change > 20:
    action_items.append(f"📈 **트렌드 주의**: AS 건수 {case_change:.1f}% 증가 → 계절성/특이사항 분석")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")

# 자동 새로고침 기능
if auto_refresh:
    import time
    time.sleep(30)
    st.experimental_rerun()