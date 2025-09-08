import pandas as pd
import numpy as np
import streamlit as st
from collections import Counter
import traceback
import datetime
import re
import logging
from difflib import SequenceMatcher

# 로깅 설정
def setup_logging():
    """로깅 설정"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# 설정 관리 클래스
class DataProcessingConfig:
    """데이터 처리 설정 클래스"""
    
    # 날짜 매칭 윈도우
    DATE_WINDOW_MAIN = 7
    DATE_WINDOW_EXTENDED = 30
    
    # 유사도 임계값
    SIMILARITY_THRESHOLD = 0.6
    
    # 캐시 설정
    CACHE_TTL = 3600
    
    # 컬럼 매핑
    COLUMN_MAPPINGS = {
        '대분류': '작업유형',
        '중분류': '정비대상', 
        '소분류': '정비작업',
        '제조사명': '브랜드',
        '제조사모델명': '모델명'
    }
    
    # 키워드 룰 확장
    KEYWORD_RULES = [
        (['타이어','d/w','고무','휠'], ['타이어','d/w','고무','휠']),
        (['충전','전압','탭','f6-2'], ['충전','충전기','탭']),
        (['레드빔','전조등','후미등','램프','등화'], ['등','램프','레드빔','전조','후미']),
        (['유압','호스','누유','틸트'], ['유압','호스','틸트']),
        (['냉각','팬','펜','a0-5'], ['냉각','팬']),
        (['브레이크','리턴'], ['브레이크']),
        (['에어','필터','크리너'], ['에어','필터','크리너']),
        (['래치','켓치','손잡이'], ['래치','켓치','손잡이']),
        (['구동','모터','전후진'], ['구동','모터']),
        (['배선','단선','단락','can통신'], ['배선','선','케이블']),
    ]

@st.cache_data(ttl=DataProcessingConfig.CACHE_TTL)
def load_data(file):
    """파일에서 데이터를 로드하는 함수 - 개선된 버전"""
    try:
        logger.info(f"파일 로드 시작: {file.name}")
        
        # 첫 번째 시도: 모든 컬럼을 문자열로 로드
        df = pd.read_excel(file, dtype=str)
        
        # 컬럼명 정리
        df.columns = [str(col).strip().replace('\n', '').replace('\r', '') for col in df.columns]
        
        # 빈 문자열을 NaN으로 변환
        df = df.replace('', np.nan)
        
        # 관리번호 처리 (앞의 0이 사라지는 것 방지)
        if '관리번호' in df.columns:
            df['관리번호'] = df['관리번호'].astype(str).str.strip()
        
        # 숫자형 컬럼 자동 감지 및 변환
        numeric_keywords = ['금액', '시간', '비용', '단가', '수량', '가격', '점수']
        for col in df.columns:
            if any(keyword in col.lower() for keyword in numeric_keywords):
                # 쉼표 제거 후 숫자 변환
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('원', '')
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 날짜형 컬럼 자동 감지 및 변환
        date_keywords = ['일자', '날짜', 'date', '시간', '시각']
        for col in df.columns:
            if any(keyword in col.lower() for keyword in date_keywords):
                # 다양한 날짜 형식 처리
                df[col] = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)
        
        logger.info(f"파일 로드 완료: {len(df)}행, {len(df.columns)}컬럼")
        return df
        
    except Exception as e:
        logger.error(f"파일 로드 오류: {e}")
        st.error(f"파일 로드 오류: {e}")
        return None

def validate_data_quality(df, data_type="데이터"):
    """데이터 품질 검증 및 리포트"""
    if df is None or df.empty:
        st.error(f"{data_type}가 비어있습니다.")
        return False
    
    st.write(f"### {data_type} 품질 리포트")
    
    # 기본 정보
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 행 수", len(df))
    with col2:
        st.metric("총 컬럼 수", len(df.columns))
    with col3:
        st.metric("메모리 사용량", f"{df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    
    # 결측값 분석
    missing_data = df.isnull().sum()
    if missing_data.sum() > 0:
        st.write("**결측값 현황:**")
        missing_df = pd.DataFrame({
            '컬럼명': missing_data.index,
            '결측값 수': missing_data.values,
            '결측률(%)': (missing_data.values / len(df) * 100).round(1)
        })
        missing_df = missing_df[missing_df['결측값 수'] > 0].sort_values('결측률(%)', ascending=False)
        st.dataframe(missing_df, use_container_width=True)
    
    # 중복값 확인
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        st.warning(f"중복된 행: {duplicates}개")
    
    return True

def safe_merge_operation(df1, df2, merge_func, operation_name):
    """안전한 병합 작업을 위한 래퍼 함수"""
    try:
        if df1 is None:
            st.warning(f"{operation_name}: 첫 번째 데이터프레임이 None입니다.")
            return None
        if df2 is None:
            st.warning(f"{operation_name}: 두 번째 데이터프레임이 None입니다.")
            return df1
        
        logger.info(f"{operation_name} 시작")
        result = merge_func(df1, df2)
        logger.info(f"{operation_name} 완료")
        st.success(f"{operation_name} 완료")
        return result
        
    except Exception as e:
        logger.error(f"{operation_name} 중 오류 발생: {str(e)}")
        st.error(f"{operation_name} 중 오류 발생: {str(e)}")
        return df1

def analyze_matching_quality(result_df):
    """매칭 품질 분석 및 시각화"""
    if '수리비' not in result_df.columns:
        return
    
    st.subheader("매칭 품질 분석")
    
    matched = result_df[result_df['수리비'] > 0]
    
    if matched.empty:
        st.warning("매칭된 데이터가 없습니다.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 신뢰도 분포
        if '매칭신뢰도' in matched.columns:
            st.write("**매칭 신뢰도 분포**")
            reliability_counts = pd.cut(matched['매칭신뢰도'], 
                                      bins=[0, 3, 5, 7, 10, float('inf')], 
                                      labels=['낮음(0-3)', '보통(3-5)', '높음(5-7)', '매우높음(7-10)', '최고(10+)']).value_counts()
            st.bar_chart(reliability_counts)
    
    with col2:
        # 수리비 분포
        st.write("**수리비 분포**")
        cost_ranges = pd.cut(matched['수리비'], 
                           bins=[0, 50000, 100000, 200000, 500000, float('inf')],
                           labels=['~5만원', '5-10만원', '10-20만원', '20-50만원', '50만원+']).value_counts()
        st.bar_chart(cost_ranges)
    
    # 통계 요약
    st.write("**매칭 통계 요약**")
    stats_df = pd.DataFrame({
        '지표': ['총 건수', '매칭 건수', '매칭률(%)', '평균 신뢰도', '평균 수리비(원)', '고신뢰도 비율(%)'],
        '값': [
            len(result_df),
            len(matched),
            f"{len(matched)/len(result_df)*100:.1f}",
            f"{matched['매칭신뢰도'].mean():.2f}" if '매칭신뢰도' in matched.columns else 'N/A',
            f"{matched['수리비'].mean():,.0f}",
            f"{(matched['매칭신뢰도'] >= 7).sum()/len(matched)*100:.1f}" if '매칭신뢰도' in matched.columns else 'N/A'
        ]
    })
    st.dataframe(stats_df, use_container_width=True)

def extract_region_from_address(address):
    """주소에서 지역 정보를 정확하게 추출하는 함수"""
    if not isinstance(address, str):
        return None, None

    address = address.strip()

    region_prefixes = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
                       '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주']

    tokens = address.split()
    if len(tokens) < 2:
        return None, None

    first, second = tokens[0], tokens[1]
    if first in region_prefixes and second.endswith(('시', '군', '구')):
        return first, address

    return None, None

@st.cache_data
def extract_and_apply_region(df):
    """ADDR 컬럼에서 지역과 주소를 추출하여 적용하는 함수"""
    df_copy = df.copy()
    
    # ADDR 컬럼이 있는 경우 우선 사용
    if 'ADDR' in df_copy.columns:
        results = df_copy['ADDR'].apply(extract_region_from_address)
        df_copy['지역'] = results.map(lambda x: x[0])
        df_copy['주소'] = results.map(lambda x: x[1])
    # ADDR이 없고 현장 컬럼이 있는 경우
    elif '현장' in df_copy.columns:
        results = df_copy['현장'].apply(extract_region_from_address)
        df_copy['지역'] = results.map(lambda x: x[0])
        df_copy['주소'] = results.map(lambda x: x[1])
        # 주소가 추출되지 않은 경우 현장명으로 저장
        df_copy['현장명'] = np.where(df_copy['주소'].isna(), df_copy['현장'], None)
    
    return df_copy

# 문자열 리스트 변환
def convert_to_str_list(arr):
    """NaN과 혼합 유형을 처리하여 문자열 리스트로 변환"""
    return [str(x) for x in arr if not pd.isna(x)]

# 작은 비율 항목을 '기타'로 그룹화
def group_small_categories(series, threshold=0.03):
    """작은 비율의 항목을 '기타'로 그룹화"""
    total = series.sum()
    mask = series / total < threshold
    if mask.any():
        others = pd.Series({'기타': series[mask].sum()})
        return pd.concat([series[~mask], others])
    return series

# 최근 정비일자 계산
@st.cache_data
def calculate_previous_maintenance_dates(df):
    """각 관리번호별 이전 정비일자 계산"""
    df_copy = df.copy()
    
    if '관리번호' not in df_copy.columns or '정비일자' not in df_copy.columns:
        return df_copy

    # 정비일자 정렬 및 그룹화
    df_copy = df_copy.sort_values(['관리번호', '정비일자'])

    # 각 관리번호별로 이전 정비일자 계산
    df_copy['최근정비일자'] = df_copy.groupby('관리번호')['정비일자'].shift(1)

    return df_copy

# 조직도 데이터와 정비자번호/출고자 매핑 - 수정된 버전
@st.cache_data
def map_employee_data(df, org_df):
    """정비자번호 또는 출고자를 조직도 데이터와 매핑 - 개선된 버전"""
    if org_df is None or df is None:
        return df

    try:
        logger.info("직원 데이터 매핑 시작")
        
        # 결과 데이터프레임 복사
        result_df = df.copy()
        org_temp = org_df.copy()
        
        # 조직도 데이터 컬럼명 확인 및 정리
        st.write("### 🔍 조직도 매핑 디버깅")
        st.write(f"조직도 원본 컬럼: {org_temp.columns.tolist()}")
        st.write(f"조직도 데이터 형태: {org_temp.shape}")
        
        # 조직도 컬럼이 헤더 없이 로드된 경우 처리
        if len(org_temp.columns) >= 6 and '이름' not in org_temp.columns:
            expected_cols = ['이름', '파트', '직급', '담당', '직책', '사번']
            org_temp.columns = expected_cols[:len(org_temp.columns)]
            st.info("조직도 컬럼명을 표준화했습니다.")
        
        # 조직도 데이터 샘플 확인
        st.write("**조직도 데이터 샘플:**")
        st.dataframe(org_temp.head())

        # 정비일지 데이터인 경우 (정비자 컬럼 있음)
        if '정비자' in result_df.columns:
            st.write("**정비자 기준 매핑 시도**")
            
            # 정비자 현황 확인
            workers = result_df['정비자'].value_counts().head(10)
            st.write(f"정비자 수: {len(workers)}명")
            st.write("상위 정비자들:")
            for worker, count in workers.items():
                st.write(f"  - '{worker}': {count}건")
            
            if '이름' in org_temp.columns and '파트' in org_temp.columns:
                # 문자열 변환 및 정리
                result_df['정비자'] = result_df['정비자'].astype(str).str.strip()
                org_temp['이름'] = org_temp['이름'].astype(str).str.strip()
                
                # NaN 제거
                org_clean = org_temp[['이름', '파트']].dropna()
                st.write(f"매핑 가능한 조직도 레코드: {len(org_clean)}건")
                
                # 조직도 이름들 확인
                org_names = org_clean['이름'].unique()[:10]
                st.write("조직도 이름 샘플:")
                for name in org_names:
                    st.write(f"  - '{name}'")
                
                # 공통 이름 확인
                df_workers = set(result_df['정비자'].dropna().unique())
                org_workers = set(org_clean['이름'].unique())
                common_workers = df_workers & org_workers
                
                st.write(f"**공통 이름: {len(common_workers)}명**")
                if common_workers:
                    for name in list(common_workers)[:5]:
                        st.write(f"  - {name}")
                
                # 매핑 수행
                result_df = pd.merge(
                    result_df,
                    org_clean,
                    left_on='정비자',
                    right_on='이름',
                    how='left'
                )
                
                # 컬럼명 정리
                if '파트' in result_df.columns:
                    result_df = result_df.rename(columns={'파트': '정비자소속'})
                
                # 중복 컬럼 제거
                if '이름' in result_df.columns and '이름' != '정비자':
                    result_df = result_df.drop('이름', axis=1)
                
                # 매핑 결과 확인
                mapped_count = result_df['정비자소속'].notna().sum()
                mapping_rate = (mapped_count / len(result_df) * 100) if len(result_df) > 0 else 0
                
                st.write(f"**매핑 결과: {mapped_count}건 ({mapping_rate:.1f}%)**")
                
                if mapped_count == 0:
                    st.error("매핑이 전혀 되지 않았습니다!")
                    # 실패 시 정비자명을 파트로 사용
                    result_df['정비자소속'] = result_df['정비자']
                    st.info("정비자명을 파트명으로 사용합니다.")
                elif mapping_rate < 50:
                    st.warning("매핑률이 낮습니다. 정비자명을 파트명으로 보완합니다.")
                    # 매핑되지 않은 항목은 정비자명 사용
                    unmapped_mask = result_df['정비자소속'].isna()
                    result_df.loc[unmapped_mask, '정비자소속'] = result_df.loc[unmapped_mask, '정비자']
                else:
                    st.success("매핑이 성공적으로 완료되었습니다!")
            
            else:
                st.error("조직도에 '이름' 또는 '파트' 컬럼이 없습니다!")
                result_df['정비자소속'] = result_df['정비자']
                st.info("정비자명을 파트명으로 사용합니다.")

        # 수리비 데이터인 경우 (출고자 있음)
        elif '출고자' in result_df.columns:
            st.write("**출고자 기준 매핑 시도**")
            
            if '이름' in org_temp.columns and '파트' in org_temp.columns:
                result_df['출고자'] = result_df['출고자'].astype(str).str.strip()
                org_temp['이름'] = org_temp['이름'].astype(str).str.strip()
                
                org_clean = org_temp[['이름', '파트']].dropna()
                
                result_df = pd.merge(
                    result_df,
                    org_clean,
                    left_on='출고자',
                    right_on='이름',
                    how='left'
                )
                
                if '파트' in result_df.columns:
                    result_df = result_df.rename(columns={'파트': '출고자소속'})
                
                if '이름' in result_df.columns and '이름' != '출고자':
                    result_df = result_df.drop('이름', axis=1)
                
                mapped_count = result_df['출고자소속'].notna().sum()
                st.write(f"출고자 매핑 결과: {mapped_count}건")

        logger.info("직원 데이터 매핑 완료")
        return result_df

    except Exception as e:
        logger.error(f"직원 데이터 매핑 중 오류 발생: {str(e)}")
        st.error(f"직원 데이터 매핑 중 오류 발생: {str(e)}")
        st.exception(e)
        
        # 실패 시 기본 처리
        if '정비자' in df.columns:
            df['정비자소속'] = df['정비자']
        elif '출고자' in df.columns:
            df['출고자소속'] = df['출고자']
        
        return df

# 두 데이터프레임 병합 함수 - 브랜드 매핑 문제 해결
@st.cache_data
def merge_dataframes(df1, df2):
    """정비일지 데이터와 자산조회 데이터 병합"""
    if df1 is None or df2 is None:
        return df1

    try:
        logger.info(f"데이터프레임 병합 시작: df1={len(df1)}행, df2={len(df2)}행")
        
        # 데이터 복사
        df1_copy = df1.copy()
        df2_copy = df2.copy()
        
        # 컬럼명 매핑 적용
        for old_col, new_col in DataProcessingConfig.COLUMN_MAPPINGS.items():
            if old_col in df1_copy.columns:
                df1_copy.rename(columns={old_col: new_col}, inplace=True)
            if old_col in df2_copy.columns:
                df2_copy.rename(columns={old_col: new_col}, inplace=True)
        
        # 데이터 타입 통일 - 관리번호를 문자열로 변환
        df1_copy['관리번호'] = df1_copy['관리번호'].astype(str)
        df2_copy['관리번호'] = df2_copy['관리번호'].astype(str)
        
        # 중복 관리번호 확인 및 제거 (자산 데이터에서)
        if df2_copy['관리번호'].duplicated().any():
            # 중복 제거 (첫 번째 값 유지)
            df2_copy = df2_copy.drop_duplicates(subset='관리번호')
            
        # 자산 데이터에서 필요한 컬럼만 선택
        available_cols = ['관리번호']
        optional_cols = ['브랜드', '모델명', '제조년도', '취득가', '자재내역']
        for col in optional_cols:
            if col in df2_copy.columns:
                available_cols.append(col)
        
        df2_subset = df2_copy[available_cols]
        
        # 관리번호 컬럼을 기준으로 왼쪽 조인으로 병합 (AS 데이터는 모두 유지)
        merged_df = pd.merge(df1_copy, df2_subset, on='관리번호', how='left')
            
        # 브랜드 컬럼 처리
        if '브랜드_x' in merged_df.columns and '브랜드_y' in merged_df.columns:
            # 두 컬럼이 모두 있는 경우 - 병합 처리
            merged_df['브랜드'] = merged_df['브랜드_x'].fillna(merged_df['브랜드_y'])
            # 원본 컬럼 삭제
            merged_df = merged_df.drop(['브랜드_x', '브랜드_y'], axis=1)
        elif '브랜드_y' in merged_df.columns:
            # 자산 데이터의 브랜드만 있는 경우
            merged_df['브랜드'] = merged_df['브랜드_y']
            merged_df = merged_df.drop(['브랜드_y'], axis=1)
        elif '브랜드_x' in merged_df.columns:
            # AS 데이터의 브랜드만 있는 경우
            merged_df['브랜드'] = merged_df['브랜드_x']
            merged_df = merged_df.drop(['브랜드_x'], axis=1)
        
        # 브랜드에 여전히 NaN이 있으면 '기타'로 채움
        if '브랜드' in merged_df.columns:
            merged_df['브랜드'] = merged_df['브랜드'].fillna('기타')
        else:
            # 브랜드 컬럼이 없는 경우 새로 생성
            merged_df['브랜드'] = '기타'
        
        # 모델명 처리 (브랜드와 동일한 방식)
        if '모델명_x' in merged_df.columns and '모델명_y' in merged_df.columns:
            merged_df['모델명'] = merged_df['모델명_x'].fillna(merged_df['모델명_y'])
            merged_df = merged_df.drop(['모델명_x', '모델명_y'], axis=1)
        elif '모델명_y' in merged_df.columns:
            merged_df['모델명'] = merged_df['모델명_y']
            merged_df = merged_df.drop(['모델명_y'], axis=1)
        elif '모델명_x' in merged_df.columns:
            merged_df['모델명'] = merged_df['모델명_x']
            merged_df = merged_df.drop(['모델명_x'], axis=1)
            
        # 자재내역 컬럼 분할 (있는 경우만)
        if '자재내역' in merged_df.columns and merged_df['자재내역'].notna().any():
            # 자재내역에서 추가 정보 추출 (공백으로 나누기)
            split_result = merged_df['자재내역'].str.split(' ', n=3, expand=True)
            # 결과가 있을 때만 컬럼 추가
            if len(split_result.columns) >= 4:
                merged_df[['연료', '운전방식', '적재용량', '마스트']] = split_result
            else:
                # 결과 컬럼 수가 부족한 경우 빈 컬럼 생성
                for i, col_name in enumerate(['연료', '운전방식', '적재용량', '마스트']):
                    if i < len(split_result.columns):
                        merged_df[col_name] = split_result[i]
                    else:
                        merged_df[col_name] = None

        # 브랜드와 모델명으로 브랜드_모델 컬럼 생성
        if '브랜드' in merged_df.columns and '모델명' in merged_df.columns:
            mask = merged_df['브랜드'].notna() & merged_df['모델명'].notna()
            merged_df.loc[mask, '브랜드_모델'] = merged_df.loc[mask, '브랜드'].astype(str) + '_' + merged_df.loc[mask, '모델명'].astype(str)
        
        # 고장유형 조합 (이제 브랜드가 적절히 설정되었으므로 수행)
        if all(col in merged_df.columns for col in ['작업유형', '정비대상', '정비작업']):
            # nan 값을 가진 행 필터링하여 처리
            mask = merged_df['작업유형'].notna() & merged_df['정비대상'].notna() & merged_df['정비작업'].notna()
            merged_df.loc[mask, '고장유형'] = (merged_df.loc[mask, '작업유형'].astype(str) + '_' + 
                                            merged_df.loc[mask, '정비대상'].astype(str) + '_' + 
                                            merged_df.loc[mask, '정비작업'].astype(str))

        logger.info(f"데이터프레임 병합 완료: 결과={len(merged_df)}행")
        return merged_df
        
    except Exception as e:
        logger.error(f"데이터 병합 중 오류 발생: {e}")
        st.error(f"데이터 병합 중 오류 발생: {e}")
        st.error(traceback.format_exc())
        return df1

@st.cache_data
def merge_repair_costs(maintenance_df, parts_df, 
                      day_window_main=DataProcessingConfig.DATE_WINDOW_MAIN, 
                      day_window_ext=DataProcessingConfig.DATE_WINDOW_EXTENDED):
    """고도화된 수리비 매칭 함수"""
    
    if maintenance_df is None or parts_df is None:
        return maintenance_df

    logger.info(f"수리비 매칭 시작: 정비={len(maintenance_df)}건, 부품={len(parts_df)}건")
    
    dfm = maintenance_df.copy()
    dfp = parts_df.copy()

    # ---------- 1) 컬럼/타입 정리 ----------
    # 정비(AS)
    for c in ['관리번호','정비일자','최근정비일자','최근출고일자','정비자','모델명','증상','정비번호']:
        if c not in dfm.columns: dfm[c] = np.nan
    dfm['관리번호'] = dfm['관리번호'].astype(str).str.strip()
    for dc in ['정비일자','최근정비일자','최근출고일자']:
        dfm[dc] = pd.to_datetime(dfm[dc], errors='coerce')
    dfm['정비자'] = dfm['정비자'].fillna('').astype(str).str.strip()
    dfm['모델명'] = dfm['모델명'].fillna('').astype(str).str.strip()
    dfm['증상']   = dfm['증상'].fillna('').astype(str)

    # 출고(부품)
    for c in ['관리번호','출고일자','기사명','출고자','출고금액','자재명','출고번호','순번','모델명','이동유형','이동유형명']:
        if c not in dfp.columns: dfp[c] = np.nan
    dfp['관리번호'] = dfp['관리번호'].fillna('').astype(str).str.strip()
    dfp['출고일자'] = pd.to_datetime(dfp['출고일자'], errors='coerce')
    dfp['기사명']   = dfp['기사명'].fillna('').astype(str).str.strip()
    dfp['출고자']   = dfp['출고자'].fillna('').astype(str).str.strip() if '출고자' in dfp.columns else ''
    dfp['출고금액'] = pd.to_numeric(dfp['출고금액'], errors='coerce').fillna(0)
    dfp['자재명']   = dfp['자재명'].fillna('').astype(str).str.strip()
    dfp['출고번호'] = dfp['출고번호'].fillna('').astype(str).str.strip()
    dfp['순번']     = dfp['순번'].fillna('').astype(str).str.strip()
    dfp['모델명']   = dfp['모델명'].fillna('').astype(str).str.strip()
    dfp['이동유형'] = dfp['이동유형'].fillna('').astype(str).str.strip()
    dfp['이동유형명']= dfp['이동유형명'].fillna('').astype(str).str.strip()

    # 기준일자(정비일자 > 최근정비일자 > 최근출고일자)
    dfm['기준일자'] = dfm['정비일자']
    dfm.loc[dfm['기준일자'].isna(), '기준일자'] = dfm['최근정비일자']
    dfm.loc[dfm['기준일자'].isna(), '기준일자'] = dfm['최근출고일자']

    dfm = dfm[~dfm['기준일자'].isna()].copy()
    dfp = dfp[~dfp['출고일자'].isna()].copy()

    dfm['AS_ROW_ID']   = np.arange(len(dfm))
    dfp['PART_ROW_ID'] = np.arange(len(dfp))

    # ---------- 2) 후보 생성 ----------
    # 2-1 관리번호 정합 + 날짜 ±7
    cand1 = dfm[['AS_ROW_ID','관리번호','기준일자','정비자','모델명','증상']].merge(
        dfp[['PART_ROW_ID','관리번호','출고일자','기사명','출고자','출고금액','자재명','출고번호','순번','모델명','이동유형','이동유형명']],
        on='관리번호', how='inner'
    )
    cand1['일자차이'] = (cand1['출고일자'] - cand1['기준일자']).dt.days
    cand1 = cand1[cand1['일자차이'].abs() <= day_window_main]

    # 2-2 관리번호가 비었거나 실패한 건 대비: 모델명(정확/부분) + 날짜 ±14 (느슨)
    left  = dfm[['AS_ROW_ID','기준일자','정비자','모델명','증상']].copy()
    right = dfp[['PART_ROW_ID','출고일자','기사명','출고자','출고금액','자재명','출고번호','순번','모델명']].copy()

    left['키'] = 0; right['키'] = 0
    tmp = left.merge(right, on='키', how='outer')
    tmp['일자차이'] = (tmp['출고일자'] - tmp['기준일자']).dt.days
    tmp = tmp[tmp['일자차이'].abs() <= day_window_ext]

    def sim(a,b):
        a=(a or '').lower().strip(); b=(b or '').lower().strip()
        return SequenceMatcher(None, a, b).ratio()

    tmp['모델_sim'] = tmp.apply(lambda r: sim(r.get('모델명_x',''), r.get('모델명_y','')), axis=1)
    cand2 = tmp[tmp['모델_sim'] >= DataProcessingConfig.SIMILARITY_THRESHOLD].copy()
    cand2 = cand2.drop(columns=['키'])

    # 통합 후보(중복 제거)
    cand = pd.concat([
        cand1.rename(columns={'모델명_x':'모델명_AS','모델명_y':'모델명_PART'}),
        cand2.rename(columns={
            '모델명_x':'모델명_AS','모델명_y':'모델명_PART'
        })
    ], ignore_index=True, sort=False).drop_duplicates(subset=['AS_ROW_ID','PART_ROW_ID'])

    if cand.empty:
        out = dfm.copy()
        out['수리비']=0; out['사용부품']=''; out['매칭신뢰도']=0.0; out['매칭근거']=''
        st.warning("생성된 후보가 없습니다.")
        return out

    # ---------- 3) 스코어링 ----------
    # 사람 매칭(정비자 = 기사명 or 출고자)
    cand['정비자_기사명_일치'] = (cand['정비자'].fillna('') == cand['기사명'].fillna('')).astype(int)
    cand['정비자_출고자_일치'] = (cand['정비자'].fillna('') == cand.get('출고자','').fillna('')).astype(int)

    # 모델명 일치도
    if '모델_sim' not in cand.columns:
        cand['모델_sim'] = cand.apply(lambda r: sim(r.get('모델명_AS',''), r.get('모델명_PART','')), axis=1)

    # 키워드 룰(증상↔자재명) - 설정에서 가져오기
    kw_rules = DataProcessingConfig.KEYWORD_RULES
    
    def kw_score(symptom, partname):
        s=(symptom or '').lower(); p=(partname or '').lower()
        score=0
        for left,right in kw_rules:
            if any(k in s for k in left) and any(k in p for k in right):
                score += 1
        return score
    cand['키워드점수'] = cand.apply(lambda r: kw_score(r.get('증상',''), r.get('자재명','')), axis=1)

    # 관리번호 일치 플래그( cand1 은 내재적으로 일치, cand2는 비일치일 수 있음 )
    cand['관리번호일치'] = (cand.get('관리번호', '').astype(str).str.len() > 0).astype(int)

    # 총점(자유도 줄이고 날짜 근접 가산/패널티)
    # 가중치: 관리번호 +5, 사람 +3(둘 중 하나라도 맞으면 +3, 둘 다면 +4.5), 모델 유사도*2, 키워드 +1, 날짜 패널티(abs/2)
    cand['사람점수'] = np.maximum(cand['정비자_기사명_일치'], cand['정비자_출고자_일치'])*3 + \
                     (cand['정비자_기사명_일치'] & cand['정비자_출고자_일치']) * 1.5
    cand['점수'] = (
        cand['관리번호일치']*5 +
        cand['사람점수'] +
        cand['모델_sim']*2 +
        cand['키워드점수']*1 -
        (cand['일자차이'].abs()/2.0)
    )

    # ---------- 4) 중복 방지 + 출고 묶음 합산 ----------
    cand['출고키'] = cand['출고번호'].astype(str) + '#' + cand['순번'].astype(str)
    cand = cand.sort_values(['점수','일자차이'], ascending=[False, True])

    assigned_part = set()
    chosen = []
    for as_id, grp in cand.groupby('AS_ROW_ID', sort=False):
        for _, r in grp.iterrows():
            k = r['출고키']
            if k not in assigned_part:
                chosen.append(r)
                assigned_part.add(k)

    matched = pd.DataFrame(chosen)
    if matched.empty:
        out = dfm.copy()
        out['수리비']=0; out['사용부품']=''; out['매칭신뢰도']=0.0; out['매칭근거']=''
        st.warning("매칭 결과가 없습니다.")
        return out

    # 같은 AS_ROW_ID + 같은 출고번호 묶어서(여러 자재) 합계
    agg = matched.groupby(['AS_ROW_ID','출고번호']).agg(
        합계=('출고금액','sum'),
        자재목록=('자재명', lambda x: ', '.join(sorted(set([t for t in x if isinstance(t,str) and t])))),
        평균점수=('점수','mean'),
        최고점수=('점수','max')
    ).reset_index()

    final = agg.groupby('AS_ROW_ID').agg(
        수리비=('합계','sum'),
        사용부품=('자재목록', lambda x: ', '.join(sorted(set(', '.join(x).split(', '))))),
        매칭신뢰도=('평균점수','mean'),
        최고점수=('최고점수','max'),
        출고건수=('합계','count')
    ).reset_index()

    # 근거 텍스트
    reason = matched.sort_values('점수', ascending=False).groupby('AS_ROW_ID').head(1).copy()
    reason['매칭근거'] = reason.apply(
        lambda r: f"관리번호:{'O' if r['관리번호일치'] else 'X'}, 사람매칭:{'O' if r['사람점수']>0 else 'X'}, "
                  f"모델유사:{r['모델_sim']:.2f}, 키워드:{int(r['키워드점수'])}, 일자차이:{int(abs(r['일자차이']))}일",
        axis=1
    )
    reason = reason[['AS_ROW_ID','매칭근거']]

    out = dfm.merge(final, on='AS_ROW_ID', how='left').merge(reason, on='AS_ROW_ID', how='left')
    out['수리비'] = out['수리비'].fillna(0).astype(float)
    out['사용부품'] = out['사용부품'].fillna('')
    out['매칭신뢰도'] = out['매칭신뢰도'].fillna(0.0)

    matched_cnt = (out['수리비'] > 0).sum()
    logger.info(f"수리비 매칭 완료: {matched_cnt}/{len(out)}건 ({matched_cnt/len(out)*100:.1f}%)")
    st.info(f"총 {len(out)}건 중 {matched_cnt}건 수리비 매칭 ({matched_cnt/len(out)*100:.1f}%)")
    st.caption("신뢰도=출고건 평균 점수. 관리번호/사람/모델/키워드/날짜에 의해 결정.")
    
    return out

# 재정비 간격 계산을 위한 날짜 처리
@st.cache_data
def process_date_columns(df):
    """날짜 컬럼 처리 및 재정비 간격 계산"""
    df_copy = df.copy()
    
    try:
        date_columns = ['정비일자', '최근정비일자']
        for col in date_columns:
            if col in df_copy.columns:
                try:
                    # 기본 날짜 변환 시도
                    df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
                except Exception:
                    try:
                        # Excel 날짜 숫자 처리 시도
                        df_copy[col] = pd.to_datetime(df_copy[col], origin='1899-12-30', unit='D', errors='coerce')
                    except Exception:
                        pass

        # 재정비 간격 계산 (정비일자 - 최근정비일자)
        if '최근정비일자' in df_copy.columns and '정비일자' in df_copy.columns:
            df_copy['재정비간격'] = (df_copy['정비일자'] - df_copy['최근정비일자']).dt.days
            # 30일 내 재정비 여부
            df_copy['30일내재정비'] = (df_copy['재정비간격'] <= 30) & (df_copy['재정비간격'] > 0)

    except Exception as e:
        logger.error(f"날짜 처리 중 오류 발생: {e}")
        st.error(f"날짜 처리 중 오류 발생: {e}")
        st.error(traceback.format_exc())
    
    return df_copy

# 수리비 데이터 전처리
@st.cache_data
def preprocess_repair_costs(df):
    """수리비 데이터 전처리"""
    df_copy = df.copy()
    
    try:
        # 날짜 변환
        if '출고일자' in df_copy.columns:
            df_copy['출고일자'] = pd.to_datetime(df_copy['출고일자'], errors='coerce')

        # 금액 컬럼 숫자로 변환
        for col in df_copy.columns:
            if '단가' in col or '금액' in col:
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                
    except Exception as e:
        st.warning(f"수리비 데이터 전처리 중 오류가 발생했습니다: {e}")
    
    return df_copy

def preprocess_maintenance_data(df):
    """정비일지 데이터 전처리 함수"""
    try:
        logger.info("정비일지 데이터 전처리 시작")
        
        # 컬럼명 정리 (줄바꿈, 공백 제거)
        df.columns = [str(col).strip().replace('\n', '') for col in df.columns]
        
        # 정비구분 컬럼 전처리
        if '정비구분' in df.columns:
            df['정비구분'] = df['정비구분'].astype(str).apply(lambda x: x.strip().replace('\n', '') if not pd.isna(x) else x)
            # 'nan' 문자열을 실제 NaN으로 변환
            df.loc[df['정비구분'] == 'nan', '정비구분'] = np.nan
            
            # 내부/외부 값 표준화 (대소문자 구분 없이)
            def standardize_maintenance_type(value):
                if pd.isna(value):
                    return value
                value_lower = str(value).lower()
                if '내부' in value_lower:
                    return '내부'
                elif '외부' in value_lower:
                    return '외부'
                return value
            
            df['정비구분'] = df['정비구분'].apply(standardize_maintenance_type)
        
        # 수치형 데이터 처리
        numeric_columns = ['가동시간', '수리시간', '수리비']
        for col in numeric_columns:
            if col in df.columns:
                # 숫자가 아닌 값을 NaN으로 변환
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        logger.info("정비일지 데이터 전처리 완료")
        return df
    
    except Exception as e:
        logger.error(f"정비일지 데이터 전처리 중 오류 발생: {e}")
        st.error(f"정비일지 데이터 전처리 중 오류 발생: {e}")
        return df

def generate_fault_type_column(df):
    """고장유형 컬럼 생성 함수"""
    if all(col in df.columns for col in ['작업유형', '정비대상', '정비작업']):
        mask = df['작업유형'].notna() & df['정비대상'].notna() & df['정비작업'].notna()
        df.loc[mask, '고장유형'] = df.loc[mask, ['작업유형', '정비대상', '정비작업']].astype(str).agg('_'.join, axis=1)
        df['고장유형'] = df['고장유형'].replace('nan_nan_nan', np.nan)
    return df

@st.cache_data
def preprocess_satisfaction_data(df):
    """만족도 조사 데이터 전처리"""
    try:
        logger.info("만족도 데이터 전처리 시작")
        
        df_copy = df.copy()
        
        # 컬럼명 정리
        df_copy.columns = [str(col).strip().replace('\n', '') for col in df_copy.columns]
        
        # 관리번호 문자열 변환
        if '관리번호' in df_copy.columns:
            df_copy['관리번호'] = df_copy['관리번호'].astype(str)
        
        # 사번 문자열 변환
        if '사번' in df_copy.columns:
            df_copy['사번'] = df_copy['사번'].astype(str)
        
        # 답변 점수 숫자로 변환
        if '답변' in df_copy.columns:
            df_copy['만족도점수'] = pd.to_numeric(df_copy['답변'], errors='coerce')
        
        # 날짜 변환
        date_cols = ['접수일시', '기사배정일시', '처리일시', '작성일시']
        for col in date_cols:
            if col in df_copy.columns:
                df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
        
        # 질문 카테고리 매핑
        def categorize_question(question):
            if pd.isna(question):
                return '기타'
            question = str(question).lower()
            if '처리 속도' in question or '속도' in question:
                return '처리속도'
            elif '전문지식' in question or '기술' in question:
                return '기술수준'
            elif '응대' in question or '친절' in question or '서비스' in question:
                return '서비스태도'
            elif '장비 상태' in question or '수리' in question and '상태' in question:
                return '수리품질'
            elif '추천' in question:
                return '추천의향'
            else:
                return '기타'
        
        if '질문' in df_copy.columns:
            df_copy['질문카테고리'] = df_copy['질문'].apply(categorize_question)
        
        logger.info("만족도 데이터 전처리 완료")
        return df_copy
    
    except Exception as e:
        logger.error(f"만족도 데이터 전처리 중 오류 발생: {e}")
        st.error(f"만족도 데이터 전처리 중 오류 발생: {e}")
        return df

@st.cache_data
def merge_satisfaction_with_maintenance(maintenance_df, satisfaction_df):
    """정비일지와 만족도 데이터 병합 - 정비일자, 정비자, 관리번호 기준"""
    if maintenance_df is None or satisfaction_df is None:
        return maintenance_df
    
    try:
        logger.info("만족도 데이터 병합 시작")
        
        df1 = maintenance_df.copy()
        df5 = satisfaction_df.copy()
        
        # 관리번호를 문자열로 통일
        df1['관리번호'] = df1['관리번호'].astype(str)
        df5['관리번호'] = df5['관리번호'].astype(str)
        
        # 정비자/이름을 문자열로 통일
        df1['정비자'] = df1['정비자'].astype(str)
        df5['이름'] = df5['이름'].astype(str)
        
        # 날짜 처리 - 날짜 부분만 추출
        if '정비일자' in df1.columns:
            df1['정비일자_날짜'] = pd.to_datetime(df1['정비일자']).dt.date
        
        if '처리일자' in df5.columns:
            df5['처리일자_날짜'] = pd.to_datetime(df5['처리일자']).dt.date
        else:
            st.warning("만족도 데이터에서 '처리일자' 컬럼을 찾을 수 없습니다.")
            return maintenance_df
        
        # 매핑을 위한 키 생성
        df1['매핑키'] = df1['정비일자_날짜'].astype(str) + '_' + df1['정비자'] + '_' + df1['관리번호']
        df5['매핑키'] = df5['처리일자_날짜'].astype(str) + '_' + df5['이름'] + '_' + df5['관리번호']
        
        # 만족도 데이터 통계 계산
        satisfaction_stats = df5.groupby('매핑키').agg({
            '만족도점수': [
                'mean',      # 평균
                'median',    # 중앙값
                'std',       # 표준편차
                'min',       # 최솟값
                'max',       # 최댓값
                'count',     # 응답 수
                lambda x: x.quantile(0.25),  # 1분위수
                lambda x: x.quantile(0.75),  # 3분위수
                lambda x: (x >= 4).sum() / len(x) * 100,  # 만족률(4점 이상 비율)
                lambda x: (x <= 2).sum() / len(x) * 100,  # 불만족률(2점 이하 비율)
            ]
        }).round(2)
        
        # 컬럼명 정리
        satisfaction_stats.columns = [
            '만족도_평균', '만족도_중앙값', '만족도_표준편차', 
            '만족도_최솟값', '만족도_최댓값', '만족도_응답수',
            '만족도_1분위수', '만족도_3분위수', '만족도_만족률', '만족도_불만족률'
        ]
        
        # 추가 통계 지표 계산
        satisfaction_stats['만족도_범위'] = satisfaction_stats['만족도_최댓값'] - satisfaction_stats['만족도_최솟값']
        satisfaction_stats['만족도_IQR'] = satisfaction_stats['만족도_3분위수'] - satisfaction_stats['만족도_1분위수']
        satisfaction_stats['만족도_변동계수'] = (satisfaction_stats['만족도_표준편차'] / satisfaction_stats['만족도_평균'] * 100).round(2)
        
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
        
        satisfaction_stats['만족도_등급'] = satisfaction_stats['만족도_평균'].apply(classify_satisfaction)
        
        # 카테고리별 만족도도 계산
        if '질문카테고리' in df5.columns:
            category_pivot = df5.pivot_table(
                index='매핑키',
                columns='질문카테고리',
                values='만족도점수',
                aggfunc=['mean', 'count']
            )
            
            # 카테고리별 평균 점수
            if len(category_pivot.columns.levels) > 1 and 'mean' in category_pivot.columns.levels[0]:
                mean_cols = category_pivot['mean']
                mean_cols.columns = [f'만족도_{col}_평균' for col in mean_cols.columns]
                satisfaction_stats = pd.concat([satisfaction_stats, mean_cols], axis=1)
            
            # 카테고리별 응답 수
            if len(category_pivot.columns.levels) > 1 and 'count' in category_pivot.columns.levels[0]:
                count_cols = category_pivot['count']
                count_cols.columns = [f'만족도_{col}_응답수' for col in count_cols.columns]
                satisfaction_stats = pd.concat([satisfaction_stats, count_cols], axis=1)
        
        # 인덱스를 컬럼으로 변환
        satisfaction_stats = satisfaction_stats.reset_index()
        
        # 정비일지와 병합
        merged_df = pd.merge(df1, satisfaction_stats, on='매핑키', how='left')
        
        # 임시 컬럼 제거
        columns_to_drop = ['정비일자_날짜', '매핑키']
        merged_df = merged_df.drop(columns=[col for col in columns_to_drop if col in merged_df.columns])
        
        # 매핑 결과 확인
        matched_count = merged_df['만족도_평균'].notna().sum()
        total_count = len(merged_df)
        
        logger.info(f"만족도 매핑 완료: {matched_count}/{total_count}건")
        st.info(f"만족도 매핑 결과: {matched_count}/{total_count}건 매핑됨")
        
        return merged_df
    
    except Exception as e:
        logger.error(f"만족도 데이터 병합 중 오류 발생: {e}")
        st.error(f"만족도 데이터 병합 중 오류 발생: {e}")
        return maintenance_df


