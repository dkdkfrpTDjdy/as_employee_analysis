import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import logging

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석 (df3 수리품목 중심)")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

# 세션 상태 디버깅
st.sidebar.header("🔍 세션 상태 확인")
st.sidebar.write("**현재 세션 키들:**")
for key in st.session_state.keys():
    st.sidebar.write(f"- {key}")

# 데이터 확인 - 정확한 세션 키 사용
available_data = {}

# df1 데이터 확인
if 'df1_with_costs' in st.session_state:
    available_data['df1'] = st.session_state['df1_with_costs']
    st.sidebar.success("✅ df1_with_costs 발견")
else:
    st.sidebar.error("❌ df1_with_costs 없음")

# df3 데이터 확인 - 여러 가능한 키 체크
df3_keys = ['df3_with_org', 'df3_raw', 'df3_integrated']
df3_data = None

for key in df3_keys:
    if key in st.session_state:
        df3_data = st.session_state[key]
        available_data['df3'] = df3_data
        st.sidebar.success(f"✅ {key} 발견: {len(df3_data)}행")
        break

if df3_data is None:
    st.sidebar.error("❌ df3 데이터 없음")

# 조직도 데이터 확인
org_keys = ['org_data', 'df4', 'organization_data']
org_data = None

for key in org_keys:
    if key in st.session_state:
        org_data = st.session_state[key]
        available_data['org'] = org_data
        st.sidebar.success(f"✅ {key} 발견: {len(org_data)}행")
        break

if org_data is None:
    st.sidebar.error("❌ 조직도 데이터 없음")

# 데이터 없으면 중단
if not available_data:
    st.error("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

# df3가 없으면 에러
if 'df3' not in available_data:
    st.error("🚨 df3 수리품목 데이터가 필요합니다. 메인 페이지에서 소모품 출고 데이터를 업로드해주세요.")
    st.stop()

# 데이터 로드
df3_data = available_data['df3']
df1_data = available_data.get('df1', pd.DataFrame())
org_data = available_data.get('org', None)

st.success(f"✅ df3 데이터 로드 완료: {len(df3_data)}행")

# df3 중심 데이터 처리
@st.cache_data(show_spinner=False)
def create_df3_centered_analysis(df3, df1, org_df):
    """df3를 중심으로 분석용 데이터 생성"""
    
    logger.info("df3 중심 분석 데이터 생성 시작")
    st.write("### 🔄 df3 데이터 처리 중...")
    
    # df3 기본 전처리
    df3_processed = df3.copy()
    
    st.write(f"**df3 원본 데이터:** {len(df3_processed)}행, {len(df3_processed.columns)}컬럼")
    st.write(f"**df3 컬럼:** {df3_processed.columns.tolist()}")
    
    # 출고일자 처리
    if '출고일자' in df3_processed.columns:
        df3_processed['출고일자'] = pd.to_datetime(df3_processed['출고일자'], errors='coerce')
        df3_processed['출고년'] = df3_processed['출고일자'].dt.year
        df3_processed['출고월'] = df3_processed['출고일자'].dt.month
        df3_processed['출고년월'] = df3_processed['출고일자'].dt.to_period('M')
        st.write("✅ 출고일자 처리 완료")
    
    # 수리비 처리
    cost_col = None
    for col in ['출고금액', '금액', '단가', '수리비']:
        if col in df3_processed.columns:
            cost_col = col
            break
    
    if cost_col:
        df3_processed['수리비'] = pd.to_numeric(df3_processed[cost_col], errors='coerce').fillna(0)
        st.write(f"✅ 수리비 처리 완료 (기준 컬럼: {cost_col})")
        st.write(f"   총 수리비: {df3_processed['수리비'].sum():,.0f}원")
    else:
        df3_processed['수리비'] = 0
        st.warning("⚠️ 수리비 컬럼을 찾을 수 없습니다.")
    
    # 관리번호 정리
    if '관리번호' in df3_processed.columns:
        df3_processed['관리번호'] = df3_processed['관리번호'].astype(str).str.strip()
        st.write("✅ 관리번호 정리 완료")
    
    # 조직도 매핑 (출고자 기준)
    if org_df is not None and '출고자' in df3_processed.columns:
        st.write("### 🔍 조직도 매핑 (출고자 기준)")
        
        # 출고자를 사번으로 간주하여 매핑
        df3_processed['출고자'] = df3_processed['출고자'].astype(str).str.strip()
        org_clean = org_df.copy()
        
        st.write(f"**조직도 컬럼:** {org_clean.columns.tolist()}")
        
        # 조직도 컬럼 정리
        if '사번' in org_clean.columns and '파트' in org_clean.columns:
            org_clean['사번'] = org_clean['사번'].astype(str).str.strip()
            org_mapping = org_clean[['사번', '파트', '직급', '직책']].dropna(subset=['사번', '파트'])
            
            st.write(f"**매핑 가능한 조직도 레코드:** {len(org_mapping)}건")
            
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
            elif mapping_rate < 50:
                st.warning("매핑률이 낮습니다. 매핑되지 않은 항목은 출고자를 파트로 사용합니다.")
                unmapped_mask = df3_processed['파트'].isna()
                df3_processed.loc[unmapped_mask, '파트'] = df3_processed.loc[unmapped_mask, '출고자']
        else:
            st.warning("조직도에 필요한 컬럼이 없습니다.")
            df3_processed['파트'] = df3_processed.get('출고자', '미분류')
    else:
        # 조직도가 없거나 출고자 컬럼이 없는 경우
        if '출고자' in df3_processed.columns:
            df3_processed['파트'] = df3_processed['출고자']
            st.info("조직도 없음. 출고자를 파트로 사용합니다.")
        else:
            df3_processed['파트'] = '미분류'
            st.warning("출고자 컬럼이 없습니다. 미분류로 처리합니다.")
    
    # df1과 매핑 (업체명과 작업유형 정보 가져오기)
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
            st.write("✅ 작업유형 생성 완료")
        
        # 업체명 컬럼 찾기
        client_col = None
        for col in ['현장명', '업체명', '현장']:
            if col in df1_temp.columns:
                client_col = col
                break
        
        # 매핑 수행
        if client_col or '작업유형' in df1_temp.columns:
            mapping_cols = ['관리번호']
            if client_col:
                mapping_cols.append(client_col)
            if '작업유형' in df1_temp.columns:
                mapping_cols.append('작업유형')
            
            # 년월 기준 매핑 시도
            if '정비년월' in df1_temp.columns and '출고년월' in df3_processed.columns:
                mapping_cols.append('정비년월')
                df1_mapping = df1_temp[mapping_cols].drop_duplicates()
                
                df3_processed = pd.merge(
                    df3_processed,
                    df1_mapping,
                    left_on=['관리번호', '출고년월'],
                    right_on=['관리번호', '정비년월'],
                    how='left'
                )
                
                # 정비년월 컬럼 제거
                if '정비년월' in df3_processed.columns:
                    df3_processed = df3_processed.drop('정비년월', axis=1)
                    
                st.write("✅ 년월 + 관리번호 기준 매핑 완료")
            else:
                # 관리번호만으로 매핑
                df1_mapping = df1_temp[mapping_cols].drop_duplicates().groupby('관리번호').first().reset_index()
                
                df3_processed = pd.merge(
                    df3_processed,
                    df1_mapping,
                    on='관리번호',
                    how='left'
                )
                
                st.write("✅ 관리번호 기준 매핑 완료")
            
            # 컬럼명 통일
            if client_col and client_col in df3_processed.columns:
                df3_processed['업체명'] = df3_processed[client_col]
                if client_col != '업체명':
                    df3_processed = df3_processed.drop(client_col, axis=1)
            
            # 매핑 결과 확인
            if '업체명' in df3_processed.columns:
                mapped_clients = df3_processed['업체명'].notna().sum()
                st.write(f"**업체명 매핑: {mapped_clients}건**")
            
            if '작업유형' in df3_processed.columns:
                mapped_work_types = df3_processed['작업유형'].notna().sum()
                st.write(f"**작업유형 매핑: {mapped_work_types}건**")
    
    # 임시 컬럼 정리
    cleanup_cols = ['사번']
    for col in cleanup_cols:
        if col in df3_processed.columns:
            df3_processed = df3_processed.drop(col, axis=1)
    
    logger.info(f"df3 중심 분석 데이터 생성 완료: {len(df3_processed)}건")
    st.success(f"✅ 최종 데이터 생성 완료: {len(df3_processed)}건")
    
    return df3_processed

# 통합 데이터 생성
df3_integrated = create_df3_centered_analysis(df3_data, df1_data, org_data)

if df3_integrated is None or df3_integrated.empty:
    st.error("분석할 데이터가 없습니다.")
    st.stop()

# 파트 컬럼 확인
if '파트' not in df3_integrated.columns or df3_integrated['파트'].isna().all():
    st.error("파트 정보가 없습니다.")
    st.stop()

# 파트별 데이터 확인
part_counts = df3_integrated['파트'].value_counts()
st.write("### 📊 파트별 데이터 현황")
st.write(f"**총 파트 수:** {len(part_counts)}개")
st.write("**상위 파트:**")
for part, count in part_counts.head(10).items():
    st.write(f"- {part}: {count}건")

# 사이드바 필터
st.sidebar.header("🔧 분석 옵션")

# 기간 필터
date_col = '출고일자' if '출고일자' in df3_integrated.columns else '정비일자'
if date_col in df3_integrated.columns and df3_integrated[date_col].notna().any():
    min_date = df3_integrated[date_col].min().date()
    max_date = df3_integrated[date_col].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df3_integrated = df3_integrated[
            (df3_integrated[date_col].dt.date >= start_date) & 
            (df3_integrated[date_col].dt.date <= end_date)
        ]

# 파트별 전체 현황
st.header("📊 파트별 전체 현황 (df3 수리품목 기준)")

# 파트별 통계 계산
agg_dict = {
    '관리번호': 'count',
    '수리비': ['sum', 'mean']
}

if '자재명' in df3_integrated.columns:
    agg_dict['자재명'] = lambda x: ', '.join(x.dropna().astype(str).unique()[:3])

part_stats = df3_integrated.groupby('파트').agg(agg_dict).round(2)

# 컬럼명 정리
if '자재명' in df3_integrated.columns:
    part_stats.columns = ['출고건수', '총출고금액', '평균출고금액', '주요자재']
else:
    part_stats.columns = ['출고건수', '총출고금액', '평균출고금액']
    part_stats['주요자재'] = ''

part_stats = part_stats.reset_index()

# 직급, 직책 정보 추가
for info_col in ['직급', '직책']:
    if info_col in df3_integrated.columns:
        part_info = df3_integrated.groupby('파트')[info_col].first().reset_index()
        part_stats = pd.merge(part_stats, part_info, on='파트', how='left')

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
        title="파트별 총 출고금액"
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
        title="파트별 출고건수"
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계")

# 컬럼 순서 정리
display_columns = ['파트', '출고건수', '총출고금액', '건당출고금액']

for col in ['직급', '직책']:
    if col in part_stats.columns:
        display_columns.append(col)

display_columns.extend(['주요자재', '효율성점수'])

display_stats = part_stats[[col for col in display_columns if col in part_stats.columns]]

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

# 파트 선택 및 상세 분석
st.header("🔍 파트별 상세 분석")

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
        
        st.subheader(f"🔧 {part} 파트 상세 분석")
        
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
        
        # 파트별 세부 분석
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**🔨 주요 작업 유형**")
            if '작업유형' in part_data.columns and part_data['작업유형'].notna().any():
                valid_work_types = part_data['작업유형'].dropna()
                valid_work_types = valid_work_types[valid_work_types != '미분류']
                valid_work_types = valid_work_types[valid_work_types.str.strip() != '']
                
                if not valid_work_types.empty:
                    work_types = valid_work_types.value_counts().head(5)
                    for work, count in work_types.items():
                        percentage = (count / len(part_data) * 100)
                        work_short = work[:30] + "..." if len(str(work)) > 30 else str(work)
                        st.write(f"• {work_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("작업유형 데이터 없음")
            else:
                st.write("작업유형 데이터 없음")
        
        with col2:
            st.write("**⚙️ 주요 정비 대상 (자재)**")
            if '자재명' in part_data.columns and part_data['자재명'].notna().any():
                valid_materials = part_data['자재명'].dropna()
                valid_materials = valid_materials[valid_materials.str.strip() != '']
                
                if not valid_materials.empty:
                    materials = valid_materials.value_counts().head(5)
                    for material, count in materials.items():
                        percentage = (count / len(part_data) * 100)
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

# 데이터 다운로드
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
    # 통합 데이터 다운로드
    excel_data2 = to_excel_download(df3_integrated, "df3_통합데이터.xlsx")
    st.download_button(
        label="📄 df3 통합 데이터 (Excel)",
        data=excel_data2,
        file_name="df3_통합데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col3:
    # 선택된 파트 데이터
    if selected_parts:
        selected_data = df3_integrated[df3_integrated['파트'].isin(selected_parts)]
        excel_data3 = to_excel_download(selected_data, "선택된_파트_데이터.xlsx")
        st.download_button(
            label="🎯 선택된 파트 데이터 (Excel)",
            data=excel_data3,
            file_name="선택된_파트_데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
