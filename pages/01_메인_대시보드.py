import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="경영 대시보드", layout="wide")
st.title("📊 경영 대시보드")

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

# 다중 시트 엑셀 다운로드 함수
def to_excel_multi_sheet(data_dict, filename):
    """여러 DataFrame을 다중 시트 엑셀로 변환"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in data_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output.getvalue()

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# df3 원본 데이터 확인
df3_with_org = st.session_state.get('df3_with_org', None)

# 빠른 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_dashboard_data(df):
    # 날짜 처리
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df = df.dropna(subset=['정비일자'])
        df['년월'] = df['정비일자'].dt.to_period('M')
        df['년'] = df['정비일자'].dt.year
        df['월'] = df['정비일자'].dt.month
    
    # 수리비 처리
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    return df

df = prepare_dashboard_data(df)

if df.empty:
    st.error("처리 가능한 데이터가 없습니다.")
    st.stop()

# 사이드바 설정 (간소화)
st.sidebar.header("📊 분석 설정")

# 기간 선택
available_months = sorted(df['년월'].dropna().unique(), reverse=True)
if not available_months:
    st.error("분석 가능한 데이터가 없습니다.")
    st.stop()

selected_month = st.sidebar.selectbox(
    "분석 기준 월", 
    available_months,
    format_func=lambda x: str(x)
)

# 비교 월 설정
compare_months = [m for m in available_months if m < selected_month]
compare_month = compare_months[0] if compare_months else None

# 현재 월과 비교 월 데이터
current_data = df[df['년월'] == selected_month]
prev_data = df[df['년월'] == compare_month] if compare_month else pd.DataFrame()

# 핵심 지표 계산
current_cases = len(current_data)
current_cost = current_data['수리비'].sum()
current_avg = current_cost / current_cases if current_cases > 0 else 0

prev_cases = len(prev_data) if not prev_data.empty else 0
prev_cost = prev_data['수리비'].sum() if not prev_data.empty else 0
prev_avg = prev_cost / prev_cases if prev_cases > 0 else 0

# 증감률 계산
case_change = ((current_cases - prev_cases) / prev_cases * 100) if prev_cases > 0 else 0
cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
avg_change = ((current_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0

# 상단 KPI
st.header(f"🎯 {selected_month} 핵심 지표")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if compare_month:
        st.metric("AS 건수", f"{current_cases:,}건", f"{case_change:+.1f}%")
    else:
        st.metric("AS 건수", f"{current_cases:,}건")

with col2:
    if compare_month:
        st.metric("총 수리비", f"{current_cost:,.0f}원", f"{cost_change:+.1f}%")
    else:
        st.metric("총 수리비", f"{current_cost:,.0f}원")

with col3:
    if compare_month:
        st.metric("건당 평균", f"{current_avg:,.0f}원", f"{avg_change:+.1f}%")
    else:
        st.metric("건당 평균", f"{current_avg:,.0f}원")

with col4:
    unique_equipment = current_data['관리번호'].nunique()
    st.metric("수리 장비", f"{unique_equipment}대")

# df3 기준 추가 KPI
if df3_with_org is not None:
    st.subheader("🔧 df3 수리품목 기준 지표")
    
    # 해당 월의 df3 데이터 필터링
    df3_current = df3_with_org[df3_with_org['출고년월'] == selected_month] if '출고년월' in df3_with_org.columns else pd.DataFrame()
    
    if not df3_current.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            df3_cases = len(df3_current)
            st.metric("총 출고건수", f"{df3_cases:,}건")
        
        with col2:
            df3_cost = df3_current['수리비'].sum() if '수리비' in df3_current.columns else 0
            st.metric("총 출고금액", f"{df3_cost:,.0f}원")
        
        with col3:
            df3_avg = df3_cost / df3_cases if df3_cases > 0 else 0
            st.metric("건당 평균 출고금액", f"{df3_avg:,.0f}원")
        
        with col4:
            df3_parts = df3_current['파트'].nunique() if '파트' in df3_current.columns else 0
            st.metric("관련 파트", f"{df3_parts}개")

# 알림
if current_avg > df['수리비'].mean() * 1.3:
    st.error(f"⚠️ 이번 달 평균 수리비가 전체 평균보다 {((current_avg/df['수리비'].mean()-1)*100):.1f}% 높습니다!")

st.markdown("---")

# 메인 분석
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 월별 트렌드 (최근 12개월)")
    
    # 월별 데이터 집계
    recent_months = available_months[:12]
    monthly_data = df[df['년월'].isin(recent_months)].groupby('년월').agg({
        '수리비': 'sum',
        '관리번호': 'count'
    }).reset_index()
    monthly_data['년월_str'] = monthly_data['년월'].astype(str)
    monthly_data = monthly_data.sort_values('년월')
    
    if not monthly_data.empty:
        fig = go.Figure()
        
        # 수리비 트렌드
        fig.add_trace(go.Scatter(
            x=monthly_data['년월_str'],
            y=monthly_data['수리비'],
            mode='lines+markers',
            name='월별 수리비',
            line=dict(color='#FF6B6B', width=3),
            yaxis='y'
        ))
        
        # AS 건수 (보조축)
        fig.add_trace(go.Scatter(
            x=monthly_data['년월_str'],
            y=monthly_data['관리번호'],
            mode='lines+markers',
            name='AS 건수',
            line=dict(color='#4ECDC4', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            height=400,
            yaxis=dict(title="수리비 (원)", side="left"),
            yaxis2=dict(title="AS 건수", side="right", overlaying="y"),
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🚨 주요 이슈")
    
    # 파트별 수리비 (상위 5개) - df1과 df3 통합 분석
    if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
        part_costs = current_data[current_data['정비자소속'].notna()].groupby('정비자소속')['수리비'].sum().nlargest(5)
        
        if not part_costs.empty:
            st.write("**💰 수리비 상위 파트 (df1 기준):**")
            for idx, (part, cost) in enumerate(part_costs.items()):
                icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                st.write(f"{icon} {part}: {cost:,.0f}원")
        else:
            st.write("**💰 파트별 수리비 정보 없음**")
    else:
        st.write("**💰 파트 정보 없음**")
    
    # df3 기준 파트별 출고금액 (상위 5개)
    if df3_with_org is not None and not df3_current.empty and '파트' in df3_current.columns:
        df3_part_costs = df3_current.groupby('파트')['수리비'].sum().nlargest(5)
        
        if not df3_part_costs.empty:
            st.write("**🔧 출고금액 상위 파트 (df3 기준):**")
            for idx, (part, cost) in enumerate(df3_part_costs.items()):
                icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                st.write(f"{icon} {part}: {cost:,.0f}원")
    
    # 업체별 수리비 (상위 5개)
    client_col = None
    if '현장명' in current_data.columns and current_data['현장명'].notna().any():
        client_col = '현장명'
    elif '업체명' in current_data.columns and current_data['업체명'].notna().any():
        client_col = '업체명'
    elif '현장' in current_data.columns and current_data['현장'].notna().any():
        client_col = '현장'
    
    if client_col and not current_data.empty:
        client_costs = current_data[current_data[client_col].notna()].groupby(client_col)['수리비'].sum().nlargest(5)
        
        if not client_costs.empty:
            st.write("**🏢 수리비 상위 업체:**")
            for idx, (client, cost) in enumerate(client_costs.items()):
                icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                client_short = str(client)[:15] + "..." if len(str(client)) > 15 else str(client)
                st.write(f"{icon} {client_short}: {cost:,.0f}원")
        else:
            st.write("**🏢 업체별 수리비 정보 없음**")
    else:
        st.write("**🏢 업체 정보 없음**")

# 하단 상세 분석 - df3 정보 포함
st.header("📋 상세 분석")

tab1, tab2, tab3 = st.tabs(["파트별", "업체별", "df3 수리품목"])

with tab1:
    st.subheader("👥 파트별 분석 (df1 기준)")
    
    if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
        # NaN 제거 후 분석
        valid_part_data = current_data[current_data['정비자소속'].notna()]
        
        if not valid_part_data.empty:
            part_analysis = valid_part_data.groupby('정비자소속').agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean']
            })
            part_analysis.columns = ['건수', '총수리비', '평균수리비']
            
            # 0으로 나누기 방지
            part_analysis['효율성'] = np.where(
                part_analysis['총수리비'] > 0,
                part_analysis['건수'] / part_analysis['총수리비'] * 1000000,
                0
            )
            
            part_analysis = part_analysis.sort_values('총수리비', ascending=False)
            
            st.dataframe(
                part_analysis.style.format({
                    '총수리비': '{:,.0f}원',
                    '평균수리비': '{:,.0f}원',
                    '효율성': '{:.2f}'
                }),
                use_container_width=True
            )
        else:
            st.info("파트별 데이터가 없습니다.")
    else:
        st.info("정비자소속 정보가 없습니다.")

with tab2:
    st.subheader("🏢 업체별 분석")
    
    if client_col and client_col in current_data.columns:
        valid_client_data = current_data[current_data[client_col].notna()]
        
        if not valid_client_data.empty:
            client_analysis = valid_client_data.groupby(client_col).agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean']
            })
            client_analysis.columns = ['건수', '총수리비', '평균수리비']
            client_analysis = client_analysis.sort_values('총수리비', ascending=False).head(20)
            
            st.dataframe(
                client_analysis.style.format({
                    '총수리비': '{:,.0f}원',
                    '평균수리비': '{:,.0f}원'
                }),
                use_container_width=True
            )
        else:
            st.info("업체별 데이터가 없습니다.")
    else:
        st.info("업체 정보가 없습니다.")

with tab3:
    st.subheader("🔧 df3 수리품목 분석")
    
    if df3_with_org is not None and not df3_current.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # df3 파트별 분석
            if '파트' in df3_current.columns:
                df3_part_analysis = df3_current.groupby('파트').agg({
                    '관리번호': 'count',
                    '수리비': ['sum', 'mean']
                })
                df3_part_analysis.columns = ['출고건수', '총출고금액', '평균출고금액']
                df3_part_analysis = df3_part_analysis.sort_values('총출고금액', ascending=False)
                
                st.write("**파트별 출고 현황:**")
                st.dataframe(
                    df3_part_analysis.style.format({
                        '총출고금액': '{:,.0f}원',
                        '평균출고금액': '{:,.0f}원'
                    }),
                    use_container_width=True
                )
        
        with col2:
            # df3 주요 자재 분석
            if '자재명' in df3_current.columns:
                material_analysis = df3_current['자재명'].value_counts().head(10)
                
                st.write("**주요 출고 자재 TOP 10:**")
                for idx, (material, count) in enumerate(material_analysis.items()):
                    st.write(f"{idx+1}. {material}: {count}건")
    else:
        st.info("df3 수리품목 데이터가 없습니다.")

# 액션 아이템
st.markdown("---")
st.header("📋 액션 아이템")

action_items = []

if current_cost > 10000000:
    action_items.append(f"💰 **고비용 주의**: 총 수리비 {current_cost:,.0f}원 → 비용 절감 방안 검토")

if case_change > 30:
    action_items.append(f"📈 **건수 급증**: 전월 대비 {case_change:.1f}% 증가 → 원인 분석 필요")

if avg_change > 25:
    action_items.append(f"⚠️ **단가 상승**: 건당 평균 {avg_change:.1f}% 상승 → 수리 품질 점검")

# df3 기준 액션 아이템 추가
if df3_with_org is not None and not df3_current.empty:
    df3_high_cost_parts = df3_current.groupby('파트')['수리비'].sum().nlargest(1)
    if not df3_high_cost_parts.empty:
        top_part = df3_high_cost_parts.index[0]
        top_cost = df3_high_cost_parts.iloc[0]
        action_items.append(f"🔧 **df3 고출고 파트**: {top_part} ({top_cost:,.0f}원) → 자재 사용량 점검")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")

# 데이터 다운로드 - 엑셀 버전
st.markdown("---")
st.subheader("📥 경영 대시보드 데이터 다운로드")

col1, col2, col3 = st.columns(3)

with col1:
    # 현재 월 상세 데이터
    excel_data = to_excel_download(current_data, f"{selected_month}_경영대시보드_상세데이터.xlsx")
    st.download_button(
        label="📄 현재 월 상세 데이터 (Excel)",
        data=excel_data,
        file_name=f"{selected_month}_경영대시보드_상세데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col2:
    # 월별 트렌드 데이터
    if not monthly_data.empty:
        trend_excel = to_excel_download(monthly_data, "월별_트렌드_데이터.xlsx")
        st.download_button(
            label="📈 월별 트렌드 데이터 (Excel)",
            data=trend_excel,
            file_name="월별_트렌드_데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with col3:
    # 종합 대시보드 리포트 (다중 시트)
    dashboard_data = {
        '현재월_상세데이터': current_data,
        '월별_트렌드': monthly_data if not monthly_data.empty else pd.DataFrame()
    }
    
    # 파트별 분석 데이터 추가
    if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
        valid_part_data = current_data[current_data['정비자소속'].notna()]
        if not valid_part_data.empty:
            part_summary = valid_part_data.groupby('정비자소속').agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean']
            })
            part_summary.columns = ['건수', '총수리비', '평균수리비']
            dashboard_data['파트별_분석'] = part_summary.reset_index()
    
    # df3 데이터 추가
    if df3_with_org is not None and not df3_current.empty:
        dashboard_data['df3_수리품목'] = df3_current
    
    # 빈 데이터프레임 제거
    dashboard_data = {k: v for k, v in dashboard_data.items() if not v.empty}
    
    if dashboard_data:
        multi_excel = to_excel_multi_sheet(dashboard_data, f"{selected_month}_경영대시보드_종합리포트.xlsx")
        st.download_button(
            label="📊 종합 대시보드 리포트 (Excel)",
            data=multi_excel,
            file_name=f"{selected_month}_경영대시보드_종합리포트.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
