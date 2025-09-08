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

# 수리비 처리
if '수리비' not in df.columns:
    df['수리비'] = 0
df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)

# 년월 컬럼 생성
df['년월'] = df['정비일자'].dt.to_period('M')

# 만족도 데이터 확인
has_satisfaction = '만족도_평균' in df.columns and df['만족도_평균'].notna().any()

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

st.header("🎯 핵심 지표")

# 기본 통계 계산
current_cases = len(current_data)
current_cost = current_data['수리비'].sum()
current_avg = current_cost / current_cases if current_cases > 0 else 0

# 만족도 통계 (만족도 데이터가 있는 경우)
current_satisfaction = None
current_satisfaction_rate = None
if has_satisfaction:
    satisfaction_data = current_data[current_data['만족도_평균'].notna()]
    if not satisfaction_data.empty:
        current_satisfaction = satisfaction_data['만족도_평균'].mean()
        if '만족도_만족률' in satisfaction_data.columns:
            current_satisfaction_rate = satisfaction_data['만족도_만족률'].mean()

# 이전 월 통계
prev_cases = len(prev_data) if not prev_data.empty else 0
prev_cost = prev_data['수리비'].sum() if not prev_data.empty else 0
prev_avg = prev_cost / prev_cases if prev_cases > 0 else 0

prev_satisfaction = None
if has_satisfaction and not prev_data.empty:
    prev_satisfaction_data = prev_data[prev_data['만족도_평균'].notna()]
    if not prev_satisfaction_data.empty:
        prev_satisfaction = prev_satisfaction_data['만족도_평균'].mean()

# 증감률 계산
case_change = ((current_cases - prev_cases) / prev_cases * 100) if prev_cases > 0 else 0
cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
avg_change = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0
satisfaction_change = ((current_satisfaction - prev_satisfaction) / prev_satisfaction * 100) if prev_satisfaction and current_satisfaction else None

# KPI 표시 (만족도 포함)
if has_satisfaction:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
else:
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
    # 최고비용 업체 (현장명 우선 사용)
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
    elif '업체명' in current_data.columns and not current_data.empty:
        client_costs = current_data.groupby('업체명')['수리비'].sum()
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

# 만족도 지표 추가
if has_satisfaction:
    with col6:
        if current_satisfaction is not None:
            satisfaction_color = "🟢" if current_satisfaction >= 4.0 else "🟡" if current_satisfaction >= 3.5 else "🔴"
            if satisfaction_change is not None:
                st.metric(f"{satisfaction_color} 평균 만족도", 
                         f"{current_satisfaction:.2f}점", 
                         f"{satisfaction_change:+.1f}%")
            else:
                st.metric(f"{satisfaction_color} 평균 만족도", f"{current_satisfaction:.2f}점")
        else:
            st.metric("😊 평균 만족도", "데이터 없음")

st.markdown("---")

# 트렌드 분석 (만족도 트렌드 추가)
st.header("📈 실시간 트렌드 분석")

if has_satisfaction:
    col1, col2, col3 = st.columns(3)
else:
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

# 만족도 트렌드 추가
if has_satisfaction:
    with col3:
        st.subheader("월별 만족도 추이 (최근 12개월)")
        
        # 만족도 월별 집계
        satisfaction_monthly = df[df['년월'].isin(recent_months) & df['만족도_평균'].notna()].groupby('년월').agg({
            '만족도_평균': 'mean',
            '만족도_응답수': 'sum'
        }).reset_index()
        satisfaction_monthly['년월_str'] = satisfaction_monthly['년월'].astype(str)
        satisfaction_monthly = satisfaction_monthly.sort_values('년월')
        
        if not satisfaction_monthly.empty:
            fig3 = go.Figure()
            
            fig3.add_trace(go.Scatter(
                x=satisfaction_monthly['년월_str'],
                y=satisfaction_monthly['만족도_평균'],
                mode='lines+markers',
                name='월별 평균 만족도',
                line=dict(color='#45B7D1', width=3),
                marker=dict(size=8)
            ))
            
            # 목표선 추가 (4.0점)
            fig3.add_hline(y=4.0, line_dash="dash", line_color="green", 
                          annotation_text="목표: 4.0점")
            
            fig3.update_layout(
                title="최근 12개월 만족도 트렌드",
                xaxis_title="월",
                yaxis_title="만족도 (점)",
                yaxis=dict(range=[1, 5]),
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("만족도 트렌드 분석을 위한 데이터가 부족합니다.")

# 주요 이슈 분석 (만족도 이슈 추가)
st.header("🚨 주요 이슈 및 액션 포인트")

if has_satisfaction:
    col1, col2, col3, col4 = st.columns(4)
else:
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
    
    # 현장명 우선 사용
    client_col = None
    if '현장명' in current_data.columns:
        client_col = '현장명'
    elif '업체명' in current_data.columns:
        client_col = '업체명'
    
    if client_col and not current_data.empty:
        client_costs = current_data.groupby(client_col)['수리비'].sum().nlargest(5)
        
        for client, cost in client_costs.items():
            if cost > 500000:  # 50만원 이상
                color = "🔴" if cost > 2000000 else "🟡"
                client_short = client[:15] + "..." if len(client) > 15 else client
                st.write(f"{color} **{client_short}**")
                st.write(f"   수리비: {cost:,.0f}원")
                
                # 전월 대비 (가능한 경우)
                if compare_month and not prev_data.empty and client_col in prev_data.columns:
                    prev_client_cost = prev_data[prev_data[client_col] == client]['수리비'].sum()
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

# 만족도 문제 업체 (만족도 데이터가 있는 경우)
if has_satisfaction:
    with col4:
        st.subheader("😞 만족도 문제 업체")
        
        client_col = '현장명' if '현장명' in current_data.columns else '업체명'
        
        if client_col and not current_data.empty:
            # 만족도가 있는 데이터만 필터링
            satisfaction_current = current_data[current_data['만족도_평균'].notna()]
            
            if not satisfaction_current.empty:
                client_satisfaction = satisfaction_current.groupby(client_col).agg({
                    '만족도_평균': 'mean',
                    '만족도_불만족률': 'mean',
                    '수리비': 'sum'
                }).reset_index()
                
                # 만족도 낮은 업체 (4.0 미만)
                problem_satisfaction = client_satisfaction[
                    client_satisfaction['만족도_평균'] < 4.0
                ].sort_values('만족도_평균')
                
                if not problem_satisfaction.empty:
                    for idx, row in problem_satisfaction.head(5).iterrows():
                        satisfaction_score = row['만족도_평균']
                        color = "🔴" if satisfaction_score < 3.0 else "🟡"
                        client_short = row[client_col][:15] + "..." if len(row[client_col]) > 15 else row[client_col]
                        
                        st.write(f"{color} **{client_short}**")
                        st.write(f"   만족도: {satisfaction_score:.2f}점")
                        if '만족도_불만족률' in row and pd.notna(row['만족도_불만족률']):
                            st.write(f"   불만족률: {row['만족도_불만족률']:.1f}%")
                else:
                    st.success("만족도 문제 업체 없음")
            else:
                st.info("만족도 조사 데이터 없음")

# 액션 아이템 (만족도 기준 추가)
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
    
    # 만족도 관련 액션 아이템
    if has_satisfaction and current_satisfaction is not None:
        if current_satisfaction < 3.5:
            action_items.append(f"😞 **만족도 위험**: 평균 만족도 {current_satisfaction:.2f}점 → 서비스 품질 개선 시급")
        elif satisfaction_change and satisfaction_change < -10:
            action_items.append(f"📉 **만족도 하락**: 전월 대비 {satisfaction_change:.1f}% 하락 → 원인 분석 및 개선 필요")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")

# 데이터 요약 정보 (만족도 정보 포함)
st.markdown("---")
summary_text = f"📊 **데이터 요약**: 분석 기간 {selected_month} | 총 {current_cases:,}건 | 총 수리비 {current_cost:,.0f}원"

if has_satisfaction and current_satisfaction is not None:
    summary_text += f" | 평균 만족도 {current_satisfaction:.2f}점"

summary_text += f" | 전체 데이터 기간: {available_months[-1]} ~ {available_months[0]}"

st.info(summary_text)

# 자동 새로고침 (실제 운영시에만 사용)
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()
