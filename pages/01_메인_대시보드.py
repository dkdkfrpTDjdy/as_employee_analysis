# pages/01_경영_대시보드.py - 들여쓰기 수정 버전
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="경영 대시보드", layout="wide")
st.title("📊 경영 대시보드")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs.copy()

# df3 원본 데이터 로드 및 조직도 매핑
@st.cache_data(show_spinner=False)
def load_and_process_df3():
    """df3 원본 데이터를 로드하고 조직도와 매핑"""
    
    if not hasattr(st.session_state, 'df3_raw'):
        return None
    
    df3 = st.session_state.df3_raw.copy()
    
    # 조직도 데이터 로드
    import os
    if not os.path.exists("data/조직도데이터.xlsx"):
        return df3
    
    try:
        df4 = pd.read_excel("data/조직도데이터.xlsx", dtype=str)
        
        # 조직도 전처리
        if len(df4) > 0:
            first_row = df4.iloc[0]
            if any(keyword in str(first_row.iloc[i]).lower() 
                   for i in range(min(len(first_row), 3)) 
                   for keyword in ['이름', '파트', '사번']):
                new_columns = df4.iloc[0].tolist()
                df4 = df4.iloc[1:].reset_index(drop=True)
                df4.columns = new_columns
        
        df4.columns = [str(col).strip().replace('\n', '') for col in df4.columns]
        
        # df3와 조직도 매핑
        if '출고자' in df3.columns and '사번' in df4.columns and '파트' in df4.columns:
            df3['출고자'] = df3['출고자'].astype(str).str.strip()
            df4['사번'] = df4['사번'].astype(str).str.strip()
            
            df3_with_org = pd.merge(
                df3,
                df4[['사번', '파트', '직급', '직책', '이름']],
                left_on='출고자',
                right_on='사번',
                how='left'
            )
            
            # 수리비 처리
            cost_col = None
            for col in ['출고금액', '금액', '단가']:
                if col in df3_with_org.columns:
                    cost_col = col
                    break
            
            if cost_col:
                df3_with_org['수리비'] = pd.to_numeric(df3_with_org[cost_col], errors='coerce').fillna(0)
            
            # 출고일자 처리
            if '출고일자' in df3_with_org.columns:
                df3_with_org['출고일자'] = pd.to_datetime(df3_with_org['출고일자'], errors='coerce')
                df3_with_org['년월'] = df3_with_org['출고일자'].dt.to_period('M')
            
            return df3_with_org
        
    except Exception as e:
        pass
    
    return df3

# 빠른 데이터 전처리
@st.cache_data(show_spinner=False)
def prepare_dashboard_data(df):
    if '정비일자' in df.columns:
        df['정비일자'] = pd.to_datetime(df['정비일자'], errors='coerce')
        df = df.dropna(subset=['정비일자'])
        df['년월'] = df['정비일자'].dt.to_period('M')
        df['년'] = df['정비일자'].dt.year
        df['월'] = df['정비일자'].dt.month
    
    df['수리비'] = pd.to_numeric(df['수리비'], errors='coerce').fillna(0)
    
    return df

df = prepare_dashboard_data(df)
df3 = load_and_process_df3()

if df.empty:
    st.error("처리 가능한 데이터가 없습니다.")
    st.stop()

# 사이드바 설정
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

# df3 현재 월 데이터
current_df3_data = None
if df3 is not None and '년월' in df3.columns:
    current_df3_data = df3[df3['년월'] == selected_month]

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

# 알림
if current_avg > df['수리비'].mean() * 1.3:
    st.error(f"⚠️ 이번 달 평균 수리비가 전체 평균보다 {((current_avg/df['수리비'].mean()-1)*100):.1f}% 높습니다!")

st.markdown("---")

# 메인 분석
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 월별 트렌드 (최근 12개월)")
    
    recent_months = available_months[:12]
    monthly_data = df[df['년월'].isin(recent_months)].groupby('년월').agg({
        '수리비': 'sum',
        '관리번호': 'count'
    }).reset_index()
    monthly_data['년월_str'] = monthly_data['년월'].astype(str)
    monthly_data = monthly_data.sort_values('년월')
    
    if not monthly_data.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=monthly_data['년월_str'],
            y=monthly_data['수리비'],
            mode='lines+markers',
            name='월별 수리비',
            line=dict(color='#FF6B6B', width=3),
            yaxis='y'
        ))
        
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
    
    # 파트별 수리비 (df3 기준)
    if current_df3_data is not None and '파트' in current_df3_data.columns:
        df3_part_costs = current_df3_data[current_df3_data['파트'].notna()].groupby('파트')['수리비'].sum().nlargest(5)
        
        if not df3_part_costs.empty:
            st.write("**💰 수리비 상위 파트 (df3 기준):**")
            for idx, (part, cost) in enumerate(df3_part_costs.items()):
                icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                st.write(f"{icon} {part}: {cost:,.0f}원")
    else:
        # df1 백업
        if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
            part_costs = current_data[current_data['정비자소속'].notna()].groupby('정비자소속')['수리비'].sum().nlargest(5)
            
            if not part_costs.empty:
                st.write("**💰 수리비 상위 파트 (df1 기준):**")
                for idx, (part, cost) in enumerate(part_costs.items()):
                    icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                    st.write(f"{icon} {part}: {cost:,.0f}원")
    
    # 업체별 수리비
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

# 하단 상세 분석
st.header("📋 상세 분석")

tab1, tab2, tab3, tab4 = st.tabs(["파트별", "업체별", "지역별", "고장유형별"])

with tab1:
    st.subheader("👥 파트별 분석 (df3 기준)")
    
    if current_df3_data is not None and '파트' in current_df3_data.columns:
        valid_part_data = current_df3_data[current_df3_data['파트'].notna()]
        
        if not valid_part_data.empty:
            part_analysis = valid_part_data.groupby('파트').agg({
                '관리번호': 'count',
                '수리비': ['sum', 'mean']
            })
            part_analysis.columns = ['수리품목건수', '총수리비', '평균수리비']
            
            part_analysis['효율성'] = np.where(
                part_analysis['총수리비'] > 0,
                part_analysis['수리품목건수'] / part_analysis['총수리비'] * 1000000,
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
            st.info("df3 파트별 데이터가 없습니다.")
    else:
        # df1 백업
        if '정비자소속' in current_data.columns and current_data['정비자소속'].notna().any():
            valid_part_data = current_data[current_data['정비자소속'].notna()]
            
            if not valid_part_data.empty:
                part_analysis = valid_part_data.groupby('정비자소속').agg({
                    '관리번호': 'count',
                    '수리비': ['sum', 'mean']
                })
                part_analysis.columns = ['AS건수', '총수리비', '평균수리비']
                part_analysis = part_analysis.sort_values('총수리비', ascending=False)
                
                st.dataframe(
                    part_analysis.style.format({
                        '총수리비': '{:,.0f}원',
                        '평균수리비': '{:,.0f}원'
                    }),
                    use_container_width=True
                )

with tab2:
    st.subheader("🏢 업체별 분석")
    
    client_col = None
    if '현장명' in current_data.columns and current_data['현장명'].notna().any():
        client_col = '현장명'
    elif '업체명' in current_data.columns and current_data['업체명'].notna().any():
        client_col = '업체명'
    elif '현장' in current_data.columns and current_data['현장'].notna().any():
        client_col = '현장'
    
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
    st.subheader("🗺️ 지역별 분석")
    
    if '지역' in current_data.columns and current_data['지역'].notna().any():
        valid_region_data = current_data[current_data['지역'].notna()]
        
        if not valid_region_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                region_analysis = valid_region_data.groupby('지역').agg({
                    '관리번호': 'count',
                    '수리비': 'sum',
                    '현장명': 'nunique' if '현장명' in valid_region_data.columns else lambda x: 0
                }).rename(columns={'관리번호': '건수', '현장명': '업체수'})
                
                region_analysis['평균수리비'] = (region_analysis['수리비'] / region_analysis['건수']).round(0)
                region_analysis = region_analysis.sort_values('수리비', ascending=False)
                
                region_data_for_chart = region_analysis.reset_index()
                
                fig = px.bar(
                    region_data_for_chart,
                    x='지역',
                    y='건수',
                    title="지역별 AS 건수",
                    color='건수',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(
                    region_data_for_chart,
                    x='지역',
                    y='수리비',
                    title="지역별 총 수리비",
                    color='수리비',
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(
                region_analysis.style.format({
                    '수리비': '{:,.0f}원',
                    '평균수리비': '{:,.0f}원'
                }),
                use_container_width=True
            )
            
            st.write("**🎯 지역별 효율성 분석**")
            avg_cost_per_case = region_analysis['평균수리비'].mean()
            
            high_cost_regions = region_analysis[region_analysis['평균수리비'] > avg_cost_per_case * 1.2]
            if not high_cost_regions.empty:
                st.warning("**고비용 지역 (평균 대비 20% 이상):**")
                for region, data in high_cost_regions.iterrows():
                    excess_rate = (data['평균수리비'] / avg_cost_per_case - 1) * 100
                    st.write(f"• **{region}**: 평균 {data['평균수리비']:,.0f}원 (+{excess_rate:.1f}%)")
            else:
                st.success("✅ 모든 지역이 평균 범위 내에 있습니다.")
        else:
            st.info("지역별 데이터가 없습니다.")
    else:
        st.info("지역 정보가 없습니다.")

with tab4:
    st.subheader("🔧 고장유형별 분석")
    
    # df3 기준 자재별 분석
    if current_df3_data is not None and '자재명' in current_df3_data.columns:
        st.write("**🔧 주요 자재별 수리비 (df3 기준)**")
        
        material_analysis = current_df3_data[current_df3_data['자재명'].notna()].groupby('자재명').agg({
            '관리번호': 'count',
            '수리비': 'sum'
        }).rename(columns={'관리번호': '건수'})
        
        material_analysis['비율(%)'] = (material_analysis['건수'] / material_analysis['건수'].sum() * 100).round(1)
        material_analysis = material_analysis.sort_values('수리비', ascending=False).head(10)
        
        if not material_analysis.empty:
            chart_data = material_analysis.reset_index()
            chart_data['자재명_short'] = chart_data['자재명'].apply(
                lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x)
            )
            
            fig = px.bar(
                chart_data,
                x='수리비',
                y='자재명_short',
                orientation='h',
                title="주요 자재별 수리비 (상위 10개)",
                color='수리비',
                color_continuous_scale='Oranges'
            )
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
            for idx, (material, row) in enumerate(material_analysis.head(5).iterrows()):
                icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                material_short = str(material)[:25] + "..." if len(str(material)) > 25 else str(material)
                st.write(f"{icon} {material_short}")
                st.write(f"   {row['건수']}건 ({row['비율(%)']:.1f}%) - {row['수리비']:,.0f}원")
    
    else:
        # df1 기준 고장유형 분석 (백업)
        fault_columns = ['작업유형', '정비대상', '정비작업']
        available_fault_columns = [col for col in fault_columns if col in current_data.columns and current_data[col].notna().any()]
        
        if available_fault_columns:
            col1, col2, col3 = st.columns(3)
            
            for i, col_name in enumerate(available_fault_columns[:3]):
                with [col1, col2, col3][i]:
                    st.write(f"**{col_name} 분석**")
                    
                    fault_analysis = current_data[current_data[col_name].notna()].groupby(col_name).agg({
                        '관리번호': 'count',
                        '수리비': 'sum'
                    })
                    fault_analysis.columns = ['건수', '총수리비']
                    fault_analysis['비율(%)'] = (fault_analysis['건수'] / fault_analysis['건수'].sum() * 100).round(1)
                    fault_analysis = fault_analysis.sort_values('총수리비', ascending=False).head(5)
                    
                    for idx, (fault_type, row) in enumerate(fault_analysis.iterrows()):
                        icon = "🔴" if idx == 0 else "🟡" if idx == 1 else "🟢"
                        fault_short = str(fault_type)[:15] + "..." if len(str(fault_type)) > 15 else str(fault_type)
                        st.write(f"{icon} {fault_short}")
                        st.write(f"   {row['건수']}건 ({row['비율(%)']:.1f}%) - {row['총수리비']:,.0f}원")
        else:
            st.info("고장유형 정보가 없습니다.")

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

# df3 기반 추가 액션 아이템
if current_df3_data is not None and '파트' in current_df3_data.columns:
    df3_part_costs = current_df3_data[current_df3_data['파트'].notna()].groupby('파트')['수리비'].sum()
    if len(df3_part_costs) > 0:
        top_df3_part = df3_part_costs.idxmax()
        top_df3_cost = df3_part_costs.max()
        df3_total = df3_part_costs.sum()
        
        if df3_total > 0 and (top_df3_cost / df3_total) > 0.4:
            action_items.append(f"🔧 **파트 집중도 높음**: {top_df3_part} 파트가 수리비의 {(top_df3_cost/df3_total)*100:.1f}% 차지")

if not action_items:
    action_items.append("✅ 현재 특이사항 없음 - 정상 운영 중")

for item in action_items:
    st.markdown(f"- {item}")
