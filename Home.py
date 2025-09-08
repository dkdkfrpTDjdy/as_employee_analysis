# main.py - 개선된 메인 페이지
import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
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

# 간단한 데이터 로드 함수 (캐싱 강화)
@st.cache_data(ttl=3600, show_spinner=False)
def load_simple_data(file):
    """빠른 데이터 로드 - 기본 기능만"""
    try:
        df = pd.read_excel(file, dtype=str)
        df.columns = [str(col).strip().replace('\n', '') for col in df.columns]
        return df
    except Exception as e:
        st.error(f"파일 로드 오류: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def load_static_files():
    """내장 파일 로드"""
    try:
        # 자산조회 데이터
        asset_path = "data/자산조회데이터.xlsx"
        df2 = pd.read_excel(asset_path) if os.path.exists(asset_path) else None
        
        # 조직도 데이터  
        org_path = "data/조직도데이터.xlsx"
        df4 = pd.read_excel(org_path, dtype=str, header=None) if os.path.exists(org_path) else None
        
        if df4 is not None:
            expected_columns = ['이름', '파트', '직급', '담당', '직책', '사번']
            df4.columns = expected_columns[:len(df4.columns)]
            df4 = df4.replace('', np.nan)
        
        return df2, df4
    except Exception as e:
        st.sidebar.error(f"내장 데이터 로드 오류: {e}")
        return None, None

# 빠른 데이터 병합 (필수 기능만)
@st.cache_data(show_spinner=False)
def quick_merge(df1, df2=None):
    """빠른 병합 - 핵심 기능만"""
    if df1 is None:
        return None
    
    result = df1.copy()
    
    # 관리번호 문자열 변환
    if '관리번호' in result.columns:
        result['관리번호'] = result['관리번호'].astype(str)
    
    # 수리비 처리
    if '수리비' not in result.columns:
        result['수리비'] = 0
    result['수리비'] = pd.to_numeric(result['수리비'], errors='coerce').fillna(0)
    
    # 날짜 처리
    if '정비일자' in result.columns:
        result['정비일자'] = pd.to_datetime(result['정비일자'], errors='coerce')
        result['년월'] = result['정비일자'].dt.to_period('M')
    
    # 자산 데이터 병합 (간단하게)
    if df2 is not None and '관리번호' in df2.columns:
        df2_simple = df2[['관리번호', '브랜드', '모델명']].drop_duplicates(subset='관리번호')
        df2_simple['관리번호'] = df2_simple['관리번호'].astype(str)
        result = pd.merge(result, df2_simple, on='관리번호', how='left')
    
    # 브랜드 정리
    if '브랜드' in result.columns:
        result['브랜드'] = result['브랜드'].fillna('기타')
    
    return result

# 사이드바 - 간소화된 업로드
st.sidebar.title("📁 데이터 업로드")

# 파일 업로더들
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

# 데이터 처리 (간소화)
processed_data = None

if uploaded_file1 is not None:
    with st.spinner("데이터 처리 중..."):
        # 정비일지 로드
        df1 = load_simple_data(uploaded_file1)
        
        if df1 is not None:
            # 빠른 병합
            processed_data = quick_merge(df1, df2)
            
            # 세션에 저장
            st.session_state.df1_with_costs = processed_data
            st.session_state.data_loaded = True
            
            st.success("✅ 정비일지 데이터 로드 완료")

# 소모품 데이터 처리 (선택적)
if uploaded_file3 is not None:
    df3 = load_simple_data(uploaded_file3)
    if df3 is not None:
        st.session_state.df3 = df3
        st.success("✅ 소모품 출고 데이터 로드 완료")

# 만족도 데이터 처리 (선택적)  
if uploaded_file5 is not None:
    df5 = load_simple_data(uploaded_file5)
    if df5 is not None:
        st.session_state.df5 = df5
        st.success("✅ 만족도 조사 데이터 로드 완료")

# 데이터 현황 표시
if st.session_state.data_loaded and processed_data is not None:
    st.header("📊 데이터 현황")
    
    # 기본 통계 (빠른 계산)
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
    
    # 컬럼 선택 (주요 컬럼만)
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
        # 월별 건수 (간단히)
        if '년월' in processed_data.columns:
            monthly_counts = processed_data['년월'].value_counts().sort_index().tail(6)
            st.write("**📅 최근 6개월 건수**")
            for month, count in monthly_counts.items():
                st.write(f"• {month}: {count}건")

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
