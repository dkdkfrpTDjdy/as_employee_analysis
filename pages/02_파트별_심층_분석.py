import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="업체별 분석", layout="wide")
st.title("🏢 업체별 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_company_data(df):
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df['년월'] = df['정비일자'].dt.to_period('M')
    
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    # 업체명 컬럼 찾기 및 정리
    company_col = None
    for col in ['현장명', '업체명', '현장']:
        if col in df.columns:
            company_col = col
            break
    
    if company_col:
        df['업체명'] = df[company_col].astype(str).str.strip()
        df['업체명'] = df['업체명'].replace(['nan', 'NaN', ''], '기타')
    else:
        df['업체명'] = '기타'
    
    return df

df = prepare_company_data(df)

# 사이드바 필터
st.sidebar.header("🔧 분석 옵션")

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
min_cases = st.sidebar.slider(
    "최소 AS 건수 (필터링)",
    min_value=1,
    max_value=50,
    value=5,
    help="선택한 건수 이상의 AS가 발생한 업체만 분석"
)

# 업체별 전체 현황
st.header("📊 업체별 전체 현황")

# 업체별 통계 계산
company_stats = df.groupby('업체명').agg({
    '관리번호': 'count',
    '수리비': ['sum', 'mean']
}).round(2)

company_stats.columns = ['AS건수', '총수리비', '평균수리비']
company_stats = company_stats.reset_index()

# 건당 수리비 및 위험도 지표 추가
company_stats['건당수리비'] = company_stats['총수리비'] / company_stats['AS건수']
company_stats['위험도점수'] = (company_stats['건당수리비'] / company_stats['AS건수'] * 100).round(2)

# 최소 건수 필터 적용
company_stats = company_stats[company_stats['AS건수'] >= min_cases]
company_stats = company_stats.sort_values('건당수리비', ascending=False)

# 전체 현황 메트릭
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_companies = len(company_stats)
    st.metric("분석 대상 업체", f"{total_companies}개")

with col2:
    total_cases = company_stats['AS건수'].sum()
    st.metric("총 AS 건수", f"{total_cases:,}건")

with col3:
    total_cost = company_stats['총수리비'].sum()
    st.metric("총 수리비", f"{total_cost:,.0f}원")

with col4:
    avg_cost_per_case = total_cost / total_cases if total_cases > 0 else 0
    st.metric("전체 평균 건당수리비", f"{avg_cost_per_case:,.0f}원")

st.markdown("---")

# 고비용 업체 분석
st.header("🚨 고비용 업체 분석 (건당 수리비 기준)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 건당 수리비 TOP 10")
    top_cost_per_case = company_stats.head(10)
    
    fig = px.bar(
        top_cost_per_case,
        x='건당수리비',
        y='업체명',
        orientation='h',
        color='건당수리비',
        color_continuous_scale='Reds',
        text='AS건수'
    )
    fig.update_traces(texttemplate='%{text}건', textposition='outside')
    fig.update_layout(
        height=400, 
        yaxis={'categoryorder': 'total ascending'},
        title="건당 수리비가 높은 업체 (AS 건수 표시)"
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 총 수리비 TOP 10")
    top_total_cost = company_stats.nlargest(10, '총수리비')
    
    fig2 = px.bar(
        top_total_cost,
        x='총수리비',
        y='업체명',
        orientation='h',
        color='총수리비',
        color_continuous_scale='Oranges',
        text='AS건수'
    )
    fig2.update_traces(texttemplate='%{text}건', textposition='outside')
    fig2.update_layout(
        height=400,
        yaxis={'categoryorder': 'total ascending'},
        title="총 수리비가 높은 업체 (AS 건수 표시)"
    )
    st.plotly_chart(fig2, use_container_width=True)

# 위험도 매트릭스
st.subheader("🎯 업체 위험도 매트릭스")

# 위험도 분류
def classify_risk(row):
    if row['건당수리비'] > company_stats['건당수리비'].quantile(0.8):
        if row['AS건수'] >= 10:
            return "🔴 고위험 (고비용+다빈도)"
        else:
            return "🟠 주의 (고비용)"
    elif row['AS건수'] >= 20:
        return "🟡 모니터링 (다빈도)"
    else:
        return "🟢 안정"

company_stats['위험도분류'] = company_stats.apply(classify_risk, axis=1)

# 위험도 매트릭스 시각화
fig = px.scatter(
    company_stats,
    x='AS건수',
    y='건당수리비',
    size='총수리비',
    color='위험도분류',
    hover_name='업체명',
    hover_data=['총수리비'],
    title="업체별 위험도 매트릭스 (크기: 총수리비)",
    color_discrete_map={
        "🔴 고위험 (고비용+다빈도)": "red",
        "🟠 주의 (고비용)": "orange", 
        "🟡 모니터링 (다빈도)": "gold",
        "🟢 안정": "green"
    }
)
fig.update_layout(height=500)
st.plotly_chart(fig, use_container_width=True)

# 위험도별 업체 현황
st.subheader("📋 위험도별 업체 현황")

risk_summary = company_stats.groupby('위험도분류').agg({
    '업체명': 'count',
    'AS건수': 'sum',
    '총수리비': 'sum',
    '건당수리비': 'mean'
}).round(0)

risk_summary.columns = ['업체수', '총AS건수', '총수리비', '평균건당수리비']
st.dataframe(risk_summary, use_container_width=True)

st.markdown("---")

# 상세 업체 분석
st.header("🔍 상세 업체 분석")

# 분석할 업체 선택
available_companies = company_stats['업체명'].tolist()
selected_companies = st.multiselect(
    "상세 분석할 업체 선택",
    available_companies,
    default=available_companies[:3] if len(available_companies) >= 3 else available_companies
)

if selected_companies:
    for i, company in enumerate(selected_companies):
        if i > 0:
            st.markdown("---")
        
        company_data = df[df['업체명'] == company]
        company_info = company_stats[company_stats['업체명'] == company].iloc[0]
        
        st.subheader(f"🏢 {company}")
        
        # 업체 KPI
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 AS 건수", f"{company_info['AS건수']:,}건")
        
        with col2:
            st.metric("총 수리비", f"{company_info['총수리비']:,.0f}원")
        
        with col3:
            st.metric("건당 수리비", f"{company_info['건당수리비']:,.0f}원")
        
        with col4:
            risk_class = company_info['위험도분류']
            st.metric("위험도", risk_class)
        
        # 상세 분석
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**🔧 주요 브랜드**")
            if '브랜드' in company_data.columns:
                brands = company_data['브랜드'].value_counts().head(5)
                for brand, count in brands.items():
                    percentage = (count / len(company_data) * 100)
                    st.write(f"• {brand}: {count}건 ({percentage:.1f}%)")
            else:
                st.write("브랜드 데이터 없음")
        
        with col2:
            st.write("**⚙️ 주요 작업 유형**")
            if '작업유형' in company_data.columns:
                work_types = company_data['작업유형'].value_counts().head(5)
                for work, count in work_types.items():
                    percentage = (count / len(company_data) * 100)
                    st.write(f"• {work}: {count}건 ({percentage:.1f}%)")
            else:
                st.write("작업유형 데이터 없음")
        
        with col3:
            st.write("**👥 주요 담당 파트**")
            if '정비자소속' in company_data.columns:
                parts = company_data['정비자소속'].value_counts().head(5)
                for part, count in parts.items():
                    percentage = (count / len(company_data) * 100)
                    st.write(f"• {part}: {count}건 ({percentage:.1f}%)")
            else:
                st.write("파트 데이터 없음")
        
        # 월별 트렌드
        if '년월' in company_data.columns and len(company_data) > 1:
            st.write("**📈 월별 AS 트렌드**")
            
            monthly_trend = company_data.groupby('년월').agg({
                '관리번호': 'count',
                '수리비': 'sum'
            }).reset_index()
            monthly_trend.columns = ['년월', 'AS건수', '수리비']
            monthly_trend['년월_str'] = monthly_trend['년월'].astype(str)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Bar(x=monthly_trend['년월_str'], y=monthly_trend['AS건수'], 
                       name="AS건수", marker_color='lightblue'),
                secondary_y=False,
            )
            
            fig.add_trace(
                go.Scatter(x=monthly_trend['년월_str'], y=monthly_trend['수리비'],
                          mode='lines+markers', name="수리비", line=dict(color='red')),
                secondary_y=True,
            )
            
            fig.update_xaxes(title_text="년월")
            fig.update_yaxes(title_text="AS건수", secondary_y=False)
            fig.update_yaxes(title_text="수리비(원)", secondary_y=True)
            fig.update_layout(height=300, title=f"{company} 월별 트렌드")
            
            st.plotly_chart(fig, use_container_width=True)
        
        # 고비용 케이스
        if company_data['수리비'].sum() > 0:
            st.write("**💰 고비용 수리 케이스**")
            high_cost_cases = company_data.nlargest(3, '수리비')
            
            for idx, (_, case) in enumerate(high_cost_cases.iterrows()):
                브랜드 = case.get('브랜드', 'N/A')
                모델명 = case.get('모델명', 'N/A')
                수리비 = case.get('수리비', 0)
                작업유형 = case.get('작업유형', 'N/A')
                
                st.write(f"**{idx+1}. {브랜드} - {모델명}**")
                st.write(f"   💰 수리비: {수리비:,.0f}원 | 작업: {작업유형}")

# 업체 간 비교 분석
if len(selected_companies) > 1:
    st.markdown("---")
    st.header("⚖️ 선택된 업체 간 비교")
    
    comparison_data = []
    for company in selected_companies:
        company_info = company_stats[company_stats['업체명'] == company].iloc[0]
        comparison_data.append({
            '업체명': company,
            'AS건수': company_info['AS건수'],
            '총수리비': company_info['총수리비'],
            '건당수리비': company_info['건당수리비'],
            '위험도': company_info['위험도분류']
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            comparison_df,
            x='업체명',
            y='건당수리비',
            color='건당수리비',
            title="업체별 건당 수리비 비교",
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            comparison_df,
            x='업체명',
            y='총수리비',
            color='총수리비',
            title="업체별 총 수리비 비교",
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)

# 업체 랭킹
st.markdown("---")
st.header("🏆 업체 랭킹")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🚨 디마케팅 위험도 TOP 10")
    risk_ranking = company_stats.head(10)[['업체명', '건당수리비', 'AS건수', '위험도분류']]
    
    for idx, (_, row) in enumerate(risk_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['업체명']}** {row['위험도분류']}")
        st.write(f"   건당 수리비: {row['건당수리비']:,.0f}원 ({row['AS건수']}건)")

with col2:
    st.subheader("💰 총 수리비 TOP 10")
    cost_ranking = company_stats.nlargest(10, '총수리비')[['업체명', '총수리비', 'AS건수', '위험도분류']]
    
    for idx, (_, row) in enumerate(cost_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['업체명']}** {row['위험도분류']}")
        st.write(f"   총 수리비: {row['총수리비']:,.0f}원 ({row['AS건수']}건)")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    csv_data = company_stats.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📊 업체별 통계 다운로드 (CSV)",
        data=csv_data,
        file_name="업체별_위험도분석.csv",
        mime="text/csv"
    )

with col2:
    download_columns = ['업체명', '관리번호', '정비일자', '수리비', '브랜드', '작업유형', '정비자소속']
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_csv = detailed_data.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 상세 데이터 다운로드 (CSV)",
        data=detailed_csv,
        file_name="업체별_상세데이터.csv",
        mime="text/csv"
    )
