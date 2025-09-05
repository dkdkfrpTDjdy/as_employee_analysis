# pages/04_월별_종합_분석.py

import streamlit as st
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

if 'df_maintenance' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df_maintenance

# 날짜 전처리
df['년월'] = df['정비일자'].dt.to_period('M')
df['년'] = df['정비일자'].dt.year
df['월'] = df['정비일자'].dt.month

# 사이드바 - 분석 조건 선택
st.sidebar.header("📊 분석 조건 설정")

# 년도/월 선택
available_years = sorted(df['년'].dropna().unique(), reverse=True)
available_months = sorted(df['월'].dropna().unique())

selected_year = st.sidebar.selectbox("분석 년도", available_years)
selected_month = st.sidebar.selectbox("분석 월", available_months, 
                                     format_func=lambda x: f"{x}월 ({calendar.month_name[x]})")

# 장비 구분
equipment_filter = st.sidebar.selectbox("장비 구분", ["전체", "지게차", "AWP"])

# 정비구분 필터
if '정비구분' in df.columns:
    maintenance_types = ['전체'] + list(df['정비구분'].dropna().unique())
    selected_maintenance_type = st.sidebar.selectbox("정비구분", maintenance_types)
else:
    selected_maintenance_type = "전체"

# 데이터 필터링
filtered_df = df[(df['년'] == selected_year) & (df['월'] == selected_month)].copy()

if equipment_filter != "전체":
    if equipment_filter == "지게차" and '자재내역' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['자재내역'].str.contains('지게차|FORKLIFT|전동|디젤', na=False, case=False)]
    elif equipment_filter == "AWP" and '자재내역' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['자재내역'].str.contains('AWP|고소작업대|수직형', na=False, case=False)]

if selected_maintenance_type != "전체" and '정비구분' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['정비구분'] == selected_maintenance_type]

# 메인 제목
st.header(f"🗓️ {selected_year}년 {selected_month}월 ({equipment_filter}) 상세 분석 리포트")

if filtered_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 기본 통계
total_cases = len(filtered_df)
total_cost = filtered_df['수리비'].sum() if '수리비' in filtered_df.columns else 0
avg_cost_per_case = total_cost / total_cases if total_cases > 0 else 0

# 대시보드 상단 - 핵심 지표
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("총 AS 건수", f"{total_cases:,}건")

with col2:
    st.metric("총 수리비", f"{total_cost:,.0f}원")

with col3:
    st.metric("건당 평균 수리비", f"{avg_cost_per_case:,.0f}원")

with col4:
    unique_clients = filtered_df['현장명'].nunique() if '현장명' in filtered_df.columns else 0
    st.metric("관련 업체 수", f"{unique_clients}개")

with col5:
    unique_equipment = filtered_df['관리번호'].nunique()
    st.metric("수리 장비 수", f"{unique_equipment}대")

st.markdown("---")

# 탭으로 구분된 상세 분석
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "👥 정비자/파트별", "🔧 고장유형별", "⏱️ 시간분석", "🏢 업체/지역별", "🚛 장비별", "💰 수리비분석"
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
                st.info(f"{title} 정보가 없습니다.")
    
    # 조합된 정비사유 분석 (대>중>소)
    if all(col in filtered_df.columns for col in ['작업유형', '정비대상', '정비작업']):
        st.write("**📋 상세 정비사유 분석 (대>중>소 조합)**")
        
        filtered_df['정비사유조합'] = (filtered_df['작업유형'].astype(str) + ' > ' + 
                                   filtered_df['정비대상'].astype(str) + ' > ' + 
                                   filtered_df['정비작업'].astype(str))
        
        repair_reason_analysis = filtered_df.groupby('정비사유조합').agg({
            '관리번호': 'count',
            '수리비': ['sum', 'mean'],
            '수리시간': 'mean' if '수리시간' in filtered_df.columns else lambda x: 0
        }).round(1)
        
        repair_reason_analysis.columns = ['건수', '총수리비', '평균수리비', '평균수리시간']
        repair_reason_analysis = repair_reason_analysis.sort_values('건수', ascending=False).head(15)
        
        st.dataframe(
            repair_reason_analysis.style.format({
                '총수리비': '{:,.0f}원',
                '평균수리비': '{:,.0f}원',
                '평균수리시간': '{:.1f}시간'
            }),
            use_container_width=True
        )

# 탭 3: 시간분석
with tab3:
    st.subheader("⏱️ 가동시간 및 수리시간 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 가동시간 분포 분석
        if '가동시간' in filtered_df.columns:
            st.write("**⚡ 가동시간 분포 분석**")
            
            # 가동시간 구간별 분석
            operation_time_bins = [0, 1000, 3000, 5000, 8000, float('inf')]
            operation_time_labels = ['0-1000h', '1000-3000h', '3000-5000h', '5000-8000h', '8000h+']
            
            filtered_df['가동시간구간'] = pd.cut(filtered_df['가동시간'], 
                                             bins=operation_time_bins, 
                                             labels=operation_time_labels)
            
            operation_analysis = filtered_df.groupby('가동시간구간').agg({
                '관리번호': 'count',
                '수리비': 'mean',
                '수리시간': 'mean' if '수리시간' in filtered_df.columns else lambda x: 0
            }).round(1)
            
            operation_analysis.columns = ['건수', '평균수리비', '평균수리시간']
            
            # 가동시간과 수리비 관계 차트
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
            st.info("가동시간 정보가 없습니다.")
    
    with col2:
        # 수리시간 분석
        if '수리시간' in filtered_df.columns:
            st.write("**🔧 수리시간 상세 분석**")
            
            # 분류별 수리시간 분석
            if '작업유형' in filtered_df.columns:
                repair_time_analysis = filtered_df.groupby('작업유형').agg({
                    '수리시간': ['count', 'sum', 'mean', 'min', 'max']
                }).round(1)
                
                repair_time_analysis.columns = ['건수', '총수리시간', '평균수리시간', '최단시간', '최장시간']
                repair_time_analysis = repair_time_analysis.sort_values('총수리시간', ascending=False)
                
                # 수리시간 분포 차트
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
            st.info("수리시간 정보가 없습니다.")
    
    # 가동시간과 수리시간의 연계성 분석
    if all(col in filtered_df.columns for col in ['가동시간', '수리시간']):
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
            
            region_analysis = filtered_df.groupby('지역').agg({
                '관리번호': 'count',
                '수리비': 'sum',
                '현장명': 'nunique'
            }).rename(columns={'관리번호': '건수', '현장명': '업체수'})
            
            region_analysis['평균수리비'] = (region_analysis['수리비'] / region_analysis['건수']).round(0)
            region_analysis = region_analysis.sort_values('건수', ascending=False)
            
            # 지역별 건수 맵
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
            st.info("지역 정보가 없습니다.")
    
    with col2:
        # 업체별 상세 분석
        if '현장명' in filtered_df.columns:
            st.write("**🏢 주요 업체별 AS 현황**")
            
            client_analysis = filtered_df.groupby('현장명').agg({
                '관리번호': 'count',
                '수리비': 'sum',
                '관리번호': lambda x: x.nunique()  # 수리한 장비 수
            })
            client_analysis.columns = ['건수', '총수리비', '수리장비수']
            client_analysis['건당평균수리비'] = (client_analysis['총수리비'] / client_analysis['건수']).round(0)
            
            # 수리비 기준 상위 10개 업체
            top_clients = client_analysis.nlargest(10, '총수리비')
            
            fig = px.bar(
                x=top_clients['총수리비'],
                y=top_clients.index,
                orientation='h',
                title="수리비 상위 10개 업체",
                color=top_clients['총수리비'],
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
            st.info("브랜드 정보가 없습니다.")
    
    with col2:
        # 도입연도별 분석
        if '제조년도' in filtered_df.columns:
            st.write("**📅 도입연도별 AS 현황**")
            
            # 연식 구간별 분석
            current_year = pd.Timestamp.now().year
            filtered_df['장비연식'] = current_year - pd.to_numeric(filtered_df['제조년도'], errors='coerce')
            
            age_bins = [0, 5, 10, 15, 20, float('inf')]
            age_labels = ['0-5년', '6-10년', '11-15년', '16-20년', '20년+']
            
            filtered_df['연식구간'] = pd.cut(filtered_df['장비연식'], bins=age_bins, labels=age_labels)
            
            age_analysis = filtered_df.groupby('연식구간').agg({
                '관리번호': 'count',
                '수리비': 'mean'
            }).rename(columns={'관리번호': '건수', '수리비': '평균수리비'})
            
            # 연식별 AS 건수 차트
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
            st.info("제조년도 정보가 없습니다.")

# 탭 6: 수리비 분석
with tab6:
    st.subheader("💰 수리비 상세 분석")
    
    if '수리비' in filtered_df.columns:
        col1, col2 = st.columns(2)
        
        with col1:
            # 수리비 구간별 분석
            st.write("**💵 수리비 구간별 분포**")
            
            cost_bins = [0, 100000, 500000, 1000000, 2000000, float('inf')]
            cost_labels = ['10만원 이하', '10-50만원', '50-100만원', '100-200만원', '200만원+']
            
            filtered_df['수리비구간'] = pd.cut(filtered_df['수리비'], bins=cost_bins, labels=cost_labels)
            
            cost_distribution = filtered_df['수리비구간'].value_counts()
            
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
            
            if not high_cost_cases.empty:
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
    if '정비자소속' in filtered_df.columns:
        part_costs = filtered_df.groupby('정비자소속')['수리비'].sum()
        if len(part_costs) > 0:
            top_cost_part = part_costs.idxmax()
            top_cost_amount = part_costs.max()
            recommendations.append(f"🔴 **{top_cost_part}** 파트의 수리비가 {top_cost_amount:,.0f}원으로 가장 높음")
    
    if '현장명' in filtered_df.columns:
        client_costs = filtered_df.groupby('현장명')['수리비'].sum()
        if len(client_costs) > 0:
            top_cost_client = client_costs.idxmax()
            top_cost_client_amount = client_costs.max()
            if len(top_cost_client) > 20:
                top_cost_client = top_cost_client[:20] + "..."
            recommendations.append(f"🟡 **{top_cost_client}** 업체의 수리비가 {top_cost_client_amount:,.0f}원으로 높음")
    
    if avg_cost_per_case > 500000:
        recommendations.append(f"🟠 건당 평균 수리비({avg_cost_per_case:,.0f}원)가 높은 편임")
    
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
    csv_data = filtered_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 상세 데이터 다운로드 (CSV)",
        data=csv_data,
        file_name=f"{selected_year}년{selected_month}월_AS상세데이터.csv",
        mime="text/csv"
    )

with col2:
    # 요약 리포트 다운로드 (파트별)
    if '정비자소속' in filtered_df.columns:
        summary_data = filtered_df.groupby('정비자소속').agg({
            '관리번호': 'count',
            '수리비': 'sum',
            '현장명': 'nunique'
        }).rename(columns={'관리번호': '건수', '현장명': '업체수'})
        
        summary_csv = summary_data.to_csv(encoding='utf-8-sig')
        st.download_button(
            label="📊 파트별 요약 (CSV)",
            data=summary_csv,
            file_name=f"{selected_year}년{selected_month}월_파트별요약.csv",
            mime="text/csv"
        )

with col3:
    # 업체별 리포트 다운로드
    if '현장명' in filtered_df.columns:
        client_summary = filtered_df.groupby('현장명').agg({
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