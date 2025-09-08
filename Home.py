# main.py - 조직도 매핑 디버깅 강화 버전
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
            df4 = pd.read_excel("data/조직도데이터.xlsx", dtype=str, header=None)
            if len(df4.columns) >= 6:
                df4.columns = ['이름', '파트', '직급', '담당', '직책', '사번']
            else:
                df4.columns = ['이름', '파트'] + [f'컬럼{i}' for i in range(2, len(df4.columns))]
            df4 = df4.replace('', np.nan)
        except Exception as e:
            st.sidebar.error(f"조직도 로드 오류: {e}")
            df4 = None
    
    return df2, df4

# 초간단 머지 함수 - 디버깅 강화
@st.cache_data
def simple_merge_all(df1, df2=None, df3=None, df4=None, df5=None):
    """모든 데이터를 df1에 머지 - 디버깅 강화"""
    
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
            cost_col = None
            for col in ['출고금액', '금액', '단가']:
                if col in df3.columns:
                    cost_col = col
                    break
            
            if cost_col:
                df3['관리번호'] = df3['관리번호'].astype(str)
                df3['출고금액'] = pd.to_numeric(df3[cost_col], errors='coerce').fillna(0)
                
                cost_summary = df3.groupby('관리번호')['출고금액'].sum().reset_index()
                cost_summary.columns = ['관리번호', '수리비']
                
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
    
    # 4. 조직도 데이터로 소속 매핑 (df4) - 강화된 디버깅
    if df4 is not None:
        st.write("### 🔍 조직도 매핑 디버깅")
        
        # 조직도 데이터 상태 확인
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**📋 정비일지 정비자 정보:**")
            if '정비자' in result.columns:
                workers = result['정비자'].value_counts().head(10)
                st.write(f"• 총 정비자 수: {len(workers)}명")
                st.write("• 상위 10명:")
                for worker, count in workers.items():
                    st.write(f"  - '{worker}': {count}건")
            else:
                st.error("정비자 컬럼이 없습니다!")
        
        with col2:
            st.write("**👥 조직도 정보:**")
            st.write(f"• 조직도 레코드: {len(df4)}건")
            st.write(f"• 조직도 컬럼: {df4.columns.tolist()}")
            
            if '이름' in df4.columns:
                org_names = df4['이름'].dropna().head(10)
                st.write(f"• 조직도 이름 수: {len(df4['이름'].dropna())}명")
                st.write("• 상위 10명:")
                for name in org_names:
                    st.write(f"  - '{name}'")
            else:
                st.error("조직도에 이름 컬럼이 없습니다!")
        
        try:
            # 매핑 시도
            if '정비자' in result.columns and '이름' in df4.columns and '파트' in df4.columns:
                # 문자열로 변환 및 정리
                result['정비자'] = result['정비자'].astype(str).str.strip()
                df4['이름'] = df4['이름'].astype(str).str.strip()
                
                # 조직도에서 필요한 컬럼만 선택 (NaN 제거)
                org_simple = df4[['이름', '파트']].dropna()
                st.write(f"**매핑 가능한 조직도 레코드: {len(org_simple)}건**")
                
                # 매핑 전 공통 이름 확인
                df1_workers = set(result['정비자'].dropna().unique())
                org_workers = set(org_simple['이름'].unique())
                common_workers = df1_workers & org_workers
                
                st.write(f"**공통 이름: {len(common_workers)}명**")
                if len(common_workers) > 0:
                    st.write("공통 이름들:")
                    for name in list(common_workers)[:5]:
                        st.write(f"  - {name}")
                
                # 이름으로 매핑
                result = pd.merge(result, org_simple, left_on='정비자', right_on='이름', how='left')
                
                # 컬럼명 변경 및 중복 컬럼 제거
                result = result.rename(columns={'파트': '정비자소속'})
                
                if '이름' in result.columns:
                    result = result.drop('이름', axis=1)
                
                mapped_count = result['정비자소속'].notna().sum()
                mapping_rate = (mapped_count / len(result) * 100) if len(result) > 0 else 0
                
                if mapped_count > 0:
                    st.success(f"✅ 조직도 매핑 성공: {mapped_count}건 ({mapping_rate:.1f}%)")
                else:
                    st.error("❌ 조직도 매핑 실패: 0건")
                
                # 매핑 실패한 경우 정비자명을 파트로 사용
                if mapped_count < len(result) * 0.5:  # 50% 미만 매핑 시
                    unmapped_mask = result['정비자소속'].isna()
                    result.loc[unmapped_mask, '정비자소속'] = result.loc[unmapped_mask, '정비자']
                    st.warning("⚠️ 매핑률이 낮아 정비자명을 파트명으로 사용합니다.")
            
            else:
                st.error("매핑에 필요한 컬럼이 없습니다!")
                # 정비자를 파트로 사용
                if '정비자' in result.columns:
                    result['정비자소속'] = result['정비자']
                    st.info("정비자명을 파트명으로 사용합니다.")
                
        except Exception as e:
            st.error(f"조직도 매핑 실패: {e}")
            st.exception(e)
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
            
            if '답변' in df5.columns:
                df5['만족도점수'] = pd.to_numeric(df5['답변'], errors='coerce')
                
                satisfaction_summary = df5.groupby('관리번호')['만족도점수'].agg([
                    'mean', 'count'
                ]).reset_index()
                satisfaction_summary.columns = ['관리번호', '만족도_평균', '만족도_응답수']
                
                result = pd.merge(result, satisfaction_summary, on='관리번호', how='left')
                
                mapped_count = result['만족도_평균'].notna().sum()
                st.info(f"✅ 만족도 매핑 완료: {mapped_count}건")
            
        except Exception as e:
            st.warning(f"만족도 매핑 실패: {e}")
    
    # 6. 지역 정보 추출
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
    
    # 7. 필요한 컬럼만 유지
    keep_columns = [
        '관리번호', '정비일자', '년월', '정비자', '정비자소속',
        '브랜드', '모델명', '수리비', '작업유형', '정비대상', '정비작업',
        '현장명', '지역', '수리시간', '가동시간'
    ]
    
    if '만족도_평균' in result.columns:
        keep_columns.extend(['만족도_평균', '만족도_응답수'])
    
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
else:
    st.sidebar.warning("⚠️ 자산조회 데이터 없음")

if df4 is not None:
    st.sidebar.success("✅ 조직도 데이터 준비됨")
    st.sidebar.write(f"조직도 레코드: {len(df4)}건")
else:
    st.sidebar.error("❌ 조직도 데이터 없음")

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
                st.success("✅ 정비일지 데이터 로드 완료")
                
                # 정비일지 컬럼 확인
                st.write("**📋 정비일지 컬럼:**")
                st.write(df1.columns.tolist())
                
                # 한 번에 모든 머지 수행
                final_data = simple_merge_all(df1, df2, df3, df4, df5)
                
                # 세션에 저장
                st.session_state.df1_with_costs = final_data
                st.session_state.data_loaded = True
                
                st.success("✅ 모든 데이터 처리 완료!")
                
                # 최종 결과 확인
                st.write("**📊 최종 처리 결과:**")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("총 레코드", f"{len(final_data):,}건")
                
                with col2:
                    total_cost = final_data['수리비'].sum()
                    st.metric("총 수리비", f"{total_cost:,.0f}원")
                
                with col3:
                    if '정비자소속' in final_data.columns:
                        part_count = final_data['정비자소속'].nunique()
                        st.metric("파트 수", f"{part_count}개")
                    else:
                        st.metric("파트 수", "0개")
                
                with col4:
                    if '만족도_평균' in final_data.columns:
                        satisfaction_records = final_data['만족도_평균'].notna().sum()
                        st.metric("만족도 조사", f"{satisfaction_records}건")
                    else:
                        st.metric("만족도 조사", "0건")
                
                # 미리보기
                st.subheader("📋 데이터 미리보기")
                st.dataframe(final_data.head(10), use_container_width=True)
                
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

# 하단
st.markdown("---")

# 조직도 매핑 상태 상세 확인
if st.session_state.data_loaded and st.checkbox("🔍 조직도 매핑 상태 상세 확인"):
    final_data = st.session_state.df1_with_costs
    
    st.subheader("조직도 매핑 상세 분석")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**정비자 현황:**")
        if '정비자' in final_data.columns:
            unique_workers = final_data['정비자'].nunique()
            st.write(f"• 고유 정비자: {unique_workers}명")
            
            # 정비자별 건수
            worker_counts = final_data['정비자'].value_counts()
            st.write("• 상위 5명:")
            for worker, count in worker_counts.head(5).items():
                st.write(f"  - {worker}: {count}건")
    
    with col2:
        st.write("**파트 현황:**")
        if '정비자소속' in final_data.columns:
            unique_parts = final_data['정비자소속'].nunique()
            mapped_parts = final_data['정비자소속'].notna().sum()
            st.write(f"• 고유 파트: {unique_parts}개")
            st.write(f"• 매핑된 건수: {mapped_parts}건")
            
            # 파트별 건수
            part_counts = final_data['정비자소속'].value_counts()
            st.write("• 파트별 건수:")
            for part, count in part_counts.head(5).items():
                st.write(f"  - {part}: {count}건")
    
    with col3:
        st.write("**매핑 품질:**")
        if '정비자소속' in final_data.columns:
            total_records = len(final_data)
            mapped_records = final_data['정비자소속'].notna().sum()
            mapping_rate = (mapped_records / total_records * 100)
            
            st.write(f"• 전체 레코드: {total_records}건")
            st.write(f"• 매핑 성공: {mapped_records}건")
            st.write(f"• 매핑률: {mapping_rate:.1f}%")
            
            if mapping_rate < 50:
                st.error("매핑률이 50% 미만입니다!")
            elif mapping_rate < 80:
                st.warning("매핑률이 80% 미만입니다.")
            else:
                st.success("매핑률이 양호합니다.")
