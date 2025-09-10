# Home.py - 완전 개선된 버전
import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
import re
from difflib import get_close_matches
from utils.data_processing import simple_merge_all_enhanced, analyze_satisfaction_performance
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
        engines_to_try = ['openpyxl', 'xlrd', None]
        
        for engine in engines_to_try:
            try:
                if engine:
                    df = pd.read_excel(file, dtype=str, engine=engine)
                else:
                    df = pd.read_excel(file, dtype=str)
                
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
            
            first_row = df4.iloc[0] if len(df4) > 0 else pd.Series()
            
            if any(keyword in str(first_row.iloc[i]).lower() 
                   for i in range(min(len(first_row), 3)) 
                   for keyword in ['이름', '파트', '사번', '소속']):
                
                new_columns = df4.iloc[0].tolist()
                df4 = df4.iloc[1:].reset_index(drop=True)
                df4.columns = new_columns
                st.sidebar.info("조직도: 첫 번째 행을 헤더로 사용")
            
            df4.columns = [str(col).strip().replace('\n', '').replace('\r', '') for col in df4.columns]
            df4 = df4.replace(['', 'nan', 'NaN'], np.nan)
            
            for col in df4.columns:
                if col in ['이름', '파트', '직급', '담당', '직책', '사번']:
                    df4[col] = df4[col].astype(str).str.strip()
                    df4[col] = df4[col].replace('nan', np.nan)
            
            st.sidebar.success(f"✅ 조직도 로드 완료: {len(df4)}건")
            
        except Exception as e:
            st.sidebar.error(f"조직도 로드 오류: {e}")
            df4 = None
    
    return df2, df4

# 만족도 데이터와 조직도 매핑 함수
@st.cache_data
def merge_satisfaction_by_employee_id(satisfaction_df, org_df):
    """만족도 데이터를 사번 기준으로 조직도와 매핑"""
    if satisfaction_df is None or org_df is None:
        return satisfaction_df
    
    try:
        df5 = satisfaction_df.copy()
        org_temp = org_df.copy()
        
        df5['사번'] = df5['사번'].astype(str).str.strip()
        org_temp['사번'] = org_temp['사번'].astype(str).str.strip()
        
        org_mapping = org_temp[['사번', '파트', '이름']].dropna()
        
        df5_with_part = pd.merge(
            df5,
            org_mapping,
            on='사번',
            how='left'
        )
        
        mapped_count = df5_with_part['파트'].notna().sum()
        total_count = len(df5_with_part)
        
        st.info(f"만족도-조직도 매핑: {mapped_count}/{total_count}건 매핑됨")
        
        return df5_with_part
        
    except Exception as e:
        st.error(f"만족도-조직도 매핑 중 오류: {e}")
        return satisfaction_df

def aggregate_satisfaction_by_part(satisfaction_df):
    """파트별 만족도 통계 집계"""
    if satisfaction_df is None or '파트' not in satisfaction_df.columns:
        return None
    
    try:
        part_satisfaction = satisfaction_df.groupby('파트').agg({
            '만족도점수': [
                'mean',      
                'count',     
                lambda x: (x >= 4).sum() / len(x) * 100,  
                lambda x: (x <= 2).sum() / len(x) * 100,  
            ]
        }).round(2)
        
        part_satisfaction.columns = [
            '만족도_평균', '만족도_응답수', '만족도_만족률', '만족도_불만족률'
        ]
        
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
        st.error(f"파트별 만족도 집계 중 오류: {e}")
        return None

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
                
                # 만족도 데이터 전처리 및 조직도 매핑
                if df5 is not None and df4 is not None:
                    if '답변' in df5.columns:
                        df5['만족도점수'] = pd.to_numeric(df5['답변'], errors='coerce')
                    
                    df5_with_part = merge_satisfaction_by_employee_id(df5, df4)
                    part_satisfaction_stats = aggregate_satisfaction_by_part(df5_with_part)
                    
                    # 만족도 성과 분석 추가
                    lowest_performers, detailed_analysis = analyze_satisfaction_performance(df5_with_part, df1)
                    
                    # 세션에 저장
                    st.session_state.satisfaction_data = df5_with_part
                    st.session_state.part_satisfaction_stats = part_satisfaction_stats
                    st.session_state.lowest_performers = lowest_performers
                    st.session_state.detailed_analysis = detailed_analysis
                    
                    st.success("✅ 만족도 데이터 처리 완료!")
                
                # 개선된 머지 함수 사용
                final_data = simple_merge_all_enhanced(df1, df2, df3, df4, df5)
                
                # 세션에 저장
                st.session_state.df1_with_costs = final_data
                st.session_state.data_loaded = True
                
                st.success("✅ 모든 데이터 처리 완료!")
                
                # 최종 결과 확인
                st.write("**📊 최종 처리 결과:**")
                col1, col2, col3, col4, col5 = st.columns(5)
                
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
                    if 'part_satisfaction_stats' in st.session_state and st.session_state.part_satisfaction_stats is not None:
                        satisfaction_parts = len(st.session_state.part_satisfaction_stats)
                        st.metric("만족도 조사 파트", f"{satisfaction_parts}개")
                    else:
                        st.metric("만족도 조사", "0건")
                
                with col5:
                    if '작업내용' in final_data.columns:
                        work_types = final_data['작업내용'].nunique()
                        st.metric("작업내용 유형", f"{work_types}개")
                    else:
                        st.metric("작업내용 유형", "0개")
                
                # 미리보기 - 작업내용 컬럼 포함
                st.subheader("📋 데이터 미리보기")
                preview_columns = ['관리번호', '정비일자', '정비자', '정비자소속', '브랜드', '작업내용', '수리비']
                available_preview_columns = [col for col in preview_columns if col in final_data.columns]
                st.dataframe(final_data[available_preview_columns].head(10), use_container_width=True)
                
        except Exception as e:
            st.error(f"데이터 처리 실패: {e}")
            st.exception(e)

else:
    st.info("👈 정비일지 데이터를 업로드해주세요.")
    
    st.markdown("""
    ## 🎯 분석 메뉴 (개선됨)
    
    - **📊 메인 대시보드**: 월별 트렌드, 파트별/지역별 분석, 작업내용별 분석
    - **👥 파트별 분석**: 파트/개인별 성과 평가, 정비자별 상세 분석  
    - **🏢 업체별 분석**: 디마케팅 위험도 분석
    - **📅 월별 분석**: 종합 리포트 및 다운로드
    - **😊 만족도 분석**: 최저 성과자 분석 및 개선 방안
    """)

# 하단
st.markdown("---")

# 작업내용 컬럼 확인
if st.session_state.data_loaded and st.checkbox("🔍 작업내용 컬럼 확인"):
    final_data = st.session_state.df1_with_costs
    
    if '작업내용' in final_data.columns:
        st.subheader("작업내용 분석")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**작업내용 상위 10개:**")
            work_content_counts = final_data['작업내용'].value_counts().head(10)
            for content, count in work_content_counts.items():
                st.write(f"• {content}: {count}건")
        
        with col2:
            st.write("**작업내용 통계:**")
            st.write(f"• 총 작업내용 유형: {final_data['작업내용'].nunique()}개")
            st.write(f"• 작업내용 있는 건수: {final_data['작업내용'].notna().sum()}건")
            st.write(f"• 작업내용 비율: {final_data['작업내용'].notna().sum()/len(final_data)*100:.1f}%")

# 만족도 최저 성과자 확인
if st.session_state.data_loaded and 'lowest_performers' in st.session_state and st.checkbox("😞 만족도 최저 성과자 확인"):
    if st.session_state.lowest_performers is not None:
        st.subheader("만족도 최저 성과자 분석")
        
        lowest_performers = st.session_state.lowest_performers
        detailed_analysis = st.session_state.detailed_analysis
        
        for idx, (_, performer) in enumerate(lowest_performers.iterrows()):
            with st.expander(f"🔴 {performer['이름']} (평균 만족도: {performer['평균만족도']:.2f}점)"):
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("평균 만족도", f"{performer['평균만족도']:.2f}점")
                    st.metric("최저 만족도", f"{performer['최저만족도']:.2f}점")
                
                with col2:
                    st.metric("응답 수", f"{performer['응답수']}건")
                    st.metric("만족도 편차", f"{performer['만족도편차']:.2f}")
                
                with col3:
                    if performer['이름'] in detailed_analysis:
                        analysis = detailed_analysis[performer['이름']]
                        
                        if analysis['주요작업유형'] is not None:
                            st.write("**주요 작업:**")
                            for work, count in analysis['주요작업유형'].head(3).items():
                                st.write(f"• {work}: {count}건")
                
                # 개선 방안 제시
                st.write("**💡 개선 방안:**")
                if performer['평균만족도'] < 2.0:
                    st.error("🚨 긴급 개선 필요")
                    st.write("- 즉시 1:1 면담 및 교육 실시")
                    st.write("- 작업 품질 점검 강화")
                    st.write("- 멘토링 프로그램 배정")
                elif performer['평균만족도'] < 3.0:
                    st.warning("⚠️ 개선 필요")
                    st.write("- 고객 응대 교육 실시")
                    st.write("- 작업 프로세스 재점검")
                    st.write("- 정기적 피드백 제공")
                else:
                    st.info("💡 모니터링 강화")
                    st.write("- 지속적인 성과 모니터링")
                    st.write("- 동료 우수사례 학습")
    else:
        st.info("만족도 성과 분석 데이터가 없습니다.")

