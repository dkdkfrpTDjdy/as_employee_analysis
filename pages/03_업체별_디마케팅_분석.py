# pages/03_업체별_디마케팅_분석.py

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import seaborn as sns

# pandas 경고 무시 (임시 해결책)
pd.options.mode.chained_assignment = None

st.set_page_config(page_title="업체별 디마케팅 분석", layout="wide")
st.title("🏢 업체별 디마케팅 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

# 원본 데이터를 복사하여 사용
df = st.session_state.df1_with_costs.copy()

# 현장명 컬럼 확인 및 정리
if '현장명' not in df.columns:
    if '현장' in df.columns:
        df = df.copy()  # 명시적 복사
        df['현장명'] = df['현장']
    else:
        st.error("현장명 또는 현장 컬럼이 없습니다.")
        st.stop()

# 데이터 전처리 - 명시적으로 새 DataFrame 생성
df_clean = df.dropna(subset=['현장명']).copy()
df_clean.loc[:, '현장명'] = df_clean['현장명'].astype(str)

# 수리비 컬럼 처리
if '수리비' not in df_clean.columns:
    df_clean.loc[:, '수리비'] = 0
df_clean.loc[:, '수리비'] = pd.to_numeric(df_clean['수리비'], errors='coerce').fillna(0)

# 정비일자 처리
if '정비일자' in df_clean.columns:
    df_clean.loc[:, '정비일자'] = pd.to_datetime(df_clean['정비일자'], errors='coerce')

# 이제 df_clean을 df로 재할당
df = df_clean.copy()

# 사이드바 설정
st.sidebar.header("🎯 분석 설정")

# 기간 필터
if '정비일자' in df.columns and df['정비일자'].notna().any():
    min_date = df['정비일자'].min().date()
    max_date = df['정비일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간 선택",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        # 새로운 DataFrame으로 필터링
        df = df.loc[
            (df['정비일자'].dt.date >= start_date) & 
            (df['정비일자'].dt.date <= end_date)
        ].copy()

# 최소 AS 건수 필터
min_cases = st.sidebar.slider("최소 AS 건수 (분석 대상)", 1, 20, 3)

# 그룹 필터링 - 새로운 방식으로 처리
client_counts = df.groupby('현장명').size()
valid_clients = client_counts[client_counts >= min_cases].index
df_filtered = df[df['현장명'].isin(valid_clients)].copy()

if df_filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 업체별 종합 점수 계산 함수
@st.cache_data
def calculate_client_score(client_data, df_total):
    """업체별 디마케팅 위험도 점수 계산"""
    if len(client_data) == 0:
        return 0, 0, 0, 0
    
    # 기본 지표 계산
    total_cost = client_data['수리비'].sum()
    case_count = len(client_data)
    avg_cost_per_case = total_cost / case_count if case_count > 0 else 0
    
    # 전체 평균과 비교
    global_avg_cost = df_total['수리비'].mean()
    global_avg_cases = len(df_total) / df_total['현장명'].nunique()
    
    # 정규화된 점수 계산 (1.0이 평균)
    cost_score = avg_cost_per_case / global_avg_cost if global_avg_cost > 0 else 0
    frequency_score = case_count / global_avg_cases if global_avg_cases > 0 else 0
    
    # 가중 평균으로 종합 점수 계산 (수리비 70%, 빈도 30%)
    total_score = (cost_score * 0.7) + (frequency_score * 0.3)
    
    return total_score, avg_cost_per_case, case_count, total_cost

# 전체 업체 분석
st.header("📊 전체 업체 현황")

# 업체별 기본 통계
if '정비일자' in df_filtered.columns:
    client_stats = df_filtered.groupby('현장명').agg({
        '수리비': ['sum', 'mean', 'count'],
        '정비일자': ['min', 'max']
    }).round(0)
    client_stats.columns = ['총수리비', '평균수리비', 'AS건수', '첫수리일', '최근수리일']
else:
    client_stats = df_filtered.groupby('현장명').agg({
        '수리비': ['sum', 'mean', 'count']
    }).round(0)
    client_stats.columns = ['총수리비', '평균수리비', 'AS건수']

client_stats = client_stats.reset_index()

# 상위 업체 시각화
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 수리비 상위 업체 TOP 10")
    top_cost_clients = client_stats.nlargest(10, '총수리비')
    
    if not top_cost_clients.empty:
        fig = px.bar(
            top_cost_clients,
            x='총수리비',
            y='현장명',
            orientation='h',
            title="업체별 총 수리비",
            color='총수리비',
            color_continuous_scale='Reds',
            text='총수리비'
        )
        fig.update_traces(texttemplate='%{text:,.0f}원', textposition='outside')
        fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("표시할 데이터가 없습니다.")

with col2:
    st.subheader("📈 AS 건수 상위 업체 TOP 10")
    top_case_clients = client_stats.nlargest(10, 'AS건수')
    
    if not top_case_clients.empty:
        fig2 = px.bar(
            top_case_clients,
            x='AS건수',
            y='현장명',
            orientation='h',
            title="업체별 AS 건수",
            color='AS건수',
            color_continuous_scale='Blues',
            text='AS건수'
        )
        fig2.update_traces(texttemplate='%{text}건', textposition='outside')
        fig2.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("표시할 데이터가 없습니다.")

# 디마케팅 위험도 분석
st.header("🚨 디마케팅 위험도 분석")

# 모든 업체에 대해 점수 계산
client_analysis = []
for client in df_filtered['현장명'].unique():
    client_data = df_filtered[df_filtered['현장명'] == client].copy()
    score, avg_cost, case_count, total_cost = calculate_client_score(client_data, df_filtered)
    
    # 최근 활동 정보
    if '정비일자' in client_data.columns:
        recent_date = client_data['정비일자'].max()
        first_date = client_data['정비일자'].min()
        activity_period = (recent_date - first_date).days if pd.notna(recent_date) and pd.notna(first_date) else 0
    else:
        recent_date = None
        first_date = None
        activity_period = 0
    
    client_analysis.append({
        '업체명': client,
        '위험도점수': score,
        '총수리비': total_cost,
        '평균건당수리비': avg_cost,
        'AS건수': case_count,
        '최근수리일': recent_date,
        '첫수리일': first_date,
        '활동기간': activity_period,
        '월평균AS건수': case_count / max(activity_period / 30, 1) if activity_period > 0 else case_count
    })

client_df = pd.DataFrame(client_analysis)
client_df = client_df.sort_values('위험도점수', ascending=False)

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

if not client_df.empty:
    # 위험등급 컬럼 추가
    risk_levels = client_df['위험도점수'].apply(get_risk_level)
    client_df = client_df.copy()
    client_df.loc[:, '위험등급'] = [x[0] for x in risk_levels]
    client_df.loc[:, '위험설명'] = [x[1] for x in risk_levels]

    # 위험도 분포 시각화
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 업체별 위험도 분포")
        
        # 산점도
        fig = px.scatter(
            client_df,
            x='AS건수',
            y='총수리비',
            color='위험도점수',
            size='평균건당수리비',
            hover_name='업체명',
            hover_data=['위험등급', '위험도점수'],
            title="업체별 위험도 매트릭스 (크기: 평균 건당 수리비)",
            color_continuous_scale='Reds'
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🎯 위험등급 분포")
        
        risk_counts = client_df['위험등급'].value_counts()
        
        if not risk_counts.empty:
            fig3 = px.pie(
                values=risk_counts.values,
                names=risk_counts.index,
                title="위험등급별 업체 수",
                color_discrete_sequence=['#FF4444', '#FF8800', '#FFDD00', '#44FF44', '#4444FF']
            )
            st.plotly_chart(fig3, use_container_width=True)

    # 디마케팅 검토 대상 업체
    st.header("🎯 디마케팅 검토 대상 업체")

    risk_threshold = st.slider("위험도 점수 기준", 0.5, 5.0, 1.5, 0.1)
    risky_clients = client_df[client_df['위험도점수'] >= risk_threshold].head(15)

    if len(risky_clients) == 0:
        st.info("선택한 기준에 해당하는 위험 업체가 없습니다.")
    else:
        st.write(f"**위험도 점수 {risk_threshold} 이상 업체: {len(risky_clients)}개**")
        
        # 상세 분석
        for idx, client in risky_clients.iterrows():
            risk_icon, risk_desc = get_risk_level(client['위험도점수'])
            
            with st.expander(f"{risk_icon} {client['업체명']} (위험도: {client['위험도점수']:.2f})"):
                
                # 기본 정보
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
                        days_since = (datetime.now() - client['최근수리일']).days
                        st.metric("경과일", f"{days_since}일")
                    
                    st.metric("활동 기간", f"{client['활동기간']}일")
                
                # 상세 분석
                client_detail = df_filtered[df_filtered['현장명'] == client['업체명']].copy()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**🔧 주요 고장 유형**")
                    if '작업유형' in client_detail.columns:
                        main_faults = client_detail['작업유형'].value_counts().head(5)
                        for fault, count in main_faults.items():
                            percentage = (count / len(client_detail) * 100)
                            st.write(f"• {fault}: {count}건 ({percentage:.1f}%)")
                    else:
                        st.info("작업유형 데이터 없음")
                
                with col2:
                    st.write("**⚙️ 주요 정비 대상**")
                    if '정비대상' in client_detail.columns:
                        main_targets = client_detail['정비대상'].value_counts().head(5)
                        for target, count in main_targets.items():
                            percentage = (count / len(client_detail) * 100)
                            st.write(f"• {target}: {count}건 ({percentage:.1f}%)")
                    else:
                        st.info("정비대상 데이터 없음")
                
                # 권고사항
                st.write("**💡 디마케팅 권고사항**")
                
                recommendations = []
                
                if client['위험도점수'] >= 3.0:
                    recommendations.append("🚨 **즉시 계약 검토 필요** - 매우 높은 위험도")
                elif client['위험도점수'] >= 2.0:
                    recommendations.append("⚠️ **계약 조건 재협상 검토** - 높은 위험도")
                
                if not recommendations:
                    recommendations.append("✅ 현재 특별한 조치 불필요")
                
                for rec in recommendations:
                    st.write(f"• {rec}")

    # 요약 통계
    st.header("📊 전체 요약")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        high_risk_count = len(client_df[client_df['위험도점수'] >= 2.0])
        st.metric("고위험 업체", f"{high_risk_count}개")

    with col2:
        total_clients = len(client_df)
        st.metric("전체 분석 업체", f"{total_clients}개")

    with col3:
        avg_risk_score = client_df['위험도점수'].mean()
        st.metric("평균 위험도", f"{avg_risk_score:.2f}")

    with col4:
        high_risk_ratio = (high_risk_count / total_clients * 100) if total_clients > 0 else 0
        st.metric("고위험 업체 비율", f"{high_risk_ratio:.1f}%")

else:
    st.warning("분석할 업체 데이터가 없습니다.")
