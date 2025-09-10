# pages/01_메인_대시보드.py - 완전 개선된 버전
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="메인 대시보드", layout="wide")
st.title("📊 메인 대시보드")

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

# 사이드바 설정
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

# 메인 분석 - 개선된 버전 (그래프 추가)
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
    st.subheader("🚨 주요 이슈 (그래프)")
    
    # 파트별 수리비 차트
    if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
        part_costs = current_data[current_data['정비자소속'].notna()].groupby('정비자소속')['수리비'].sum().nlargest(5)
        
        if not part_costs.empty:
            fig = px.bar(
                x=part_costs.values,
                y=part_costs.index,
                orientation='h',
                title="수리비 상위 5개 파트",
                color=part_costs.values,
                color_continuous_scale='Reds'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("**💰 파트별 수리비 정보 없음**")
    else:
        st.write("**💰 파트 정보 없음**")

# 지역별 분석 추가 - 새로운 섹션
st.header("🗺️ 지역별 분석")

col1, col2 = st.columns(2)

with col1:
    st.subheader("지역별 AS 현황")
    
    if '지역' in current_data.columns and current_data['지역'].notna().any():
        region_analysis = current_data[current_data['지역'].notna()].groupby('지역').agg({
            '관리번호': 'count',
            '수리비': 'sum'
        }).rename(columns={'관리번호': 'AS건수'})
        
        region_analysis['평균수리비'] = (region_analysis['수리비'] / region_analysis['AS건수']).round(0)
        region_analysis = region_analysis.sort_values('수리비', ascending=False)
        
        # 지역별 수리비 차트
        fig = px.bar(
            x=region_analysis.index,
            y=region_analysis['수리비'],
            title="지역별 총 수리비",
            color=region_analysis['수리비'],
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("지역 정보가 없습니다.")

with col2:
    st.subheader("지역별 주요 작업내용")
    
    if '지역' in current_data.columns and '작업내용' in current_data.columns:
        region_work_data = current_data[current_data['지역'].notna() & current_data['작업내용'].notna()]
        
        if not region_work_data.empty:
            # 지역별 작업내용 분석
            region_work_analysis = region_work_data.groupby(['지역', '작업내용']).size().reset_index(name='건수')
            
            # 각 지역별 상위 작업내용
            top_works_by_region = region_work_analysis.loc[region_work_analysis.groupby('지역')['건수'].idxmax()]
            
            fig = px.bar(
                top_works_by_region,
                x='지역',
                y='건수',
                color='작업내용',
                title="지역별 주요 작업내용"
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("지역별 작업내용 데이터가 없습니다.")
    else:
        st.info("지역 또는 작업내용 정보가 없습니다.")

# 작업내용별 분석 - 새로운 섹션
st.header("🔧 작업내용별 분석")

if '작업내용' in current_data.columns and current_data['작업내용'].notna().any():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("작업내용별 수리비")
        
        work_content_analysis = current_data[current_data['작업내용'].notna()].groupby('작업내용').agg({
            '관리번호': 'count',
            '수리비': 'sum'
        }).rename(columns={'관리번호': 'AS건수'})
        
        work_content_analysis['평균수리비'] = (work_content_analysis['수리비'] / work_content_analysis['AS건수']).round(0)
        work_content_analysis = work_content_analysis.sort_values('수리비', ascending=False).head(10)
        
        # 작업내용명 줄임
        work_content_display = work_content_analysis.copy()
        work_content_display.index = [name[:25] + "..." if len(str(name)) > 25 else str(name) for name in work_content_display.index]
        
        fig = px.bar(
            x=work_content_display['수리비'],
            y=work_content_display.index,
            orientation='h',
            title="작업내용별 총 수리비 (상위 10개)",
            color=work_content_display['수리비'],
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("작업내용별 빈도")
        
        work_frequency = current_data['작업내용'].value_counts().head(10)
        
        # 작업내용명 줄임
        work_frequency_display = work_frequency.copy()
        work_frequency_display.index = [name[:25] + "..." if len(str(name)) > 25 else str(name) for name in work_frequency_display.index]
        
        fig = px.bar(
            x=work_frequency_display.values,
            y=work_frequency_display.index,
            orientation='h',
            title="작업내용별 AS 건수 (상위 10개)",
            color=work_frequency_display.values,
            color_continuous_scale='Greens'
        )
        fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("작업내용 정보가 없습니다.")

# 하단 상세 분석 - 개선된 버전 (작업내용 컬럼 추가)
st.header("📋 상세 분석")

tab1, tab2, tab3 = st.tabs(["파트별", "업체별", "작업내용별"])

with tab1:
    st.subheader("👥 파트별 분석")
    
    if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
        valid_part_data = current_data[current_data['정비자소속'].notna()]
        
        if not valid_part_data.empty:
            part_analysis = valid_part_data.groupby('정비자소속').agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean']
            })
            part_analysis.columns = ['건수', '총수리비', '평균수리비']
            
            # 작업내용 추가
            if '작업내용' in valid_part_data.columns:
                part_work_content = valid_part_data.groupby('정비자소속')['작업내용'].apply(
                    lambda x: x.value_counts().head(3).index.tolist()
                ).to_dict()
                
                part_analysis['주요작업내용'] = part_analysis.index.map(
                    lambda x: ', '.join(part_work_content.get(x, [])[:2])
                )
            
            part_analysis['효율성'] = np.where(
                part_analysis['총수리비'] > 0,
                part_analysis['건수'] / part_analysis['총수리비'] * 1000000,
                0
            )
            
            part_analysis = part_analysis.sort_values('총수리비', ascending=False)
            
            # 포맷팅
            format_dict = {
                '총수리비': '{:,.0f}원',
                '평균수리비': '{:,.0f}원',
                '효율성': '{:.2f}'
            }
            
            st.dataframe(
                part_analysis.style.format(format_dict),
                use_container_width=True
            )
        else:
            st.info("파트별 데이터가 없습니다.")
    else:
        st.info("정비자소속 정보가 없습니다.")

with tab2:
    st.subheader("🏢 업체별 분석")
    
    client_col = '현장명' if '현장명' in current_data.columns else '업체명'
    
    if client_col in current_data.columns:
        valid_client_data = current_data[current_data[client_col].notna()]
        
        if not valid_client_data.empty:
            client_analysis = valid_client_data.groupby(client_col).agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean']
            })
            client_analysis.columns = ['건수', '총수리비', '평균수리비']
            
            # 작업내용 추가
            if '작업내용' in valid_client_data.columns:
                client_work_content = valid_client_data.groupby(client_col)['작업내용'].apply(
                    lambda x: x.value_counts().head(2).index.tolist()
                ).to_dict()
                
                client_analysis['주요작업내용'] = client_analysis.index.map(
                    lambda x: ', '.join(client_work_content.get(x, [])[:2])
                )
            
            client_analysis = client_analysis.sort_values('총수리비', ascending=False).head(20)
            
            st.dataframe(
                client_analysis.style.format({
                    '총수리비': '{:,.0f}원',
                    '평균수리비': '{:,.0f}원'
                }),
                use_container_width=True
            )
        else:
            st.info("업체별 데이터가 없습니다.")
    else:
        st.info("업체 정보가 없습니다.")

with tab3:
    st.subheader("🔧 작업내용별 상세 분석")
    
    if '작업내용' in current_data.columns and current_data['작업내용'].notna().any():
        work_content_data = current_data[current_data['작업내용'].notna()]
        
        work_content_analysis = work_content_data.groupby('작업내용').agg({
            '관리번호': 'count',
            '수리비': ['sum', 'mean'],
            '정비자소속': lambda x: x.mode().iloc[0] if not x.mode().empty else 'N/A'
        })
        work_content_analysis.columns = ['건수', '총수리비', '평균수리비', '주요담당파트']
        
        # 업체 정보 추가
        if client_col in work_content_data.columns:
            work_client_info = work_content_data.groupby('작업내용')[client_col].apply(
                lambda x: x.value_counts().head(2).index.tolist()
            ).to_dict()
            
            work_content_analysis['주요업체'] = work_content_analysis.index.map(
                lambda x: ', '.join([str(c)[:15] + "..." if len(str(c)) > 15 else str(c) 
                                   for c in work_client_info.get(x, [])[:2]])
            )
        
        work_content_analysis = work_content_analysis.sort_values('총수리비', ascending=False).head(15)
        
        st.dataframe(
            work_content_analysis.style.format({
                '총수리비': '{:,.0f}원',
                '평균수리비': '{:,.0f}원'
            }),
            use_container_width=True
        )
    else:
        st.info("작업내용 정보가 없습니다.")

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

# 작업내용별 이슈 추가
if '작업내용' in current_data.columns and current_data['작업내용'].notna().any():
    high_cost_work = current_data[current_data['작업내용'].notna()].groupby('작업내용')['수리비'].sum().nlargest(1)
    if not high_cost_work.empty:
        work_name = high_cost_work.index[0][:30] + "..." if len(high_cost_work.index[0]) > 30 else high_cost_work.index[0]
        action_items.append(f"🔧 **고비용 작업**: '{work_name}' → {high_cost_work.iloc[0]:,.0f}원")

# 지역별 이슈 추가
if '지역' in current_data.columns and current_data['지역'].notna().any():
    high_cost_region = current_data[current_data['지역'].notna()].groupby('지역')['수리비'].sum().nlargest(1)
    if not high_cost_region.empty:
        action_items.append(f"🗺️ **고비용 지역**: {high_cost_region.index[0]} → {high_cost_region.iloc[0]:,.0f}원")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")
