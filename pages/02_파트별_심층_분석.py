import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석")

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# df3 원본 데이터 확인
df3_with_org = st.session_state.get('df3_with_org', None)

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
    
    return df

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

# 파트별 전체 현황
st.header("📊 파트별 전체 현황")

# 파트별 통계 계산 - df3 정보 포함
agg_dict = {
    '관리번호': 'count',
    '수리비': ['sum', 'mean']
}

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
base_columns = ['AS건수', '총수리비', '평균수리비']
if '수리시간' in agg_dict:
    base_columns.append('평균수리시간')

all_columns = base_columns + satisfaction_cols
part_stats.columns = all_columns
part_stats = part_stats.reset_index()

# df3 정보 추가 (수리담당파트별 통계)
if df3_with_org is not None and '파트' in df3_with_org.columns:
    st.subheader("🔧 df3 수리품목 기준 파트별 분석")
    
    df3_part_stats = df3_with_org.groupby('파트').agg({
        '수리비': ['sum', 'count', 'mean'],
        '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:5])
    }).round(2)
    
    df3_part_stats.columns = ['총출고금액', '출고건수', '평균출고금액', '주요자재']
    df3_part_stats = df3_part_stats.reset_index()
    df3_part_stats = df3_part_stats.sort_values('총출고금액', ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # df3 파트별 출고금액 차트
        fig = px.bar(
            df3_part_stats.head(10),
            x='총출고금액',
            y='파트',
            orientation='h',
            color='총출고금액',
            color_continuous_scale='Reds',
            title="df3 기준 파트별 총 출고금액"
        )
        fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # df3 파트별 출고건수 차트
        fig2 = px.bar(
            df3_part_stats.head(10),
            x='출고건수',
            y='파트',
            orientation='h',
            color='출고건수',
            color_continuous_scale='Blues',
            title="df3 기준 파트별 출고건수"
        )
        fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)
    
    # df3 파트별 상세 테이블
    st.dataframe(
        df3_part_stats.style.format({
            '총출고금액': '{:,.0f}원',
            '평균출고금액': '{:,.0f}원'
        }),
        use_container_width=True
    )

# 효율성 지표 추가
part_stats['건당수리비'] = part_stats['총수리비'] / part_stats['AS건수']
part_stats['효율성점수'] = (part_stats['AS건수'] / part_stats['총수리비'] * 1000000).round(2)
part_stats = part_stats.sort_values('총수리비', ascending=False)

# 상위 파트 시각화
st.subheader("📊 df1 기준 파트별 현황")
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 파트별 총 수리비")
    top_parts = part_stats.head(10)
    
    fig = px.bar(
        top_parts, 
        x='총수리비', 
        y='정비자소속',
        orientation='h',
        color='총수리비',
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 파트별 AS 건수")
    
    fig2 = px.bar(
        top_parts,
        x='AS건수',
        y='정비자소속', 
        orientation='h',
        color='AS건수',
        color_continuous_scale='Blues'
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 만족도 차트 추가
if satisfaction_cols:
    st.subheader("😊 파트별 고객 만족도")
    
    main_satisfaction_col = satisfaction_cols[0]
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

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계")

# 컬럼 순서 정리
display_columns = ['정비자소속', 'AS건수', '총수리비', '건당수리비']

if '평균수리시간' in part_stats.columns and part_stats['평균수리시간'].sum() > 0:
    display_columns.append('평균수리시간')

if satisfaction_cols:
    display_columns.extend(satisfaction_cols)

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

for col in satisfaction_cols:
    if col in display_stats.columns:
        format_dict[col] = '{:.2f}점'

st.dataframe(
    display_stats.style.format(format_dict),
    use_container_width=True
)

st.markdown("---")

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
        
        # 파트 KPI
        kpi_cols = 4
        if satisfaction_cols:
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
            if '수리시간' in part_data.columns and part_data['수리시간'].sum() > 0:
                avg_time = part_data['수리시간'].mean()
                st.metric("평균 수리시간", f"{avg_time:.1f}시간")
            else:
                st.metric("평균 수리시간", "데이터 없음")
        
        # 만족도 메트릭 추가
        if satisfaction_cols and kpi_cols == 5:
            with cols[4]:
                available_satisfaction_cols = []
                for col in satisfaction_cols:
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
        
        # df3 기준 해당 파트 정보 표시
        if df3_with_org is not None and '파트' in df3_with_org.columns:
            part_df3_data = df3_with_org[df3_with_org['파트'] == part]
            if not part_df3_data.empty:
                st.write(f"**🔧 df3 기준 {part} 파트 정보**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    df3_total_cost = part_df3_data['수리비'].sum()
                    st.write(f"• 총 출고금액: {df3_total_cost:,.0f}원")
                
                with col2:
                    df3_total_cases = len(part_df3_data)
                    st.write(f"• 총 출고건수: {df3_total_cases:,}건")
                
                with col3:
                    df3_avg_cost = part_df3_data['수리비'].mean()
                    st.write(f"• 평균 출고금액: {df3_avg_cost:,.0f}원")
                
                # 주요 자재
                if '자재명' in part_df3_data.columns:
                    top_materials = part_df3_data['자재명'].value_counts().head(5)
                    st.write("**주요 사용 자재:**")
                    for material, count in top_materials.items():
                        st.write(f"  - {material}: {count}회")

        # 파트별 세부 분석
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

# 데이터 다운로드 - 엑셀 버전
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2, col3 = st.columns(3)

with col1:
    # 파트별 통계 다운로드
    excel_data = to_excel_download(part_stats, "파트별_상세통계.xlsx")
    st.download_button(
        label="📊 파트별 통계 다운로드 (Excel)",
        data=excel_data,
        file_name="파트별_상세통계.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col2:
    # 상세 데이터 다운로드
    download_columns = ['정비자소속', '관리번호', '정비일자', '수리비', '작업유형', '정비대상']
    
    if satisfaction_cols:
        for col in satisfaction_cols:
            if col in df.columns:
                download_columns.append(col)
    
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_excel = to_excel_download(detailed_data, "파트별_상세데이터.xlsx")
    st.download_button(
        label="📄 상세 데이터 다운로드 (Excel)",
        data=detailed_excel,
        file_name="파트별_상세데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col3:
    # df3 데이터 다운로드
    if df3_with_org is not None:
        df3_excel = to_excel_download(df3_with_org, "df3_수리품목_조직도매핑.xlsx")
        st.download_button(
            label="🔧 df3 수리품목 데이터 (Excel)",
            data=df3_excel,
            file_name="df3_수리품목_조직도매핑.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
