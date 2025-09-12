# pages/02_파트별_심층_분석.py - 심플한 색상 버전
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# 파트별 색상 매핑 생성 (심플한 버전)
@st.cache_data
def create_part_color_mapping(parts_list):
    """파트별 심플한 색상 매핑 생성"""
    # 심플하고 구분되는 색상들
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#c49c94', '#f7b6d3', '#c7c7c7', '#dbdb8d', '#9edae5'
    ]
    
    color_mapping = {}
    for i, part in enumerate(sorted(parts_list)):
        color_mapping[part] = colors[i % len(colors)]
    
    return color_mapping

# 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_part_data(df):
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df['년월'] = df['정비일자'].dt.to_period('M')
    
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    # 수리시간 컬럼 처리
    if '수리시간' in df.columns:
        df['수리시간'] = pd.to_numeric(df['수리시간'], errors='coerce').fillna(0)
    else:
        df['수리시간'] = 0
    
    # 만족도 컬럼 확인
    satisfaction_cols = [col for col in df.columns if '만족도' in col]
    if satisfaction_cols:
        st.sidebar.success(f"✅ 만족도 데이터 발견: {len(satisfaction_cols)}개 컬럼")
        for col in satisfaction_cols[:5]:  # 상위 5개만 표시
            st.sidebar.write(f"  - {col}")
    
    return df

df = prepare_part_data(df)

# 파트 컬럼 확인
if '정비자소속' not in df.columns or df['정비자소속'].isna().all():
    st.error("파트 정보가 없습니다. 조직도 데이터가 올바르게 매핑되었는지 확인해주세요.")
    st.stop()

# 파트별 색상 매핑 생성
available_parts = df['정비자소속'].dropna().unique()
part_colors = create_part_color_mapping(available_parts)

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

# 만족도 컬럼 확인
satisfaction_cols = []
for col in df.columns:
    if '만족도' in col and df[col].notna().sum() > 0:
        satisfaction_cols.append(col)

satisfaction_columns = satisfaction_cols.copy()

# 정비자별 통계 계산 함수
@st.cache_data
def calculate_technician_stats(df_input):
    """정비자별 통계 계산"""
    # 정비자별 통계 계산 - 더 상세하게
    technician_agg_dict = {
        '관리번호': 'count',
        '수리비': ['sum', 'mean', 'std'],
        '브랜드': lambda x: x.value_counts().index[0] if not x.value_counts().empty else 'N/A'
    }
    
    # 수리시간이 있는 경우 추가
    if '수리시간' in df_input.columns and df_input['수리시간'].sum() > 0:
        technician_agg_dict['수리시간'] = ['mean', 'sum']
    
    technician_stats = df_input.groupby(['정비자', '정비자소속']).agg(technician_agg_dict).round(2)
    
    # 컬럼명 정리
    base_tech_columns = ['AS건수', '총수리비', '평균수리비', '수리비표준편차', '주요브랜드']
    if '수리시간' in technician_agg_dict:
        base_tech_columns.extend(['평균수리시간', '총수리시간'])
    
    technician_stats.columns = base_tech_columns
    technician_stats = technician_stats.reset_index()
    
    # 추가 정보 계산
    # 작업내용 (대중소분류)
    if '작업유형' in df_input.columns:
        technician_work_type = df_input.groupby('정비자')['작업유형'].apply(
            lambda x: x.value_counts().head(1).index[0] if not x.value_counts().empty else 'N/A'
        ).to_dict()
        technician_stats['주요작업유형'] = technician_stats['정비자'].map(technician_work_type)
    
    if '정비대상' in df_input.columns:
        technician_target = df_input.groupby('정비자')['정비대상'].apply(
            lambda x: x.value_counts().head(1).index[0] if not x.value_counts().empty else 'N/A'
        ).to_dict()
        technician_stats['주요정비대상'] = technician_stats['정비자'].map(technician_target)
    
    if '작업내용' in df_input.columns:
        technician_work = df_input.groupby('정비자')['작업내용'].apply(
            lambda x: x.value_counts().head(1).index[0] if not x.value_counts().empty else 'N/A'
        ).to_dict()
        technician_stats['주요작업내용'] = technician_stats['정비자'].map(technician_work)
    
    # 정비자 직급 추가 (있는 경우)
    if '정비자직급' in df_input.columns:
        technician_grade = df_input.groupby('정비자')['정비자직급'].first().to_dict()
        technician_stats['직급'] = technician_stats['정비자'].map(technician_grade)
    
    # 정비자 파트 추가 (있는 경우)
    if '정비자파트' in df_input.columns:
        technician_part = df_input.groupby('정비자')['정비자파트'].first().to_dict()
        technician_stats['파트'] = technician_stats['정비자'].map(technician_part)
    
    # 효율성 지표 추가
    technician_stats['건당수리비'] = technician_stats['총수리비'] / technician_stats['AS건수']
    technician_stats['효율성점수'] = (technician_stats['AS건수'] / technician_stats['총수리비'] * 1000000).round(2)
    
    # 수리비 기준으로 정렬
    technician_stats = technician_stats.sort_values('총수리비', ascending=False)
    
    return technician_stats

# 정비자 분석 표시 함수 (심플한 색상 적용)
def display_technician_analysis(technician_stats, df_data, part_name="전체", target_part=None):
    """정비자 분석을 표시하는 공통 함수 - 심플한 색상 적용"""
    
    # 상위 정비자 시각화
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"💰 {part_name} 수리비 상위 정비자 (Top 15)")
        top_technicians_cost = technician_stats.head(15)
        
        if not top_technicians_cost.empty:
            # 색상 적용
            fig = px.bar(
                top_technicians_cost,
                x='총수리비',
                y='정비자',
                color='정비자소속',
                color_discrete_map=part_colors,
                title=f"{part_name} 정비자별 총 수리비"
            )
            fig.update_layout(
                height=600, 
                yaxis={'categoryorder': 'total ascending'},
                showlegend=False if target_part else True
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader(f"📊 {part_name} 업무량 상위 정비자 (Top 15)")
        top_technicians_volume = technician_stats.nlargest(15, 'AS건수')
        
        if not top_technicians_volume.empty:
            fig = px.bar(
                top_technicians_volume,
                x='AS건수',
                y='정비자',
                color='정비자소속',
                color_discrete_map=part_colors,
                title=f"{part_name} 정비자별 AS 건수"
            )
            fig.update_layout(
                height=600, 
                yaxis={'categoryorder': 'total ascending'},
                showlegend=False if target_part else True
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # 월별 추이 분석
    if '년월' in df_data.columns:
        st.subheader(f"📈 {part_name} 상위 정비자 월별 수리비 추이")
        
        # 상위 10명 정비자 선택
        top_10_technicians = technician_stats.head(10)['정비자'].tolist()
        
        monthly_technician_data = df_data[df_data['정비자'].isin(top_10_technicians)].groupby(['년월', '정비자', '정비자소속'])['수리비'].sum().reset_index()
        monthly_technician_data['년월_str'] = monthly_technician_data['년월'].astype(str)
        
        if not monthly_technician_data.empty:
            fig = px.line(
                monthly_technician_data,
                x='년월_str',
                y='수리비',
                color='정비자',
                title=f"{part_name} 상위 10명 정비자 월별 수리비 추이"
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
    
    # 정비자 상세 테이블
    st.subheader(f"📋 {part_name} 정비자 상세 통계")
    
    # 표시할 컬럼 선택
    display_tech_columns = ['정비자', '정비자소속', 'AS건수', '총수리비', '평균수리비', '건당수리비', '주요브랜드']
    
    if '주요작업유형' in technician_stats.columns:
        display_tech_columns.append('주요작업유형')
    if '주요정비대상' in technician_stats.columns:
        display_tech_columns.append('주요정비대상')
    if '주요작업내용' in technician_stats.columns:
        display_tech_columns.append('주요작업내용')
    if '직급' in technician_stats.columns:
        display_tech_columns.append('직급')
    if '파트' in technician_stats.columns:
        display_tech_columns.append('파트')
    if '평균수리시간' in technician_stats.columns:
        display_tech_columns.append('평균수리시간')
    
    display_tech_stats = technician_stats[display_tech_columns].head(30)
    
    # 포맷팅 딕셔너리
    format_dict = {
        'AS건수': '{:,}건',
        '총수리비': '{:,.0f}원',
        '평균수리비': '{:,.0f}원',
        '건당수리비': '{:,.0f}원'
    }
    
    if '평균수리시간' in display_tech_stats.columns:
        format_dict['평균수리시간'] = '{:.1f}시간'
    
    st.dataframe(
        display_tech_stats.style.format(format_dict),
        use_container_width=True
    )

# 메인 탭 구성
tab1, tab2, tab3 = st.tabs(["📊 파트별 현황", "👨‍🔧 정비자별 분석", "🔍 상세 분석"])

with tab1:
    # 파트별 전체 현황
    st.header("📊 파트별 전체 현황")

    # 파트별 통계 계산 - 만족도 포함 안전한 버전
    agg_dict = {
        '관리번호': 'count',
        '수리비': ['sum', 'mean']
    }

    # 수리시간이 실제로 데이터가 있는 경우만 추가
    if '수리시간' in df.columns and df['수리시간'].sum() > 0:
        agg_dict['수리시간'] = 'mean'

    # 만족도 컬럼 확인 및 추가 - 안전한 방식
    for col in df.columns:
        if '만족도' in col and df[col].notna().sum() > 0:  # 실제 데이터가 있는 경우만
            agg_dict[col] = 'mean'

    part_stats = df.groupby('정비자소속').agg(agg_dict).round(2)

    # 컬럼명 정리
    base_columns = ['AS건수', '총수리비', '평균수리비']
    if '수리시간' in agg_dict:
        base_columns.append('평균수리시간')

    # 전체 컬럼명 설정
    all_columns = base_columns + satisfaction_columns
    part_stats.columns = all_columns
    part_stats = part_stats.reset_index()

    # 효율성 지표 추가
    part_stats['건당수리비'] = part_stats['총수리비'] / part_stats['AS건수']
    part_stats['효율성점수'] = (part_stats['AS건수'] / part_stats['총수리비'] * 1000000).round(2)
    part_stats = part_stats.sort_values('총수리비', ascending=False)

    # 상위 파트 시각화 (심플한 색상 적용)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 파트별 총 수리비")
        top_parts = part_stats.head(10)
        
        fig = px.bar(
            top_parts, 
            x='총수리비', 
            y='정비자소속',
            orientation='h',
            color='정비자소속',
            color_discrete_map=part_colors
        )
        fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("📊 파트별 AS 건수")
        
        fig2 = px.bar(
            top_parts,
            x='AS건수',
            y='정비자소속', 
            orientation='h',
            color='정비자소속',
            color_discrete_map=part_colors
        )
        fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    # 만족도 차트 추가 (심플한 색상 적용)
    if satisfaction_columns:
        st.subheader("😊 파트별 고객 만족도")
        
        # 만족도 데이터가 있는 파트만 필터링
        main_satisfaction_col = satisfaction_columns[0]
        satisfaction_data = part_stats[part_stats[main_satisfaction_col].notna()].head(10)
        
        if not satisfaction_data.empty:
            fig3 = px.bar(
                satisfaction_data,
                x=main_satisfaction_col,
                y='정비자소속',
                orientation='h',
                color='정비자소속',
                color_discrete_map=part_colors,
                title="파트별 평균 만족도"
            )
            fig3.update_layout(height=400, yaxis={'categoryorder': 'total ascending'}, showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("만족도 데이터가 있는 파트가 없습니다.")

    # 파트별 상세 통계 테이블
    st.subheader("📋 파트별 상세 통계")

    # 컬럼 순서 정리
    display_columns = ['정비자소속', 'AS건수', '총수리비', '건당수리비']

    # 수리시간 컬럼이 있고 실제 데이터가 있는 경우만 추가
    if '평균수리시간' in part_stats.columns and part_stats['평균수리시간'].sum() > 0:
        display_columns.append('평균수리시간')

    # 만족도 컬럼 추가
    if satisfaction_columns:
        display_columns.extend(satisfaction_columns)

    display_columns.append('효율성점수')

    display_stats = part_stats[display_columns]

    # 포맷팅
    format_dict = {
        'AS건수': '{:,}건',
        '총수리비': '{:,.0f}원',
        '건당수리비': '{:,.0f}원',
        '효율성점수': '{:.2f}'
    }

    if '평균수리시간' in display_stats.columns:
        format_dict['평균수리시간'] = '{:.1f}시간'

    # 만족도 컬럼 포맷팅
    for col in satisfaction_columns:
        if col in display_stats.columns:
            format_dict[col] = '{:.2f}점'

    st.dataframe(
        display_stats.style.format(format_dict),
        use_container_width=True
    )

with tab2:
    # 정비자별 상세 분석
    st.header("👨‍🔧 정비자별 상세 분석")

    if '정비자' in df.columns and '정비자소속' in df.columns:
        # 전체 정비자 통계 계산
        technician_stats = calculate_technician_stats(df)
        
        # 파트별 탭 생성
        available_parts = df['정비자소속'].dropna().unique()
        part_tabs = st.tabs(["🏆 전체 랭킹"] + [f"🔧 {part}" for part in available_parts[:10]])  # 최대 10개 파트만
        
        with part_tabs[0]:
            st.subheader("🏆 전체 정비자 랭킹 (수리비 기준)")
            display_technician_analysis(technician_stats, df, "전체")
        
        # 파트별 탭
        for i, part in enumerate(available_parts[:10]):
            with part_tabs[i+1]:
                st.subheader(f"🔧 {part} 파트 정비자 분석")
                
                # 해당 파트 데이터 필터링
                part_data = df[df['정비자소속'] == part]
                part_technician_stats = calculate_technician_stats(part_data)
                
                if part_technician_stats.empty:
                    st.warning(f"{part} 파트에 해당하는 정비자가 없습니다.")
                    continue
                
                # 파트 내 정비자 KPI
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("파트 정비자 수", f"{len(part_technician_stats)}명")
                
                with col2:
                    total_part_cost = part_technician_stats['총수리비'].sum()
                    st.metric("파트 총 수리비", f"{total_part_cost:,.0f}원")
                
                with col3:
                    total_part_cases = part_technician_stats['AS건수'].sum()
                    st.metric("파트 총 AS건수", f"{total_part_cases:,}건")
                
                with col4:
                    avg_part_efficiency = part_technician_stats['효율성점수'].mean()
                    st.metric("파트 평균 효율성", f"{avg_part_efficiency:.2f}")
                
                # 파트별 정비자 분석 표시 (해당 파트 색상 적용)
                display_technician_analysis(part_technician_stats, part_data, part, part)
                
                # 추가: 개별 정비자 상세 분석
                st.markdown("---")
                st.subheader("🔍 개별 정비자 상세 분석")
                
                selected_technician = st.selectbox(
                    f"{part} 파트 정비자 선택",
                    part_technician_stats['정비자'].tolist(),
                    key=f"tech_select_{part}"
                )
                
                if selected_technician:
                    tech_data = part_data[part_data['정비자'] == selected_technician]
                    tech_info = part_technician_stats[part_technician_stats['정비자'] == selected_technician].iloc[0]
                    
                    # 정비자 개인 KPI
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        st.metric("총 AS건수", f"{tech_info['AS건수']:,}건")
                    
                    with col2:
                        st.metric("총 수리비", f"{tech_info['총수리비']:,.0f}원")
                    
                    with col3:
                        st.metric("평균 수리비", f"{tech_info['평균수리비']:,.0f}원")
                    
                    with col4:
                        if '직급' in tech_info and pd.notna(tech_info['직급']):
                            st.metric("직급", tech_info['직급'])
                        else:
                            st.metric("직급", "미분류")
                    
                    with col5:
                        st.metric("효율성점수", f"{tech_info['효율성점수']:.2f}")
                    
                    # 상세 분석
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**🔨 주요 작업 유형**")
                        if '작업유형' in tech_data.columns:
                            work_types = tech_data['작업유형'].value_counts().head(5)
                            for work_type, count in work_types.items():
                                percentage = (count / len(tech_data) * 100)
                                st.write(f"• {work_type}: {count}건 ({percentage:.1f}%)")
                        else:
                            st.write("작업유형 데이터 없음")
                    
                    with col2:
                        st.write("**⚙️ 주요 정비 대상**")
                        if '정비대상' in tech_data.columns:
                            targets = tech_data['정비대상'].value_counts().head(5)
                            for target, count in targets.items():
                                percentage = (count / len(tech_data) * 100)
                                st.write(f"• {target}: {count}건 ({percentage:.1f}%)")
                        else:
                            st.write("정비대상 데이터 없음")
                    
                    with col3:
                        st.write("**🏭 주요 담당 브랜드/기기**")
                        if '브랜드' in tech_data.columns:
                            brands = tech_data['브랜드'].value_counts().head(5)
                            for brand, count in brands.items():
                                percentage = (count / len(tech_data) * 100)
                                st.write(f"• {brand}: {count}건 ({percentage:.1f}%)")
                        else:
                            st.write("브랜드 데이터 없음")
                    
                    # 월별 수리비 추이
                    if '년월' in tech_data.columns:
                        st.write("**📈 월별 수리비 추이**")
                        monthly_data = tech_data.groupby('년월')['수리비'].sum().reset_index()
                        monthly_data['년월_str'] = monthly_data['년월'].astype(str)
                        
                        if not monthly_data.empty:
                            fig = px.line(
                                monthly_data,
                                x='년월_str',
                                y='수리비',
                                title=f"{selected_technician} 월별 수리비 추이",
                                markers=True
                            )
                            fig.update_layout(height=300)
                            st.plotly_chart(fig, use_container_width=True)

with tab3:
    # 파트 선택 및 상세 분석
    st.header("🔍 파트별 상세 분석")

    available_parts = df['정비자소속'].dropna().unique()
    selected_parts = st.multiselect(
        "상세 분석할 파트 선택", 
        available_parts,
        default=available_parts[:2] if len(available_parts) >= 2 else available_parts
    )

    if selected_parts:
        for i, part in enumerate(selected_parts):
            if i > 0:
                st.markdown("---")
                
            part_data = df[df['정비자소속'] == part]
            
            st.subheader(f"🔧 {part} 파트 상세 분석")
            
            # 파트 KPI - 만족도 포함
            kpi_cols = 4
            if satisfaction_columns:
                kpi_cols = 5
            
            cols = st.columns(kpi_cols)
            
            with cols[0]:
                total_cases = len(part_data)
                st.metric("총 AS 건수", f"{total_cases:,}건")
            
            with cols[1]:
                total_cost = part_data['수리비'].sum()
                st.metric("총 수리비", f"{total_cost:,.0f}원")
            
            with cols[2]:
                avg_cost = part_data['수리비'].mean() if total_cases > 0 else 0
                st.metric("평균 수리비", f"{avg_cost:,.0f}원")
            
            with cols[3]:
                # 수리시간이 실제로 있는 경우만 표시
                if '수리시간' in part_data.columns and part_data['수리시간'].sum() > 0:
                    avg_time = part_data['수리시간'].mean()
                    st.metric("평균 수리시간", f"{avg_time:.1f}시간")
                else:
                    st.metric("평균 수리시간", "데이터 없음")
            
            # 만족도 메트릭 추가 - 안전한 버전
            if satisfaction_columns and kpi_cols == 5:
                with cols[4]:
                    # 실제 데이터에서 만족도 컬럼 찾기
                    available_satisfaction_cols = []
                    for col in satisfaction_columns:
                        if col in part_data.columns and part_data[col].notna().sum() > 0:
                            available_satisfaction_cols.append(col)
                    
                    if available_satisfaction_cols:
                        satisfaction_col = available_satisfaction_cols[0]
                        avg_satisfaction = part_data[satisfaction_col].mean()
                        if pd.notna(avg_satisfaction):
                            st.metric("평균 만족도", f"{avg_satisfaction:.2f}점")
                        else:
                            st.metric("평균 만족도", "데이터 없음")
                    else:
                        st.metric("평균 만족도", "데이터 없음")

            # 파트별 세부 분석 - 작업내용 포함
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**🔨 주요 작업내용**")
                if '작업내용' in part_data.columns:
                    work_contents = part_data['작업내용'].value_counts().head(5)
                    for work, count in work_contents.items():
                        percentage = (count / len(part_data) * 100)
                        work_short = str(work)[:30] + "..." if len(str(work)) > 30 else str(work)
                        st.write(f"• {work_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("작업내용 데이터 없음")
            
            with col2:
                st.write("**⚙️ 주요 정비 대상**")
                if '정비대상' in part_data.columns:
                    targets = part_data['정비대상'].value_counts().head(5)
                    for target, count in targets.items():
                        percentage = (count / len(part_data) * 100)
                        st.write(f"• {target}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("정비대상 데이터 없음")
            
            with col3:
                st.write("**🏢 주요 담당 업체**")
                client_col = None
                for col in ['현장명', '업체명', '현장']:
                    if col in part_data.columns:
                        client_col = col
                        break
                
                if client_col:
                    clients = part_data[client_col].value_counts().head(5)
                    for client, count in clients.items():
                        percentage = (count / len(part_data) * 100)
                        client_short = str(client)[:15] + "..." if len(str(client)) > 15 else str(client)
                        st.write(f"• {client_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("업체 데이터 없음")

    # 파트 간 비교 분석 (심플한 색상 적용)
    if len(selected_parts) > 1:
        st.markdown("---")
        st.header("⚖️ 선택된 파트 간 비교")
        
        comparison_data = []
        for part in selected_parts:
            part_data = df[df['정비자소속'] == part]
            
            comparison_item = {
                '파트': part,
                'AS건수': len(part_data),
                '총수리비': part_data['수리비'].sum(),
                '평균수리비': part_data['수리비'].mean(),
            }
            
            # 수리시간이 실제로 있는 경우만 추가
            if '수리시간' in part_data.columns and part_data['수리시간'].sum() > 0:
                comparison_item['평균수리시간'] = part_data['수리시간'].mean()
            
            # 만족도 추가 - 안전한 방식
            if satisfaction_columns:
                for col in satisfaction_columns:
                    if col in part_data.columns and part_data[col].notna().sum() > 0:
                        avg_satisfaction = part_data[col].mean()
                        if pd.notna(avg_satisfaction):
                            comparison_item['평균만족도'] = avg_satisfaction
                            break
            
            comparison_data.append(comparison_item)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        # 비교 차트 (심플한 색상 적용)
        chart_cols = 2 if '평균만족도' not in comparison_df.columns else 3
        cols = st.columns(chart_cols)
        
        with cols[0]:
            fig = px.bar(
                comparison_df,
                x='파트',
                y='총수리비',
                title="파트별 총 수리비 비교",
                color='파트',
                color_discrete_map=part_colors
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with cols[1]:
            fig = px.bar(
                comparison_df,
                x='파트',
                y='평균수리비',
                title="파트별 평균 수리비 비교",
                color='파트',
                color_discrete_map=part_colors
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # 만족도 비교 차트 (심플한 색상 적용)
        if chart_cols == 3 and '평균만족도' in comparison_df.columns:
            with cols[2]:
                fig = px.bar(
                    comparison_df,
                    x='파트',
                    y='평균만족도',
                    title="파트별 평균 만족도 비교",
                    color='파트',
                    color_discrete_map=part_colors
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

# 파트 성과 랭킹
st.markdown("---")
st.header("🏆 파트 성과 랭킹")

# 파트별 통계 재계산 (전체 탭에서 사용한 것과 동일)
agg_dict = {
    '관리번호': 'count',
    '수리비': ['sum', 'mean']
}

if '수리시간' in df.columns and df['수리시간'].sum() > 0:
    agg_dict['수리시간'] = 'mean'

for col in df.columns:
    if '만족도' in col and df[col].notna().sum() > 0:
        agg_dict[col] = 'mean'

part_stats = df.groupby('정비자소속').agg(agg_dict).round(2)

base_columns = ['AS건수', '총수리비', '평균수리비']
if '수리시간' in agg_dict:
    base_columns.append('평균수리시간')

all_columns = base_columns + satisfaction_columns
part_stats.columns = all_columns
part_stats = part_stats.reset_index()

part_stats['건당수리비'] = part_stats['총수리비'] / part_stats['AS건수']
part_stats['효율성점수'] = (part_stats['AS건수'] / part_stats['총수리비'] * 1000000).round(2)

ranking_cols = 2 if not satisfaction_columns else 3
cols = st.columns(ranking_cols)

with cols[0]:
    st.subheader("💰 수리비 효율성 랭킹")
    efficiency_ranking = part_stats.nsmallest(10, '건당수리비')[['정비자소속', '건당수리비', 'AS건수']]
    
    for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   건당 수리비: {row['건당수리비']:,.0f}원 ({row['AS건수']}건)")

with cols[1]:
    st.subheader("📊 업무량 랭킹")
    volume_ranking = part_stats.nlargest(10, 'AS건수')[['정비자소속', 'AS건수', '총수리비']]
    
    for idx, (_, row) in enumerate(volume_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   AS 건수: {row['AS건수']:,}건 (총 {row['총수리비']:,.0f}원)")

# 만족도 랭킹 추가 - 안전한 버전
if satisfaction_columns and ranking_cols == 3:
    with cols[2]:
        st.subheader("😊 고객 만족도 랭킹")
        
        # 만족도 데이터가 있는 파트만 필터링
        satisfaction_col = satisfaction_columns[0]
        satisfaction_ranking = part_stats[part_stats[satisfaction_col].notna()].nlargest(10, satisfaction_col)
        
        if not satisfaction_ranking.empty:
            satisfaction_ranking = satisfaction_ranking[['정비자소속', satisfaction_col, 'AS건수']]
            
            for idx, (_, row) in enumerate(satisfaction_ranking.iterrows()):
                medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
                st.write(f"{medal} **{row['정비자소속']}**")
                st.write(f"   만족도: {row[satisfaction_col]:.2f}점 ({row['AS건수']}건)")
        else:
            st.write("만족도 데이터가 있는 파트가 없습니다.")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    if 'part_stats' in locals():
        csv_data = part_stats.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 파트별 통계 다운로드 (CSV)",
            data=csv_data,
            file_name="파트별_상세통계.csv",
            mime="text/csv"
        )

with col2:
    download_columns = ['정비자소속', '정비자', '관리번호', '정비일자', '수리비', '작업유형', '정비대상', '작업내용']
    
    # 만족도 컬럼도 다운로드에 포함
    if satisfaction_columns:
        for col in satisfaction_columns:
            if col in df.columns:
                download_columns.append(col)
    
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_csv = detailed_data.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 상세 데이터 다운로드 (CSV)",
        data=detailed_csv,
        file_name="파트별_상세데이터.csv",
        mime="text/csv"
    )
