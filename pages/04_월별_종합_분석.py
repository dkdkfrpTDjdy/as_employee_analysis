# 4. pages/04_월별_종합_분석.py 전체 코드
import streamlit as st
import calendar
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.visualization import create_figure, get_image_download_link
import calendar

st.set_page_config(page_title="월별 종합 분석", layout="wide")
st.title("📅 월별 종합 분석 리포트")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs

# 수치형 데이터 안전 처리
if '수리비' not in df.columns:
    df['수리비'] = 0
    
df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)

if '수리시간' in df.columns:
    df['수리시간'] = pd.to_numeric(df['수리시간'], errors='coerce').fillna(0)

if '가동시간' in df.columns:
    df['가동시간'] = pd.to_numeric(df['가동시간'], errors='coerce').fillna(0)

# 날짜 전처리
if '정비일자' in df.columns:
    df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
    df['년월'] = df['정비일자'].dt.to_period('M')
    df['년'] = df['정비일자'].dt.year
    df['월'] = df['정비일자'].dt.month
else:
    st.error("정비일자 컬럼이 없습니다.")
    st.stop()

# 사이드바 - 분석 조건 선택
st.sidebar.header("📊 분석 조건 설정")

# 년도/월 선택
available_years = sorted(df['년'].dropna().unique(), reverse=True)
available_months = sorted(df['월'].dropna().unique())

if len(available_years) == 0 or len(available_months) == 0:
    st.error("분석 가능한 날짜 데이터가 없습니다.")
    st.stop()

selected_year = st.sidebar.selectbox("분석 년도", available_years)
selected_month = st.sidebar.selectbox("분석 월", available_months,
                                    format_func=lambda x: f"{int(x)}월 ({calendar.month_name[int(x)] if pd.notna(x) and 1 <= int(x) <= 12 else 'Unknown'})")

# 장비 구분
equipment_filter = st.sidebar.selectbox("장비 구분", ["전체", "지게차", "AWP", "기타"])

# 정비구분 필터
if '정비구분' in df.columns:
    maintenance_types = ['전체'] + list(df['정비구분'].dropna().unique())
    selected_maintenance_type = st.sidebar.selectbox("정비구분", maintenance_types)
else:
    selected_maintenance_type = "전체"

# 전월 대비 분석 옵션
compare_month = st.sidebar.checkbox("전월 대비 분석")

# 데이터 필터링
filtered_df = df[(df['년'] == selected_year) & (df['월'] == selected_month)].copy()

# 장비 구분 필터링
if equipment_filter != "전체":
    if equipment_filter == "지게차":
        if '자재내역' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['자재내역'].str.contains('지게차|FORKLIFT|전동|디젤', na=False, case=False)]
        elif '브랜드' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['브랜드'].str.contains('TOYOTA|HYUNDAI|DOOSAN', na=False, case=False)]
    elif equipment_filter == "AWP":
        if '자재내역' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['자재내역'].str.contains('AWP|고소작업대|수직형', na=False, case=False)]
        elif '브랜드' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['브랜드'].str.contains('JLG|GENIE|SKYJACK', na=False, case=False)]

if selected_maintenance_type != "전체" and '정비구분' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['정비구분'] == selected_maintenance_type]

# 전월 데이터 (비교용)
prev_month_df = pd.DataFrame()
if compare_month:
    if selected_month > 1:
        prev_month_df = df[(df['년'] == selected_year) & (df['월'] == selected_month-1)].copy()
    else:
        prev_month_df = df[(df['년'] == selected_year-1) & (df['월'] == 12)].copy()
    
    # 동일한 필터 적용
    if equipment_filter != "전체":
        if equipment_filter == "지게차":
            if '자재내역' in prev_month_df.columns:
                prev_month_df = prev_month_df[prev_month_df['자재내역'].str.contains('지게차|FORKLIFT|전동|디젤', na=False, case=False)]
        elif equipment_filter == "AWP":
            if '자재내역' in prev_month_df.columns:
                prev_month_df = prev_month_df[prev_month_df['자재내역'].str.contains('AWP|고소작업대|수직형', na=False, case=False)]

# 메인 제목
st.header(f"🗓️ {selected_year}년 {selected_month}월 ({equipment_filter}) 상세 분석 리포트")

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

# 증감률 계산
cases_change = ((total_cases - prev_total_cases) / prev_total_cases * 100) if prev_total_cases > 0 else 0
cost_change = ((total_cost - prev_total_cost) / prev_total_cost * 100) if prev_total_cost > 0 else 0
avg_change = ((avg_cost_per_case - prev_avg_cost) / prev_avg_cost * 100) if prev_avg_cost > 0 else 0

# 대시보드 상단 - 핵심 지표
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if compare_month and prev_total_cases > 0:
        st.metric("총 AS 건수", f"{total_cases:,}건", f"{cases_change:+.1f}%")
    else:
        st.metric("총 AS 건수", f"{total_cases:,}건")

with col2:
    if compare_month and prev_total_cost > 0:
        st.metric("총 수리비", f"{total_cost:,.0f}원", f"{cost_change:+.1f}%")
    else:
        st.metric("총 수리비", f"{total_cost:,.0f}원")

with col3:
    if compare_month and prev_avg_cost > 0:
        st.metric("건당 평균 수리비", f"{avg_cost_per_case:,.0f}원", f"{avg_change:+.1f}%")
    else:
        st.metric("건당 평균 수리비", f"{avg_cost_per_case:,.0f}원")

with col4:
    # 현장명 우선 사용
    if '현장명' in filtered_df.columns:
        unique_clients = filtered_df['현장명'].nunique()
    elif '업체명' in filtered_df.columns:
        unique_clients = filtered_df['업체명'].nunique()
    else:
        unique_clients = 0
    st.metric("관련 업체 수", f"{unique_clients}개")

with col5:
    unique_equipment = filtered_df['관리번호'].nunique()
    st.metric("수리 장비 수", f"{unique_equipment}대")

# 알림 기능
if avg_cost_per_case > df['수리비'].mean() * 1.5:
    st.error(f"⚠️ 이번 달 평균 수리비가 전체 평균보다 {((avg_cost_per_case/df['수리비'].mean()-1)*100):.1f}% 높습니다!")
elif total_cases > df.groupby(['년', '월']).size().mean() * 1.3:
    st.warning(f"📈 이번 달 AS 건수가 월평균보다 {((total_cases/df.groupby(['년', '월']).size().mean()-1)*100):.1f}% 높습니다!")

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "👥 정비자/파트별", "🔧 고장유형별", "⏱️ 시간분석", "🏢 업체/지역별", "🚛 장비별", "💰 수리비분석", "😊 만족도분석"
])

# 탭 1: 정비자/파트별 분석
with tab1:
    st.subheader("👥 정비자 및 소속파트별 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 파트별 건수 분석
        if '정비자소속' in filtered_df.columns:
            st.write("**📊 소속파트별 건수 및 비율**")
            
            part_analysis = filtered_df.groupby('정비자소속').agg({
                '관리번호': 'count',
                '수리비': 'sum'
            }).rename(columns={'관리번호': '건수', '수리비': '총수리비'})
            
            part_analysis['건수비율(%)'] = (part_analysis['건수'] / part_analysis['건수'].sum() * 100).round(1)
            part_analysis['평균수리비'] = (part_analysis['총수리비'] / part_analysis['건수']).round(0)
            part_analysis = part_analysis.sort_values('건수', ascending=False)
            
            # 파트별 건수 차트
            fig = px.bar(
                x=part_analysis.index,
                y=part_analysis['건수'],
                title="파트별 AS 건수",
                color=part_analysis['건수'],
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # 상세 테이블
            st.dataframe(
                part_analysis.style.format({
                    '총수리비': '{:,.0f}원',
                    '평균수리비': '{:,.0f}원',
                    '건수비율(%)': '{:.1f}%'
                }),
                use_container_width=True
            )
        else:
            st.info("정비자소속 정보가 없습니다.")
    
    with col2:
        # 개별 정비자 분석
        if '정비자' in filtered_df.columns:
            st.write("**👤 개별 정비자 성과 분석**")
            
            worker_analysis = filtered_df.groupby(['정비자', '정비자소속']).agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean'],
                '수리시간': 'mean' if '수리시간' in filtered_df.columns else lambda x: 0
            }).round(1)
            
            worker_analysis.columns = ['건수', '총수리비', '평균수리비', '평균수리시간']
            worker_analysis = worker_analysis.reset_index()
            worker_analysis = worker_analysis.sort_values('건수', ascending=False).head(10)
            
            # Top 10 정비자 차트
            if not worker_analysis.empty:
                fig = px.scatter(
                    worker_analysis,
                    x='건수',
                    y='평균수리비',
                    size='총수리비',
                    color='정비자소속',
                    hover_name='정비자',
                    title="정비자별 성과 (건수 vs 평균수리비)"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    worker_analysis.style.format({
                        '총수리비': '{:,.0f}원',
                        '평균수리비': '{:,.0f}원',
                        '평균수리시간': '{:.1f}시간'
                    }),
                    use_container_width=True
                )
            else:
                st.info("정비자별 데이터가 없습니다.")
        else:
            st.info("정비자 정보가 없습니다.")

# 탭 2: 고장유형별 분석
with tab2:
    st.subheader("🔧 고장유형별 상세 분석")
    
    # 대분류/중분류/소분류 분석
    col1, col2, col3 = st.columns(3)
    
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
                        title=f"{title} 건수 분포"
                    )
                    fig.update_layout(height=300, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 상위 5개 표시
                    st.write("**Top 5:**")
                    for idx, (cat, row) in enumerate(category_analysis.head(5).iterrows()):
                        st.write(f"{idx+1}. {cat}: {row['건수']}건 ({row['비율(%)']:.1f}%)")
                else:
                    st.info(f"{title} 데이터가 없습니다.")
            else:
                st.info(f"{title} 정보가 없습니다.")
    
    # 조합된 정비사유 분석 (대>중>소)
    if all(col in filtered_df.columns for col in ['작업유형', '정비대상', '정비작업']):
        st.write("**📋 상세 정비사유 분석 (대>중>소 조합)**")
        
        filtered_df_copy = filtered_df.copy()
        filtered_df_copy['정비사유조합'] = (filtered_df_copy['작업유형'].astype(str) + ' > ' + 
                                       filtered_df_copy['정비대상'].astype(str) + ' > ' + 
                                       filtered_df_copy['정비작업'].astype(str))
        
        repair_reason_analysis = filtered_df_copy.groupby('정비사유조합').agg({
            '관리번호': 'count',
            '수리비': ['sum', 'mean'],
            '수리시간': 'mean' if '수리시간' in filtered_df_copy.columns else lambda x: 0
        }).round(1)
        
        repair_reason_analysis.columns = ['건수', '총수리비', '평균수리비', '평균수리시간']
        repair_reason_analysis = repair_reason_analysis.sort_values('건수', ascending=False).head(15)
        
        if not repair_reason_analysis.empty:
            st.dataframe(
                repair_reason_analysis.style.format({
                    '총수리비': '{:,.0f}원',
                    '평균수리비': '{:,.0f}원',
                    '평균수리시간': '{:.1f}시간'
                }),
                use_container_width=True
            )
        else:
            st.info("정비사유 조합 데이터가 없습니다.")

# 탭 3: 시간분석
with tab3:
    st.subheader("⏱️ 가동시간 및 수리시간 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 가동시간 분포 분석
        if '가동시간' in filtered_df.columns and filtered_df['가동시간'].sum() > 0:
            st.write("**⚡ 가동시간 분포 분석**")
            
            # 가동시간 구간별 분석
            operation_time_bins = [0, 1000, 3000, 5000, 8000, float('inf')]
            operation_time_labels = ['0-1000h', '1000-3000h', '3000-5000h', '5000-8000h', '8000h+']
            
            filtered_df_copy = filtered_df.copy()
            filtered_df_copy['가동시간구간'] = pd.cut(filtered_df_copy['가동시간'], 
                                                 bins=operation_time_bins, 
                                                 labels=operation_time_labels)
            
            operation_analysis = filtered_df_copy.groupby('가동시간구간').agg({
                '관리번호': 'count',
                '수리비': 'mean',
                '수리시간': 'mean' if '수리시간' in filtered_df_copy.columns else lambda x: 0
            }).round(1)
            
            operation_analysis.columns = ['건수', '평균수리비', '평균수리시간']
            
            # 가동시간과 수리비 관계 차트
            if not operation_analysis.empty:
                fig = px.bar(
                    x=operation_analysis.index,
                    y=operation_analysis['건수'],
                    title="가동시간 구간별 AS 건수"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    operation_analysis.style.format({
                        '평균수리비': '{:,.0f}원',
                        '평균수리시간': '{:.1f}시간'
                    }),
                    use_container_width=True
                )
            else:
                st.info("가동시간 구간별 데이터가 없습니다.")
        else:
            st.info("가동시간 정보가 없습니다.")
    
    with col2:
        # 수리시간 분석
        if '수리시간' in filtered_df.columns and filtered_df['수리시간'].sum() > 0:
            st.write("**🔧 수리시간 상세 분석**")
            
            # 분류별 수리시간 분석
            if '작업유형' in filtered_df.columns:
                repair_time_analysis = filtered_df.groupby('작업유형').agg({
                    '수리시간': ['count', 'sum', 'mean', 'min', 'max']
                }).round(1)
                
                repair_time_analysis.columns = ['건수', '총수리시간', '평균수리시간', '최단시간', '최장시간']
                repair_time_analysis = repair_time_analysis.sort_values('총수리시간', ascending=False)
                
                # 수리시간 분포 차트
                if not repair_time_analysis.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=repair_time_analysis.index,
                        y=repair_time_analysis['총수리시간'],
                        name='총수리시간',
                        marker_color='lightblue'
                    ))
                    
                    fig.update_layout(
                        title="작업유형별 총 수리시간",
                        xaxis_title="작업유형",
                        yaxis_title="총 수리시간 (시간)",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.dataframe(
                        repair_time_analysis.style.format({
                            '총수리시간': '{:.1f}시간',
                            '평균수리시간': '{:.1f}시간',
                            '최단시간': '{:.1f}시간',
                            '최장시간': '{:.1f}시간'
                        }),
                        use_container_width=True
                    )
                else:
                    st.info("작업유형별 수리시간 데이터가 없습니다.")
        else:
            st.info("수리시간 정보가 없습니다.")
    
    # 가동시간과 수리시간의 연계성 분석
    if all(col in filtered_df.columns for col in ['가동시간', '수리시간']) and \
       filtered_df['가동시간'].sum() > 0 and filtered_df['수리시간'].sum() > 0:
        st.write("**🔗 가동시간과 수리시간 연계성 분석**")
        
        # 산점도로 관계 분석
        fig = px.scatter(
            filtered_df,
            x='가동시간',
            y='수리시간',
            color='작업유형' if '작업유형' in filtered_df.columns else None,
            title="가동시간 vs 수리시간 관계",
            trendline="ols"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # 상관관계 계산
        correlation = filtered_df['가동시간'].corr(filtered_df['수리시간'])
        
        if correlation > 0.3:
            st.success(f"🔗 양의 상관관계 (상관계수: {correlation:.3f}) - 가동시간이 길수록 수리시간도 증가하는 경향")
        elif correlation < -0.3:
            st.warning(f"🔗 음의 상관관계 (상관계수: {correlation:.3f}) - 가동시간이 길수록 수리시간은 감소하는 경향")
        else:
            st.info(f"🔗 상관관계 약함 (상관계수: {correlation:.3f}) - 가동시간과 수리시간 간 뚜렷한 관계없음")

# 탭 4: 업체/지역별 분석
with tab4:
    st.subheader("🏢 업체 및 지역별 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 지역별 분석
        if '지역' in filtered_df.columns:
            st.write("**🗺️ 지역별 AS 현황**")
            
            # 현장명 우선 사용
            client_col = None
            if '현장명' in filtered_df.columns:
                client_col = '현장명'
            elif '업체명' in filtered_df.columns:
                client_col = '업체명'
            
            if client_col:
                region_analysis = filtered_df.groupby('지역').agg({
                    '관리번호': 'count',
                    '수리비': 'sum',
                    client_col: 'nunique'
                }).rename(columns={'관리번호': '건수', client_col: '업체수'})
            else:
                region_analysis = filtered_df.groupby('지역').agg({
                    '관리번호': 'count',
                    '수리비': 'sum'
                }).rename(columns={'관리번호': '건수'})
                region_analysis['업체수'] = 0
            
            region_analysis['평균수리비'] = (region_analysis['수리비'] / region_analysis['건수']).round(0)
            region_analysis = region_analysis.sort_values('건수', ascending=False)
            
            # 지역별 건수 맵
            if not region_analysis.empty:
                fig = px.bar(
                    x=region_analysis.index,
                    y=region_analysis['건수'],
                    title="지역별 AS 건수",
                    color=region_analysis['건수'],
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    region_analysis.style.format({
                        '수리비': '{:,.0f}원',
                        '평균수리비': '{:,.0f}원'
                    }),
                    use_container_width=True
                )
            else:
                st.info("지역별 데이터가 없습니다.")
        else:
            st.info("지역 정보가 없습니다.")
    
    with col2:
        # 업체별 상세 분석
        st.write("**🏢 주요 업체별 AS 현황**")
        
        # 현장명 우선 사용
        client_col = None
        if '현장명' in filtered_df.columns:
            client_col = '현장명'
        elif '업체명' in filtered_df.columns:
            client_col = '업체명'
        
        if client_col:
            client_analysis = filtered_df.groupby(client_col).agg({
                '관리번호': ['count', lambda x: x.nunique()],
                '수리비': 'sum'
            })
            client_analysis.columns = ['건수', '수리장비수', '총수리비']
            client_analysis['건당평균수리비'] = (client_analysis['총수리비'] / client_analysis['건수']).round(0)
            
            # 수리비 기준 상위 10개 업체
            top_clients = client_analysis.nlargest(10, '총수리비')
            
            if not top_clients.empty:
                # 업체명이 너무 길면 줄임
                top_clients_display = top_clients.copy()
                top_clients_display.index = [name[:15] + "..." if len(str(name)) > 15 else str(name) for name in top_clients_display.index]
                
                fig = px.bar(
                    x=top_clients_display['총수리비'],
                    y=top_clients_display.index,
                    orientation='h',
                    title="수리비 상위 10개 업체",
                    color=top_clients_display['총수리비'],
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    top_clients.style.format({
                        '총수리비': '{:,.0f}원',
                        '건당평균수리비': '{:,.0f}원'
                    }),
                    use_container_width=True
                )
            else:
                st.info("업체별 데이터가 없습니다.")
        else:
            st.info("업체 정보가 없습니다.")

# 탭 5: 장비별 분석
with tab5:
    st.subheader("🚛 장비별 상세 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 제조사별 분석
        if '브랜드' in filtered_df.columns:
            st.write("**🏭 제조사별 건수 및 비율**")
            
            brand_analysis = filtered_df.groupby('브랜드').agg({
                '관리번호': 'count',
                '수리비': 'sum'
            }).rename(columns={'관리번호': '건수'})
            
            brand_analysis['비율(%)'] = (brand_analysis['건수'] / brand_analysis['건수'].sum() * 100).round(1)
            brand_analysis['평균수리비'] = (brand_analysis['수리비'] / brand_analysis['건수']).round(0)
            brand_analysis = brand_analysis.sort_values('건수', ascending=False)
            
            # 제조사별 파이 차트
            if not brand_analysis.empty:
                fig = px.pie(
                    values=brand_analysis['건수'],
                    names=brand_analysis.index,
                    title="제조사별 AS 건수 비율"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    brand_analysis.style.format({
                        '수리비': '{:,.0f}원',
                        '평균수리비': '{:,.0f}원',
                        '비율(%)': '{:.1f}%'
                    }),
                    use_container_width=True
                )
            else:
                st.info("브랜드별 데이터가 없습니다.")
        else:
            st.info("브랜드 정보가 없습니다.")
    
    with col2:
        # 도입연도별 분석
        if '제조년도' in filtered_df.columns:
            st.write("**📅 도입연도별 AS 현황**")
            
            # 연식 구간별 분석
            current_year = pd.Timestamp.now().year
            filtered_df_copy = filtered_df.copy()
            filtered_df_copy['장비연식'] = current_year - pd.to_numeric(filtered_df_copy['제조년도'], errors='coerce')
            
            age_bins = [0, 5, 10, 15, 20, float('inf')]
            age_labels = ['0-5년', '6-10년', '11-15년', '16-20년', '20년+']
            
            filtered_df_copy['연식구간'] = pd.cut(filtered_df_copy['장비연식'], bins=age_bins, labels=age_labels)
            
            age_analysis = filtered_df_copy.groupby('연식구간').agg({
                '관리번호': 'count',
                '수리비': 'mean'
            }).rename(columns={'관리번호': '건수', '수리비': '평균수리비'})
            
            # 연식별 AS 건수 차트
            if not age_analysis.empty:
                fig = px.bar(
                    x=age_analysis.index,
                    y=age_analysis['건수'],
                    title="장비 연식별 AS 건수",
                    color=age_analysis['건수'],
                    color_continuous_scale='Oranges'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    age_analysis.style.format({
                        '평균수리비': '{:,.0f}원'
                    }),
                    use_container_width=True
                )
            else:
                st.info("연식별 데이터가 없습니다.")
        else:
            st.info("제조년도 정보가 없습니다.")

# 탭 6: 수리비 분석
with tab6:
    st.subheader("💰 수리비 상세 분석")
    
    if filtered_df['수리비'].sum() > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            # 수리비 구간별 분석
            st.write("**💵 수리비 구간별 분포**")
            
            cost_bins = [0, 100000, 500000, 1000000, 2000000, float('inf')]
            cost_labels = ['10만원 이하', '10-50만원', '50-100만원', '100-200만원', '200만원+']
            
            filtered_df_copy = filtered_df.copy()
            filtered_df_copy['수리비구간'] = pd.cut(filtered_df_copy['수리비'], bins=cost_bins, labels=cost_labels)
            
            cost_distribution = filtered_df_copy['수리비구간'].value_counts()
            
            if not cost_distribution.empty:
                fig = px.bar(
                    x=cost_distribution.index,
                    y=cost_distribution.values,
                    title="수리비 구간별 건수 분포",
                    color=cost_distribution.values,
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            # 통계 정보
            st.write("**📊 수리비 통계**")
            st.write(f"• 평균: {filtered_df['수리비'].mean():,.0f}원")
            st.write(f"• 중앙값: {filtered_df['수리비'].median():,.0f}원")
            st.write(f"• 최소값: {filtered_df['수리비'].min():,.0f}원")
            st.write(f"• 최대값: {filtered_df['수리비'].max():,.0f}원")
            st.write(f"• 표준편차: {filtered_df['수리비'].std():,.0f}원")
        
        with col2:
            # 고액 수리 케이스 분석
            st.write("**🚨 고액 수리 케이스 분석**")
            
            # 상위 10% 고액 케이스
            high_cost_threshold = filtered_df['수리비'].quantile(0.9)
            high_cost_cases = filtered_df[filtered_df['수리비'] >= high_cost_threshold]
            
            if not high_cost_cases.empty and '작업유형' in high_cost_cases.columns:
                high_cost_analysis = high_cost_cases.groupby('작업유형').agg({
                    '관리번호': 'count',
                    '수리비': ['mean', 'max']
                })
                high_cost_analysis.columns = ['건수', '평균수리비', '최대수리비']
                high_cost_analysis = high_cost_analysis.sort_values('평균수리비', ascending=False)
                
                fig = px.bar(
                    x=high_cost_analysis.index,
                    y=high_cost_analysis['평균수리비'],
                    title=f"고액 수리 케이스 작업유형별 분석 (상위 10%)",
                    color=high_cost_analysis['평균수리비'],
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    high_cost_analysis.style.format({
                        '평균수리비': '{:,.0f}원',
                        '최대수리비': '{:,.0f}원'
                    }),
                    use_container_width=True
                )
            else:
                st.info("고액 수리 케이스가 없습니다.")
    else:
        st.info("수리비 정보가 없습니다.")

# 탭 7: 만족도 분석 (새로 추가)
with tab7:
    st.subheader("😊 고객 만족도 분석")
    
    if '만족도_평균' in filtered_df.columns and filtered_df['만족도_평균'].notna().any():
        satisfaction_data = filtered_df[filtered_df['만족도_평균'].notna()].copy()
        
        if not satisfaction_data.empty:
            # 만족도 기본 통계
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_responses = len(satisfaction_data)
                st.metric("응답 건수", f"{total_responses}건")
            
            with col2:
                avg_satisfaction = satisfaction_data['만족도_평균'].mean()
                st.metric("평균 만족도", f"{avg_satisfaction:.2f}점")
            
            with col3:
                high_satisfaction_rate = (satisfaction_data['만족도_평균'] >= 4.0).sum() / len(satisfaction_data) * 100
                st.metric("고만족 비율", f"{high_satisfaction_rate:.1f}%")
            
            with col4:
                low_satisfaction_rate = (satisfaction_data['만족도_평균'] < 3.0).sum() / len(satisfaction_data) * 100
                st.metric("저만족 비율", f"{low_satisfaction_rate:.1f}%")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 질문별 만족도 분석
                st.write("**📋 질문별 만족도 점수**")
                
                satisfaction_categories = [col for col in satisfaction_data.columns if '만족도_' in col and col != '만족도_평균']
                
                if satisfaction_categories:
                    category_scores = {}
                    for col in satisfaction_categories:
                        category = col.replace('만족도_', '')
                        score = satisfaction_data[col].mean()
                        count = satisfaction_data[col].notna().sum()
                        if count > 0:
                            category_scores[category] = score
                    
                    if category_scores:
                        category_df = pd.DataFrame(list(category_scores.items()), columns=['질문카테고리', '평균점수'])
                        category_df = category_df.sort_values('평균점수', ascending=True)
                        
                        fig = px.bar(
                            category_df,
                            x='평균점수',
                            y='질문카테고리',
                            orientation='h',
                            title="질문별 평균 만족도",
                            color='평균점수',
                            color_continuous_scale='RdYlGn'
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 개선이 필요한 영역 식별
                        st.write("**🔍 개선 필요 영역:**")
                        for category, score in category_scores.items():
                            if score < 4.0:
                                score_color = "🔴" if score < 3.5 else "🟡"
                                st.write(f"{score_color} {category}: {score:.2f}점")
                else:
                    st.info("질문별 세부 데이터가 없습니다.")
            
            with col2:
                # 파트별 만족도 분석
                if '정비자소속' in satisfaction_data.columns:
                    st.write("**👥 파트별 만족도 분석**")
                    
                    part_satisfaction = satisfaction_data.groupby('정비자소속').agg({
                        '만족도_평균': ['mean', 'count'],
                        '수리비': 'mean'
                    }).round(2)
                    
                    part_satisfaction.columns = ['평균만족도', '응답수', '평균수리비']
                    part_satisfaction = part_satisfaction.reset_index()
                    part_satisfaction = part_satisfaction[part_satisfaction['응답수'] >= min_responses]
                    
                    if not part_satisfaction.empty:
                        part_satisfaction = part_satisfaction.sort_values('평균만족도', ascending=True)
                        
                        fig2 = px.bar(
                            part_satisfaction,
                            x='평균만족도',
                            y='정비자소속',
                            orientation='h',
                            title="파트별 평균 만족도",
                            color='평균만족도',
                            color_continuous_scale='RdYlGn'
                        )
                        fig2.update_layout(height=400)
                        st.plotly_chart(fig2, use_container_width=True)
                        
                        # 파트별 만족도 순위
                        st.write("**파트별 만족도 순위:**")
                        for idx, (_, row) in enumerate(part_satisfaction.sort_values('평균만족도', ascending=False).iterrows()):
                            rank_icon = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
                            satisfaction_icon = "🟢" if row['평균만족도'] >= 4.0 else "🟡" if row['평균만족도'] >= 3.5 else "🔴"
                            st.write(f"{rank_icon} {satisfaction_icon} {row['정비자소속']}: {row['평균만족도']:.2f}점")
                    else:
                        st.info("응답 수가 충분하지 않습니다.")
                else:
                    st.info("파트별 데이터가 없습니다.")
            
            # 만족도와 수리비/시간 상관관계 분석
            st.write("**🔗 만족도 영향 요인 분석**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # 수리비와 만족도 상관관계
                if satisfaction_data['수리비'].sum() > 0:
                    correlation_cost = satisfaction_data['만족도_평균'].corr(satisfaction_data['수리비'])
                    
                    if abs(correlation_cost) > 0.3:
                        direction = "높을수록" if correlation_cost > 0 else "낮을수록"
                        strength = "강한" if abs(correlation_cost) > 0.5 else "중간"
                        st.write(f"💰 **수리비 영향**: {strength} 상관관계")
                        st.write(f"수리비가 {direction} 만족도 증가")
                        st.write(f"상관계수: {correlation_cost:.3f}")
                    else:
                        st.write("💰 **수리비 영향**: 약한 관계")
                        st.write(f"상관계수: {correlation_cost:.3f}")
            
            with col2:
                # 수리시간과 만족도 상관관계
                if '수리시간' in satisfaction_data.columns and satisfaction_data['수리시간'].sum() > 0:
                    correlation_time = satisfaction_data['만족도_평균'].corr(satisfaction_data['수리시간'])
                    
                    if abs(correlation_time) > 0.3:
                        direction = "길수록" if correlation_time > 0 else "짧을수록"
                        strength = "강한" if abs(correlation_time) > 0.5 else "중간"
                        st.write(f"⏱️ **수리시간 영향**: {strength} 상관관계")
                        st.write(f"수리시간이 {direction} 만족도 증가")
                        st.write(f"상관계수: {correlation_time:.3f}")
                    else:
                        st.write("⏱️ **수리시간 영향**: 약한 관계")
                        st.write(f"상관계수: {correlation_time:.3f}")
                else:
                    st.info("수리시간 데이터 없음")
            
            with col3:
                # 가동시간과 만족도 상관관계
                if '가동시간' in satisfaction_data.columns and satisfaction_data['가동시간'].sum() > 0:
                    correlation_operation = satisfaction_data['만족도_평균'].corr(satisfaction_data['가동시간'])
                    
                    if abs(correlation_operation) > 0.3:
                        direction = "길수록" if correlation_operation > 0 else "짧을수록"
                        strength = "강한" if abs(correlation_operation) > 0.5 else "중간"
                        st.write(f"🔧 **가동시간 영향**: {strength} 상관관계")
                        st.write(f"가동시간이 {direction} 만족도 증가")
                        st.write(f"상관계수: {correlation_operation:.3f}")
                    else:
                        st.write("🔧 **가동시간 영향**: 약한 관계")
                        st.write(f"상관계수: {correlation_operation:.3f}")
                else:
                    st.info("가동시간 데이터 없음")
        else:
            st.info("만족도 응답 데이터가 없습니다.")
    else:
        st.info("만족도 데이터가 없습니다. 만족도 조사 데이터를 업로드해주세요.")

# 하단 - 월말 리포트 요약
st.markdown("---")
st.header("📋 월말 리포트 요약")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🎯 주요 성과 지표")
    
    # 주요 지표들을 카드 형태로 표시
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
    st.subheader("⚠️ 주의사항 및 개선점")
    
    recommendations = []
    
    # 자동 추천사항 생성
    if '정비자소속' in filtered_df.columns and not filtered_df.empty:
        part_costs = filtered_df.groupby('정비자소속')['수리비'].sum()
        if len(part_costs) > 0:
            top_cost_part = part_costs.idxmax()
            top_cost_amount = part_costs.max()
            recommendations.append(f"🔴 **{top_cost_part}** 파트의 수리비가 {top_cost_amount:,.0f}원으로 가장 높음")
    
    # 현장명 우선 사용
    client_col = None
    if '현장명' in filtered_df.columns:
        client_col = '현장명'
    elif '업체명' in filtered_df.columns:
        client_col = '업체명'
    
    if client_col and not filtered_df.empty:
        client_costs = filtered_df.groupby(client_col)['수리비'].sum()
        if len(client_costs) > 0:
            top_cost_client = client_costs.idxmax()
            top_cost_client_amount = client_costs.max()
            if len(str(top_cost_client)) > 20:
                top_cost_client = str(top_cost_client)[:20] + "..."
            recommendations.append(f"🟡 **{top_cost_client}** 업체의 수리비가 {top_cost_client_amount:,.0f}원으로 높음")
    
    if avg_cost_per_case > 500000:
        recommendations.append(f"🟠 건당 평균 수리비({avg_cost_per_case:,.0f}원)가 높은 편임")
    
    if compare_month and cases_change > 20:
        recommendations.append(f"📈 전월 대비 AS 건수가 {cases_change:.1f}% 증가")
    
    if compare_month and cost_change > 30:
        recommendations.append(f"💰 전월 대비 총 수리비가 {cost_change:.1f}% 증가")
    
    if not recommendations:
        recommendations.append("✅ 특별한 주의사항 없음")
    
    for rec in recommendations:
        st.write(f"• {rec}")

# 데이터 다운로드 기능
st.markdown("---")
st.subheader("📥 리포트 다운로드")

col1, col2, col3 = st.columns(3)

with col1:
    # 필터링된 데이터 다운로드
    if not filtered_df.empty:
        csv_data = filtered_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📄 상세 데이터 다운로드 (CSV)",
            data=csv_data,
            file_name=f"{selected_year}년{selected_month}월_AS상세데이터.csv",
            mime="text/csv"
        )

with col2:
    # 요약 리포트 다운로드 (파트별)
    if '정비자소속' in filtered_df.columns and not filtered_df.empty:
        client_col = '현장명' if '현장명' in filtered_df.columns else '업체명' if '업체명' in filtered_df.columns else None
        
        if client_col:
            summary_data = filtered_df.groupby('정비자소속').agg({
                '관리번호': 'count',
                '수리비': 'sum',
                client_col: 'nunique'
            }).rename(columns={'관리번호': '건수', client_col: '업체수'})
        else:
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

with col3:
    # 업체별 리포트 다운로드
    client_col = '현장명' if '현장명' in filtered_df.columns else '업체명' if '업체명' in filtered_df.columns else None
    
    if client_col and not filtered_df.empty:
        client_summary = filtered_df.groupby(client_col).agg({
            '관리번호': 'count',
            '수리비': 'sum',
            '지역': 'first' if '지역' in filtered_df.columns else lambda x: ''
        }).rename(columns={'관리번호': '건수'})
        
        client_csv = client_summary.to_csv(encoding='utf-8-sig')
        st.download_button(
            label="🏢 업체별 요약 (CSV)",
            data=client_csv,
            file_name=f"{selected_year}년{selected_month}월_업체별요약.csv",
            mime="text/csv"
        )

