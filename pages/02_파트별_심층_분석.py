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

# df3 데이터도 활용하기 위한 추가 처리
@st.cache_data(show_spinner=False)
def enhance_with_df3_data(df):
    """df3 데이터로 파트별 분석 강화"""
    
    # df3 데이터가 세션에 있는지 확인
    if hasattr(st.session_state, 'df3_raw'):
        df3 = st.session_state.df3_raw.copy()
        
        # df3에서 출고자-파트 매핑 정보 추출
        if '출고자' in df3.columns:
            # 조직도 데이터 로드
            import os
            if os.path.exists("data/조직도데이터.xlsx"):
                try:
                    df4 = pd.read_excel("data/조직도데이터.xlsx", dtype=str)
                    
                    # 조직도 전처리
                    if len(df4) > 0:
                        first_row = df4.iloc[0]
                        if any(keyword in str(first_row.iloc[i]).lower() 
                               for i in range(min(len(first_row), 3)) 
                               for keyword in ['이름', '파트', '사번']):
                            new_columns = df4.iloc[0].tolist()
                            df4 = df4.iloc[1:].reset_index(drop=True)
                            df4.columns = new_columns
                    
                    df4.columns = [str(col).strip().replace('\n', '') for col in df4.columns]
                    
                    # df3 출고자별 파트 매핑
                    if '사번' in df4.columns and '파트' in df4.columns:
                        df3['출고자'] = df3['출고자'].astype(str).str.strip()
                        df4['사번'] = df4['사번'].astype(str).str.strip()
                        
                        # 출고자-파트 매핑
                        df3_with_part = pd.merge(
                            df3,
                            df4[['사번', '파트', '직급', '직책']],
                            left_on='출고자',
                            right_on='사번',
                            how='left'
                        )
                        
                        # df3 파트별 수리비 통계 계산
                        if '출고금액' in df3_with_part.columns and '파트' in df3_with_part.columns:
                            df3_with_part['수리비'] = pd.to_numeric(df3_with_part['출고금액'], errors='coerce').fillna(0)
                            
                            df3_part_stats = df3_with_part.groupby('파트').agg({
                                '수리비': ['sum', 'count', 'mean'],
                                '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:5])
                            }).round(2)
                            
                            df3_part_stats.columns = ['df3_총수리비', 'df3_수리건수', 'df3_평균수리비', 'df3_주요자재']
                            df3_part_stats = df3_part_stats.reset_index()
                            
                            # 기존 df와 df3 통계 병합
                            df = pd.merge(df, df3_part_stats, left_on='정비자소속', right_on='파트', how='left')
                            
                            st.sidebar.success("✅ df3 수리비 데이터 연동 완료")
                            
                except Exception as e:
                    st.sidebar.warning(f"df3 데이터 연동 중 오류: {e}")
    
    return df

# 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_part_data(df):
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df['년월'] = df['정비일자'].dt.to_period('M')
    
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    # df3 수리비도 처리
    if 'df3_총수리비' in df.columns:
        df['df3_총수리비'] = pd.to_numeric(df['df3_총수리비'], errors='coerce').fillna(0)
        df['df3_평균수리비'] = pd.to_numeric(df['df3_평균수리비'], errors='coerce').fillna(0)
        df['df3_수리건수'] = pd.to_numeric(df['df3_수리건수'], errors='coerce').fillna(0)
    
    # 수리시간 컬럼 처리
    if '수리시간' in df.columns:
        df['수리시간'] = pd.to_numeric(df['수리시간'], errors='coerce').fillna(0)
    else:
        df['수리시간'] = 0
    
    # 만족도 컬럼 확인
    satisfaction_cols = [col for col in df.columns if '만족도' in col]
    if satisfaction_cols:
        st.sidebar.success(f"✅ 만족도 데이터 발견: {len(satisfaction_cols)}개 컬럼")
        for col in satisfaction_cols[:5]:
            st.sidebar.write(f"  - {col}")
    
    # df3 데이터 확인
    df3_cols = [col for col in df.columns if col.startswith('df3_')]
    if df3_cols:
        st.sidebar.success(f"✅ df3 연동 데이터: {len(df3_cols)}개 컬럼")
        for col in df3_cols:
            st.sidebar.write(f"  - {col}")
    
    return df

# df3 데이터 강화 적용
df = enhance_with_df3_data(df)
df = prepare_part_data(df)

# 파트 컬럼 확인
if '정비자소속' not in df.columns or df['정비자소속'].isna().all():
    st.error("파트 정보가 없습니다. 조직도 데이터가 올바르게 매핑되었는지 확인해주세요.")
    st.stop()

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

# 분석 데이터 소스 선택
analysis_source = st.sidebar.radio(
    "수리비 분석 기준",
    ["df1 기준 (정비일지)", "df3 기준 (수리품목)", "통합 분석"]
)

# 파트별 전체 현황
st.header("📊 파트별 전체 현황")

# 파트별 통계 계산 - df3 데이터 포함 강화 버전
agg_dict = {
    '관리번호': 'count',
    '수리비': ['sum', 'mean']
}

# df3 데이터가 있는 경우 추가
if 'df3_총수리비' in df.columns:
    agg_dict['df3_총수리비'] = 'first'  # 파트별로 이미 집계된 값이므로 first 사용
    agg_dict['df3_수리건수'] = 'first'
    agg_dict['df3_평균수리비'] = 'first'

# 수리시간이 실제로 데이터가 있는 경우만 추가
if '수리시간' in df.columns and df['수리시간'].sum() > 0:
    agg_dict['수리시간'] = 'mean'

# 만족도 컬럼 확인 및 추가
satisfaction_cols = []
for col in df.columns:
    if '만족도' in col and df[col].notna().sum() > 0:
        agg_dict[col] = 'mean'
        satisfaction_cols.append(col)

part_stats = df.groupby('정비자소속').agg(agg_dict).round(2)

# 컬럼명 정리
base_columns = ['AS건수', 'df1_총수리비', 'df1_평균수리비']

# df3 컬럼 추가
if 'df3_총수리비' in df.columns:
    base_columns.extend(['df3_총수리비', 'df3_수리건수', 'df3_평균수리비'])

if '수리시간' in agg_dict:
    base_columns.append('평균수리시간')

# 실제로 추가된 만족도 컬럼들
satisfaction_columns = satisfaction_cols.copy()

# 전체 컬럼명 설정
all_columns = base_columns + satisfaction_columns
part_stats.columns = all_columns
part_stats = part_stats.reset_index()

# 분석 기준에 따른 수리비 컬럼 선택
if analysis_source == "df1 기준 (정비일지)":
    cost_col = 'df1_총수리비'
    avg_cost_col = 'df1_평균수리비'
    count_col = 'AS건수'
elif analysis_source == "df3 기준 (수리품목)" and 'df3_총수리비' in part_stats.columns:
    cost_col = 'df3_총수리비'
    avg_cost_col = 'df3_평균수리비'
    count_col = 'df3_수리건수'
else:  # 통합 분석
    # df1과 df3 수리비 합계
    if 'df3_총수리비' in part_stats.columns:
        part_stats['통합_총수리비'] = part_stats['df1_총수리비'].fillna(0) + part_stats['df3_총수리비'].fillna(0)
        part_stats['통합_건수'] = part_stats['AS건수'].fillna(0) + part_stats['df3_수리건수'].fillna(0)
        part_stats['통합_평균수리비'] = part_stats['통합_총수리비'] / part_stats['통합_건수']
        cost_col = '통합_총수리비'
        avg_cost_col = '통합_평균수리비'
        count_col = '통합_건수'
    else:
        cost_col = 'df1_총수리비'
        avg_cost_col = 'df1_평균수리비'
        count_col = 'AS건수'

# 효율성 지표 추가
part_stats['건당수리비'] = part_stats[cost_col] / part_stats[count_col]
part_stats['효율성점수'] = (part_stats[count_col] / part_stats[cost_col] * 1000000).round(2)
part_stats = part_stats.sort_values(cost_col, ascending=False)

# 상위 파트 시각화
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"💰 파트별 총 수리비 ({analysis_source})")
    top_parts = part_stats.head(10)
    
    fig = px.bar(
        top_parts, 
        x=cost_col, 
        y='정비자소속',
        orientation='h',
        color=cost_col,
        color_continuous_scale='Reds',
        title=f"상위 10개 파트 - {analysis_source}"
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader(f"📊 파트별 건수 ({analysis_source})")
    
    fig2 = px.bar(
        top_parts,
        x=count_col,
        y='정비자소속', 
        orientation='h',
        color=count_col,
        color_continuous_scale='Blues',
        title=f"상위 10개 파트 - {analysis_source}"
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# df1 vs df3 비교 차트 (통합 분석인 경우)
if analysis_source == "통합 분석" and 'df3_총수리비' in part_stats.columns:
    st.subheader("📊 df1 vs df3 수리비 비교")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 상관관계 분석
        comparison_data = part_stats[['정비자소속', 'df1_총수리비', 'df3_총수리비']].copy()
        comparison_data = comparison_data.dropna()
        
        if not comparison_data.empty:
            fig = px.scatter(
                comparison_data,
                x='df1_총수리비',
                y='df3_총수리비',
                hover_name='정비자소속',
                title="df1 vs df3 수리비 상관관계",
                labels={'df1_총수리비': 'df1 수리비 (원)', 'df3_총수리비': 'df3 수리비 (원)'}
            )
            
            # 대각선 추가 (완전 일치선)
            max_val = max(comparison_data['df1_총수리비'].max(), comparison_data['df3_총수리비'].max())
            fig.add_shape(
                type="line",
                x0=0, y0=0, x1=max_val, y1=max_val,
                line=dict(color="red", dash="dash"),
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 차이 분석
        comparison_data['차이'] = comparison_data['df3_총수리비'] - comparison_data['df1_총수리비']
        comparison_data['차이율'] = (comparison_data['차이'] / comparison_data['df1_총수리비'] * 100).round(1)
        
        # 차이가 큰 파트들
        top_diff = comparison_data.nlargest(5, '차이')[['정비자소속', '차이', '차이율']]
        
        st.write("**📈 df3 > df1 차이가 큰 파트 (상위 5개)**")
        for _, row in top_diff.iterrows():
            st.write(f"• **{row['정비자소속']}**: {row['차이']:,.0f}원 ({row['차이율']:+.1f}%)")

# 만족도 차트 추가
if satisfaction_columns:
    st.subheader("😊 파트별 고객 만족도")
    
    main_satisfaction_col = satisfaction_columns[0]
    satisfaction_data = part_stats[part_stats[main_satisfaction_col].notna()].head(10)
    
    if not satisfaction_data.empty:
        fig3 = px.bar(
            satisfaction_data,
            x=main_satisfaction_col,
            y='정비자소속',
            orientation='h',
            color=main_satisfaction_col,
            color_continuous_scale='Greens',
            title="파트별 평균 만족도"
        )
        fig3.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("만족도 데이터가 있는 파트가 없습니다.")

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계")

# 컬럼 순서 정리 - 분석 기준에 따라 조정
display_columns = ['정비자소속']

if analysis_source == "df1 기준 (정비일지)":
    display_columns.extend(['AS건수', 'df1_총수리비', 'df1_평균수리비'])
elif analysis_source == "df3 기준 (수리품목)" and 'df3_총수리비' in part_stats.columns:
    display_columns.extend(['df3_수리건수', 'df3_총수리비', 'df3_평균수리비'])
else:  # 통합 분석
    if 'df3_총수리비' in part_stats.columns:
        display_columns.extend(['통합_건수', '통합_총수리비', '통합_평균수리비', 'AS건수', 'df1_총수리비', 'df3_수리건수', 'df3_총수리비'])
    else:
        display_columns.extend(['AS건수', 'df1_총수리비', 'df1_평균수리비'])

display_columns.append('건당수리비')

# 수리시간 컬럼이 있고 실제 데이터가 있는 경우만 추가
if '평균수리시간' in part_stats.columns and part_stats['평균수리시간'].sum() > 0:
    display_columns.append('평균수리시간')

# 만족도 컬럼 추가
if satisfaction_columns:
    display_columns.extend(satisfaction_columns)

display_columns.append('효율성점수')

# 실제 존재하는 컬럼만 선택
display_stats = part_stats[[col for col in display_columns if col in part_stats.columns]]

# 포맷팅
format_dict = {
    'AS건수': '{:,}건',
    'df1_총수리비': '{:,.0f}원',
    'df1_평균수리비': '{:,.0f}원',
    'df3_수리건수': '{:,}건',
    'df3_총수리비': '{:,.0f}원',
    'df3_평균수리비': '{:,.0f}원',
    '통합_건수': '{:,}건',
    '통합_총수리비': '{:,.0f}원',
    '통합_평균수리비': '{:,.0f}원',
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

# df3 주요 자재 정보 표시
if 'df3_주요자재' in df.columns and analysis_source != "df1 기준 (정비일지)":
    st.subheader("🔧 파트별 주요 사용 자재 (df3 기준)")
    
    # 주요 자재 정보가 있는 파트들
    material_info = df[df['df3_주요자재'].notna()][['정비자소속', 'df3_주요자재']].drop_duplicates()
    
    if not material_info.empty:
        for _, row in material_info.head(10).iterrows():
            with st.expander(f"🔧 {row['정비자소속']} 파트 주요 자재"):
                materials = str(row['df3_주요자재']).split(', ')
                for i, material in enumerate(materials[:5], 1):
                    st.write(f"{i}. {material}")

st.markdown("---")

# 파트 선택 및 상세 분석 (기존 로직 유지하되 df3 정보 추가)
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
        
        # 파트 KPI - df3 정보 포함
        kpi_cols = 5 if 'df3_총수리비' in part_data.columns else 4
        if satisfaction_columns:
            kpi_cols += 1
        
        cols = st.columns(min(kpi_cols, 6))  # 최대 6개 컬럼
        
        col_idx = 0
        
        with cols[col_idx]:
            total_cases = len(part_data)
            st.metric("총 AS 건수 (df1)", f"{total_cases:,}건")
        col_idx += 1
        
        with cols[col_idx]:
            total_cost = part_data['수리비'].sum()
            st.metric("총 수리비 (df1)", f"{total_cost:,.0f}원")
        col_idx += 1
        
        # df3 정보 추가
        if 'df3_총수리비' in part_data.columns and col_idx < len(cols):
            with cols[col_idx]:
                df3_cost = part_data['df3_총수리비'].iloc[0] if len(part_data) > 0 else 0
                st.metric("총 수리비 (df3)", f"{df3_cost:,.0f}원")
            col_idx += 1
        
        if 'df3_수리건수' in part_data.columns and col_idx < len(cols):
            with cols[col_idx]:
                df3_count = part_data['df3_수리건수'].iloc[0] if len(part_data) > 0 else 0
                st.metric("수리 건수 (df3)", f"{df3_count:,}건")
            col_idx += 1
        
        if col_idx < len(cols):
            with cols[col_idx]:
                avg_cost = part_data['수리비'].mean() if total_cases > 0 else 0
                st.metric("평균 수리비", f"{avg_cost:,.0f}원")
            col_idx += 1
        
        # 만족도 메트릭
        if satisfaction_columns and col_idx < len(cols):
            with cols[col_idx]:
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

        # df3 주요 자재 정보 표시
        if 'df3_주요자재' in part_data.columns:
            main_materials = part_data['df3_주요자재'].iloc[0] if len(part_data) > 0 else None
            if pd.notna(main_materials):
                st.write("**🔧 주요 사용 자재 (df3 기준):**")
                materials = str(main_materials).split(', ')
                material_text = " | ".join(materials[:5])
                st.info(material_text)

        # 기존 파트별 세부 분석 로직 유지
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**🔨 주요 작업 유형**")
            if '작업유형' in part_data.columns:
                work_types = part_data['작업유형'].value_counts().head(5)
                for work, count in work_types.items():
                    percentage = (count / len(part_data) * 100)
                    st.write(f"• {work}: {count}건 ({percentage:.1f}%)")
            else:
                st.write("작업유형 데이터 없음")
        
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

        # 나머지 기존 로직 유지 (만족도 분석, 주의 케이스 등)
        # ... (기존 코드와 동일)

# 파트 성과 랭킹 - df3 기준 추가
st.markdown("---")
st.header("🏆 파트 성과 랭킹")

ranking_cols = 3 if 'df3_총수리비' in part_stats.columns else 2
if satisfaction_columns:
    ranking_cols += 1

cols = st.columns(ranking_cols)

col_idx = 0

with cols[col_idx]:
    st.subheader("💰 수리비 효율성 랭킹 (df1)")
    efficiency_ranking = part_stats.nsmallest(10, '건당수리비')[['정비자소속', '건당수리비', count_col]]
    
    for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   건당 수리비: {row['건당수리비']:,.0f}원 ({row[count_col]}건)")

col_idx += 1

with cols[col_idx]:
    st.subheader("📊 업무량 랭킹")
    volume_ranking = part_stats.nlargest(10, count_col)[['정비자소속', count_col, cost_col]]
    
    for idx, (_, row) in enumerate(volume_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   건수: {row[count_col]:,}건 (총 {row[cost_col]:,.0f}원)")

col_idx += 1

# df3 기준 랭킹 추가
if 'df3_총수리비' in part_stats.columns and col_idx < len(cols):
    with cols[col_idx]:
        st.subheader("🔧 df3 수리비 랭킹")
        df3_ranking = part_stats.nlargest(10, 'df3_총수리비')[['정비자소속', 'df3_총수리비', 'df3_수리건수']]
        
        for idx, (_, row) in enumerate(df3_ranking.iterrows()):
            medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
            st.write(f"{medal} **{row['정비자소속']}**")
            st.write(f"   df3 수리비: {row['df3_총수리비']:,.0f}원 ({row['df3_수리건수']}건)")
    
    col_idx += 1

# 만족도 랭킹
if satisfaction_columns and col_idx < len(cols):
    with cols[col_idx]:
        st.subheader("😊 고객 만족도 랭킹")
        
        satisfaction_col = satisfaction_columns[0]
        satisfaction_ranking = part_stats[part_stats[satisfaction_col].notna()].nlargest(10, satisfaction_col)
        
        if not satisfaction_ranking.empty:
            satisfaction_ranking = satisfaction_ranking[['정비자소속', satisfaction_col, count_col]]
            
            for idx, (_, row) in enumerate(satisfaction_ranking.iterrows()):
                medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
                st.write(f"{medal} **{row['정비자소속']}**")
                st.write(f"   만족도: {row[satisfaction_col]:.2f}점 ({row[count_col]}건)")
        else:
            st.write("만족도 데이터가 있는 파트가 없습니다.")

# 데이터 다운로드 - df3 정보 포함
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    csv_data = part_stats.to_excel(index=False)
    st.download_button(
        label="📊 파트별 통계 다운로드",
        data=csv_data,
        file_name=f"파트별_상세통계_{analysis_source.replace(' ', '_')}.xlsx",
        mime="text/excel"
    )

with col2:
    download_columns = ['정비자소속', '관리번호', '정비일자', '수리비', '작업유형', '정비대상']
    
    # df3 관련 컬럼 추가
    df3_download_cols = [col for col in ['df3_총수리비', 'df3_수리건수', 'df3_주요자재'] if col in df.columns]
    download_columns.extend(df3_download_cols)
    
    # 만족도 컬럼도 다운로드에 포함
    if satisfaction_columns:
        for col in satisfaction_columns:
            if col in df.columns:
                download_columns.append(col)
    
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_excel = detailed_data.to_excel(index=False)
    st.download_button(
        label="📄 상세 데이터 다운로드",
        data=detailed_excel,
        file_name=f"파트별_상세데이터_{analysis_source.replace(' ', '_')}.xlsx",
        mime="text/excel"
    )
