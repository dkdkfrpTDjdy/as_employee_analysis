import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import calendar

st.set_page_config(page_title="월별 종합 분석", layout="wide")
st.title("📅 월별 종합 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_monthly_data(df):
    # 수치형 데이터 처리
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    if '수리시간' in df.columns:
        df['수리시간'] = pd.to_numeric(df['수리시간'], errors='coerce').fillna(0)
    
    if '가동시간' in df.columns:
        df['가동시간'] = pd.to_numeric(df['가동시간'], errors='coerce').fillna(0)
    
    # 날짜 처리
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df = df.dropna(subset=['정비일자'])
        df['년월'] = df['정비일자'].dt.to_period('M')
        df['년'] = df['정비일자'].dt.year
        df['월'] = df['정비일자'].dt.month
    
    return df

df = prepare_monthly_data(df)

if df.empty:
    st.error("처리 가능한 데이터가 없습니다.")
    st.stop()

# 사이드바 설정
st.sidebar.header("📊 분석 조건")

# 년도/월 선택
available_years = sorted(df['년'].dropna().unique(), reverse=True)
available_months = list(range(1, 13))

selected_year = st.sidebar.selectbox("분석 년도", available_years)
selected_month = st.sidebar.selectbox(
    "분석 월", 
    available_months,
    format_func=lambda x: f"{x}월"
)

# 장비 구분 (간소화)
equipment_filter = st.sidebar.selectbox("장비 구분", ["전체", "지게차", "AWP"])

# 전월 대비 분석
compare_month = st.sidebar.checkbox("전월 대비 분석")

# 데이터 필터링
filtered_df = df[(df['년'] == selected_year) & (df['월'] == selected_month)].copy()

# 장비 구분 필터링 (간단히)
if equipment_filter == "지게차":
    if '브랜드' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['브랜드'].str.contains('TOYOTA|HYUNDAI|DOOSAN', na=False, case=False)]
elif equipment_filter == "AWP":
    if '브랜드' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['브랜드'].str.contains('JLG|GENIE|SKYJACK', na=False, case=False)]

# 전월 데이터
prev_month_df = pd.DataFrame()
if compare_month:
    if selected_month > 1:
        prev_month_df = df[(df['년'] == selected_year) & (df['월'] == selected_month-1)].copy()
    else:
        prev_month_df = df[(df['년'] == selected_year-1) & (df['월'] == 12)].copy()
    
    # 동일한 필터 적용
    if equipment_filter == "지게차" and '브랜드' in prev_month_df.columns:
        prev_month_df = prev_month_df[prev_month_df['브랜드'].str.contains('TOYOTA|HYUNDAI|DOOSAN', na=False, case=False)]
    elif equipment_filter == "AWP" and '브랜드' in prev_month_df.columns:
        prev_month_df = prev_month_df[prev_month_df['브랜드'].str.contains('JLG|GENIE|SKYJACK', na=False, case=False)]

# 메인 제목
st.header(f"🗓️ {selected_year}년 {selected_month}월 ({equipment_filter}) 분석 리포트")

if filtered_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 기본 통계
total_cases = len(filtered_df)
total_cost = filtered_df['수리비'].sum()
avg_cost_per_case = total_cost / total_cases if total_cases > 0 else 0

# 전월 대비 계산
prev_total_cases = len(prev_month_df) if not prev_month_df.empty else 0
prev_total_cost = prev_month_df['수리비'].sum() if not prev_month_df.empty else 0
prev_avg_cost = prev_total_cost / prev_total_cases if prev_total_cases > 0 else 0

# 증감률
case_change = ((total_cases - prev_total_cases) / prev_total_cases * 100) if prev_total_cases > 0 else 0
cost_change = ((total_cost - prev_total_cost) / prev_total_cost * 100) if prev_total_cost > 0 else 0
avg_change = ((avg_cost_per_case - prev_avg_cost) / prev_avg_cost * 100) if prev_avg_cost > 0 else 0

# 상단 KPI
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if compare_month and prev_total_cases > 0:
        st.metric("총 AS 건수", f"{total_cases:,}건", f"{case_change:+.1f}%")
    else:
        st.metric("총 AS 건수", f"{total_cases:,}건")

with col2:
    if compare_month and prev_total_cost > 0:
        st.metric("총 수리비", f"{total_cost:,.0f}원", f"{cost_change:+.1f}%")
    else:
        st.metric("총 수리비", f"{total_cost:,.0f}원")

with col3:
    if compare_month and prev_avg_cost > 0:
        st.metric("건당 평균", f"{avg_cost_per_case:,.0f}원", f"{avg_change:+.1f}%")
    else:
        st.metric("건당 평균", f"{avg_cost_per_case:,.0f}원")

with col4:
    client_col = '현장명' if '현장명' in filtered_df.columns else '업체명'
    unique_clients = filtered_df[client_col].nunique() if client_col in filtered_df.columns else 0
    st.metric("관련 업체", f"{unique_clients}개")

with col5:
    unique_equipment = filtered_df['관리번호'].nunique()
    st.metric("수리 장비", f"{unique_equipment}대")

# 알림
if avg_cost_per_case > df['수리비'].mean() * 1.5:
    st.error(f"⚠️ 이번 달 평균 수리비가 전체 평균보다 {((avg_cost_per_case/df['수리비'].mean()-1)*100):.1f}% 높습니다!")

st.markdown("---")

# 탭 구조 간소화
tab1, tab2, tab3, tab4 = st.tabs(["👥 파트별", "🔧 고장유형별", "🏢 업체별", "💰 수리비분석"])

# 탭 1: 파트별 분석
with tab1:
    st.subheader("👥 파트별 분석")
    
    if '정비자소속' in filtered_df.columns:
        col1, col2 = st.columns(2)
        
        with col1:
            # 파트별 건수 및 수리비
            part_analysis = filtered_df.groupby('정비자소속').agg({
                '관리번호': 'count',
                '수리비': 'sum'
            }).rename(columns={'관리번호': '건수'})
            
            part_analysis['비율(%)'] = (part_analysis['건수'] / part_analysis['건수'].sum() * 100).round(1)
            part_analysis['평균수리비'] = (part_analysis['수리비'] / part_analysis['건수']).round(0)
            part_analysis = part_analysis.sort_values('건수', ascending=False)
            
            # 파트별 건수 차트
            fig = px.bar(
                x=part_analysis.index,
                y=part_analysis['건수'],
                title="파트별 AS 건수",
                color=part_analysis['건수'],
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 개별 정비자 분석 (상위 10명)
            if '정비자' in filtered_df.columns:
                worker_analysis = filtered_df.groupby(['정비자', '정비자소속']).agg({
                    '관리번호': 'count',
                    '수리비': ['sum', 'mean']
                }).round(1)
                
                worker_analysis.columns = ['건수', '총수리비', '평균수리비']
                worker_analysis = worker_analysis.reset_index()
                worker_analysis = worker_analysis.sort_values('건수', ascending=False).head(10)
                
                # 정비자별 성과 차트
                fig = px.scatter(
                    worker_analysis,
                    x='건수',
                    y='평균수리비',
                    size='총수리비',
                    color='정비자소속',
                    hover_name='정비자',
                    title="정비자별 성과"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # 파트별 상세 테이블
        st.dataframe(
            part_analysis.style.format({
                '수리비': '{:,.0f}원',
                '평균수리비': '{:,.0f}원',
                '비율(%)': '{:.1f}%'
            }),
            use_container_width=True
        )

# 탭 2: 고장유형별 분석
with tab2:
    st.subheader("🔧 고장유형별 분석")
    
    col1, col2, col3 = st.columns(3)
    
    # 대분류/중분류/소분류 분석
    classification_cols = {
        '대분류': '작업유형',
        '중분류': '정비대상', 
        '소분류': '정비작업'
    }
    
    for i, (title, col_name) in enumerate(classification_cols.items()):
        with [col1, col2, col3][i]:
            if col_name in filtered_df.columns:
                st.write(f"**{title} 분석**")
                
                category_analysis = filtered_df.groupby(col_name).agg({
                    '관리번호': 'count',
                    '수리비': 'sum'
                }).rename(columns={'관리번호': '건수'})
                
                category_analysis['비율(%)'] = (category_analysis['건수'] / category_analysis['건수'].sum() * 100).round(1)
                category_analysis = category_analysis.sort_values('건수', ascending=False)
                
                # 파이 차트
                if not category_analysis.empty:
                    fig = px.pie(
                        values=category_analysis['건수'],
                        names=category_analysis.index,
                        title=f"{title} 분포"
                    )
                    fig.update_layout(height=300, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 상위 3개 표시
                    for idx, (cat, row) in enumerate(category_analysis.head(3).iterrows()):
                        st.write(f"{idx+1}. {cat}: {row['건수']}건 ({row['비율(%)']:.1f}%)")

# 탭 3: 업체별 분석
with tab3:
    st.subheader("🏢 업체별 분석")
    
    client_col = '현장명' if '현장명' in filtered_df.columns else '업체명'
    
    if client_col in filtered_df.columns:
        col1, col2 = st.columns(2)
        
        with col1:
            # 지역별 분석
            if '지역' in filtered_df.columns:
                region_analysis = filtered_df.groupby('지역').agg({
                    '관리번호': 'count',
                    '수리비': 'sum',
                    client_col: 'nunique'
                }).rename(columns={'관리번호': '건수', client_col: '업체수'})
                
                region_analysis = region_analysis.sort_values('건수', ascending=False)
                
                fig = px.bar(
                    x=region_analysis.index,
                    y=region_analysis['건수'],
                    title="지역별 AS 건수",
                    color=region_analysis['건수'],
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 업체별 상세 분석 (상위 10개)
            client_analysis = filtered_df.groupby(client_col).agg({
                '관리번호': 'count',
                '수리비': 'sum'
            }).rename(columns={'관리번호': '건수'})
            
            client_analysis['평균수리비'] = (client_analysis['수리비'] / client_analysis['건수']).round(0)
            top_clients = client_analysis.nlargest(10, '수리비')
            
            # 업체명 줄임
            top_clients_display = top_clients.copy()
            top_clients_display.index = [name[:15] + "..." if len(str(name)) > 15 else str(name) for name in top_clients_display.index]
            
            fig = px.bar(
                x=top_clients_display['수리비'],
                y=top_clients_display.index,
                orientation='h',
                title="수리비 상위 10개 업체",
                color=top_clients_display['수리비'],
                color_continuous_scale='Reds'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

# 탭 4: 수리비 분석
with tab4:
    st.subheader("💰 수리비 분석")
    
    if filtered_df['수리비'].sum() > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            # 수리비 구간별 분석
            cost_bins = [0, 100000, 500000, 1000000, 2000000, float('inf')]
            cost_labels = ['10만원 이하', '10-50만원', '50-100만원', '100-200만원', '200만원+']
            
            filtered_df_copy = filtered_df.copy()
            filtered_df_copy['수리비구간'] = pd.cut(filtered_df_copy['수리비'], bins=cost_bins, labels=cost_labels)
            
            cost_distribution = filtered_df_copy['수리비구간'].value_counts()
            
            fig = px.bar(
                x=cost_distribution.index,
                y=cost_distribution.values,
                title="수리비 구간별 건수",
                color=cost_distribution.values,
                color_continuous_scale='Reds'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 수리비 통계
            st.write("**📊 수리비 통계**")
            stats = {
                '평균': filtered_df['수리비'].mean(),
                '중앙값': filtered_df['수리비'].median(),
                '최소값': filtered_df['수리비'].min(),
                '최대값': filtered_df['수리비'].max(),
                '표준편차': filtered_df['수리비'].std()
            }
            
            for key, value in stats.items():
                st.write(f"• **{key}**: {value:,.0f}원")
            
            # 고액 수리 케이스
            high_cost_threshold = filtered_df['수리비'].quantile(0.9)
            high_cost_cases = filtered_df[filtered_df['수리비'] >= high_cost_threshold]
            
            if not high_cost_cases.empty and '작업유형' in high_cost_cases.columns:
                st.write("**🚨 고액 수리 케이스 (상위 10%)**")
                high_cost_analysis = high_cost_cases['작업유형'].value_counts().head(5)
                
                for work_type, count in high_cost_analysis.items():
                    st.write(f"• {work_type}: {count}건")

# 월말 리포트 요약
st.markdown("---")
st.header("📋 월말 리포트 요약")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🎯 주요 성과 지표")
    
    metrics_data = [
        ("총 AS 건수", f"{total_cases:,}건"),
        ("총 수리비", f"{total_cost:,.0f}원"),
        ("건당 평균 수리비", f"{avg_cost_per_case:,.0f}원"),
        ("참여 정비자 수", f"{filtered_df['정비자'].nunique() if '정비자' in filtered_df.columns else 0}명"),
        ("관련 업체 수", f"{unique_clients}개"),
        ("수리 장비 수", f"{unique_equipment}대")
    ]
    
    for metric, value in metrics_data:
        st.write(f"• **{metric}**: {value}")

with col2:
    st.subheader("⚠️ 주요 이슈")
    
    issues = []
    
    # 자동 이슈 생성
    if '정비자소속' in filtered_df.columns and not filtered_df.empty:
        part_costs = filtered_df.groupby('정비자소속')['수리비'].sum()
        if len(part_costs) > 0:
            top_cost_part = part_costs.idxmax()
            top_cost_amount = part_costs.max()
            issues.append(f"🔴 **{top_cost_part}** 파트 수리비 최고 ({top_cost_amount:,.0f}원)")
    
    if client_col in filtered_df.columns and not filtered_df.empty:
        client_costs = filtered_df.groupby(client_col)['수리비'].sum()
        if len(client_costs) > 0:
            top_cost_client = client_costs.idxmax()
            top_cost_client_amount = client_costs.max()
            client_short = str(top_cost_client)[:20] + "..." if len(str(top_cost_client)) > 20 else str(top_cost_client)
            issues.append(f"🟡 **{client_short}** 업체 수리비 최고 ({top_cost_client_amount:,.0f}원)")
    
    if compare_month and case_change > 20:
        issues.append(f"📈 전월 대비 AS 건수 {case_change:.1f}% 증가")
    
    if compare_month and cost_change > 30:
        issues.append(f"💰 전월 대비 총 수리비 {cost_change:.1f}% 증가")
    
    if not issues:
        issues.append("✅ 특별한 이슈 없음")
    
    for issue in issues:
        st.write(f"• {issue}")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 리포트 다운로드")

col1, col2 = st.columns(2)

with col1:
    csv_data = filtered_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 상세 데이터 다운로드 (CSV)",
        data=csv_data,
        file_name=f"{selected_year}년{selected_month}월_AS상세데이터.csv",
        mime="text/csv"
    )

with col2:
    if '정비자소속' in filtered_df.columns and not filtered_df.empty:
        summary_data = filtered_df.groupby('정비자소속').agg({
            '관리번호': 'count',
            '수리비': 'sum'
        }).rename(columns={'관리번호': '건수'})
        
        summary_csv = summary_data.to_csv(encoding='utf-8-sig')
        st.download_button(
            label="📊 파트별 요약 (CSV)",
            data=summary_csv,
            file_name=f"{selected_year}년{selected_month}월_파트별요약.csv",
            mime="text/csv"
        )
