# pages/03_업체별_디마케팅_분석.py

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import seaborn as sns
import warnings

# 모든 pandas 경고 무시
warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None

st.set_page_config(page_title="업체별 디마케팅 분석", layout="wide")
st.title("🏢 업체별 디마케팅 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

# 원본 데이터 복사
original_df = st.session_state.df1_with_costs
df = original_df.copy()

# 현장명 컬럼 처리
if '현장명' not in df.columns:
    if '현장' in df.columns:
        df = df.rename(columns={'현장': '현장명'})
    else:
        st.error("현장명 또는 현장 컬럼이 없습니다.")
        st.stop()

# 데이터 정리 - 완전히 새로운 DataFrame 생성
clean_data = []
for idx, row in df.iterrows():
    if pd.notna(row.get('현장명')):
        clean_row = row.to_dict()
        clean_row['현장명'] = str(clean_row['현장명'])
        
        # 수리비 처리
        if '수리비' in clean_row:
            try:
                clean_row['수리비'] = float(clean_row['수리비']) if pd.notna(clean_row['수리비']) else 0
            except:
                clean_row['수리비'] = 0
        else:
            clean_row['수리비'] = 0
        
        # 정비일자 처리
        if '정비일자' in clean_row:
            try:
                clean_row['정비일자'] = pd.to_datetime(clean_row['정비일자'])
            except:
                clean_row['정비일자'] = None
        
        clean_data.append(clean_row)

# 새로운 DataFrame 생성
df_clean = pd.DataFrame(clean_data)

if df_clean.empty:
    st.error("처리할 수 있는 데이터가 없습니다.")
    st.stop()

# 사이드바 설정
st.sidebar.header("🎯 분석 설정")

# 기간 필터
if '정비일자' in df_clean.columns and df_clean['정비일자'].notna().any():
    valid_dates = df_clean['정비일자'].dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        
        date_range = st.sidebar.date_input(
            "분석 기간 선택",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            # 날짜 필터링
            filtered_data = []
            for idx, row in df_clean.iterrows():
                if pd.notna(row['정비일자']):
                    if start_date <= row['정비일자'].date() <= end_date:
                        filtered_data.append(row.to_dict())
            
            df_clean = pd.DataFrame(filtered_data)

# 최소 AS 건수 필터
min_cases = st.sidebar.slider("최소 AS 건수 (분석 대상)", 1, 20, 3)

# 업체별 건수 계산 및 필터링
client_counts = df_clean['현장명'].value_counts()
valid_clients = client_counts[client_counts >= min_cases].index.tolist()

# 최종 필터링된 데이터
final_data = []
for idx, row in df_clean.iterrows():
    if row['현장명'] in valid_clients:
        final_data.append(row.to_dict())

df_filtered = pd.DataFrame(final_data)

if df_filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 업체별 종합 점수 계산 함수
@st.cache_data
def calculate_client_score(client_data_dict, total_data_dict):
    """업체별 디마케팅 위험도 점수 계산"""
    if len(client_data_dict) == 0:
        return 0, 0, 0, 0
    
    # 기본 지표 계산
    costs = [row['수리비'] for row in client_data_dict]
    total_cost = sum(costs)
    case_count = len(client_data_dict)
    avg_cost_per_case = total_cost / case_count if case_count > 0 else 0
    
    # 전체 평균과 비교
    all_costs = [row['수리비'] for row in total_data_dict]
    global_avg_cost = sum(all_costs) / len(all_costs) if all_costs else 1
    
    unique_clients = len(set([row['현장명'] for row in total_data_dict]))
    global_avg_cases = len(total_data_dict) / unique_clients if unique_clients > 0 else 1
    
    # 정규화된 점수 계산
    cost_score = avg_cost_per_case / global_avg_cost if global_avg_cost > 0 else 0
    frequency_score = case_count / global_avg_cases if global_avg_cases > 0 else 0
    
    # 종합 점수
    total_score = (cost_score * 0.7) + (frequency_score * 0.3)
    
    return total_score, avg_cost_per_case, case_count, total_cost

# 전체 업체 분석
st.header("📊 전체 업체 현황")

# 업체별 통계 계산
client_stats_dict = {}
for client in df_filtered['현장명'].unique():
    client_data = df_filtered[df_filtered['현장명'] == client]
    
    total_cost = client_data['수리비'].sum()
    case_count = len(client_data)
    avg_cost = total_cost / case_count if case_count > 0 else 0
    
    if '정비일자' in client_data.columns:
        valid_dates = client_data['정비일자'].dropna()
        first_date = valid_dates.min() if not valid_dates.empty else None
        last_date = valid_dates.max() if not valid_dates.empty else None
    else:
        first_date = None
        last_date = None
    
    client_stats_dict[client] = {
        '현장명': client,
        '총수리비': total_cost,
        '평균수리비': avg_cost,
        'AS건수': case_count,
        '첫수리일': first_date,
        '최근수리일': last_date
    }

client_stats_df = pd.DataFrame(list(client_stats_dict.values()))

# 상위 업체 시각화
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 수리비 상위 업체 TOP 10")
    top_cost_clients = client_stats_df.nlargest(10, '총수리비')
    
    if not top_cost_clients.empty:
        fig = px.bar(
            top_cost_clients,
            x='총수리비',
            y='현장명',
            orientation='h',
            title="업체별 총 수리비",
            color='총수리비',
            color_continuous_scale='Reds'
        )
        fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📈 AS 건수 상위 업체 TOP 10")
    top_case_clients = client_stats_df.nlargest(10, 'AS건수')
    
    if not top_case_clients.empty:
        fig2 = px.bar(
            top_case_clients,
            x='AS건수',
            y='현장명',
            orientation='h',
            title="업체별 AS 건수",
            color='AS건수',
            color_continuous_scale='Blues'
        )
        fig2.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)

# 위험도 분석
st.header("🚨 디마케팅 위험도 분석")

# 전체 데이터를 딕셔너리 리스트로 변환
total_data_list = df_filtered.to_dict('records')

# 업체별 위험도 계산
risk_analysis = []
for client in df_filtered['현장명'].unique():
    client_data_list = [row for row in total_data_list if row['현장명'] == client]
    
    score, avg_cost, case_count, total_cost = calculate_client_score(client_data_list, total_data_list)
    
    # 활동 기간 계산
    if '정비일자' in df_filtered.columns:
        client_dates = [row['정비일자'] for row in client_data_list if pd.notna(row.get('정비일자'))]
        if client_dates:
            activity_period = (max(client_dates) - min(client_dates)).days
            recent_date = max(client_dates)
        else:
            activity_period = 0
            recent_date = None
    else:
        activity_period = 0
        recent_date = None
    
    risk_analysis.append({
        '업체명': client,
        '위험도점수': score,
        '총수리비': total_cost,
        '평균건당수리비': avg_cost,
        'AS건수': case_count,
        '최근수리일': recent_date,
        '활동기간': activity_period,
        '월평균AS건수': case_count / max(activity_period / 30, 1) if activity_period > 0 else case_count
    })

risk_df = pd.DataFrame(risk_analysis)
risk_df = risk_df.sort_values('위험도점수', ascending=False)

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

# 위험등급 추가
risk_levels = []
risk_descriptions = []
for score in risk_df['위험도점수']:
    level, desc = get_risk_level(score)
    risk_levels.append(level)
    risk_descriptions.append(desc)

risk_df = risk_df.copy()
risk_df['위험등급'] = risk_levels
risk_df['위험설명'] = risk_descriptions

# 위험도 분포 시각화
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 업체별 위험도 분포")
    
    fig = px.scatter(
        risk_df,
        x='AS건수',
        y='총수리비',
        color='위험도점수',
        size='평균건당수리비',
        hover_name='업체명',
        hover_data=['위험등급'],
        title="업체별 위험도 매트릭스",
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 위험등급 분포")
    
    risk_counts = risk_df['위험등급'].value_counts()
    
    if not risk_counts.empty:
        fig3 = px.pie(
            values=risk_counts.values,
            names=risk_counts.index,
            title="위험등급별 업체 수"
        )
        st.plotly_chart(fig3, use_container_width=True)

# 고위험 업체 상세 분석
st.header("🎯 디마케팅 검토 대상 업체")

risk_threshold = st.slider("위험도 점수 기준", 0.5, 5.0, 1.5, 0.1)
risky_clients = risk_df[risk_df['위험도점수'] >= risk_threshold].head(10)

if len(risky_clients) == 0:
    st.info("선택한 기준에 해당하는 위험 업체가 없습니다.")
else:
    st.write(f"**위험도 점수 {risk_threshold} 이상 업체: {len(risky_clients)}개**")
    
    for idx, client in risky_clients.iterrows():
        risk_icon, risk_desc = get_risk_level(client['위험도점수'])
        
        with st.expander(f"{risk_icon} {client['업체명']} (위험도: {client['위험도점수']:.2f})"):
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("총 수리비", f"{client['총수리비']:,.0f}원")
                st.metric("AS 건수", f"{client['AS건수']}건")
            
            with col2:
                st.metric("건당 평균 수리비", f"{client['평균건당수리비']:,.0f}원")
                st.metric("월평균 AS 건수", f"{client['월평균AS건수']:.1f}건")
            
            with col3:
                if pd.notna(client['최근수리일']):
                    st.metric("최근 수리일", client['최근수리일'].strftime('%Y-%m-%d'))
                st.metric("활동 기간", f"{client['활동기간']}일")
            
            # 권고사항
            st.write("**💡 디마케팅 권고사항**")
            
            if client['위험도점수'] >= 3.0:
                st.write("• 🚨 **즉시 계약 검토 필요** - 매우 높은 위험도")
            elif client['위험도점수'] >= 2.0:
                st.write("• ⚠️ **계약 조건 재협상 검토** - 높은 위험도")
            else:
                st.write("• ✅ 현재 특별한 조치 불필요")

# 요약 통계
st.header("📊 전체 요약")

col1, col2, col3, col4 = st.columns(4)

with col1:
    high_risk_count = len(risk_df[risk_df['위험도점수'] >= 2.0])
    st.metric("고위험 업체", f"{high_risk_count}개")

with col2:
    total_clients = len(risk_df)
    st.metric("전체 분석 업체", f"{total_clients}개")

with col3:
    avg_risk_score = risk_df['위험도점수'].mean()
    st.metric("평균 위험도", f"{avg_risk_score:.2f}")

with col4:
    high_risk_ratio = (high_risk_count / total_clients * 100) if total_clients > 0 else 0
    st.metric("고위험 업체 비율", f"{high_risk_ratio:.1f}%")
