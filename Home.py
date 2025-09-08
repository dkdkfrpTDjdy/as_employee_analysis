import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
from utils.data_processing import (
    load_data, 
    merge_dataframes, 
    extract_and_apply_region,
    calculate_previous_maintenance_dates, 
    map_employee_data, 
    merge_repair_costs,
    process_date_columns, 
    preprocess_repair_costs, 
    preprocess_maintenance_data,
    preprocess_satisfaction_data,
    merge_satisfaction_with_maintenance
)

warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="산업장비 AS 분석 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# 내장 파일 로드 (간소화)
@st.cache_data(ttl=3600, show_spinner=False)
def load_static_files():
    """내장 파일 로드"""
    try:
        # 자산조회 데이터
        asset_path = "data/자산조회데이터.xlsx"
        df2 = None
        if os.path.exists(asset_path):
            df2 = pd.read_excel(asset_path)
            if df2 is not None:
                df2.columns = [str(col).strip().replace('\n', '').replace('\r', '') for col in df2.columns]
        
        # 조직도 데이터  
        org_path = "data/조직도데이터.xlsx"
        df4 = None
        if os.path.exists(org_path):
            df4 = pd.read_excel(org_path, dtype=str, header=None)
            if df4 is not None:
                expected_columns = ['이름', '파트', '직급', '담당', '직책', '사번']
                df4.columns = expected_columns[:len(df4.columns)]
                df4 = df4.replace('', np.nan)
        
        return df2, df4
    except Exception as e:
        st.sidebar.error(f"내장 데이터 로드 오류: {e}")
        return None, None

# 사이드바 - 업로드
st.sidebar.title("📁 데이터 업로드")

uploaded_file1 = st.sidebar.file_uploader("**정비일지 데이터**", type=["xlsx"], key="maintenance")
uploaded_file3 = st.sidebar.file_uploader("**소모품 출고 데이터**", type=["xlsx"], key="parts")
uploaded_file5 = st.sidebar.file_uploader("**만족도 조사 데이터**", type=["xlsx"], key="satisfaction")

# 내장 데이터 로드
df2, df4 = load_static_files()

if df2 is not None:
    st.sidebar.success("✅ 자산조회 데이터 준비됨")
if df4 is not None:
    st.sidebar.success("✅ 조직도 데이터 준비됨")

# 메인 제목
st.title("🏭 산업장비 AS 분석 대시보드")
st.markdown("---")

# 데이터 처리
processed_data = None

if uploaded_file1 is not None:
    with st.spinner("데이터 처리 중..."):
        try:
            # 1. 정비일지 로드
            df1 = load_data(uploaded_file1)
            
            if df1 is not None:
                st.success("✅ 정비일지 데이터 로드 완료")
                
                # 2. 기본 전처리
                df1 = preprocess_maintenance_data(df1)
                
                # 3. 자산 데이터 병합
                if df2 is not None:
                    df1 = merge_dataframes(df1, df2)
                
                # 4. 소모품 데이터와 수리비 매핑
                if uploaded_file3 is not None:
                    df3 = load_data(uploaded_file3)
                    if df3 is not None:
                        st.info("🔄 수리비 매핑 중...")
                        df3 = preprocess_repair_costs(df3)
                        df1 = merge_repair_costs(df1, df3)
                        
                        # 매핑 결과 확인
                        mapped_count = (df1['수리비'] > 0).sum() if '수리비' in df1.columns else 0
                        mapping_rate = (mapped_count / len(df1) * 100) if len(df1) > 0 else 0
                        st.success(f"✅ 수리비 매핑 완료: {mapped_count}건 ({mapping_rate:.1f}%)")
                
                # 5. 만족도 데이터 병합
                if uploaded_file5 is not None:
                    df5 = load_data(uploaded_file5)
                    if df5 is not None:
                        st.info("😊 만족도 데이터 매핑 중...")
                        df5 = preprocess_satisfaction_data(df5)
                        df1 = merge_satisfaction_with_maintenance(df1, df5)
                        
                        # 만족도 매핑 결과
                        satisfaction_matched = df1['만족도_평균'].notna().sum() if '만족도_평균' in df1.columns else 0
                        satisfaction_rate = (satisfaction_matched / len(df1) * 100) if len(df1) > 0 else 0
                        st.success(f"✅ 만족도 매핑 완료: {satisfaction_matched}건 ({satisfaction_rate:.1f}%)")
                
                # 6. 추가 처리
                df1 = calculate_previous_maintenance_dates(df1)
                df1 = extract_and_apply_region(df1)
                df1 = process_date_columns(df1)
                
                # 7. 조직도 매핑
                if df4 is not None:
                    df1 = map_employee_data(df1, df4)
                
                # 8. 세션에 저장
                processed_data = df1
                st.session_state.df1_with_costs = processed_data
                st.session_state.data_loaded = True
                
                st.success("✅ 모든 데이터 처리 완료")
                
            else:
                st.error("정비일지 데이터 로드 실패")
                
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {e}")
            st.exception(e)

# 추가 데이터 저장 (개별 접근용)
if uploaded_file3 is not None and 'df3' not in st.session_state:
    try:
        df3 = load_data(uploaded_file3)
        if df3 is not None:
            st.session_state.df3 = df3
    except:
        pass

if uploaded_file5 is not None and 'df5' not in st.session_state:
    try:
        df5 = load_data(uploaded_file5)
        if df5 is not None:
            st.session_state.df5 = df5
    except:
        pass

# 데이터 현황 표시
if st.session_state.data_loaded and processed_data is not None:
    st.header("📊 데이터 현황")
    
    # 기본 통계
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_records = len(processed_data)
        st.metric("총 레코드", f"{total_records:,}건")
    
    with col2:
        if '정비일자' in processed_data.columns:
            date_range = processed_data['정비일자'].dt.date
            valid_dates = date_range.dropna()
            if not valid_dates.empty:
                period = f"{valid_dates.min()} ~ {valid_dates.max()}"
                st.metric("데이터 기간", period)
            else:
                st.metric("데이터 기간", "N/A")
        else:
            st.metric("데이터 기간", "N/A")
    
    with col3:
        if '수리비' in processed_data.columns:
            total_cost = processed_data['수리비'].sum()
            st.metric("총 수리비", f"{total_cost:,.0f}원")
        else:
            st.metric("총 수리비", "0원")
    
    with col4:
        unique_equipment = processed_data['관리번호'].nunique() if '관리번호' in processed_data.columns else 0
        st.metric("장비 수", f"{unique_equipment:,}대")
    
    # 간단한 미리보기
    st.subheader("🔍 데이터 미리보기")
    
    # 주요 컬럼만 표시
    display_columns = []
    for col in ['관리번호', '정비일자', '정비자', '브랜드', '모델명', '수리비', '작업유형']:
        if col in processed_data.columns:
            display_columns.append(col)
    
    if display_columns:
        preview_data = processed_data[display_columns].head(10)
        st.dataframe(preview_data, use_container_width=True)
    else:
        st.dataframe(processed_data.head(10), use_container_width=True)
    
    # 빠른 인사이트
    st.subheader("⚡ 빠른 인사이트")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 상위 브랜드
        if '브랜드' in processed_data.columns:
            top_brands = processed_data['브랜드'].value_counts().head(5)
            st.write("**🏭 주요 브랜드 TOP 5**")
            for brand, count in top_brands.items():
                percentage = (count / len(processed_data) * 100)
                st.write(f"• {brand}: {count}건 ({percentage:.1f}%)")
    
    with col2:
        # 월별 건수
        if '년월' in processed_data.columns:
            monthly_counts = processed_data['년월'].value_counts().sort_index().tail(6)
            st.write("**📅 최근 6개월 건수**")
            for month, count in monthly_counts.items():
                st.write(f"• {month}: {count}건")
    
    # 데이터 품질 정보
    st.subheader("📈 데이터 품질 정보")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**필수 컬럼 완성도**")
        essential_cols = ['관리번호', '정비일자', '정비자']
        for col in essential_cols:
            if col in processed_data.columns:
                completeness = (processed_data[col].notna().sum() / len(processed_data) * 100)
                st.write(f"• {col}: {completeness:.1f}%")
    
    with col2:
        st.write("**수리비 매핑 정보**")
        if '수리비' in processed_data.columns:
            cost_records = (processed_data['수리비'] > 0).sum()
            cost_rate = (cost_records / len(processed_data) * 100)
            st.write(f"• 수리비 있는 건수: {cost_records:,}건")
            st.write(f"• 수리비 비율: {cost_rate:.1f}%")
            
            if cost_records > 0:
                avg_cost = processed_data[processed_data['수리비'] > 0]['수리비'].mean()
                st.write(f"• 평균 수리비: {avg_cost:,.0f}원")
    
    with col3:
        st.write("**만족도 정보**")
        if '만족도_평균' in processed_data.columns:
            satisfaction_records = processed_data['만족도_평균'].notna().sum()
            satisfaction_rate = (satisfaction_records / len(processed_data) * 100)
            st.write(f"• 만족도 조사 건수: {satisfaction_records:,}건")
            st.write(f"• 만족도 조사율: {satisfaction_rate:.1f}%")
            
            if satisfaction_records > 0:
                avg_satisfaction = processed_data['만족도_평균'].mean()
                st.write(f"• 평균 만족도: {avg_satisfaction:.2f}점")
        else:
            st.write("• 만족도 데이터 없음")

else:
    # 데이터가 없을 때 안내
    st.info("👈 좌측 사이드바에서 정비일지 데이터를 업로드해주세요.")
    
    # 대시보드 소개
    st.markdown("""
    ## 🎯 주요 분석 메뉴
    
    ### 📊 **경영 대시보드**
    - 월별 AS 건수 및 수리비 트렌드
    - 전월 대비 증감률 분석  
    - 핵심 지표 모니터링
    
    ### 👥 **파트별 심층 분석**
    - 파트/개인별 성과 평가
    - 건수 대비 수리비 효율성
    - 상세 드릴다운 분석
    
    ### 🏢 **업체별 디마케팅 분석**  
    - 위험도 점수 자동 계산
    - 수리비 및 빈도 기반 등급 분류
    - 계약 조건 재검토 대상 식별
    
    ### 📅 **월별 종합 분석**
    - 고장유형별 상세 분석
    - 시간/지역/장비별 분석
    - Excel 리포트 다운로드
    """)

# 하단 정보
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.info("💡 **Tip**: 정비일지 데이터만으로도 기본 분석이 가능합니다.")

with col2:
    st.info("🔄 **업데이트**: 소모품 출고 데이터를 함께 업로드하면 수리비가 자동 매핑됩니다.")

with col3:
    st.info("😊 **만족도**: 만족도 조사 데이터도 함께 분석 가능합니다.")

# 고급 설정 (사이드바)
st.sidebar.markdown("---")
st.sidebar.header("🔧 고급 설정")

if st.sidebar.checkbox("매핑 상태 상세 보기") and st.session_state.data_loaded:
    st.sidebar.subheader("🔍 매핑 상태 분석")
    
    if 'df1_with_costs' in st.session_state:
        data = st.session_state.df1_with_costs
        
        # 수리비 매핑 상태
        if '수리비' in data.columns:
            cost_mapped = (data['수리비'] > 0).sum()
            cost_rate = (cost_mapped / len(data) * 100)
            st.sidebar.write(f"**수리비 매핑**: {cost_mapped}/{len(data)}건 ({cost_rate:.1f}%)")
        
        # 만족도 매핑 상태
        if '만족도_평균' in data.columns:
            satisfaction_mapped = data['만족도_평균'].notna().sum()
            satisfaction_rate = (satisfaction_mapped / len(data) * 100)
            st.sidebar.write(f"**만족도 매핑**: {satisfaction_mapped}/{len(data)}건 ({satisfaction_rate:.1f}%)")
        
        # 조직도 매핑 상태
        if '정비자소속' in data.columns:
            org_mapped = data['정비자소속'].notna().sum()
            org_rate = (org_mapped / len(data) * 100)
            st.sidebar.write(f"**조직도 매핑**: {org_mapped}/{len(data)}건 ({org_rate:.1f}%)")

# 디버깅 정보
if st.sidebar.checkbox("디버깅 정보"):
    st.sidebar.write("**세션 상태:**")
    st.sidebar.write(f"data_loaded: {st.session_state.data_loaded}")
    
    if df2 is not None:
        st.sidebar.write("**자산 데이터 컬럼:**")
        st.sidebar.write(list(df2.columns)[:5])
    
    if 'df1_with_costs' in st.session_state:
        st.sidebar.write("**처리된 데이터 컬럼:**")
        st.sidebar.write(list(st.session_state.df1_with_costs.columns)[:10])
