# main.py - 수정된 메인 페이지
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
        df.columns = [str(col).strip().replace('\n', '').replace('\r', '') for col in df.columns]
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

# 빠른 데이터 병합 (필수 기능만) - 수정된 버전
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
    
    # 자산 데이터 병합 (안전하게)
    if df2 is not None and '관리번호' in df2.columns:
        try:
            # 사용 가능한 컬럼만 선택
            available_cols = ['관리번호']
            optional_cols = ['브랜드', '모델명', '제조년도', '취득가']
            
            for col in optional_cols:
                if col in df2.columns:
                    available_cols.append(col)
            
            # 컬럼 매핑 처리
            column_mappings = {
                '제조사명': '브랜드',
                '제조사모델명': '모델명'
            }
            
            # 매핑된 컬럼명으로 변경
            df2_temp = df2.copy()
            for old_col, new_col in column_mappings.items():
                if old_col in df2_temp.columns and new_col not in df2_temp.columns:
                    df2_temp[new_col] = df2_temp[old_col]
                    if new_col not in available_cols:
                        available_cols.append(new_col)
            
            # 실제 존재하는 컬럼만 선택
            final_cols = [col for col in available_cols if col in df2_temp.columns]
            
            if len(final_cols) > 1:  # 관리번호 외에 다른 컬럼이 있는 경우만
                df2_simple = df2_temp[final_cols].drop_duplicates(subset='관리번호')
                df2_simple['관리번호'] = df2_simple['관리번호'].astype(str)
                result = pd.merge(result, df2_simple, on='관리번호', how='left')
        except Exception as e:
            st.sidebar.warning(f"자산 데이터 병합 중 오류: {e}")
    
    # 브랜드 정리
    if '브랜드' in result.columns:
        result['브랜드'] = result['브랜드'].fillna('기타')
    else:
        result['브랜드'] = '기타'
    
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
    # 자산 데이터 컬럼 확인 (디버깅용)
    st.sidebar.write(f"자산 데이터 컬럼: {list(df2.columns)[:5]}...")
    
if df4 is not None:
    st.sidebar.success("✅ 조직도 데이터 준비됨")

# 메인 제목
st.title("🏭 산업장비 AS 분석 대시보드")
st.markdown("---")

# 데이터 처리 (간소화)
processed_data = None

if uploaded_file1 is not None:
    with st.spinner("데이터 처리 중..."):
        try:
            # 정비일지 로드
            df1 = load_simple_data(uploaded_file1)
            
            if df1 is not None:
                st.success("✅ 정비일지 데이터 로드 완료")
                st.write(f"정비일지 컬럼: {list(df1.columns)[:10]}...")
                
                # 빠른 병합
                processed_data = quick_merge(df1, df2)
                
                if processed_data is not None:
                    # 세션에 저장
                    st.session_state.df1_with_costs = processed_data
                    st.session_state.data_loaded = True
                    st.success("✅ 데이터 병합 완료")
                else:
                    st.error("데이터 병합 실패")
            else:
                st.error("정비일지 데이터 로드 실패")
                
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {e}")
            st.write("오류 상세:")
            st.exception(e)

# 소모품 데이터 처리 (선택적)
if uploaded_file3 is not None:
    try:
        df3 = load_simple_data(uploaded_file3)
        if df3 is not None:
            st.session_state.df3 = df3
            st.success("✅ 소모품 출고 데이터 로드 완료")
    except Exception as e:
        st.warning(f"소모품 데이터 처리 중 오류: {e}")

# 만족도 데이터 처리 (선택적)  
if uploaded_file5 is not None:
    try:
        df5 = load_simple_data(uploaded_file5)
        if df5 is not None:
            st.session_state.df5 = df5
            st.success("✅ 만족도 조사 데이터 로드 완료")
    except Exception as e:
        st.warning(f"만족도 데이터 처리 중 오류: {e}")

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
        st.write("**브랜드 매핑 정보**")
        if '브랜드' in processed_data.columns:
            brand_mapped = (processed_data['브랜드'] != '기타').sum()
            mapping_rate = (brand_mapped / len(processed_data) * 100)
            st.write(f"• 매핑 건수: {brand_mapped:,}건")
            st.write(f"• 매핑률: {mapping_rate:.1f}%")
    
    with col3:
        st.write("**수리비 정보**")
        if '수리비' in processed_data.columns:
            cost_records = (processed_data['수리비'] > 0).sum()
            cost_rate = (cost_records / len(processed_data) * 100)
            st.write(f"• 수리비 있는 건수: {cost_records:,}건")
            st.write(f"• 수리비 비율: {cost_rate:.1f}%")
            
            if cost_records > 0:
                avg_cost = processed_data[processed_data['수리비'] > 0]['수리비'].mean()
                st.write(f"• 평균 수리비: {avg_cost:,.0f}원")

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
    st.info("🔄 **업데이트**: 데이터는 자동으로 캐시되어 빠르게 로드됩니다.")

with col3:
    st.info("📱 **모바일**: 반응형 디자인으로 모든 기기에서 사용 가능합니다.")

# 디버깅 정보 (개발용)
if st.sidebar.checkbox("디버깅 정보 표시"):
    st.sidebar.write("**세션 상태:**")
    st.sidebar.write(f"data_loaded: {st.session_state.data_loaded}")
    
    if df2 is not None:
        st.sidebar.write("**자산 데이터 컬럼:**")
        st.sidebar.write(list(df2.columns))
    
    if 'df1_with_costs' in st.session_state:
        st.sidebar.write("**처리된 데이터 컬럼:**")
        st.sidebar.write(list(st.session_state.df1_with_costs.columns))
