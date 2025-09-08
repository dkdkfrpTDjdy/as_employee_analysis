# main.py - 전체 수정 버전
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

# 초간단 데이터 로드
@st.cache_data(ttl=3600)
def load_excel_simple(file):
    """엑셀 파일 로드 - 다양한 형식 지원"""
    try:
        # 파일 확장자 확인
        file_name = file.name.lower()
        
        # 여러 엔진으로 시도
        engines_to_try = []
        
        if file_name.endswith('.xlsx'):
            engines_to_try = ['openpyxl', None]
        elif file_name.endswith('.xls'):
            engines_to_try = ['xlrd', None]
        else:
            engines_to_try = ['openpyxl', 'xlrd', None]
        
        for engine in engines_to_try:
            try:
                if engine:
                    df = pd.read_excel(file, dtype=str, engine=engine)
                else:
                    df = pd.read_excel(file, dtype=str)
                
                # 성공하면 컬럼명 정리 후 반환
                df.columns = [str(col).strip().replace('\n', '').replace('\r', '') for col in df.columns]
                return df
                
            except Exception as engine_error:
                continue
        
        # 모든 엔진 실패 시 에러
        raise Exception(f"모든 엔진으로 로드 실패. 파일을 .xlsx 형식으로 다시 저장해보세요.")
        
    except Exception as e:
        st.error(f"파일 로드 오류: {e}")
        st.info("💡 **해결 방법**: Excel에서 '다른 이름으로 저장' → 'Excel 통합 문서(.xlsx)' 선택 후 다시 업로드")
        return None

# 내장 데이터 로드
@st.cache_data
def load_static_data():
    """내장 데이터 로드"""
    df2, df4 = None, None
    
    # 자산조회 데이터
    if os.path.exists("data/자산조회데이터.xlsx"):
        try:
            df2 = pd.read_excel("data/자산조회데이터.xlsx")
            df2.columns = [str(col).strip().replace('\n', '') for col in df2.columns]
        except:
            df2 = None
    
    # 조직도 데이터
    if os.path.exists("data/조직도데이터.xlsx"):
        try:
            df4 = pd.read_excel("data/조직도데이터.xlsx", dtype=str, header=None)
            if len(df4.columns) >= 6:
                df4.columns = ['이름', '파트', '직급', '담당', '직책', '사번']
            else:
                df4.columns = ['이름', '파트'] + [f'컬럼{i}' for i in range(2, len(df4.columns))]
            df4 = df4.replace('', np.nan)
        except:
            df4 = None
    
    return df2, df4

# 초간단 머지 함수
@st.cache_data
def simple_merge_all(df1, df2=None, df3=None, df4=None, df5=None):
    """모든 데이터를 df1에 머지하고 필요한 것만 남기기"""
    
    result = df1.copy()
    
    # 1. 기본 정리
    if '관리번호' in result.columns:
        result['관리번호'] = result['관리번호'].astype(str)
    
    if '정비일자' in result.columns:
        result['정비일자'] = pd.to_datetime(result['정비일자'], errors='coerce')
        result['년월'] = result['정비일자'].dt.to_period('M')
    
    # 수리비 초기화
    result['수리비'] = 0
    
    # 2. 자산 데이터 머지 (df2)
    if df2 is not None and '관리번호' in df2.columns:
        try:
            # 브랜드/모델명만 가져오기
            asset_cols = ['관리번호']
            if '브랜드' in df2.columns:
                asset_cols.append('브랜드')
            elif '제조사명' in df2.columns:
                df2['브랜드'] = df2['제조사명']
                asset_cols.append('브랜드')
            
            if '모델명' in df2.columns:
                asset_cols.append('모델명')
            elif '제조사모델명' in df2.columns:
                df2['모델명'] = df2['제조사모델명']
                asset_cols.append('모델명')
            
            df2_simple = df2[asset_cols].drop_duplicates(subset='관리번호')
            df2_simple['관리번호'] = df2_simple['관리번호'].astype(str)
            
            result = pd.merge(result, df2_simple, on='관리번호', how='left')
            st.info(f"✅ 자산 데이터 머지 완료")
            
        except Exception as e:
            st.warning(f"자산 데이터 머지 실패: {e}")
    
    # 브랜드 정리
    if '브랜드' not in result.columns:
        result['브랜드'] = '기타'
    else:
        result['브랜드'] = result['브랜드'].fillna('기타')
    
    # 3. 소모품 데이터로 수리비 매핑 (df3)
    if df3 is not None and '관리번호' in df3.columns:
        try:
            # 출고금액 찾기
            cost_col = None
            for col in ['출고금액', '금액', '단가']:
                if col in df3.columns:
                    cost_col = col
                    break
            
            if cost_col:
                df3['관리번호'] = df3['관리번호'].astype(str)
                df3['출고금액'] = pd.to_numeric(df3[cost_col], errors='coerce').fillna(0)
                
                # 간단 매핑: 관리번호별 총 출고금액
                cost_summary = df3.groupby('관리번호')['출고금액'].sum().reset_index()
                cost_summary.columns = ['관리번호', '수리비']
                
                # 기존 수리비 컬럼 제거 후 머지
                if '수리비' in result.columns:
                    result = result.drop('수리비', axis=1)
                
                result = pd.merge(result, cost_summary, on='관리번호', how='left')
                result['수리비'] = result['수리비'].fillna(0)
                
                mapped_count = (result['수리비'] > 0).sum()
                mapping_rate = (mapped_count / len(result) * 100)
                st.info(f"✅ 수리비 매핑 완료: {mapped_count}건 ({mapping_rate:.1f}%)")
            
        except Exception as e:
            st.warning(f"수리비 매핑 실패: {e}")
            result['수리비'] = 0
    
    # 4. 조직도 데이터로 소속 매핑 (df4) - 수정된 버전
    if df4 is not None:
        try:
            # 정비자 이름으로 매핑
            if '정비자' in result.columns and '이름' in df4.columns and '파트' in df4.columns:
                # 문자열로 변환 및 정리
                result['정비자_원본'] = result['정비자'].copy()  # 원본 보존
                result['정비자'] = result['정비자'].astype(str).str.strip()
                df4['이름'] = df4['이름'].astype(str).str.strip()
                
                # 조직도에서 필요한 컬럼만 선택 (NaN 제거)
                org_simple = df4[['이름', '파트']].dropna()
                
                # 매핑 전 상태 확인
                unique_workers = result['정비자'].nunique()
                org_count = len(org_simple)
                st.info(f"매핑 시도: 정비자 {unique_workers}명, 조직도 {org_count}명")
                
                # 이름으로 매핑
                result = pd.merge(result, org_simple, left_on='정비자', right_on='이름', how='left')
                
                # 컬럼명 변경 및 중복 컬럼 제거
                result = result.rename(columns={'파트': '정비자소속'})
                
                # 중복된 이름 컬럼 제거
                if '이름' in result.columns:
                    result = result.drop('이름', axis=1)
                
                mapped_count = result['정비자소속'].notna().sum()
                mapping_rate = (mapped_count / len(result) * 100) if len(result) > 0 else 0
                st.info(f"✅ 조직도 매핑 완료: {mapped_count}건 ({mapping_rate:.1f}%)")
                
                # 매핑 실패한 경우 정비자명을 파트로 사용 (임시 해결책)
                if mapped_count == 0:
                    result['정비자소속'] = result['정비자']
                    st.warning("⚠️ 조직도 매핑 실패로 정비자명을 파트명으로 사용합니다.")
                else:
                    # 매핑 실패한 정비자들 확인
                    unmapped_workers = result[result['정비자소속'].isna()]['정비자'].value_counts()
                    if len(unmapped_workers) > 0:
                        st.warning(f"⚠️ 매핑되지 않은 정비자: {len(unmapped_workers)}명")
                        
                        # 매핑되지 않은 정비자도 본인 이름을 파트로 사용
                        unmapped_mask = result['정비자소속'].isna()
                        result.loc[unmapped_mask, '정비자소속'] = result.loc[unmapped_mask, '정비자']
            
            else:
                st.warning("정비자 또는 조직도 컬럼이 없습니다.")
                # 정비자를 파트로 사용
                if '정비자' in result.columns:
                    result['정비자소속'] = result['정비자']
                    st.info("정비자명을 파트명으로 사용합니다.")
                
        except Exception as e:
            st.error(f"조직도 매핑 실패: {e}")
            # 실패 시에도 정비자를 파트로 사용
            if '정비자' in result.columns:
                result['정비자소속'] = result['정비자']
                st.info("매핑 실패로 정비자명을 파트명으로 사용합니다.")
    
    # 정비자소속이 여전히 없으면 기본값 설정
    if '정비자소속' not in result.columns:
        if '정비자' in result.columns:
            result['정비자소속'] = result['정비자']
        else:
            result['정비자소속'] = '미분류'
        st.info("정비자소속 컬럼을 생성했습니다.")
    
    # 5. 만족도 데이터 간단 매핑 (df5)
    if df5 is not None and '관리번호' in df5.columns:
        try:
            df5['관리번호'] = df5['관리번호'].astype(str)
            
            # 답변을 만족도 점수로 변환
            if '답변' in df5.columns:
                df5['만족도점수'] = pd.to_numeric(df5['답변'], errors='coerce')
                
                # 관리번호별 평균 만족도
                satisfaction_summary = df5.groupby('관리번호')['만족도점수'].agg([
                    'mean', 'count'
                ]).reset_index()
                satisfaction_summary.columns = ['관리번호', '만족도_평균', '만족도_응답수']
                
                result = pd.merge(result, satisfaction_summary, on='관리번호', how='left')
                
                mapped_count = result['만족도_평균'].notna().sum()
                st.info(f"✅ 만족도 매핑 완료: {mapped_count}건")
            
        except Exception as e:
            st.warning(f"만족도 매핑 실패: {e}")
    
    # 6. 지역 정보 추출 (간단히)
    if '현장' in result.columns:
        def extract_region_simple(address):
            if not isinstance(address, str):
                return None
            regions = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
                      '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주']
            for region in regions:
                if region in address:
                    return region
            return None
        
        result['지역'] = result['현장'].apply(extract_region_simple)
        result['현장명'] = result['현장']
    
    # 7. 필요한 컬럼만 유지 (메모리 절약)
    keep_columns = [
        '관리번호', '정비일자', '년월', '정비자', '정비자소속',
        '브랜드', '모델명', '수리비', '작업유형', '정비대상', '정비작업',
        '현장명', '지역', '수리시간', '가동시간'
    ]
    
    # 만족도 컬럼 추가
    if '만족도_평균' in result.columns:
        keep_columns.extend(['만족도_평균', '만족도_응답수'])
    
    # 실제 존재하는 컬럼만 유지
    final_columns = [col for col in keep_columns if col in result.columns]
    result = result[final_columns]
    
    return result

# 사이드바
st.sidebar.title("📁 데이터 업로드")

uploaded_file1 = st.sidebar.file_uploader("**정비일지 데이터**", type=["xlsx", "xls"])
uploaded_file3 = st.sidebar.file_uploader("**소모품 출고 데이터**", type=["xlsx", "xls"])
uploaded_file5 = st.sidebar.file_uploader("**만족도 조사 데이터**", type=["xlsx", "xls"])

# 내장 데이터
df2, df4 = load_static_data()

if df2 is not None:
    st.sidebar.success("✅ 자산조회 데이터 준비됨")
if df4 is not None:
    st.sidebar.success("✅ 조직도 데이터 준비됨")

# 메인
st.title("🏭 산업장비 AS 분석 대시보드")
st.markdown("---")

# 데이터 처리 (한 번에!)
if uploaded_file1 is not None:
    with st.spinner("데이터 처리 중... (잠시만 기다려주세요)"):
        try:
            # 모든 파일 로드
            df1 = load_excel_simple(uploaded_file1)
            df3 = load_excel_simple(uploaded_file3) if uploaded_file3 else None
            df5 = load_excel_simple(uploaded_file5) if uploaded_file5 else None
            
            if df1 is not None:
                # 한 번에 모든 머지 수행
                final_data = simple_merge_all(df1, df2, df3, df4, df5)
                
                # 세션에 저장
                st.session_state.df1_with_costs = final_data
                st.session_state.data_loaded = True
                
                st.success("✅ 모든 데이터 처리 완료!")
                
                # 간단한 통계
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("총 레코드", f"{len(final_data):,}건")
                
                with col2:
                    total_cost = final_data['수리비'].sum()
                    st.metric("총 수리비", f"{total_cost:,.0f}원")
                
                with col3:
                    cost_records = (final_data['수리비'] > 0).sum()
                    cost_rate = (cost_records / len(final_data) * 100)
                    st.metric("수리비 매핑률", f"{cost_rate:.1f}%")
                
                with col4:
                    if '만족도_평균' in final_data.columns:
                        satisfaction_records = final_data['만족도_평균'].notna().sum()
                        satisfaction_rate = (satisfaction_records / len(final_data) * 100)
                        st.metric("만족도 조사율", f"{satisfaction_rate:.1f}%")
                    else:
                        st.metric("만족도 조사율", "0%")
                
                # 미리보기
                st.subheader("📋 데이터 미리보기")
                st.dataframe(final_data.head(10), use_container_width=True)
                
                # 매핑 상태 확인
                if st.checkbox("🔍 매핑 상태 상세 확인"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**정비자 정보:**")
                        if '정비자' in final_data.columns:
                            workers = final_data['정비자'].value_counts().head(5)
                            for worker, count in workers.items():
                                st.write(f"• {worker}: {count}건")
                        
                        if '정비자소속' in final_data.columns:
                            parts = final_data['정비자소속'].value_counts().head(5)
                            st.write("**파트 정보:**")
                            for part, count in parts.items():
                                st.write(f"• {part}: {count}건")
                    
                    with col2:
                        if df4 is not None:
                            st.write("**조직도 정보:**")
                            st.write(f"• 조직도 레코드: {len(df4)}건")
                            if '이름' in df4.columns:
                                org_names = df4['이름'].dropna().head(5).tolist()
                                st.write("• 조직도 이름:")
                                for name in org_names:
                                    st.write(f"  - {name}")
                
        except Exception as e:
            st.error(f"데이터 처리 실패: {e}")
            st.exception(e)

else:
    st.info("👈 정비일지 데이터를 업로드해주세요.")
    
    st.markdown("""
    ## 🎯 분석 메뉴
    
    - **📊 경영 대시보드**: 월별 트렌드 및 핵심 지표
    - **👥 파트별 분석**: 파트/개인별 성과 평가  
    - **🏢 업체별 분석**: 디마케팅 위험도 분석
    - **📅 월별 분석**: 종합 리포트 및 다운로드
    """)
