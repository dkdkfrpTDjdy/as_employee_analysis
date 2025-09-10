# pages/05_만족도_분석.py - 새로 추가된 페이지
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="만족도 분석", layout="wide")
st.title("😊 고객 만족도 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

# 만족도 데이터 확인
if 'satisfaction_data' not in st.session_state or st.session_state.satisfaction_data is None:
    st.warning("⚠️ 만족도 조사 데이터가 없습니다. 메인 페이지에서 만족도 데이터를 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()
satisfaction_df = st.session_state.satisfaction_data.copy()

# 만족도 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_satisfaction_data(satisfaction_df):
    # 만족도 점수 확인
    if '만족도점수' not in satisfaction_df.columns:
        if '답변' in satisfaction_df.columns:
            satisfaction_df['만족도점수'] = pd.to_numeric(satisfaction_df['답변'], errors='coerce')
        else:
            st.error("만족도 점수 데이터를 찾을 수 없습니다.")
            return None
    
    # 날짜 처리
    if '처리일자' in satisfaction_df.columns:
        satisfaction_df['처리일자'] = pd.to_datetime(satisfaction_df['처리일자'], errors='coerce')
        satisfaction_df['년월'] = satisfaction_df['처리일자'].dt.to_period('M')
    
    return satisfaction_df

satisfaction_df = prepare_satisfaction_data(satisfaction_df)

if satisfaction_df is None:
    st.stop()

# 사이드바 설정
st.sidebar.header("📊 분석 설정")

# 기간 필터
if '처리일자' in satisfaction_df.columns and satisfaction_df['처리일자'].notna().any():
    min_date = satisfaction_df['처리일자'].min().date()
    max_date = satisfaction_df['처리일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        satisfaction_df = satisfaction_df[
            (satisfaction_df['처리일자'].dt.date >= start_date) & 
            (satisfaction_df['처리일자'].dt.date <= end_date)
        ]

# 전체 만족도 현황
st.header("📊 전체 만족도 현황")

col1, col2, col3, col4 = st.columns(4)

with col1:
    avg_satisfaction = satisfaction_df['만족도점수'].mean()
    st.metric("평균 만족도", f"{avg_satisfaction:.2f}점")

with col2:
    total_responses = len(satisfaction_df)
    st.metric("총 응답 수", f"{total_responses:,}건")

with col3:
    high_satisfaction = (satisfaction_df['만족도점수'] >= 4).sum()
    satisfaction_rate = (high_satisfaction / total_responses * 100) if total_responses > 0 else 0
    st.metric("만족률 (4점 이상)", f"{satisfaction_rate:.1f}%")

with col4:
    low_satisfaction = (satisfaction_df['만족도점수'] <= 2).sum()
    dissatisfaction_rate = (low_satisfaction / total_responses * 100) if total_responses > 0 else 0
    st.metric("불만족률 (2점 이하)", f"{dissatisfaction_rate:.1f}%")

# 만족도 분포 차트
col1, col2 = st.columns(2)

with col1:
    st.subheader("만족도 점수 분포")
    
    score_distribution = satisfaction_df['만족도점수'].value_counts().sort_index()
    
    fig = px.bar(
        x=score_distribution.index,
        y=score_distribution.values,
        title="만족도 점수별 응답 수",
        color=score_distribution.values,
        color_continuous_scale='RdYlGn'
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("만족도 등급 분포")
    
    def classify_satisfaction(score):
        if pd.isna(score):
            return '미응답'
        elif score >= 4.5:
            return '매우만족'
        elif score >= 4.0:
            return '만족'
        elif score >= 3.0:
            return '보통'
        elif score >= 2.0:
            return '불만족'
        else:
            return '매우불만족'
    
    satisfaction_df['만족도등급'] = satisfaction_df['만족도점수'].apply(classify_satisfaction)
    grade_distribution = satisfaction_df['만족도등급'].value_counts()
    
    fig = px.pie(
        values=grade_distribution.values,
        names=grade_distribution.index,
        title="만족도 등급별 분포"
    )
    st.plotly_chart(fig, use_container_width=True)

# 파트별 만족도 분석
st.header("👥 파트별 만족도 분석")

if '파트' in satisfaction_df.columns or 'part_satisfaction_stats' in st.session_state:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("파트별 평균 만족도")
        
        if '파트' in satisfaction_df.columns:
            part_satisfaction = satisfaction_df.groupby('파트')['만족도점수'].agg([
                'mean', 'count', 'std'
            ]).round(2)
            part_satisfaction.columns = ['평균만족도', '응답수', '표준편차']
            part_satisfaction = part_satisfaction.sort_values('평균만족도', ascending=False)
            
            fig = px.bar(
                x=part_satisfaction['평균만족도'],
                y=part_satisfaction.index,
                orientation='h',
                title="파트별 평균 만족도",
                color=part_satisfaction['평균만족도'],
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("파트 정보가 없습니다.")
    
    with col2:
        st.subheader("파트별 응답 수")
        
        if '파트' in satisfaction_df.columns:
            fig = px.bar(
                x=part_satisfaction['응답수'],
                y=part_satisfaction.index,
                orientation='h',
                title="파트별 응답 수",
                color=part_satisfaction['응답수'],
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("파트 정보가 없습니다.")
    
    # 파트별 상세 테이블
    if '파트' in satisfaction_df.columns:
        st.subheader("파트별 만족도 상세 통계")
        
        # 만족률/불만족률 추가 계산
        part_detailed = satisfaction_df.groupby('파트').apply(
            lambda x: pd.Series({
                '평균만족도': x['만족도점수'].mean(),
                '응답수': len(x),
                '만족률': (x['만족도점수'] >= 4).sum() / len(x) * 100,
                '불만족률': (x['만족도점수'] <= 2).sum() / len(x) * 100,
                '표준편차': x['만족도점수'].std()
            })
        ).round(2)
        
        part_detailed['만족도등급'] = part_detailed['평균만족도'].apply(classify_satisfaction)
        part_detailed = part_detailed.sort_values('평균만족도', ascending=False)
        
        st.dataframe(
            part_detailed.style.format({
                '평균만족도': '{:.2f}점',
                '만족률': '{:.1f}%',
                '불만족률': '{:.1f}%',
                '표준편차': '{:.2f}'
            }),
            use_container_width=True
        )

# 최저 성과자 분석
st.header("🔴 만족도 최저 성과자 분석")

if 'lowest_performers' in st.session_state and st.session_state.lowest_performers is not None:
    lowest_performers = st.session_state.lowest_performers
    detailed_analysis = st.session_state.detailed_analysis
    
    st.write(f"**최근 30일 기준 만족도 최저 5명**")
    
    # 최저 성과자 차트
    fig = px.bar(
        lowest_performers,
        x='이름',
        y='평균만족도',
        title="만족도 최저 성과자 5명",
        color='평균만족도',
        color_continuous_scale='Reds_r'
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # 상세 분석
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
                    
                    if analysis['주요작업유형'] is not None and not analysis['주요작업유형'].empty:
                        st.write("**주요 작업:**")
                        for work, count in analysis['주요작업유형'].head(3).items():
                            work_short = str(work)[:20] + "..." if len(str(work)) > 20 else str(work)
                            st.write(f"• {work_short}: {count}건")
                    
                    if analysis['담당업체'] is not None and not analysis['담당업체'].empty:
                        st.write("**주요 업체:**")
                        for client, count in analysis['담당업체'].head(2).items():
                            client_short = str(client)[:15] + "..." if len(str(client)) > 15 else str(client)
                            st.write(f"• {client_short}: {count}건")
            
            # 개선 방안 제시
            st.write("**💡 개선 방안:**")
            if performer['평균만족도'] < 2.0:
                st.error("🚨 긴급 개선 필요")
                st.write("- 즉시 1:1 면담 및 교육 실시")
                st.write("- 작업 품질 점검 강화")
                st.write("- 멘토링 프로그램 배정")
                st.write("- 고객 응대 매뉴얼 재교육")
            elif performer['평균만족도'] < 3.0:
                st.warning("⚠️ 개선 필요")
                st.write("- 고객 응대 교육 실시")
                st.write("- 작업 프로세스 재점검")
                st.write("- 정기적 피드백 제공")
                st.write("- 우수 사례 벤치마킹")
            else:
                st.info("💡 모니터링 강화")
                st.write("- 지속적인 성과 모니터링")
                st.write("- 동료 우수사례 학습")
                st.write("- 정기적 코칭 실시")
            
            # 최근 정비 이력 (있는 경우)
            if performer['이름'] in detailed_analysis and '최근정비이력' in detailed_analysis[performer['이름']]:
                recent_history = detailed_analysis[performer['이름']]['최근정비이력']
                
                if not recent_history.empty:
                    st.write("**📋 최근 정비 이력 (최근 10건):**")
                    
                    display_columns = ['정비일자', '관리번호', '수리비', '작업내용']
                    available_columns = [col for col in display_columns if col in recent_history.columns]
                    
                    if available_columns:
                        recent_display = recent_history[available_columns].copy()
                        
                        # 날짜 포맷팅
                        if '정비일자' in recent_display.columns:
                            recent_display['정비일자'] = pd.to_datetime(recent_display['정비일자']).dt.strftime('%Y-%m-%d')
                        
                        # 작업내용 줄임
                        if '작업내용' in recent_display.columns:
                            recent_display['작업내용'] = recent_display['작업내용'].apply(
                                lambda x: str(x)[:30] + "..." if len(str(x)) > 30 else str(x)
                            )
                        
                        st.dataframe(recent_display, use_container_width=True)

else:
    st.info("최저 성과자 분석 데이터가 없습니다.")

# 월별 만족도 추이
if '년월' in satisfaction_df.columns:
    st.header("📈 월별 만족도 추이")
    
    monthly_satisfaction = satisfaction_df.groupby('년월').agg({
        '만족도점수': ['mean', 'count']
    }).round(2)
    monthly_satisfaction.columns = ['평균만족도', '응답수']
    monthly_satisfaction = monthly_satisfaction.reset_index()
    monthly_satisfaction['년월_str'] = monthly_satisfaction['년월'].astype(str)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.line(
            monthly_satisfaction,
            x='년월_str',
            y='평균만족도',
            title="월별 평균 만족도 추이",
            markers=True
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            monthly_satisfaction,
            x='년월_str',
            y='응답수',
            title="월별 응답 수",
            color='응답수',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# 질문 카테고리별 분석 (있는 경우)
if '질문카테고리' in satisfaction_df.columns:
    st.header("❓ 질문 카테고리별 만족도")
    
    category_satisfaction = satisfaction_df.groupby('질문카테고리')['만족도점수'].agg([
        'mean', 'count'
    ]).round(2)
    category_satisfaction.columns = ['평균만족도', '응답수']
    category_satisfaction = category_satisfaction.sort_values('평균만족도', ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            x=category_satisfaction['평균만족도'],
            y=category_satisfaction.index,
            orientation='h',
            title="카테고리별 평균 만족도",
            color=category_satisfaction['평균만족도'],
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.dataframe(
            category_satisfaction.style.format({
                '평균만족도': '{:.2f}점'
            }),
            use_container_width=True
        )

# 만족도 개선 액션 플랜
st.header("📋 만족도 개선 액션 플랜")

action_items = []

# 전체 만족도 기준 액션 아이템
if avg_satisfaction < 3.5:
    action_items.append("🚨 **전체 만족도 낮음** → 전사적 서비스 품질 개선 필요")

if dissatisfaction_rate > 20:
    action_items.append(f"⚠️ **불만족률 높음** ({dissatisfaction_rate:.1f}%) → 불만 원인 분석 및 개선")

# 파트별 액션 아이템
if '파트' in satisfaction_df.columns:
    low_satisfaction_parts = satisfaction_df.groupby('파트')['만족도점수'].mean()
    low_parts = low_satisfaction_parts[low_satisfaction_parts < 3.0]
    
    if not low_parts.empty:
        for part, score in low_parts.items():
            action_items.append(f"🔴 **{part} 파트** 만족도 {score:.2f}점 → 집중 관리 필요")

# 최저 성과자 액션 아이템
if 'lowest_performers' in st.session_state and st.session_state.lowest_performers is not None:
    critical_performers = st.session_state.lowest_performers[st.session_state.lowest_performers['평균만족도'] < 2.5]
    
    if not critical_performers.empty:
        action_items.append(f"🚨 **긴급 개선 대상** {len(critical_performers)}명 → 즉시 교육 및 코칭 실시")

if not action_items:
    action_items.append("✅ 전반적으로 양호한 만족도 수준 유지 중")

for item in action_items:
    st.markdown(f"- {item}")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 만족도 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    if '파트' in satisfaction_df.columns:
        part_satisfaction_csv = part_detailed.to_csv(encoding='utf-8-sig')
        st.download_button(
            label="📊 파트별 만족도 통계 (CSV)",
            data=part_satisfaction_csv,
            file_name="파트별_만족도통계.csv",
            mime="text/csv"
        )

with col2:
    satisfaction_csv = satisfaction_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 만족도 상세 데이터 (CSV)",
        data=satisfaction_csv,
        file_name="만족도_상세데이터.csv",
        mime="text/csv"
    )