import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import sys
import os

# 유틸리티 함수 import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from data_processing_utils import (
    map_employee_data, 
    merge_repair_costs,
    clean_string_data,
    normalize_names_for_matching,
    setup_logging
)

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석 (df3 수리품목 중심)")

logger = setup_logging()

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

# 기본 데이터 로드
df1_data = st.session_state.get('df1_with_costs', pd.DataFrame())
df3_data = st.session_state.get('df3_with_org', None)
org_data = st.session_state.get('org_data', None)

# df3 중심 데이터 처리 및 통합
@st.cache_data(show_spinner=False)
def create_df3_centered_analysis(df1, df3, org_df):
    """df3를 중심으로 df1과 조직도를 통합하여 분석용 데이터 생성"""
    
    if df3 is None:
        st.error("df3 수리품목 데이터가 없습니다.")
        return None
    
    logger.info("df3 중심 분석 데이터 생성 시작")
    
    # df3 기본 전처리
    df3_processed = df3.copy()
    
    # 출고일자 처리
    if '출고일자' in df3_processed.columns:
        df3_processed['출고일자'] = pd.to_datetime(df3_processed['출고일자'], errors='coerce')
        df3_processed['출고년'] = df3_processed['출고일자'].dt.year
        df3_processed['출고월'] = df3_processed['출고일자'].dt.month
        df3_processed['출고년월'] = df3_processed['출고일자'].dt.to_period('M')
    
    # 수리비 처리
    cost_col = None
    for col in ['출고금액', '금액', '단가', '수리비']:
        if col in df3_processed.columns:
            cost_col = col
            break
    
    if cost_col:
        df3_processed['수리비'] = pd.to_numeric(df3_processed[cost_col], errors='coerce').fillna(0)
    else:
        df3_processed['수리비'] = 0
    
    # 관리번호 정리
    if '관리번호' in df3_processed.columns:
        df3_processed['관리번호'] = df3_processed['관리번호'].astype(str).str.strip()
    
    # 조직도 매핑 (출고자 기준)
    if org_df is not None and '출고자' in df3_processed.columns:
        st.write("### 🔍 조직도 매핑 (출고자 기준)")
        
        # 출고자를 사번으로 간주하여 매핑
        df3_processed['출고자'] = df3_processed['출고자'].astype(str).str.strip()
        org_clean = org_df.copy()
        
        # 조직도 컬럼 정리
        if '사번' in org_clean.columns and '파트' in org_clean.columns:
            org_clean['사번'] = org_clean['사번'].astype(str).str.strip()
            org_mapping = org_clean[['사번', '파트', '직급', '직책']].dropna(subset=['사번', '파트'])
            
            # 매핑 수행
            df3_processed = pd.merge(
                df3_processed,
                org_mapping,
                left_on='출고자',
                right_on='사번',
                how='left'
            )
            
            # 매핑 결과 확인
            mapped_count = df3_processed['파트'].notna().sum()
            mapping_rate = (mapped_count / len(df3_processed) * 100) if len(df3_processed) > 0 else 0
            
            st.write(f"**조직도 매핑 결과: {mapped_count}건 ({mapping_rate:.1f}%)**")
            
            if mapped_count == 0:
                st.warning("조직도 매핑이 실패했습니다. 출고자를 파트로 사용합니다.")
                df3_processed['파트'] = df3_processed['출고자']
        else:
            st.warning("조직도에 필요한 컬럼이 없습니다.")
            df3_processed['파트'] = df3_processed.get('출고자', '미분류')
    
    # df1과 매핑 (년월 + 관리번호 기준으로 업체명과 작업유형 정보 가져오기)
    if not df1.empty and '정비일자' in df1.columns and '관리번호' in df1.columns:
        st.write("### 🔍 df1과 매핑 (업체명, 작업유형)")
        
        # df1 전처리
        df1_temp = df1.copy()
        df1_temp['정비일자'] = pd.to_datetime(df1_temp['정비일자'], errors='coerce')
        df1_temp['정비년월'] = df1_temp['정비일자'].dt.to_period('M')
        df1_temp['관리번호'] = df1_temp['관리번호'].astype(str).str.strip()
        
        # 대분류/중분류/소분류 합쳐서 작업유형 생성
        work_type_parts = []
        for col in ['대분류', '중분류', '소분류']:
            if col in df1_temp.columns:
                work_type_parts.append(df1_temp[col].astype(str))
        
        if work_type_parts:
            df1_temp['작업유형'] = work_type_parts[0]
            for part in work_type_parts[1:]:
                df1_temp['작업유형'] = df1_temp['작업유형'] + ' > ' + part
            
            # 'nan' 제거 및 정리
            df1_temp['작업유형'] = df1_temp['작업유형'].str.replace('nan', '').str.replace(' > ', ' > ').str.strip(' > ')
            df1_temp['작업유형'] = df1_temp['작업유형'].replace('', '미분류')
        
        # 업체명 컬럼 찾기
        client_col = None
        for col in ['현장명', '업체명', '현장']:
            if col in df1_temp.columns:
                client_col = col
                break
        
        # 매핑할 컬럼들 준비
        mapping_cols = ['관리번호', '정비년월']
        if client_col:
            mapping_cols.append(client_col)
        if '작업유형' in df1_temp.columns:
            mapping_cols.append('작업유형')
        
        if len(mapping_cols) > 2:
            # 년월 + 관리번호 기준 매핑
            df1_mapping = df1_temp[mapping_cols].drop_duplicates()
            
            df3_processed = pd.merge(
                df3_processed,
                df1_mapping,
                left_on=['관리번호', '출고년월'],
                right_on=['관리번호', '정비년월'],
                how='left'
            )
            
            # 매핑되지 않은 경우 관리번호만으로 재시도
            if client_col:
                unmapped_mask = df3_processed[client_col].isna()
                if unmapped_mask.any():
                    simple_mapping_cols = ['관리번호']
                    if client_col:
                        simple_mapping_cols.append(client_col)
                    if '작업유형' in df1_temp.columns:
                        simple_mapping_cols.append('작업유형')
                    
                    df1_mapping_simple = df1_temp[simple_mapping_cols].drop_duplicates().groupby('관리번호').first()
                    
                    for idx, row in df3_processed[unmapped_mask].iterrows():
                        if row['관리번호'] in df1_mapping_simple.index:
                            for col in simple_mapping_cols[1:]:
                                df3_processed.loc[idx, col] = df1_mapping_simple.loc[row['관리번호'], col]
            
            # 컬럼명 통일
            if client_col:
                df3_processed['업체명'] = df3_processed[client_col]
            
            # 매핑 결과 확인
            if client_col:
                mapped_clients = df3_processed['업체명'].notna().sum()
                st.write(f"**업체명 매핑: {mapped_clients}건**")
            
            if '작업유형' in df3_processed.columns:
                mapped_work_types = df3_processed['작업유형'].notna().sum()
                st.write(f"**작업유형 매핑: {mapped_work_types}건**")
    
    # 임시 컬럼 정리
    if '정비년월' in df3_processed.columns:
        df3_processed = df3_processed.drop('정비년월', axis=1)
    if '사번' in df3_processed.columns:
        df3_processed = df3_processed.drop('사번', axis=1)
    
    logger.info(f"df3 중심 분석 데이터 생성 완료: {len(df3_processed)}건")
    return df3_processed

# 통합 데이터 생성
df3_integrated = create_df3_centered_analysis(df1_data, df3_data, org_data)

if df3_integrated is None or df3_integrated.empty:
    st.error("분석할 데이터가 없습니다.")
    st.stop()

# 파트 컬럼 확인
if '파트' not in df3_integrated.columns or df3_integrated['파트'].isna().all():
    st.error("파트 정보가 없습니다. 조직도 매핑을 확인해주세요.")
    st.stop()

# 사이드바 필터
st.sidebar.header("🔧 분석 옵션")

# 기간 필터
if '출고일자' in df3_integrated.columns and df3_integrated['출고일자'].notna().any():
    min_date = df3_integrated['출고일자'].min().date()
    max_date = df3_integrated['출고일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df3_integrated = df3_integrated[
            (df3_integrated['출고일자'].dt.date >= start_date) & 
            (df3_integrated['출고일자'].dt.date <= end_date)
        ]

# 파트별 전체 현황 (df3 중심)
st.header("📊 파트별 전체 현황 (df3 수리품목 기준)")

# 파트별 통계 계산
part_stats = df3_integrated.groupby('파트').agg({
    '관리번호': 'count',
    '수리비': ['sum', 'mean'],
    '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:3]) if '자재명' in df3_integrated.columns else ''
}).round(2)

# 컬럼명 정리
part_stats.columns = ['출고건수', '총출고금액', '평균출고금액', '주요자재']
part_stats = part_stats.reset_index()

# 직급, 직책 정보 추가
if '직급' in df3_integrated.columns:
    part_position = df3_integrated.groupby('파트')['직급'].first().reset_index()
    part_stats = pd.merge(part_stats, part_position, on='파트', how='left')

if '직책' in df3_integrated.columns:
    part_role = df3_integrated.groupby('파트')['직책'].first().reset_index()
    part_stats = pd.merge(part_stats, part_role, on='파트', how='left')

# 효율성 지표 추가
part_stats['건당출고금액'] = part_stats['총출고금액'] / part_stats['출고건수']
part_stats['효율성점수'] = (part_stats['출고건수'] / part_stats['총출고금액'] * 1000000).round(2)
part_stats = part_stats.sort_values('총출고금액', ascending=False)

# 상위 파트 시각화
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 파트별 총 출고금액")
    top_parts = part_stats.head(10)
    
    fig = px.bar(
        top_parts, 
        x='총출고금액', 
        y='파트',
        orientation='h',
        color='총출고금액',
        color_continuous_scale='Reds',
        title="파트별 총 출고금액 (df3 기준)"
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 파트별 출고건수")
    
    fig2 = px.bar(
        top_parts,
        x='출고건수',
        y='파트', 
        orientation='h',
        color='출고건수',
        color_continuous_scale='Blues',
        title="파트별 출고건수 (df3 기준)"
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계 (df3 기준)")

# 컬럼 순서 정리
display_columns = ['파트', '출고건수', '총출고금액', '건당출고금액']

if '직급' in part_stats.columns:
    display_columns.append('직급')
if '직책' in part_stats.columns:
    display_columns.append('직책')

display_columns.extend(['주요자재', '효율성점수'])

display_stats = part_stats[display_columns]

# 포맷팅
format_dict = {
    '출고건수': '{:,}건',
    '총출고금액': '{:,.0f}원',
    '건당출고금액': '{:,.0f}원',
    '효율성점수': '{:.2f}'
}

st.dataframe(
    display_stats.style.format(format_dict),
    use_container_width=True
)

st.markdown("---")

# 파트 선택 및 상세 분석 (df3 중심)
st.header("🔍 파트별 상세 분석 (df3 수리품목 중심)")

available_parts = df3_integrated['파트'].dropna().unique()
selected_parts = st.multiselect(
    "상세 분석할 파트 선택",
    available_parts,
    default=available_parts[:2] if len(available_parts) >= 2 else available_parts
)

if selected_parts:
    for i, part in enumerate(selected_parts):
        if i > 0:
            st.markdown("---")
        
        part_data = df3_integrated[df3_integrated['파트'] == part]
        
        st.subheader(f"🔧 {part} 파트 상세 분석 (df3 기준)")
        
        # 파트 KPI
        cols = st.columns(5)
        
        with cols[0]:
            total_cases = len(part_data)
            st.metric("총 출고건수", f"{total_cases:,}건")
        
        with cols[1]:
            total_cost = part_data['수리비'].sum()
            st.metric("총 출고금액", f"{total_cost:,.0f}원")
        
        with cols[2]:
            avg_cost = part_data['수리비'].mean() if total_cases > 0 else 0
            st.metric("평균 출고금액", f"{avg_cost:,.0f}원")
        
        with cols[3]:
            unique_equipment = part_data['관리번호'].nunique()
            st.metric("관련 장비", f"{unique_equipment}대")
        
        with cols[4]:
            unique_clients = part_data['업체명'].nunique() if '업체명' in part_data.columns else 0
            st.metric("관련 업체", f"{unique_clients}개")
        
        # 파트 정보 표시
        if '직급' in part_data.columns or '직책' in part_data.columns:
            st.write("**👤 파트 정보**")
            col1, col2 = st.columns(2)
            
            with col1:
                if '직급' in part_data.columns:
                    position = part_data['직급'].iloc[0] if not part_data['직급'].isna().all() else "정보 없음"
                    st.write(f"• **직급**: {position}")
            
            with col2:
                if '직책' in part_data.columns:
                    role = part_data['직책'].iloc[0] if not part_data['직책'].isna().all() else "정보 없음"
                    st.write(f"• **직책**: {role}")
        
        # 파트별 세부 분석 - 수정된 버전
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**🔨 주요 작업 유형**")
            if '작업유형' in part_data.columns and part_data['작업유형'].notna().any():
                # 작업유형에서 'nan' 및 빈 값 제거
                valid_work_types = part_data['작업유형'].dropna()
                valid_work_types = valid_work_types[valid_work_types != '미분류']
                valid_work_types = valid_work_types[valid_work_types.str.strip() != '']
                
                if not valid_work_types.empty:
                    work_types = valid_work_types.value_counts().head(5)
                    for work, count in work_types.items():
                        percentage = (count / len(part_data) * 100)
                        # 작업유형이 너무 길면 줄임
                        work_short = work[:30] + "..." if len(str(work)) > 30 else str(work)
                        st.write(f"• {work_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("작업유형 데이터 없음")
            else:
                st.write("작업유형 데이터 없음")
        
        with col2:
            st.write("**⚙️ 주요 정비 대상 (자재)**")
            if '자재명' in part_data.columns and part_data['자재명'].notna().any():
                # 자재명에서 유효한 값만 추출
                valid_materials = part_data['자재명'].dropna()
                valid_materials = valid_materials[valid_materials.str.strip() != '']
                
                if not valid_materials.empty:
                    materials = valid_materials.value_counts().head(5)
                    for material, count in materials.items():
                        percentage = (count / len(part_data) * 100)
                        # 자재명이 너무 길면 줄임
                        material_short = material[:25] + "..." if len(str(material)) > 25 else str(material)
                        st.write(f"• {material_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("자재명 데이터 없음")
            else:
                st.write("자재명 데이터 없음")
        
        with col3:
            st.write("**🏢 주요 담당 업체**")
            if '업체명' in part_data.columns and part_data['업체명'].notna().any():
                valid_clients = part_data['업체명'].dropna()
                valid_clients = valid_clients[valid_clients.str.strip() != '']
                
                if not valid_clients.empty:
                    clients = valid_clients.value_counts().head(5)
                    for client, count in clients.items():
                        percentage = (count / len(part_data) * 100)
                        client_short = str(client)[:15] + "..." if len(str(client)) > 15 else str(client)
                        st.write(f"• {client_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("업체명 데이터 없음")
            else:
                st.write("업체명 데이터 없음")
        
        # 고액 출고 케이스
        st.write("**🚨 주의 깊게 봐야 할 케이스들**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 고액 출고 케이스
            if part_data['수리비'].sum() > 0:
                high_cost_threshold = part_data['수리비'].quantile(0.9)
                high_cost_cases = part_data[part_data['수리비'] > high_cost_threshold]
                
                if not high_cost_cases.empty:
                    st.write("🔴 **고액 출고 케이스 (상위 10%):**")
                    for idx, (_, case) in enumerate(high_cost_cases.head(3).iterrows()):
                        관리번호 = case.get('관리번호', 'N/A')
                        자재명 = case.get('자재명', 'N/A')
                        출고금액 = case.get('수리비', 0)
                        
                        # 자재명이 너무 길면 줄임
                        자재명_short = 자재명[:20] + "..." if len(str(자재명)) > 20 else str(자재명)
                        
                        st.write(f"• {관리번호} - {자재명_short}")
                        st.write(f"  💰 {출고금액:,.0f}원")
                else:
                    st.write("고액 출고 케이스 없음")
            else:
                st.write("출고금액 데이터 없음")
        
        with col2:
            # 반복 출고 장비
            if '관리번호' in part_data.columns:
                repeat_cases = part_data['관리번호'].value_counts()
                repeat_cases = repeat_cases[repeat_cases > 1].head(3)
                
                if not repeat_cases.empty:
                    st.write("🔄 **반복 출고 장비:**")
                    for 관리번호, 횟수 in repeat_cases.items():
                        equipment_info = part_data[part_data['관리번호'] == 관리번호].iloc[-1]
                        업체명 = equipment_info.get('업체명', 'N/A')
                        업체명_short = str(업체명)[:15] + "..." if len(str(업체명)) > 15 else str(업체명)
                        
                        st.write(f"• {관리번호}")
                        st.write(f"  📊 {횟수}회 출고 ({업체명_short})")
                else:
                    st.write("반복 출고 장비 없음")
            else:
                st.write("관리번호 데이터 없음")

# 파트 간 비교 분석 (df3 중심)
if len(selected_parts) > 1:
    st.markdown("---")
    st.header("⚖️ 선택된 파트 간 비교 (df3 기준)")
    
    comparison_data = []
    for part in selected_parts:
        part_data = df3_integrated[df3_integrated['파트'] == part]
        
        comparison_item = {
            '파트': part,
            '출고건수': len(part_data),
            '총출고금액': part_data['수리비'].sum(),
            '평균출고금액': part_data['수리비'].mean(),
            '관련장비수': part_data['관리번호'].nunique(),
            '관련업체수': part_data['업체명'].nunique() if '업체명' in part_data.columns else 0
        }
        
        comparison_data.append(comparison_item)
    
    comparison_df = pd.DataFrame(comparison_data)
    
    # 비교 차트
    cols = st.columns(3)
    
    with cols[0]:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='총출고금액',
            title="파트별 총 출고금액 비교",
            color='총출고금액',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with cols[1]:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='평균출고금액',
            title="파트별 평균 출고금액 비교",
            color='평균출고금액',
            color_continuous_scale='Plasma'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with cols[2]:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='출고건수',
            title="파트별 출고건수 비교",
            color='출고건수',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)

# 파트 성과 랭킹 (df3 중심)
st.markdown("---")
st.header("🏆 파트 성과 랭킹 (df3 기준)")

cols = st.columns(3)

with cols[0]:
    st.subheader("💰 출고금액 효율성 랭킹")
    efficiency_ranking = part_stats.nsmallest(10, '건당출고금액')[['파트', '건당출고금액', '출고건수']]
    
    for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['파트']}**")
        st.write(f"   건당 출고금액: {row['건당출고금액']:,.0f}원 ({row['출고건수']}건)")

with cols[1]:
    st.subheader("📊 출고량 랭킹")
    volume_ranking = part_stats.nlargest(10, '출고건수')[['파트', '출고건수', '총출고금액']]
    
    for idx, (_, row) in enumerate(volume_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['파트']}**")
        st.write(f"   출고건수: {row['출고건수']:,}건 (총 {row['총출고금액']:,.0f}원)")

with cols[2]:
    st.subheader("💎 총 출고금액 랭킹")
    cost_ranking = part_stats.nlargest(10, '총출고금액')[['파트', '총출고금액', '출고건수']]
    
    for idx, (_, row) in enumerate(cost_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['파트']}**")
        st.write(f"   총 출고금액: {row['총출고금액']:,.0f}원 ({row['출고건수']}건)")

# 데이터 다운로드 - 엑셀 버전
st.markdown("---")
st.subheader("📥 분석 결과 다운로드 (df3 중심)")

col1, col2, col3 = st.columns(3)

with col1:
    # 파트별 통계 다운로드
    excel_data = to_excel_download(part_stats, "df3_파트별_상세통계.xlsx")
    st.download_button(
        label="📊 파트별 통계 다운로드 (Excel)",
        data=excel_data,
        file_name="df3_파트별_상세통계.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col2:
    # df3 통합 데이터 다운로드
    download_columns = ['파트', '관리번호', '출고일자', '수리비', '자재명', '직급', '직책', '작업유형']
    if '업체명' in df3_integrated.columns:
        download_columns.append('업체명')
    
    available_columns = [col for col in download_columns if col in df3_integrated.columns]
    detailed_data = df3_integrated[available_columns].copy()
    detailed_excel = to_excel_download(detailed_data, "df3_통합_상세데이터.xlsx")
    st.download_button(
        label="📄 df3 통합 상세 데이터 (Excel)",
        data=detailed_excel,
        file_name="df3_통합_상세데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col3:
    # 선택된 파트 상세 데이터
    if selected_parts:
        selected_data = df3_integrated[df3_integrated['파트'].isin(selected_parts)]
        selected_excel = to_excel_download(selected_data, "선택된_파트_상세데이터.xlsx")
        st.download_button(
            label="🎯 선택된 파트 데이터 (Excel)",
            data=selected_excel,
            file_name="선택된_파트_상세데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# 디버깅 정보 (개발용)
if st.sidebar.checkbox("🔍 디버깅 정보 표시"):
    st.subheader("🔍 디버깅 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**df3_integrated 컬럼:**")
        st.write(df3_integrated.columns.tolist())
        st.write(f"**데이터 형태:** {df3_integrated.shape}")
    
    with col2:
        st.write("**파트별 데이터 수:**")
        part_counts = df3_integrated['파트'].value_counts().head(10)
        for part, count in part_counts.items():
            st.write(f"- {part}: {count}건")
    
    st.write("**샘플 데이터:**")
    st.dataframe(df3_integrated.head())
