# pages/03_업체별_디마케팅_분석.py - 완전 개선된 버전
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="업체별 디마케팅 분석", layout="wide")
st.title("🏢 업체별 디마케팅 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# 현장명/업체명 컬럼 확인
client_col = None
if '현장명' in df.columns and df['현장명'].notna().any():
    client_col = '현장명'
elif '업체명' in df.columns and df['업체명'].notna().any():
    client_col = '업체명'
else:
    st.error("현장명 또는 업체명 컬럼이 없습니다.")
    st.stop()

# 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_client_data(df, client_col):
    # 업체명 정리
    df = df[df[client_col].notna()].copy()
    df['업체명'] = df[client_col].astype(str)
    
    # 수리비 처리
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    # 날짜 처리
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
    
    return df

df = prepare_client_data(df, client_col)

if df.empty:
    st.error("처리할 수 있는 데이터가 없습니다.")
    st.stop()

# 사이드바 설정
st.sidebar.header("🎯 분석 설정")

# 기간 필터
if '정비일자' in df.columns and df['정비일자'].notna().any():
    min_date = df['정비일자'].min().date()
    max_date = df['정비일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[(df['정비일자'].dt.date >= start_date) & 
                (df['정비일자'].dt.date <= end_date)]

# 최소 AS 건수 필터
min_cases = st.sidebar.slider("최소 AS 건수", 1, 20, 3)

# 업체별 통계 계산 - 작업내용 포함
client_stats = df.groupby('업체명').agg({
    '관리번호': 'count',
    '수리비': ['sum', 'mean'],
    '정비일자': ['min', 'max'] if '정비일자' in df.columns else lambda x: None
}).round(0)

if '정비일자' in df.columns:
    client_stats.columns = ['AS건수', '총수리비', '평균수리비', '첫수리일', '최근수리일']
else:
    client_stats.columns = ['AS건수', '총수리비', '평균수리비']

client_stats = client_stats.reset_index()
client_stats = client_stats[client_stats['AS건수'] >= min_cases]

# 작업내용 정보 추가
if '작업내용' in df.columns:
    client_work_content = df.groupby('업체명')['작업내용'].apply(
        lambda x: x.value_counts().head(3).index.tolist()
    ).to_dict()
    
    client_stats['주요작업내용'] = client_stats['업체명'].map(
        lambda x: ', '.join([str(work)[:20] + "..." if len(str(work)) > 20 else str(work) 
                           for work in client_work_content.get(x, [])[:2]])
    )

# 지역 정보 추가
if '지역' in df.columns:
    client_region = df.groupby('업체명')['지역'].first().to_dict()
    client_stats['지역'] = client_stats['업체명'].map(client_region)

if client_stats.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 위험도 점수 계산
@st.cache_data(show_spinner=False)
def calculate_risk_scores(client_stats):
    # 전체 평균 계산
    global_avg_cost = client_stats['평균수리비'].mean()
    global_avg_cases = client_stats['AS건수'].mean()
    
    # 정규화된 점수 계산
    client_stats['비용점수'] = client_stats['평균수리비'] / global_avg_cost
    client_stats['빈도점수'] = client_stats['AS건수'] / global_avg_cases
    
    # 종합 위험도 점수 (비용 70%, 빈도 30%)
    client_stats['위험도점수'] = (client_stats['비용점수'] * 0.7) + (client_stats['빈도점수'] * 0.3)
    
    return client_stats

client_stats = calculate_risk_scores(client_stats)

# 위험도 등급 분류
def get_risk_level(score):
    if score >= 2.5:
        return "🔴 HIGH", "매우 위험"
    elif score >= 1.8:
        return "🟠 MID-HIGH", "위험"
    elif score >= 1.3:
        return "🟡 MID", "주의"
    elif score >= 0.8:
        return "🟢 LOW", "양호"
    else:
        return "🔵 VERY LOW", "매우 양호"

client_stats['위험등급'], client_stats['위험설명'] = zip(*client_stats['위험도점수'].apply(get_risk_level))

# 전체 업체 현황
st.header("📊 전체 업체 현황")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 수리비 상위 업체 TOP 10")
    top_cost_clients = client_stats.nlargest(10, '총수리비')
    
    # 업체명 줄임
    top_cost_display = top_cost_clients.copy()
    top_cost_display['업체명_short'] = top_cost_display['업체명'].apply(
        lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
    )
    
    fig = px.bar(
        top_cost_display,
        x='총수리비',
        y='업체명_short',
        orientation='h',
        color='총수리비',
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📈 AS 건수 상위 업체 TOP 10")
    top_case_clients = client_stats.nlargest(10, 'AS건수')
    
    top_case_display = top_case_clients.copy()
    top_case_display['업체명_short'] = top_case_display['업체명'].apply(
        lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
    )
    
    fig2 = px.bar(
        top_case_display,
        x='AS건수',
        y='업체명_short',
        orientation='h',
        color='AS건수',
        color_continuous_scale='Blues'
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 지역별 업체 분석 - 새로 추가
if '지역' in client_stats.columns:
    st.header("🗺️ 지역별 업체 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("지역별 업체 수 및 수리비")
        
        region_analysis = client_stats.groupby('지역').agg({
            '업체명': 'count',
            '총수리비': 'sum',
            '평균수리비': 'mean'
        }).rename(columns={'업체명': '업체수'}).round(0)
        
        region_analysis = region_analysis.sort_values('총수리비', ascending=False)
        
        fig = px.bar(
            x=region_analysis.index,
            y=region_analysis['총수리비'],
            title="지역별 총 수리비",
            color=region_analysis['총수리비'],
            color_continuous_scale='Viridis'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("지역별 위험도 분포")
        
        region_risk = client_stats.groupby(['지역', '위험등급']).size().reset_index(name='업체수')
        
        fig = px.bar(
            region_risk,
            x='지역',
            y='업체수',
            color='위험등급',
            title="지역별 위험등급 분포"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# 작업내용별 업체 분석 - 새로 추가
if '주요작업내용' in client_stats.columns:
    st.header("🔧 작업내용별 업체 분석")
    
    # 주요 작업내용별 수리비 분석
    work_content_analysis = df.groupby(['업체명', '작업내용']).agg({
        '수리비': 'sum',
        '관리번호': 'count'
    }).reset_index()
    
    # 상위 작업내용 추출
    top_work_contents = df['작업내용'].value_counts().head(5).index.tolist()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("주요 작업내용별 수리비")
        
        work_cost_summary = df.groupby('작업내용')['수리비'].sum().nlargest(10)
        
        # 작업내용명 줄임
        work_cost_display = work_cost_summary.copy()
        work_cost_display.index = [name[:25] + "..." if len(str(name)) > 25 else str(name) for name in work_cost_display.index]
        
        fig = px.bar(
            x=work_cost_display.values,
            y=work_cost_display.index,
            orientation='h',
            title="작업내용별 총 수리비 (상위 10개)",
            color=work_cost_display.values,
            color_continuous_scale='Oranges'
        )
        fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("고비용 작업내용 업체 분포")
        
        if top_work_contents:
            selected_work = st.selectbox("작업내용 선택", top_work_contents)
            
            work_specific_data = df[df['작업내용'] == selected_work]
            work_client_analysis = work_specific_data.groupby('업체명')['수리비'].sum().nlargest(10)
            
            # 업체명 줄임
            work_client_display = work_client_analysis.copy()
            work_client_display.index = [name[:20] + "..." if len(str(name)) > 20 else str(name) for name in work_client_display.index]
            
            fig = px.bar(
                x=work_client_display.values,
                y=work_client_display.index,
                orientation='h',
                title=f"'{selected_work[:30]}...' 작업 상위 업체",
                color=work_client_display.values,
                color_continuous_scale='Purples'
            )
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

# 위험도 분석
st.header("🚨 디마케팅 위험도 분석")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 업체별 위험도 매트릭스")
    
    client_display = client_stats.copy()
    client_display['업체명_short'] = client_display['업체명'].apply(
        lambda x: x[:15] + "..." if len(str(x)) > 15 else str(x)
    )
    
    fig = px.scatter(
        client_display,
        x='AS건수',
        y='총수리비',
        color='위험도점수',
        size='평균수리비',
        hover_name='업체명',
        hover_data=['위험등급', '지역'] if '지역' in client_display.columns else ['위험등급'],
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 위험등급 분포")
    
    risk_counts = client_stats['위험등급'].value_counts()
    
    fig3 = px.pie(
        values=risk_counts.values,
        names=risk_counts.index,
        title="위험등급별 업체 수"
    )
    st.plotly_chart(fig3, use_container_width=True)

# 고위험 업체 상세 분석
st.header("🎯 디마케팅 검토 대상 업체")

risk_threshold = st.slider("위험도 점수 기준", 0.5, 5.0, 1.5, 0.1)
risky_clients = client_stats[client_stats['위험도점수'] >= risk_threshold].sort_values('위험도점수', ascending=False).head(10)

if len(risky_clients) == 0:
    st.info("선택한 기준에 해당하는 위험 업체가 없습니다.")
else:
    st.write(f"**위험도 점수 {risk_threshold} 이상 업체: {len(risky_clients)}개**")
    
    for idx, (_, client) in enumerate(risky_clients.iterrows()):
        risk_icon, risk_desc = get_risk_level(client['위험도점수'])
        
        client_name_display = str(client['업체명'])[:30] + "..." if len(str(client['업체명'])) > 30 else str(client['업체명'])
        
        with st.expander(f"{risk_icon} {client_name_display} (위험도: {client['위험도점수']:.2f})"):
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("총 수리비", f"{client['총수리비']:,.0f}원")
                st.metric("AS 건수", f"{client['AS건수']}건")
            
            with col2:
                st.metric("건당 평균 수리비", f"{client['평균수리비']:,.0f}원")
                st.metric("위험도 점수", f"{client['위험도점수']:.2f}")
            
            with col3:
                if '최근수리일' in client and pd.notna(client['최근수리일']):
                    st.metric("최근 수리일", client['최근수리일'].strftime('%Y-%m-%d'))
                st.metric("위험 등급", client['위험설명'])
                if '지역' in client and pd.notna(client['지역']):
                    st.metric("지역", client['지역'])
            
            # 상세 분석
            client_detail = df[df['업체명'] == client['업체명']]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**🔧 주요 수리 유형**")
                if '작업내용' in client_detail.columns:
                    work_contents = client_detail['작업내용'].value_counts().head(3)
                    for work, count in work_contents.items():
                        work_short = str(work)[:25] + "..." if len(str(work)) > 25 else str(work)
                        st.write(f"• {work_short}: {count}건")
                elif '작업유형' in client_detail.columns:
                    work_types = client_detail['작업유형'].value_counts().head(3)
                    for work, count in work_types.items():
                        st.write(f"• {work}: {count}건")
            
            with col2:
                st.write("**🚛 주요 장비 브랜드**")
                if '브랜드' in client_detail.columns:
                    brands = client_detail['브랜드'].value_counts().head(3)
                    for brand, count in brands.items():
                        st.write(f"• {brand}: {count}건")
            
            with col3:
                st.write("**👥 주요 담당 파트**")
                if '정비자소속' in client_detail.columns:
                    parts = client_detail['정비자소속'].value_counts().head(3)
                    for part, count in parts.items():
                        st.write(f"• {part}: {count}건")
            
            # 월별 수리비 추이 (해당 업체)
            if '정비일자' in client_detail.columns and '년월' in client_detail.columns:
                st.write("**📈 월별 수리비 추이**")
                
                monthly_trend = client_detail.groupby('년월')['수리비'].sum().tail(12)
                monthly_trend_df = monthly_trend.reset_index()
                monthly_trend_df['년월_str'] = monthly_trend_df['년월'].astype(str)
                
                if not monthly_trend_df.empty:
                    fig = px.line(
                        monthly_trend_df,
                        x='년월_str',
                        y='수리비',
                        title=f"{client_name_display} 월별 수리비 추이 (최근 12개월)"
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
            
            # 권고사항
            st.write("**💡 디마케팅 권고사항**")
            
            if client['위험도점수'] >= 3.0:
                st.error("🚨 **즉시 계약 검토 필요** - 매우 높은 위험도")
                st.write("- 계약 해지 또는 대폭적인 조건 변경 검토")
                st.write("- 수리비 상한선 설정 또는 유상 전환")
                st.write("- 예방정비 교육 강화로 고장 빈도 감소")
            elif client['위험도점수'] >= 2.0:
                st.warning("⚠️ **계약 조건 재협상 검토** - 높은 위험도")
                st.write("- 월 수리비 한도 설정")
                st.write("- 예방정비 교육으로 고장 빈도 감소")
                st.write("- 정기적인 장비 점검 실시")
            elif client['위험도점수'] >= 1.5:
                st.info("💡 **모니터링 강화** - 중간 위험도")
                st.write("- 정기적인 수리비 모니터링")
                st.write("- 고객 교육을 통한 예방정비 강화")
                st.write("- 분기별 수리비 리뷰")
            else:
                st.success("✅ 현재 특별한 조치 불필요")

# 위험도별 상세 통계
st.header("📊 위험도별 상세 통계")

col1, col2 = st.columns(2)

with col1:
    st.subheader("위험등급별 업체 통계")
    risk_summary = client_stats.groupby('위험등급').agg({
        '업체명': 'count',
        '총수리비': 'sum',
        '평균수리비': 'mean',
        'AS건수': 'sum'
    }).round(0)
    risk_summary.columns = ['업체수', '총수리비합계', '평균건당수리비', '총AS건수']
    
    st.dataframe(
        risk_summary.style.format({
            '총수리비합계': '{:,.0f}원',
            '평균건당수리비': '{:,.0f}원',
            '총AS건수': '{:,}건'
        }),
        use_container_width=True
    )

with col2:
    st.subheader("수리비 분포")
    
    # 수리비 구간별 분포
    cost_bins = [0, 500000, 1000000, 2000000, 5000000, float('inf')]
    cost_labels = ['50만원 이하', '50-100만원', '100-200만원', '200-500만원', '500만원+']
    
    client_stats['수리비구간'] = pd.cut(client_stats['총수리비'], bins=cost_bins, labels=cost_labels)
    cost_distribution = client_stats['수리비구간'].value_counts()
    
    fig = px.bar(
        x=cost_distribution.index,
        y=cost_distribution.values,
        title="총 수리비 구간별 업체 수",
        color=cost_distribution.values,
        color_continuous_scale='Reds'
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

# 요약 통계
st.header("📊 전체 요약")

col1, col2, col3, col4 = st.columns(4)

with col1:
    high_risk_count = len(client_stats[client_stats['위험도점수'] >= 2.0])
    st.metric("고위험 업체", f"{high_risk_count}개")

with col2:
    total_clients = len(client_stats)
    st.metric("전체 분석 업체", f"{total_clients}개")

with col3:
    avg_risk_score = client_stats['위험도점수'].mean()
    st.metric("평균 위험도", f"{avg_risk_score:.2f}")

with col4:
    high_risk_ratio = (high_risk_count / total_clients * 100) if total_clients > 0 else 0
    st.metric("고위험 업체 비율", f"{high_risk_ratio:.1f}%")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    csv_data = client_stats.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📊 위험도 분석 결과 다운로드 (CSV)",
        data=csv_data,
        file_name="업체별_위험도분석.csv",
        mime="text/csv"
    )

with col2:
    # 상세 데이터 (업체별)
    download_columns = ['업체명', '관리번호', '정비일자', '수리비', '작업유형', '브랜드', '작업내용']
    if '지역' in df.columns:
        download_columns.append('지역')
    
    available_columns = [col for col in download_columns if col in df.columns]
    detailed_data = df[available_columns].copy()
    detailed_csv = detailed_data.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📄 업체별 상세 데이터 다운로드 (CSV)",
        data=detailed_csv,
        file_name="업체별_상세데이터.csv",
        mime="text/csv"
    )
