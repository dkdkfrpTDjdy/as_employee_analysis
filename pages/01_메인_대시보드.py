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

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs

# 데이터 전처리
if '정비일자' not in df.columns:
    st.error("정비일자 컬럼이 없습니다.")
    st.stop()

# 날짜 처리
df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
df = df.dropna(subset=['정비일자'])  # 날짜가 없는 데이터 제거

if df.empty:
    st.error("유효한 정비일자 데이터가 없습니다.")
    st.stop()

# 현장명 처리
if '현장명' not in df.columns:
    if '현장' in df.columns:
        df['현장명'] = df['현장']

# 수리비 처리
if '수리비' not in df.columns:
    df['수리비'] = 0
df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)

# 년월 컬럼 생성
df['년월'] = df['정비일자'].dt.to_period('M')

# 사이드바 - 분석 기간 선택
st.sidebar.header("📊 분석 설정")

# 사용 가능한 년월 목록
available_months = sorted(df['년월'].dropna().unique(), reverse=True)

if len(available_months) == 0:
    st.error("분석 가능한 데이터가 없습니다.")
    st.stop()

# 기본값을 최신 월로 설정
default_month = available_months[0]
selected_month = st.sidebar.selectbox(
    "분석 기준 월", 
    available_months,
    index=0,
    format_func=lambda x: str(x)
)

# 비교 기준 월 (이전 월)
compare_months = [m for m in available_months if m < selected_month]
if compare_months:
    compare_month = compare_months[0]  # 가장 최근의 이전 월
else:
    compare_month = None

# 상단 필터
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    period_type = st.selectbox("분석 기간", ["월별", "분기별", "반기별"], key="period_main")
with col2:
    compare_type = st.selectbox("비교 기준", ["전월 대비", "전년 동기 대비", "전분기 대비"], key="compare_main")
with col3:
    auto_refresh = st.checkbox("자동 새로고침 (30초)")

# 선택된 월과 비교 월의 데이터
current_data = df[df['년월'] == selected_month]
prev_data = df[df['년월'] == compare_month] if compare_month else pd.DataFrame()

st.header("🎯 핵심 지표 (Key Performance Indicators)")

# 기본 통계 계산
current_cases = len(current_data)
current_cost = current_data['수리비'].sum()
current_avg = current_cost / current_cases if current_cases > 0 else 0

# 이전 월 통계
prev_cases = len(prev_data) if not prev_data.empty else 0
prev_cost = prev_data['수리비'].sum() if not prev_data.empty else 0
prev_avg = prev_cost / prev_cases if prev_cases > 0 else 0

# 증감률 계산
case_change = ((current_cases - prev_cases) / prev_cases * 100) if prev_cases > 0 else 0
cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
avg_change = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0

# KPI 표시
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if compare_month:
        st.metric(f"📋 {selected_month} AS 건수", 
                 f"{current_cases:,}건", 
                 f"{case_change:+.1f}%" if prev_cases > 0 else None)
    else:
        st.metric(f"📋 {selected_month} AS 건수", f"{current_cases:,}건")

with col2:
    if compare_month:
        st.metric(f"💰 {selected_month} 수리비", 
                 f"{current_cost:,.0f}원", 
                 f"{cost_change:+.1f}%" if prev_cost > 0 else None)
    else:
        st.metric(f"💰 {selected_month} 수리비", f"{current_cost:,.0f}원")

with col3:
    if compare_month:
        st.metric("📊 건당 평균 수리비", 
                 f"{current_avg:,.0f}원", 
                 f"{avg_change:+.1f}%" if prev_avg > 0 else None)
    else:
        st.metric("📊 건당 평균 수리비", f"{current_avg:,.0f}원")

with col4:
    # 최고비용 파트
    if '정비자소속' in current_data.columns and not current_data.empty:
        part_costs = current_data.groupby('정비자소속')['수리비'].sum()
        if not part_costs.empty:
            worst_part = part_costs.idxmax()
            worst_cost = part_costs.max()
            st.metric("⚠️ 최고비용 파트", 
                     worst_part, 
                     f"{worst_cost:,.0f}원")
        else:
            st.metric("⚠️ 최고비용 파트", "데이터 없음")
    else:
        st.metric("⚠️ 최고비용 파트", "데이터 없음")

with col5:
    # 최고비용 업체
    if '현장명' in current_data.columns and not current_data.empty:
        client_costs = current_data.groupby('현장명')['수리비'].sum()
        if not client_costs.empty:
            worst_client = client_costs.idxmax()
            worst_client_cost = client_costs.max()
            display_name = worst_client[:10] + "..." if len(worst_client) > 10 else worst_client
            st.metric("🏢 최고비용 업체", 
                     display_name, 
                     f"{worst_client_cost:,.0f}원")
        else:
            st.metric("🏢 최고비용 업체", "데이터 없음")
    else:
        st.metric("🏢 최고비용 업체", "데이터 없음")

st.markdown("---")

# 트렌드 분석
st.header("📈 실시간 트렌드 분석")

col1, col2 = st.columns(2)

with col1:
    st.subheader("월별 수리비 추이 (최근 12개월)")
    
    # 최근 12개월 데이터
    recent_months = available_months[:12]  # 최신 12개월
    
    monthly_analysis = df[df['년월'].isin(recent_months)].groupby('년월').agg({
        '수리비': 'sum',
        '관리번호': 'count'
    }).reset_index()
    monthly_analysis['년월_str'] = monthly_analysis['년월'].astype(str)
    monthly_analysis = monthly_analysis.sort_values('년월')
    
    if not monthly_analysis.empty:
        fig = go.Figure()
        
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
    else:
        st.info("트렌드 분석을 위한 데이터가 부족합니다.")

with col2:
    st.subheader("월별 AS 건수 추이 (최근 12개월)")
    
    if not monthly_analysis.empty:
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

# 주요 이슈 분석
st.header("🚨 주요 이슈 및 액션 포인트")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🔥 수리비 급증 파트 TOP 5")
    
    if '정비자소속' in df.columns and compare_month and not current_data.empty and not prev_data.empty:
        current_part_cost = current_data.groupby('정비자소속')['수리비'].sum()
        prev_part_cost = prev_data.groupby('정비자소속')['수리비'].sum()
        
        part_comparison = pd.DataFrame({
            '이번달': current_part_cost,
            '지난달': prev_part_cost
        }).fillna(0)
        
        part_comparison['증감률'] = ((part_comparison['이번달'] - part_comparison['지난달']) / 
                                   part_comparison['지난달'].replace(0, 1) * 100)
        part_comparison['증감액'] = part_comparison['이번달'] - part_comparison['지난달']
        
        top_increases = part_comparison.nlargest(5, '증감률')
        
        if not top_increases.empty:
            for idx, (part, row) in enumerate(top_increases.iterrows()):
                if row['증감률'] > 20:
                    color = "🔴" if row['증감률'] > 50 else "🟡"
                    st.write(f"{color} **{part}**")
                    st.write(f"   증감: +{row['증감률']:.1f}% (+{row['증감액']:,.0f}원)")
                else:
                    break
        else:
            st.info("급증한 파트가 없습니다.")
    else:
        st.info("비교할 데이터가 없습니다.")

with col2:
    st.subheader("⚠️ 문제 업체 TOP 5")
    
    if '현장명' in current_data.columns and not current_data.empty:
        client_costs = current_data.groupby('현장명')['수리비'].sum().nlargest(5)
        
        for client, cost in client_costs.items():
            if cost > 500000:  # 50만원 이상
                color = "🔴" if cost > 2000000 else "🟡"
                client_short = client[:15] + "..." if len(client) > 15 else client
                st.write(f"{color} **{client_short}**")
                st.write(f"   수리비: {cost:,.0f}원")
                
                # 전월 대비 (가능한 경우)
                if compare_month and not prev_data.empty and '현장명' in prev_data.columns:
                    prev_client_cost = prev_data[prev_data['현장명'] == client]['수리비'].sum()
                    if prev_client_cost > 0:
                        change_rate = ((cost - prev_client_cost) / prev_client_cost * 100)
                        st.write(f"   전월대비: {change_rate:+.1f}%")
    else:
        st.info("업체 정보가 없습니다.")

with col3:
    st.subheader("🔧 주요 고장 유형")
    
    if all(col in current_data.columns for col in ['작업유형', '정비대상']) and not current_data.empty:
        fault_analysis = current_data.groupby(['작업유형', '정비대상']).agg({
            '수리비': 'sum',
            '관리번호': 'count'
        }).reset_index()
        
        fault_analysis['고장유형'] = fault_analysis['작업유형'] + ' > ' + fault_analysis['정비대상']
        top_faults = fault_analysis.nlargest(5, '수리비')
        
        for idx, row in top_faults.iterrows():
            cost_level = "🔴" if row['수리비'] > 1000000 else "🟡" if row['수리비'] > 500000 else "🟢"
            st.write(f"{cost_level} **{row['고장유형']}**")
            st.write(f"   수리비: {row['수리비']:,.0f}원 ({row['관리번호']}건)")
    else:
        st.info("고장 유형 정보가 없습니다.")

# 액션 아이템
st.markdown("---")
st.header("📋 액션 아이템")

action_items = []

# 데이터 기반 액션 아이템 생성
if not current_data.empty:
    # 고비용 케이스 확인
    if current_cost > 10000000:  # 1천만원 이상
        action_items.append(f"💰 **고비용 주의**: {selected_month} 총 수리비 {current_cost:,.0f}원 → 비용 절감 방안 검토")
    
    # AS 건수 급증 확인
    if case_change > 30:
        action_items.append(f"📈 **건수 급증**: 전월 대비 {case_change:.1f}% 증가 → 원인 분석 필요")
    
    # 평균 수리비 상승 확인
    if avg_change > 25:
        action_items.append(f"⚠️ **단가 상승**: 건당 평균 수리비 {avg_change:.1f}% 상승 → 수리 품질 점검")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")

# 데이터 요약 정보
st.markdown("---")
st.info(f"📊 **데이터 요약**: 분석 기간 {selected_month} | 총 {current_cases:,}건 | 총 수리비 {current_cost:,.0f}원 | 전체 데이터 기간: {available_months[-1]} ~ {available_months[0]}")

# 자동 새로고침 (실제 운영시에만 사용)
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()
