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

# df3 조직도 매핑 함수 (수정됨)
@st.cache_data
def create_df3_with_organization(df3, df4):
    """df3를 조직도와 매핑하여 파트 정보 추가"""
    
    if df3 is None:
        return None
    
    try:
        st.write("### 🔍 df3 + 조직도 매핑")
        
        df3_processed = df3.copy()
        
        # 기본 전처리
        if '관리번호' in df3_processed.columns:
            df3_processed['관리번호'] = df3_processed['관리번호'].astype(str).str.strip()
        
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
            st.write(f"✅ 수리비 컬럼 처리 완료 (기준: {cost_col})")
        else:
            df3_processed['수리비'] = 0
            st.warning("⚠️ 수리비 관련 컬럼을 찾을 수 없습니다.")
        
        # 조직도 매핑 (출고자 = 사번)
        if df4 is not None and '출고자' in df3_processed.columns:
            st.write("**출고자-조직도 매핑 시도**")
            
            # 출고자를 사번으로 간주하여 매핑
            df3_processed['출고자'] = df3_processed['출고자'].astype(str).str.strip()
            df4_clean = df4.copy()
            
            # 조직도 컬럼 확인
            st.write(f"조직도 컬럼: {df4_clean.columns.tolist()}")
            
            required_cols = ['사번', '파트']
            available_cols = [col for col in required_cols if col in df4_clean.columns]
            
            if len(available_cols) == 2:  # 사번, 파트 모두 있음
                df4_clean['사번'] = df4_clean['사번'].astype(str).str.strip()
                
                # 조직도 매핑 정보 준비
                org_cols = ['사번', '파트']
                if '직급' in df4_clean.columns:
                    org_cols.append('직급')
                if '직책' in df4_clean.columns:
                    org_cols.append('직책')
                
                org_mapping = df4_clean[org_cols].dropna(subset=['사번', '파트'])
                
                st.write(f"매핑 가능한 조직도 레코드: {len(org_mapping)}건")
                
                # 출고자 현황 확인
                df3_workers = df3_processed['출고자'].value_counts().head(10)
                st.write("**df3 출고자 현황:**")
                for worker, count in df3_workers.items():
                    st.write(f"  - {worker}: {count}건")
                
                # 조직도 사번 현황 확인
                org_workers = org_mapping['사번'].value_counts().head(10)
                st.write("**조직도 사번 현황:**")
                for worker, count in org_workers.items():
                    st.write(f"  - {worker}: {count}건")
                
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
                
                # 매핑되지 않은 경우 출고자를 파트로 사용
                unmapped_mask = df3_processed['파트'].isna()
                if unmapped_mask.any():
                    df3_processed.loc[unmapped_mask, '파트'] = df3_processed.loc[unmapped_mask, '출고자']
                    st.info(f"매핑되지 않은 {unmapped_mask.sum()}건은 출고자를 파트명으로 사용합니다.")
                
                # 중복 사번 컬럼 제거
                if '사번' in df3_processed.columns:
                    df3_processed = df3_processed.drop('사번', axis=1)
                    
            else:
                st.error(f"조직도에 필요한 컬럼이 없습니다. 필요: {required_cols}, 있음: {available_cols}")
                # 출고자를 파트로 사용
                df3_processed['파트'] = df3_processed.get('출고자', '미분류')
                df3_processed['직급'] = '정보없음'
                df3_processed['직책'] = '정보없음'
        else:
            # 조직도가 없거나 출고자 컬럼이 없는 경우
            if '출고자' in df3_processed.columns:
                df3_processed['파트'] = df3_processed['출고자']
                st.info("조직도 없음. 출고자를 파트로 사용합니다.")
            else:
                df3_processed['파트'] = '미분류'
                st.warning("출고자 컬럼이 없습니다. 미분류로 처리합니다.")
        
        return df3_processed
        
    except Exception as e:
        st.error(f"df3 조직도 매핑 오류: {e}")
        return df3

# df3와 df1 매핑 함수 (업체명 가져오기)
@st.cache_data
def merge_df3_with_df1_client_info(df3_with_org, df1):
    """df3에 df1의 업체명 정보 매핑"""
    
    if df3_with_org is None or df1 is None:
        return df3_with_org
    
    try:
        st.write("### 🔍 df3 + df1 업체명 매핑")
        
        df3_temp = df3_with_org.copy()
        df1_temp = df1.copy()
        
        # df1 전처리
        df1_temp['관리번호'] = df1_temp['관리번호'].astype(str).str.strip()
        df1_temp['정비일자'] = pd.to_datetime(df1_temp['정비일자'], errors='coerce')
        df1_temp['정비년'] = df1_temp['정비일자'].dt.year
        df1_temp['정비월'] = df1_temp['정비일자'].dt.month
        df1_temp['정비년월'] = df1_temp['정비일자'].dt.to_period('M')
        
        # 대분류/중분류/소분류 합쳐서 작업유형 생성
        work_type_parts = []
        for col in ['대분류', '중분류', '소분류']:
            if col in df1_temp.columns:
                work_type_parts.append(df1_temp[col].astype(str))
        
        if work_type_parts:
            df1_temp['작업유형_통합'] = work_type_parts[0]
            for part in work_type_parts[1:]:
                df1_temp['작업유형_통합'] = df1_temp['작업유형_통합'] + ' > ' + part
            
            # 'nan' 제거 및 정리
            df1_temp['작업유형_통합'] = df1_temp['작업유형_통합'].str.replace('nan', '').str.replace(' > ', ' > ').str.strip(' > ')
            df1_temp['작업유형_통합'] = df1_temp['작업유형_통합'].replace('', '미분류')
            st.write("✅ df1 작업유형 통합 완료")
        
        # 업체명 컬럼 찾기
        client_col = None
        for col in ['현장명', '업체명', '현장']:
            if col in df1_temp.columns:
                client_col = col
                break
        
        if client_col:
            st.write(f"**업체명 컬럼 발견: {client_col}**")
            
            # 매핑할 정보 준비
            mapping_cols = ['관리번호', '정비년월', client_col]
            if '작업유형_통합' in df1_temp.columns:
                mapping_cols.append('작업유형_통합')
            
            # 중복 제거
            df1_mapping = df1_temp[mapping_cols].drop_duplicates()
            
            st.write(f"df1 매핑 데이터: {len(df1_mapping)}건")
            
            # 년월 + 관리번호 기준 매핑
            df3_final = pd.merge(
                df3_temp,
                df1_mapping,
                left_on=['관리번호', '출고년월'],
                right_on=['관리번호', '정비년월'],
                how='left'
            )
            
            # 매핑되지 않은 경우 관리번호만으로 재시도
            unmapped_mask = df3_final[client_col].isna()
            if unmapped_mask.any():
                st.write(f"년월 매핑 실패: {unmapped_mask.sum()}건 → 관리번호만으로 재시도")
                
                # 관리번호만으로 매핑
                simple_mapping_cols = ['관리번호', client_col]
                if '작업유형_통합' in df1_temp.columns:
                    simple_mapping_cols.append('작업유형_통합')
                
                df1_simple_mapping = df1_temp[simple_mapping_cols].drop_duplicates().groupby('관리번호').first().reset_index()
                
                # 매핑되지 않은 항목에 대해 관리번호 기준으로 매핑
                for idx, row in df3_final[unmapped_mask].iterrows():
                    matching_rows = df1_simple_mapping[df1_simple_mapping['관리번호'] == row['관리번호']]
                    if not matching_rows.empty:
                        for col in simple_mapping_cols[1:]:  # 관리번호 제외
                            df3_final.loc[idx, col] = matching_rows.iloc[0][col]
            
            # 컬럼명 통일
            df3_final['업체명'] = df3_final[client_col]
            if '작업유형_통합' in df3_final.columns:
                df3_final['작업유형'] = df3_final['작업유형_통합']
            
            # 임시 컬럼 제거
            cleanup_cols = ['정비년월']
            if client_col != '업체명':
                cleanup_cols.append(client_col)
            if '작업유형_통합' in df3_final.columns:
                cleanup_cols.append('작업유형_통합')
            
            for col in cleanup_cols:
                if col in df3_final.columns:
                    df3_final = df3_final.drop(col, axis=1)
            
            # 매핑 결과 확인
            mapped_clients = df3_final['업체명'].notna().sum()
            client_mapping_rate = (mapped_clients / len(df3_final) * 100) if len(df3_final) > 0 else 0
            
            st.write(f"**업체명 매핑 결과: {mapped_clients}건 ({client_mapping_rate:.1f}%)**")
            
            if '작업유형' in df3_final.columns:
                mapped_work_types = df3_final['작업유형'].notna().sum()
                st.write(f"**작업유형 매핑 결과: {mapped_work_types}건**")
            
            return df3_final
        else:
            st.warning("df1에서 업체명 관련 컬럼을 찾을 수 없습니다.")
            return df3_temp
            
    except Exception as e:
        st.error(f"df3-df1 매핑 오류: {e}")
        return df3_with_org

# df1 기본 처리 함수
@st.cache_data
def process_df1_basic(df1, df2, df4):
    """df1 기본 처리 (자산정보, 조직도 매핑)"""
    
    if df1 is None:
        return None
    
    result = df1.copy()
    
    # 1. 기본 정리
    if '관리번호' in result.columns:
        result['관리번호'] = result['관리번호'].astype(str)
    
    if '정비일자' in result.columns:
        result['정비일자'] = pd.to_datetime(result['정비일자'], errors='coerce')
        result['년월'] = result['정비일자'].dt.to_period('M')
    
    # 2. 자산 데이터 머지 (df2)
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
    
    # 3. 조직도 데이터로 정비자 소속 매핑 (df4)
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
    
    # 4. 지역 정보 추출
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
    
    return result

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
                
                st.session_state.data_loaded = True
                st.success("✅ 데이터 처리 완료")
                
                # 데이터 미리보기
                st.subheader("📊 처리된 데이터 현황")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**df1 처리 결과:**")
                    if df1_processed is not None:
                        st.write(f"- 총 건수: {len(df1_processed):,}건")
                        st.write(f"- 총 수리비: {df1_processed.get('수리비', pd.Series([0])).sum():,.0f}원")
                        st.write(f"- 파트 수: {df1_processed['정비자소속'].nunique()}개")
                
                with col2:
                    st.write("**df3 처리 결과:**")
                    if 'df3_final' in st.session_state:
                        df3_final = st.session_state['df3_final']
                        st.write(f"- 총 건수: {len(df3_final):,}건")
                        st.write(f"- 총 출고금액: {df3_final['수리비'].sum():,.0f}원")
                        st.write(f"- 파트 수: {df3_final['파트'].nunique()}개")
                
                # df3 데이터 미리보기
                if 'df3_final' in st.session_state:
                    st.subheader("📊 df3 최종 데이터 미리보기")
                    st.dataframe(st.session_state['df3_final'].head(10), use_container_width=True)
                
        except Exception as e:
            st.error(f"데이터 처리 실패: {e}")
            st.exception(e)
else:
    st.info("👈 정비일지 데이터를 업로드해주세요.")

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

# 하단
st.markdown("---")
