# 3. pages/03_업체별_디마케팅_분석.py 전체 코드
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

# 현장명 컬럼 처리 - 현장명이 있으면 그대로 사용, 없으면 업체명 사용
client_col = None
if '현장명' in df.columns and df['현장명'].notna().any():
    client_col = '현장명'
elif '업체명' in df.columns and df['업체명'].notna().any():
    client_col = '업체명'
elif '현장' in df.columns and df['현장'].notna().any():
    client_col = '현장'
else:
    st.error("현장명, 업체명, 또는 현장 컬럼이 없습니다.")
    st.stop()

# 데이터 정리
clean_data = []
for idx, row in df.iterrows():
    if pd.notna(row.get(client_col)):
        clean_row = row.to_dict()
        clean_row['업체명'] = str(clean_row[client_col])
        
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
client_counts = df_clean['업체명'].value_counts()
valid_clients = client_counts[client_counts >= min_cases].index.tolist()

# 최종 필터링된 데이터
final_data = []
for idx, row in df_clean.iterrows():
    if row['업체명'] in valid_clients:
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
    
    unique_clients = len(set([row['업체명'] for row in total_data_dict]))
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
for client in df_filtered['업체명'].unique():
    client_data = df_filtered[df_filtered['업체명'] == client]
    
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
        '업체명': client,
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
        # 업체명이 너무 길면 줄임
        top_cost_clients_display = top_cost_clients.copy()
        top_cost_clients_display['업체명_short'] = top_cost_clients_display['업체명'].apply(
            lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
        )
        
        fig = px.bar(
            top_cost_clients_display,
            x='총수리비',
            y='업체명_short',
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
        # 업체명이 너무 길면 줄임
        top_case_clients_display = top_case_clients.copy()
        top_case_clients_display['업체명_short'] = top_case_clients_display['업체명'].apply(
            lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
        )
        
        fig2 = px.bar(
            top_case_clients_display,
            x='AS건수',
            y='업체명_short',
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
for client in df_filtered['업체명'].unique():
    client_data_list = [row for row in total_data_list if row['업체명'] == client]
    
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
    
    # 업체명이 너무 길면 hover에서만 전체 이름 표시
    risk_df_display = risk_df.copy()
    risk_df_display['업체명_short'] = risk_df_display['업체명'].apply(
        lambda x: x[:15] + "..." if len(str(x)) > 15 else str(x)
    )
    
    fig = px.scatter(
        risk_df_display,
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
        
        # 업체명이 너무 길면 줄임
        client_name_display = str(client['업체명'])[:30] + "..." if len(str(client['업체명'])) > 30 else str(client['업체명'])
        
        with st.expander(f"{risk_icon} {client_name_display} (위험도: {client['위험도점수']:.2f})"):
            
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
            
            # 해당 업체의 상세 정보
            client_detail = df_filtered[df_filtered['업체명'] == client['업체명']]
            
            st.write("**📋 상세 정보**")
            col1, col2 = st.columns(2)
            
            with col1:
                if '작업유형' in client_detail.columns:
                    st.write("주요 작업 유형:")
                    work_types = client_detail['작업유형'].value_counts().head(3)
                    for work, count in work_types.items():
                        st.write(f"• {work}: {count}건")
            
            with col2:
                if '브랜드' in client_detail.columns:
                    st.write("주요 장비 브랜드:")
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
                st.write("- 일부 수리 항목 유상 전환")
            elif client['위험도점수'] >= 1.5:
                st.info("💡 **모니터링 강화** - 중간 위험도")
                st.write("- 월별 수리비 모니터링 강화")
                st.write("- 예방정비 교육 실시")
            else:
                st.success("✅ 현재 특별한 조치 불필요")

# 위험도별 상세 통계
st.header("📊 위험도별 상세 통계")

col1, col2 = st.columns(2)

with col1:
    st.subheader("위험등급별 업체 통계")
    risk_summary = risk_df.groupby('위험등급').agg({
        '업체명': 'count',
        '총수리비': 'sum',
        '평균건당수리비': 'mean',
        'AS건수': 'sum'
    }).round(0)
    risk_summary.columns = ['업체수', '총수리비합계', '평균건당수리비', '총AS건수']
    
    st.dataframe(
        risk_summary.style.format({
            '총수리비합계': '{:,.0f}원',
            '평균건당수리비': '{:,.0f}원',
            '총AS건수': '{:,}건'
        }),
        use_container_width=True
    )

with col2:
    st.subheader("월평균 AS 건수 분포")
    
    # 월평균 AS 건수 히스토그램
    fig = px.histogram(
        risk_df,
        x='월평균AS건수',
        nbins=20,
        title="업체별 월평균 AS 건수 분포",
        color_discrete_sequence=['#FF6B6B']
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

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

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    if not risk_df.empty:
        csv_data = risk_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 위험도 분석 결과 다운로드 (CSV)",
            data=csv_data,
            file_name="업체별_위험도분석.csv",
            mime="text/csv"
        )

with col2:
    if not client_stats_df.empty:
        stats_csv = client_stats_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📋 업체별 통계 다운로드 (CSV)",
            data=stats_csv,
            file_name="업체별_기본통계.csv",
            mime="text/csv"
        )
