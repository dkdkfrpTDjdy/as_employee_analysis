import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("⚠️ 메인 페이지에서 데이터를 먼저 업로드해주세요.")
    st.stop()

df1 = st.session_state.df1_with_costs.copy()

# df3 원본 데이터 로드 및 조직도 매핑
@st.cache_data(show_spinner=False)
def load_and_process_df3():
    """df3 원본 데이터를 로드하고 조직도와 매핑"""
    
    # 세션에서 df3 원본 데이터 확인
    if not hasattr(st.session_state, 'df3_raw'):
        st.error("df3 수리품목 데이터가 없습니다.")
        return None
    
    df3 = st.session_state.df3_raw.copy()
    
    # 조직도 데이터 로드
    import os
    if not os.path.exists("data/조직도데이터.xlsx"):
        st.warning("조직도 데이터가 없습니다.")
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
        
        # df3와 조직도 매핑 (출고자 = 사번)
        if '출고자' in df3.columns and '사번' in df4.columns and '파트' in df4.columns:
            df3['출고자'] = df3['출고자'].astype(str).str.strip()
            df4['사번'] = df4['사번'].astype(str).str.strip()
            
            # 출고자(사번) -> 파트 매핑
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
            else:
                df3_with_org['수리비'] = 0
            
            # 출고일자 처리
            if '출고일자' in df3_with_org.columns:
                df3_with_org['출고일자'] = pd.to_datetime(df3_with_org['출고일자'], errors='coerce')
                df3_with_org['년월'] = df3_with_org['출고일자'].dt.to_period('M')
            
            st.sidebar.success("✅ df3 + 조직도 매핑 완료")
            return df3_with_org
        
    except Exception as e:
        st.sidebar.warning(f"df3 조직도 매핑 오류: {e}")
    
    return df3

# df3 데이터 로드
df3 = load_and_process_df3()

if df3 is None:
    st.error("df3 데이터를 로드할 수 없습니다.")
    st.stop()

# 파트 정보 확인
if '파트' not in df3.columns or df3['파트'].isna().all():
    st.error("파트 정보가 없습니다. 조직도 매핑을 확인해주세요.")
    st.stop()

# 사이드바 필터
st.sidebar.header("🔧 분석 옵션")

# 기간 필터 (df3 출고일자 기준)
if '출고일자' in df3.columns and df3['출고일자'].notna().any():
    min_date = df3['출고일자'].min().date()
    max_date = df3['출고일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간 (출고일자 기준)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df3 = df3[(df3['출고일자'].dt.date >= start_date) & 
                  (df3['출고일자'].dt.date <= end_date)]

# 파트별 전체 현황 (df3 기준)
st.header("📊 파트별 전체 현황 (수리품목 기준)")

# df3 파트별 통계 계산
df3_filtered = df3[df3['파트'].notna()].copy()

part_stats = df3_filtered.groupby('파트').agg({
    '관리번호': 'count',
    '수리비': ['sum', 'mean'],
    '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:5]),
    '출고자': 'nunique'
}).round(2)

part_stats.columns = ['수리품목건수', '총수리비', '평균수리비', '주요자재', '담당자수']
part_stats = part_stats.reset_index()
part_stats = part_stats.rename(columns={'파트': '정비자소속'})

# df1에서 AS 건수만 가져오기 (참고용)
if '정비자소속' in df1.columns:
    df1_as_count = df1.groupby('정비자소속')['관리번호'].count().reset_index()
    df1_as_count.columns = ['정비자소속', 'AS건수']
    part_stats = pd.merge(part_stats, df1_as_count, on='정비자소속', how='left')
    part_stats['AS건수'] = part_stats['AS건수'].fillna(0).astype(int)

# 효율성 지표 추가
part_stats['건당수리비'] = part_stats['총수리비'] / part_stats['수리품목건수']
part_stats['효율성점수'] = (part_stats['수리품목건수'] / part_stats['총수리비'] * 1000000).round(2)
part_stats = part_stats.sort_values('총수리비', ascending=False)

# 상위 파트 시각화
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 파트별 총 수리비 (df3 기준)")
    top_parts = part_stats.head(10)
    
    fig = px.bar(
        top_parts, 
        x='총수리비', 
        y='정비자소속',
        orientation='h',
        color='총수리비',
        color_continuous_scale='Reds',
        title="상위 10개 파트 - 수리품목 기준"
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 파트별 수리품목 건수 (df3 기준)")
    
    fig2 = px.bar(
        top_parts,
        x='수리품목건수',
        y='정비자소속', 
        orientation='h',
        color='수리품목건수',
        color_continuous_scale='Blues',
        title="상위 10개 파트 - 수리품목 기준"
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 주요 자재 분석
st.subheader("🔧 파트별 주요 사용 자재")

col1, col2 = st.columns(2)

with col1:
    # 자재 다양성 분석
    material_diversity = part_stats[part_stats['주요자재'].notna()].copy()
    material_diversity['자재종류수'] = material_diversity['주요자재'].apply(
        lambda x: len(str(x).split(', ')) if pd.notna(x) else 0
    )
    
    fig = px.bar(
        material_diversity.head(10),
        x='자재종류수',
        y='정비자소속',
        orientation='h',
        color='자재종류수',
        color_continuous_scale='Greens',
        title="파트별 사용 자재 종류 수"
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # 상위 파트별 주요 자재
    st.write("**상위 5개 파트 주요 자재:**")
    for _, row in part_stats.head(5).iterrows():
        if pd.notna(row.get('주요자재')):
            st.write(f"**{row['정비자소속']}**")
            materials = str(row['주요자재']).split(', ')[:3]
            for material in materials:
                st.write(f"  • {material}")
            st.write("")

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계")

# 표시할 컬럼
display_columns = ['정비자소속', '수리품목건수', '총수리비', '평균수리비', '건당수리비', '담당자수', '효율성점수']

# AS건수가 있으면 추가
if 'AS건수' in part_stats.columns:
    display_columns.insert(-1, 'AS건수')

display_stats = part_stats[display_columns]

# 포맷팅
format_dict = {
    '수리품목건수': '{:,}건',
    '총수리비': '{:,.0f}원',
    '평균수리비': '{:,.0f}원',
    '건당수리비': '{:,.0f}원',
    'AS건수': '{:,}건',
    '담당자수': '{:,}명',
    '효율성점수': '{:.2f}'
}

st.dataframe(
    display_stats.style.format(format_dict),
    use_container_width=True
)

# 파트 선택 및 상세 분석
st.markdown("---")
st.header("🔍 파트별 상세 분석")

available_parts = df3_filtered['파트'].dropna().unique()
selected_parts = st.multiselect(
    "상세 분석할 파트 선택", 
    available_parts,
    default=available_parts[:2] if len(available_parts) >= 2 else available_parts
)

if selected_parts:
    for i, part in enumerate(selected_parts):
        if i > 0:
            st.markdown("---")
            
        part_data = df3_filtered[df3_filtered['파트'] == part]
        
        st.subheader(f"🔧 {part} 파트 상세 분석")
        
        # 파트 KPI
        cols = st.columns(5)
        
        with cols[0]:
            total_items = len(part_data)
            st.metric("총 수리품목 건수", f"{total_items:,}건")
        
        with cols[1]:
            total_cost = part_data['수리비'].sum()
            st.metric("총 수리비", f"{total_cost:,.0f}원")
        
        with cols[2]:
            avg_cost = part_data['수리비'].mean() if total_items > 0 else 0
            st.metric("평균 수리비", f"{avg_cost:,.0f}원")
        
        with cols[3]:
            unique_materials = part_data['자재명'].nunique()
            st.metric("사용 자재 종류", f"{unique_materials}개")
        
        with cols[4]:
            unique_equipment = part_data['관리번호'].nunique()
            st.metric("관련 장비 수", f"{unique_equipment}대")

        # 상세 분석
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**🔧 주요 자재 (상위 5개)**")
            materials = part_data['자재명'].value_counts().head(5)
            for material, count in materials.items():
                percentage = (count / len(part_data) * 100)
                material_short = str(material)[:20] + "..." if len(str(material)) > 20 else str(material)
                st.write(f"• {material_short}: {count}건 ({percentage:.1f}%)")
        
        with col2:
            st.write("**👥 주요 담당자 (상위 5개)**")
            if '이름' in part_data.columns:
                workers = part_data['이름'].value_counts().head(5)
                for worker, count in workers.items():
                    percentage = (count / len(part_data) * 100)
                    st.write(f"• {worker}: {count}건 ({percentage:.1f}%)")
            else:
                st.write("담당자 정보 없음")
        
        with col3:
            st.write("**🏢 주요 관련 장비 (상위 5개)**")
            equipment = part_data['관리번호'].value_counts().head(5)
            for equip, count in equipment.items():
                percentage = (count / len(part_data) * 100)
                st.write(f"• {equip}: {count}건 ({percentage:.1f}%)")

        # 고비용 케이스 분석
        st.write("**🚨 주의 깊게 봐야 할 케이스들**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 고비용 케이스
            if part_data['수리비'].sum() > 0:
                high_cost_threshold = part_data['수리비'].quantile(0.9)
                high_cost_cases = part_data[part_data['수리비'] > high_cost_threshold]
                
                if not high_cost_cases.empty:
                    st.write("🔴 **고비용 수리 케이스 (상위 10%):**")
                    for idx, (_, case) in enumerate(high_cost_cases.head(3).iterrows()):
                        자재명 = case.get('자재명', 'N/A')
                        관리번호 = case.get('관리번호', 'N/A')
                        수리비 = case.get('수리비', 0)
                        
                        자재명_short = str(자재명)[:20] + "..." if len(str(자재명)) > 20 else str(자재명)
                        st.write(f"• {자재명_short}")
                        st.write(f"  장비: {관리번호} | 💰 {수리비:,.0f}원")
                else:
                    st.write("고비용 케이스 없음")
        
        with col2:
            # 반복 사용 자재
            repeat_materials = part_data['자재명'].value_counts()
            repeat_materials = repeat_materials[repeat_materials > 1].head(3)
            
            if not repeat_materials.empty:
                st.write("🔄 **자주 사용되는 자재:**")
                for 자재명, 횟수 in repeat_materials.items():
                    자재명_short = str(자재명)[:20] + "..." if len(str(자재명)) > 20 else str(자재명)
                    st.write(f"• {자재명_short}")
                    st.write(f"  📊 {횟수}회 사용")
            else:
                st.write("반복 사용 자재 없음")

# 파트 성과 랭킹
st.markdown("---")
st.header("🏆 파트 성과 랭킹")

cols = st.columns(3)

with cols[0]:
    st.subheader("💰 수리비 효율성 랭킹 (df1 기준)")
    if 'AS건수' in part_stats.columns:
        # df1 AS건수 기준 효율성
        df1_efficiency = part_stats[part_stats['AS건수'] > 0].copy()
        df1_efficiency['df1_건당수리비'] = df1_efficiency['총수리비'] / df1_efficiency['AS건수']
        efficiency_ranking = df1_efficiency.nsmallest(10, 'df1_건당수리비')[['정비자소속', 'df1_건당수리비', 'AS건수']]
        
        for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
            medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
            st.write(f"{medal} **{row['정비자소속']}**")
            st.write(f"   건당 수리비: {row['df1_건당수리비']:,.0f}원 ({row['AS건수']}건)")
    else:
        st.write("df1 AS건수 데이터 없음")

with cols[1]:
    st.subheader("📊 수리품목 업무량 랭킹 (df3 기준)")
    volume_ranking = part_stats.nlargest(10, '수리품목건수')[['정비자소속', '수리품목건수', '총수리비']]
    
    for idx, (_, row) in enumerate(volume_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   수리품목: {row['수리품목건수']:,}건 (총 {row['총수리비']:,.0f}원)")

with cols[2]:
    st.subheader("🔧 수리비 총액 랭킹 (df3 기준)")
    cost_ranking = part_stats.nlargest(10, '총수리비')[['정비자소속', '총수리비', '수리품목건수']]
    
    for idx, (_, row) in enumerate(cost_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['정비자소속']}**")
        st.write(f"   총 수리비: {row['총수리비']:,.0f}원 ({row['수리품목건수']}건)")

# 엑셀 다운로드 함수
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='파트별분석')
    return output.getvalue()

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    excel_data = to_excel(part_stats)
    st.download_button(
        label="📊 파트별 통계 다운로드 (Excel)",
        data=excel_data,
        file_name="파트별_상세통계_df3기준.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col2:
    # df3 상세 데이터 다운로드
    download_columns = ['파트', '관리번호', '출고일자', '수리비', '자재명', '출고자', '이름']
    available_columns = [col for col in download_columns if col in df3_filtered.columns]
    detailed_data = df3_filtered[available_columns].copy()
    
    detailed_excel = to_excel(detailed_data)
    st.download_button(
        label="📄 수리품목 상세 데이터 다운로드 (Excel)",
        data=detailed_excel,
        file_name="파트별_수리품목_상세데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
