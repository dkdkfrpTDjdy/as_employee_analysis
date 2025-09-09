import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
import re
from difflib import get_close_matches
from io import BytesIO
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

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

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

# df3와 df1 매핑 강화 함수 (출고자-조직도 매핑 포함)
@st.cache_data
def enhanced_merge_df3_with_org(df1, df3, df4):
    """df3를 조직도와 매핑하고 df1과 통합하는 강화된 함수"""
    
    if df1 is None or df3 is None:
        return df1
    
    try:
        st.write("### 🔍 df3 수리품목 데이터 매핑 (조직도 연동)")
        
        df1_temp = df1.copy()
        df3_temp = df3.copy()
        
        # df3에 조직도 정보 매핑 (출고자 기준)
        if df4 is not None and '출고자' in df3_temp.columns:
            # 출고자를 사번으로 간주하여 조직도와 매핑
            df3_temp['출고자'] = df3_temp['출고자'].astype(str).str.strip()
            df4_temp = df4.copy()
            df4_temp['사번'] = df4_temp['사번'].astype(str).str.strip()
            
            # 조직도 매핑
            org_mapping = df4_temp[['사번', '파트', '직급', '직책']].dropna(subset=['사번'])
            df3_with_org = pd.merge(
                df3_temp,
                org_mapping,
                left_on='출고자',
                right_on='사번',
                how='left'
            )
            
            mapped_count = df3_with_org['파트'].notna().sum()
            st.write(f"**조직도 매핑 결과: {mapped_count}건 매핑됨**")
            
        else:
            df3_with_org = df3_temp.copy()
            st.write("**조직도 매핑 불가 (출고자 또는 조직도 데이터 없음)**")
        
        # df1 전처리
        df1_temp['관리번호'] = df1_temp['관리번호'].astype(str).str.strip()
        df1_temp['정비일자'] = pd.to_datetime(df1_temp['정비일자'], errors='coerce')
        df1_temp['정비년월'] = df1_temp['정비일자'].dt.to_period('M')
        
        # df3 전처리
        df3_with_org['관리번호'] = df3_with_org['관리번호'].astype(str).str.strip()
        df3_with_org['출고일자'] = pd.to_datetime(df3_with_org['출고일자'], errors='coerce')
        df3_with_org['출고년월'] = df3_with_org['출고일자'].dt.to_period('M')
        
        # 수리비 컬럼 처리
        cost_col = None
        for col in ['출고금액', '금액', '단가', '수리비']:
            if col in df3_with_org.columns:
                cost_col = col
                break
        
        if cost_col:
            df3_with_org['수리비'] = pd.to_numeric(df3_with_org[cost_col], errors='coerce').fillna(0)
            
            # 관리번호 + 년월 기준으로 집계
            cost_summary = df3_with_org.groupby(['관리번호', '출고년월']).agg({
                '수리비': 'sum',
                '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:3]),
                '파트': 'first',  # 파트 정보 추가
                '직급': 'first',  # 직급 정보 추가
                '직책': 'first'   # 직책 정보 추가
            }).reset_index()
            
            cost_summary.columns = ['관리번호', '년월', '수리비', '사용부품', '수리담당파트', '수리담당직급', '수리담당직책']
            
            # df1과 매핑
            result = pd.merge(
                df1_temp,
                cost_summary,
                left_on=['관리번호', '정비년월'],
                right_on=['관리번호', '년월'],
                how='left'
            )
            
            # 매핑되지 않은 경우 관리번호만으로 재시도
            unmapped_mask = result['수리비'].isna() | (result['수리비'] == 0)
            if unmapped_mask.any():
                avg_cost_by_equipment = df3_with_org.groupby('관리번호').agg({
                    '수리비': 'mean',
                    '파트': 'first',
                    '직급': 'first',
                    '직책': 'first'
                }).reset_index()
                avg_cost_by_equipment.columns = ['관리번호', '평균수리비', '평균수리담당파트', '평균수리담당직급', '평균수리담당직책']
                
                result = pd.merge(result, avg_cost_by_equipment, on='관리번호', how='left')
                
                # 매핑되지 않은 항목에 평균값 적용
                for col_pair in [('수리비', '평균수리비'), ('수리담당파트', '평균수리담당파트'), 
                               ('수리담당직급', '평균수리담당직급'), ('수리담당직책', '평균수리담당직책')]:
                    original_col, avg_col = col_pair
                    if avg_col in result.columns:
                        mask = unmapped_mask & result[avg_col].notna()
                        if original_col == '수리비':
                            result.loc[mask, original_col] = result.loc[mask, avg_col]
                        else:
                            result.loc[result[original_col].isna() & result[avg_col].notna(), original_col] = \
                                result.loc[result[original_col].isna() & result[avg_col].notna(), avg_col]
                
                # 임시 컬럼 제거
                avg_cols = [col for col in result.columns if col.startswith('평균수리')]
                result = result.drop(avg_cols, axis=1)
            
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
            
            # df3 원본을 세션에 저장 (조직도 매핑된 버전)
            st.session_state.df3_with_org = df3_with_org
            
            return result
        else:
            st.warning("df3에서 수리비 관련 컬럼을 찾을 수 없습니다.")
            df1_temp['수리비'] = 0
            return df1_temp
            
    except Exception as e:
        st.error(f"df3 매핑 오류: {e}")
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
        org_mapping = org_temp[['사번', '파트', '이름', '직급', '직책']].dropna()
        
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

# 통합 머지 함수 - df3 중심 강화 버전
@st.cache_data
def comprehensive_merge_all(df1, df2=None, df3=None, df4=None, df5=None):
    """모든 데이터를 df1에 머지 - df3 중심 강화 버전"""
    
    result = df1.copy()
    
    # 1. 기본 정리
    if '관리번호' in result.columns:
        result['관리번호'] = result['관리번호'].astype(str)
    
    if '정비일자' in result.columns:
        result['정비일자'] = pd.to_datetime(result['정비일자'], errors='coerce')
        result['년월'] = result['정비일자'].dt.to_period('M')
    
    # 2. df3 수리비 매핑 (조직도 연동 강화)
    if df3 is not None:
        result = enhanced_merge_df3_with_org(result, df3, df4)
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
            
            # 업체명 매핑 추가
            if '업체명' in df2.columns:
                asset_cols.append('업체명')
            
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
    
    # 4. 조직도 데이터로 정비자 소속 매핑 (df4)
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
                
                org_mapping = df4_clean[['이름', '파트', '직급', '직책']].set_index('이름')
                
                def map_to_org_info(worker_name):
                    if pd.isna(worker_name) or worker_name not in org_mapping.index:
                        return pd.Series([np.nan, np.nan, np.nan])
                    return org_mapping.loc[worker_name, ['파트', '직급', '직책']]
                
                org_info = result['정비자_clean'].apply(map_to_org_info)
                result['정비자소속'] = org_info.iloc[:, 0]
                result['정비자직급'] = org_info.iloc[:, 1]
                result['정비자직책'] = org_info.iloc[:, 2]
                
                # 매핑되지 않은 경우 처리
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
    
    # 5. 만족도 데이터 매핑 (df5)
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
        '관리번호', '정비일자', '년월', '정비자', '정비자소속', '정비자직급', '정비자직책',
        '브랜드', '모델명', '수리비', '작업유형', '정비대상', '정비작업',
        '현장명', '지역', '수리시간', '가동시간', '수리담당파트', '수리담당직급', '수리담당직책'
    ]
    
    if '사용부품' in result.columns:
        keep_columns.append('사용부품')
    if '만족도_평균' in result.columns:
        keep_columns.extend(['만족도_평균', '만족도_응답수'])
    if '업체명' in result.columns:
        keep_columns.append('업체명')
    
    final_columns = [col for col in keep_columns if col in result.columns]
    result = result[final_columns]
    
    # 8. AWP 파트 제외 처리
    if '정비자소속' in result.columns:
        result = result[~result['정비자소속'].str.contains('AWP', case=False, na=False)]
    
    return result

# 사이드바
st.sidebar.title("📁 데이터 업로드")

uploaded_file1 = st.sidebar.file_uploader("정비일지 데이터 (필수)", type=["xlsx", "xls"])
uploaded_file3 = st.sidebar.file_uploader("소모품 출고 데이터 (수리비)", type=["xlsx", "xls"])
uploaded_file5 = st.sidebar.file_uploader("만족도 조사 데이터", type=["xlsx", "xls"])

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
                    
                    # 세션에 저장
                    st.session_state.satisfaction_data = df5_with_part
                
                # 통합 데이터 생성 (df3 중심 강화)
                final_data = comprehensive_merge_all(df1, df2, df3, df4, df5)
                
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
""")

# 하단
st.markdown("---")
