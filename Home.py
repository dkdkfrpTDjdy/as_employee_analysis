import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
from io import BytesIO
warnings.filterwarnings('ignore')

# 데이터 프로세싱 모듈 임포트
try:
    from data_processing import (
        load_data,
        load_static_data,
        create_df3_with_organization,
        merge_df3_with_df1_client_info,
        process_df1_basic,
        merge_satisfaction_by_employee_id,
        validate_data_quality,
        preprocess_maintenance_data,
        preprocess_repair_costs,
        preprocess_satisfaction_data,
        extract_and_apply_region
    )
    DATA_PROCESSING_AVAILABLE = True
except ImportError:
    st.error("데이터 프로세싱 모듈을 찾을 수 없습니다!")
    DATA_PROCESSING_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="산업장비 AS 분석 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

# 사이드바
st.sidebar.title("📁 데이터 업로드")

uploaded_file1 = st.sidebar.file_uploader("정비일지 데이터 (필수)", type=["xlsx", "xls"])
uploaded_file3 = st.sidebar.file_uploader("소모품 출고 데이터 (수리비)", type=["xlsx", "xls"])
uploaded_file5 = st.sidebar.file_uploader("만족도 조사 데이터", type=["xlsx", "xls"])

# 메인
st.title("🏭 산업장비 AS 분석 대시보드")
st.markdown("---")

if not DATA_PROCESSING_AVAILABLE:
    st.error("데이터 프로세싱 모듈이 필요합니다!")
    st.stop()

# 데이터 처리
if uploaded_file1 is not None:
    with st.spinner("데이터 처리 중..."):
        try:
            # 내장 데이터 로드
            df2, df4 = load_static_data()
            
            # 업로드된 데이터 로드
            df1 = load_data(uploaded_file1)
            df3 = load_data(uploaded_file3) if uploaded_file3 else None
            df5 = load_data(uploaded_file5) if uploaded_file5 else None
            
            if df1 is not None:
                # 1. df3 조직도 매핑
                df3_with_org = None
                if df3 is not None:
                    df3_with_org = create_df3_with_organization(df3, df4)
                    if df3_with_org is not None:
                        st.session_state.df3_with_org = df3_with_org
                
                # 2. df3에 df1 업체명 정보 매핑
                if df3_with_org is not None:
                    df3_final = merge_df3_with_df1_client_info(df3_with_org, df1)
                    if df3_final is not None:
                        st.session_state.df3_final = df3_final
                
                # 3. df1 기본 처리
                df1_processed = process_df1_basic(df1, df2, df4)
                if df1_processed is not None:
                    st.session_state.df1_with_costs = df1_processed
                
                # 4. 만족도 데이터 처리
                if df5 is not None and df4 is not None:
                    if '답변' in df5.columns:
                        df5['만족도점수'] = pd.to_numeric(df5['답변'], errors='coerce')
                    
                    df5_with_part = merge_satisfaction_by_employee_id(df5, df4)
                    st.session_state.satisfaction_data = df5_with_part
                
                # 5. 고급 전처리
                try:
                    # df1 전처리
                    if 'df1_with_costs' in st.session_state:
                        df1_processed = preprocess_maintenance_data(st.session_state.df1_with_costs)
                        df1_processed = extract_and_apply_region(df1_processed)
                        st.session_state.df1_with_costs = df1_processed
                    
                    # df3 전처리
                    if 'df3_final' in st.session_state:
                        df3_final = preprocess_repair_costs(st.session_state.df3_final)
                        st.session_state.df3_final = df3_final
                    
                    # 만족도 전처리
                    if 'satisfaction_data' in st.session_state:
                        satisfaction_processed = preprocess_satisfaction_data(st.session_state.satisfaction_data)
                        st.session_state.satisfaction_data = satisfaction_processed
                    
                    st.info("✅ 고급 전처리 완료")
                    
                except Exception as e:
                    st.warning(f"고급 전처리 중 일부 오류 발생: {e}")
                
                st.session_state.data_loaded = True
                st.success("✅ 데이터 처리 완료")
                
                # 데이터 현황
                st.subheader("📊 처리된 데이터 현황")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**df1 처리 결과:**")
                    if 'df1_with_costs' in st.session_state:
                        df1_processed = st.session_state.df1_with_costs
                        st.write(f"- 총 건수: {len(df1_processed):,}건")
                        if '수리비' in df1_processed.columns:
                            st.write(f"- 총 수리비: {df1_processed['수리비'].sum():,.0f}원")
                        st.write(f"- 파트 수: {df1_processed['정비자소속'].nunique()}개")
                
                with col2:
                    st.write("**df3 처리 결과:**")
                    if 'df3_final' in st.session_state:
                        df3_final = st.session_state['df3_final']
                        st.write(f"- 총 건수: {len(df3_final):,}건")
                        if '수리비' in df3_final.columns:
                            st.write(f"- 총 출고금액: {df3_final['수리비'].sum():,.0f}원")
                        if '파트' in df3_final.columns:
                            st.write(f"- 파트 수: {df3_final['파트'].nunique()}개")
                
                # 미리보기
                if 'df3_final' in st.session_state:
                    st.subheader("📊 df3 최종 데이터 미리보기")
                    st.dataframe(st.session_state['df3_final'].head(10), use_container_width=True)
                
        except Exception as e:
            st.error(f"데이터 처리 실패: {e}")
            st.exception(e)
else:
    st.info("👈 정비일지 데이터를 업로드해주세요.")

st.sidebar.success("✅ 데이터 프로세싱 모듈 활성화")

st.markdown("""
## 🎯 분석 메뉴

- **📊 경영 대시보드**: 월별 트렌드 및 핵심 지표 (df3 중심)
- **👥 파트별 분석**: 파트별 성과 평가 (df3 중심 + 조직도 매핑)
- **🏢 업체별 분석**: 디마케팅 위험도 분석 (df3 중심)
- **📅 월별 분석**: 종합 리포트 및 다운로드 (df3 중심)

### 📋 데이터 매핑 방식 (df3 중심)
- **df3 조직도 매핑**: 출고자(사번) → 파트, 직급, 직책
- **df3 업체명 매핑**: df1의 년월+관리번호 → 업체명, 작업유형
- **df1 조직도 매핑**: 정비자 → 파트, 직급, 직책 (기존 분석용)
- **자산정보 매핑**: 관리번호 → 브랜드, 모델명
- **만족도 매핑**: 사번 기준으로 조직도와 연동
""")

st.markdown("---")
