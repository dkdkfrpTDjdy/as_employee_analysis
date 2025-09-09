# main.py - df3 중심 매핑 강화 버전
import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
import re
from difflib import get_close_matches
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
        # 여러 엔진으로 시도
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
        
        raise Exception(f"모든 엔진으로 로드 실패")
        
    except Exception as e:
        st.error(f"파일 로드 오류: {e}")
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
            df4 = pd.read_excel("data/조직도데이터.xlsx", dtype=str)
            
            # 첫 번째 행이 실제 헤더인지 확인
            first_row = df4.iloc[0] if len(df4) > 0 else pd.Series()
            
            # 첫 번째 행에 헤더 키워드가 있으면 헤더로 사용
            if any(keyword in str(first_row.iloc[i]).lower() 
                   for i in range(min(len(first_row), 3)) 
                   for keyword in ['이름', '파트', '사번', '소속']):
                
                # 첫 번째 행을 헤더로 설정하고 나머지를 데이터로 사용
                new_columns = df4.iloc[0].tolist()
                df4 = df4.iloc[1:].reset_index(drop=True)
                df4.columns = new_columns

            # 컬럼명 정리
            df4.columns = [str(col).strip().replace('\n', '').replace('\r', '') for col in df4.columns]
            
            # 빈 문자열과 'nan' 문자열을 NaN으로 변환
            df4 = df4.replace(['', 'nan', 'NaN'], np.nan)
            
            # 데이터 타입 정리
            for col in df4.columns:
                if col in ['이름', '파트', '직급', '담당', '직책', '사번']:
                    df4[col] = df4[col].astype(str).str.strip()
                    df4[col] = df4[col].replace('nan', np.nan)
                        
        except Exception as e:
            df4 = None
    
    return df2, df4

# df3 수리비 매핑 강화 함수
@st.cache_data
def enhanced_merge_repair_costs(df1, df3):
    """df3 수리비를 df1에 정확하게 매핑하는 강화된 함수"""
    
    if df1 is None or df3 is None:
        return df1
    
    try:
        st.write("### 🔍 수리비 매핑 (df3 기준)")
        
        df1_temp = df1.copy()
        df3_temp = df3.copy()
        
        # df1 전처리
        df1_temp['관리번호'] = df1_temp['관리번호'].astype(str).str.strip()
        df1_temp['정비일자'] = pd.to_datetime(df1_temp['정비일자'], errors='coerce')
        df1_temp['정비년월'] = df1_temp['정비일자'].dt.to_period('M')
        
        # df3 전처리
        df3_temp['관리번호'] = df3_temp['관리번호'].astype(str).str.strip()
        df3_temp['출고일자'] = pd.to_datetime(df3_temp['출고일자'], errors='coerce')
        df3_temp['출고년월'] = df3_temp['출고일자'].dt.to_period('M')
        
        # 수리비 컬럼 처리
        cost_col = None
        for col in ['출고금액', '금액', '단가']:
            if col in df3_temp.columns:
                cost_col = col
                break
        
        if cost_col:
            df3_temp['수리비'] = pd.to_numeric(df3_temp[cost_col], errors='coerce').fillna(0)
            
            # 1차 매핑: 관리번호 + 년월
            cost_summary = df3_temp.groupby(['관리번호', '출고년월']).agg({
                '수리비': 'sum',
                '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:3])
            }).reset_index()
            cost_summary.columns = ['관리번호', '년월', '수리비', '사용부품']
            
            # df1과 매핑
            result = pd.merge(
                df1_temp,
                cost_summary,
                left_on=['관리번호', '정비년월'],
                right_on=['관리번호', '년월'],
                how='left'
            )
            
            # 2차 매핑: 매핑되지 않은 경우 관리번호만으로 재시도
            unmapped_mask = result['수리비'].isna() | (result['수리비'] == 0)
            if unmapped_mask.any():
                avg_cost_by_equipment = df3_temp.groupby('관리번호')['수리비'].mean().reset_index()
                avg_cost_by_equipment.columns = ['관리번호', '평균수리비']
                
                result = pd.merge(result, avg_cost_by_equipment, on='관리번호', how='left')
                result.loc[unmapped_mask & result['평균수리비'].notna(), '수리비'] = \
                    result.loc[unmapped_mask & result['평균수리비'].notna(), '평균수리비']
                
                if '평균수리비' in result.columns:
                    result = result.drop('평균수리비', axis=1)
            
            # 임시 컬럼 제거
            if '년월' in result.columns:
                result = result.drop('년월', axis=1)
            if '정비년월' in result.columns:
                result = result.drop('정비년월', axis=1)
            
            # 매핑 결과
            mapped_count = (result['수리비'] > 0).sum()
            mapping_rate = (mapped_count / len(result) * 100) if len(result) > 0 else 0
            
            st.write(f"**수리비 매핑 결과: {mapped_count}건 ({mapping_rate:.1f}%)**")
            st.write(f"**총 수리비: {result['수리비'].sum():,.0f}원**")
            
            return result
        else:
            st.warning("df3에서 수리비 관련 컬럼을 찾을 수 없습니다.")
            df1_temp['수리비'] = 0
            return df1_temp
            
    except Exception as e:
        st.error(f"수리비 매핑 오류: {e}")
        df1['수리비'] = 0
        return df1

# 만족도 데이터와 조직도 매핑 함수
@st.cache_data
def merge_satisfaction_by_employee_id(satisfaction_df, org_df):
    """만족도 데이터를 사번 기준으로 조직도와 매핑"""
    if satisfaction_df is None or org_df is None:
        return satisfaction_df
    
    try:
        df5 = satisfaction_df.copy()
        org_temp = org_df.copy()
        
        # 사번을 문자열로 통일
        df5['사번'] = df5['사번'].astype(str).str.strip()
        org_temp['사번'] = org_temp['사번'].astype(str).str.strip()
        
        # 조직도에서 사번-파트 매핑 정보 추출
        org_mapping = org_temp[['사번', '파트', '이름']].dropna()
        
        # 만족도 데이터와 조직도 매핑
        df5_with_part = pd.merge(
            df5,
            org_mapping,
            on='사번',
            how='left'
        )
        
        return df5_with_part
        
    except Exception as e:
        return satisfaction_df

def aggregate_satisfaction_by_part(satisfaction_df):
    """파트별 만족도 통계 집계"""
    if satisfaction_df is None or '파트' not in satisfaction_df.columns:
        return None
    
    try:
        # 파트별 만족도 통계 계산
        part_satisfaction = satisfaction_df.groupby('파트').agg({
            '만족도점수': [
                'mean',      # 평균
                'count',     # 응답 수
                lambda x: (x >= 4).sum() / len(x) * 100,  # 만족률
                lambda x: (x <= 2).sum() / len(x) * 100,  # 불만족률
            ]
        }).round(2)
        
        # 컬럼명 정리
        part_satisfaction.columns = [
            '만족도_평균', '만족도_응답수', '만족도_만족률', '만족도_불만족률'
        ]
        
        # 만족도 등급 분류
        def classify_satisfaction(avg_score):
            if pd.isna(avg_score):
                return '미조사'
            elif avg_score >= 4.5:
                return '매우만족'
            elif avg_score >= 4.0:
                return '만족'
            elif avg_score >= 3.0:
                return '보통'
            elif avg_score >= 2.0:
                return '불만족'
            else:
                return '매우불만족'
        
        part_satisfaction['만족도_등급'] = part_satisfaction['만족도_평균'].apply(classify_satisfaction)
        
        return part_satisfaction.reset_index()
        
    except Exception as e:
        return None

# 통합 머지 함수 - df3 수리비 매핑 강화 버전
@st.cache_data
def simple_merge_all(df1, df2=None, df3=None, df4=None, df5=None):
    """모든 데이터를 df1에 머지 - df3 수리비 매핑 강화 버전"""
    
    result = df1.copy()
    
    # 1. 기본 정리
    if '관리번호' in result.columns:
        result['관리번호'] = result['관리번호'].astype(str)
    
    if '정비일자' in result.columns:
        result['정비일자'] = pd.to_datetime(result['정비일자'], errors='coerce')
        result['년월'] = result['정비일자'].dt.to_period('M')
    
    # 2. df3 수리비 매핑 (강화된 로직)
    if df3 is not None:
        result = enhanced_merge_repair_costs(result, df3)
        # df3 원본을 세션에 저장
        st.session_state.df3_raw = df3
    else:
        result['수리비'] = 0
    
    # 3. 자산 데이터 머지 (df2)
    if df2 is not None and '관리번호' in df2.columns:
        try:
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
            
        except Exception as e:
            pass
    
    # 브랜드 정리
    if '브랜드' not in result.columns:
        result['브랜드'] = '기타'
    else:
        result['브랜드'] = result['브랜드'].fillna('기타')
    
    # 4. 조직도 데이터로 소속 매핑 (df4)
    if df4 is not None:
        df4_clean = df4.copy()
        
        for col in ['이름', '파트']:
            if col in df4_clean.columns:
                df4_clean[col] = df4_clean[col].astype(str).str.strip()
                df4_clean[col] = df4_clean[col].replace(['nan', 'NaN', ''], np.nan)
        
        df4_clean = df4_clean.dropna(subset=['이름', '파트'])
        
        try:
            if '정비자' in result.columns and '이름' in df4_clean.columns and '파트' in df4_clean.columns:
                
                result['정비자_clean'] = result['정비자'].astype(str).str.strip()
                result['정비자_clean'] = result['정비자_clean'].replace(['nan', 'NaN', ''], np.nan)
                
                org_mapping = df4_clean[['이름', '파트']].set_index('이름')['파트'].to_dict()
                
                def map_to_part(worker_name):
                    if pd.isna(worker_name):
                        return np.nan
                    return org_mapping.get(worker_name, np.nan)
                
                result['정비자소속'] = result['정비자_clean'].apply(map_to_part)
                
                unmapped_mask = result['정비자소속'].isna()
                if unmapped_mask.any():
                    result.loc[unmapped_mask, '정비자소속'] = '미분류'
                
                if '정비자_clean' in result.columns:
                    result = result.drop('정비자_clean', axis=1)
            
            else:
                result['정비자소속'] = '미분류'
                
        except Exception as e:
            result['정비자소속'] = '미분류'
    
    else:
        result['정비자소속'] = '미분류'
    
    # 5. 만족도 데이터 간단 매핑 (df5)
    if df5 is not None and '관리번호' in df5.columns:
        try:
            df5['관리번호'] = df5['관리번호'].astype(str)
            
            if '답변' in df5.columns:
                df5['만족도점수'] = pd.to_numeric(df5['답변'], errors='coerce')
                
                satisfaction_summary = df5.groupby('관리번호')['만족도점수'].agg([
                    'mean', 'count'
                ]).reset_index()
                satisfaction_summary.columns = ['관리번호', '만족도_평균', '만족도_응답수']
                
                result = pd.merge(result, satisfaction_summary, on='관리번호', how='left')
            
        except Exception as e:
            pass
    
    # 6. 지역 정보 추출 강화
    if '현장' in result.columns:
        def extract_region_enhanced(address):
            if not isinstance(address, str):
                return None
            
            regions = {
                '서울': ['서울', '서울시', '서울특별시'],
                '부산': ['부산', '부산시', '부산광역시'],
                '대구': ['대구', '대구시', '대구광역시'],
                '인천': ['인천', '인천시', '인천광역시'],
                '광주': ['광주', '광주시', '광주광역시'],
                '대전': ['대전', '대전시', '대전광역시'],
                '울산': ['울산', '울산시', '울산광역시'],
                '세종': ['세종', '세종시', '세종특별자치시'],
                '경기': ['경기', '경기도'],
                '강원': ['강원', '강원도'],
                '충북': ['충북', '충청북도'],
                '충남': ['충남', '충청남도'],
                '전북': ['전북', '전라북도'],
                '전남': ['전남', '전라남도'],
                '경북': ['경북', '경상북도'],
                '경남': ['경남', '경상남도'],
                '제주': ['제주', '제주도', '제주특별자치도']
            }
            
            address_lower = address.lower()
            for region, keywords in regions.items():
                if any(keyword.lower() in address_lower for keyword in keywords):
                    return region
            
            return None
        
        result['지역'] = result['현장'].apply(extract_region_enhanced)
        result['현장명'] = result['현장']
    
    # 7. 필요한 컬럼만 유지
    keep_columns = [
        '관리번호', '정비일자', '년월', '정비자', '정비자소속',
        '브랜드', '모델명', '수리비', '작업유형', '정비대상', '정비작업',
        '현장명', '지역', '수리시간', '가동시간'
    ]
    
    if '사용부품' in result.columns:
        keep_columns.append('사용부품')
    if '만족도_평균' in result.columns:
        keep_columns.extend(['만족도_평균', '만족도_응답수'])
    
    final_columns = [col for col in keep_columns if col in result.columns]
    result = result[final_columns]

    # 8. AWP 파트 제외 처리
    if '정비자소속' in result.columns:
        result = result[~result['정비자소속'].str.contains('AWP', case=False, na=False)]
    
    return result

# 사이드바
st.sidebar.title("📁 데이터 업로드")

uploaded_file1 = st.sidebar.file_uploader("**정비일지 데이터** (필수)", type=["xlsx", "xls"])
uploaded_file3 = st.sidebar.file_uploader("**소모품 출고 데이터** (수리비)", type=["xlsx", "xls"])
uploaded_file5 = st.sidebar.file_uploader("**만족도 조사 데이터**", type=["xlsx", "xls"])

# 내장 데이터
df2, df4 = load_static_data()

# 메인
st.title("🏭 산업장비 AS 분석 대시보드")
st.markdown("---")

# 데이터 처리
if uploaded_file1 is not None:
    with st.spinner("데이터 처리 중..."):
        try:
            # 모든 파일 로드
            df1 = load_excel_simple(uploaded_file1)
            df3 = load_excel_simple(uploaded_file3) if uploaded_file3 else None
            df5 = load_excel_simple(uploaded_file5) if uploaded_file5 else None
            
            if df1 is not None:
                # 만족도 데이터 전처리 및 조직도 매핑
                if df5 is not None and df4 is not None:
                    # 만족도 데이터 전처리
                    if '답변' in df5.columns:
                        df5['만족도점수'] = pd.to_numeric(df5['답변'], errors='coerce')
                    
                    # 조직도와 매핑 (사번 기준)
                    df5_with_part = merge_satisfaction_by_employee_id(df5, df4)
                    
                    # 파트별 만족도 통계 집계
                    part_satisfaction_stats = aggregate_satisfaction_by_part(df5_with_part)
                    
                    # 세션에 저장
                    st.session_state.satisfaction_data = df5_with_part
                    st.session_state.part_satisfaction_stats = part_satisfaction_stats

                # df3 수리비를 df1에 매핑
                final_data = simple_merge_all(df1, df2, df3, df4, df5)
                
                if final_data is not None:
                    # 세션에 저장
                    st.session_state.df1_with_costs = final_data
                    st.session_state.data_loaded = True
                    
                    st.success("✅ 데이터 처리 완료")
                    
                    # 데이터 미리보기
                    st.subheader("📊 통합 데이터 미리보기")
                    st.write(f"총 {len(final_data)}건의 AS 데이터")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("총 수리비", f"{final_data['수리비'].sum():,.0f}원")
                    with col2:
                        st.metric("파트 수", f"{final_data['정비자소속'].nunique()}개")
                    with col3:
                        st.metric("지역 수", f"{final_data['지역'].nunique() if '지역' in final_data.columns else 0}개")
                    with col4:
                        st.metric("장비 수", f"{final_data['관리번호'].nunique()}대")
                    
                    st.dataframe(final_data.head(10), use_container_width=True)
                else:
                    st.error("데이터 통합에 실패했습니다.")
                
        except Exception as e:
            st.error(f"데이터 처리 실패: {e}")
            st.exception(e)

else:
    st.info("👈 정비일지 데이터를 업로드해주세요.")
    
    st.markdown("""
    ## 🎯 분석 메뉴
    
    - **📊 경영 대시보드**: 월별 트렌드 및 핵심 지표 (df3 수리비 반영)
    - **👥 파트별 분석**: 파트별 성과 평가 (조직도 매핑 + df3 수리비)
    - **🏢 업체별 분석**: 디마케팅 위험도 분석 (df3 수리비 반영)
    - **📅 월별 분석**: 종합 리포트 및 다운로드 (df3 수리비 반영)
    
    ### 📋 데이터 매핑 방식
    - **수리비 매핑**: df3 출고일자(년월) + 관리번호 → df1 수리비
    - **조직도 매핑**: 정비자 → 파트, 직급, 직책
    - **자산정보 매핑**: 관리번호 → 브랜드, 모델명
    - **지역정보 추출**: 현장명 → 지역 자동 분류
    - **만족도 매핑**: 사번 기준으로 조직도와 연동
    """)

# 하단
st.markdown("---")
