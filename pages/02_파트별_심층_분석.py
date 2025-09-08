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

# 파트별 통계 계산 - 수정된 버전
agg_dict = {
    '관리번호': 'count',
    '수리비': ['sum', 'mean']
}

# 수리시간이 실제로 데이터가 있는 경우만 추가
if '수리시간' in df.columns and df['수리시간'].sum() > 0:
    agg_dict['수리시간'] = 'mean'

part_stats = df.groupby('정비자소속').agg(agg_dict).round(2)

# 컬럼명 정리
if '수리시간' in agg_dict:
    part_stats.columns = ['AS건수', '총수리비', '평균수리비', '평균수리시간']
else:
    part_stats.columns = ['AS건수', '총수리비', '평균수리비']

part_stats = part_stats.reset_index()

# 효율성 지표 추가
part_stats['건당수리비'] = part_stats['총수리비'] / part_stats['AS건수']
part_stats['효율성점수'] = (part_stats['AS건수'] / part_stats['총수리비'] * 1000000).round(2)
part_stats = part_stats.sort_values('총수리비', ascending=False)

# 상위 파트 시각화
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

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계")

# 컬럼 순서 정리
display_columns = ['정비자소속', 'AS건수', '총수리비', '건당수리비', '효율성점수']

# 수리시간 컬럼이 있고 실제 데이터가 있는 경우만 추가
if '평균수리시간' in part_stats.columns and part_stats['평균수리시간'].sum() > 0:
    display_columns.insert(-1, '평균수리시간')

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
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_cases = len(part_data)
            st.metric("총 AS 건수", f"{total_cases:,}건")
        
        with col2:
            total_cost = part_data['수리비'].sum()
            st.metric("총 수리비", f"{total_cost:,.0f}원")
        
        with col3:
            avg_cost = part_data['수리비'].mean() if total_cases > 0 else 0
            st.metric("평균 수리비", f"{avg_cost:,.0f}원")
        
        with col4:
            # 수리시간이 실제로 있는 경우만 표시
            if '수리시간' in part_data.columns and part_data['수리시간'].sum() > 0:
                avg_time = part_data['수리시간'].mean()
                st.metric("평균 수리시간", f"{avg_time:.1f}시간")
            else:
                st.metric("평균 수리시간", "데이터 없음")

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

        # 주의 깊게 봐야 할 케이스들
        st.write("**🚨 주의 깊게 봐야 할 케이스들**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 고비용 케이스
            if part_data['수리비'].sum() > 0:
                high_cost_threshold = part_data['수리비'].quantile(0.9)
                high_cost_cases = part_data[part_data['수리비'] > high_cost_threshold]
                
                if not high_cost_cases.empty:
                    st.write("🔴 **고비용 수리 케이스 (상위 10%):**")
                    for idx, (_, case) in enumerate(high_cost_cases.head(3).iterrows()):
                        # 업체명 찾기
                        업체명 = "N/A"
                        for col in ['현장명', '업체명', '현장']:
                            if col in case and pd.notna(case[col]):
                                업체명 = str(case[col])[:15] + "..." if len(str(case[col])) > 15 else str(case[col])
                                break
                        
                        브랜드 = case.get('브랜드', 'N/A')
                        수리비 = case.get('수리비', 0)
                        
                        st.write(f"• {업체명} - {브랜드}")
                        st.write(f"  💰 {수리비:,.0f}원")
                else:
                    st.write("고비용 케이스 없음")
            else:
                st.write("수리비 데이터 없음")
        
        with col2:
            # 반복 수리 케이스
            if '관리번호' in part_data.columns:
                repeat_cases = part_data['관리번호'].value_counts()
                repeat_cases = repeat_cases[repeat_cases > 1].head(3)
                
                if not repeat_cases.empty:
                    st.write("🔄 **반복 수리 장비:**")
                    for 관리번호, 횟수 in repeat_cases.items():
                        equipment_info = part_data[part_data['관리번호'] == 관리번호].iloc[-1]
                        브랜드 = equipment_info.get('브랜드', 'N/A')
                        
                        st.write(f"• {관리번호}")
                        st.write(f"  📊 {횟수}회 수리 ({브랜드})")
                else:
                    st.write("반복 수리 장비 없음")
            else:
                st.write("관리번호 데이터 없음")

# 파트 간 비교 분석
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
        
        comparison_data.append(comparison_item)
    
    comparison_df = pd.DataFrame(comparison_data)
    
    # 비교 차트
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='총수리비',
            title="파트별 총 수리비 비교",
            color='총수리비',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='평균수리비',
            title="파트별 평균 수리비 비교",
            color='평균수리비',
            color_continuous_scale='Plasma'
        )
        st.plotly_chart(fig, use_container_width=True)

# 파트 성과 랭킹
st.markdown("---")
st.header("🏆 파트 성과 랭킹")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 수리비 효율성 랭킹")
    efficiency_ranking = part_stats.nsmallest(10, '건당수리비')[['정비자소속', '건당수리비', 'AS건수']]
    
    for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   건당 수리비: {row['건당수리비']:,.0f}원 ({row['AS건수']}건)")

with col2:
    st.subheader("📊 업무량 랭킹")
    volume_ranking = part_stats.nlargest(10, 'AS건수')[['정비자소속', 'AS건수', '총수리비']]
    
    for idx, (_, row) in enumerate(volume_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   AS 건수: {row['AS건수']:,}건 (총 {row['총수리비']:,.0f}원)")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    csv_data = part_stats.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📊 파트별 통계 다운로드 (CSV)",
        data=csv_data,
        file_name="파트별_상세통계.csv",
        mime="text/csv"
    )

with col2:
    download_columns = ['정비자소속', '관리번호', '정비일자', '수리비', '작업유형', '정비대상']
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_csv = detailed_data.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 상세 데이터 다운로드 (CSV)",
        data=detailed_csv,
        file_name="파트별_상세데이터.csv",
        mime="text/csv"
    )
