import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석 (df3 수리품목 중심)")

# 엑셀 다운로드 함수
def to_excel_download(df, filename):
    """DataFrame을 엑셀로 변환하여 다운로드 버튼 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='데이터')
    output.seek(0)
    return output.getvalue()

# 세션 상태 확인
st.sidebar.header("🔍 데이터 상태 확인")

# df3 머지된 데이터 확인
if 'df3_with_org' in st.session_state:
    df3_merged = st.session_state['df3_with_org']
    st.sidebar.success(f"✅ df3 머지 데이터: {len(df3_merged)}행")
else:
    st.sidebar.error("❌ df3 머지 데이터 없음")
    st.error("df3 수리품목 데이터가 없습니다. 메인 페이지에서 소모품 출고 데이터를 업로드해주세요.")
    st.stop()

# df1 머지된 데이터 확인
if 'df1_with_costs' in st.session_state:
    df1_merged = st.session_state['df1_with_costs']
    st.sidebar.success(f"✅ df1 머지 데이터: {len(df1_merged)}행")
else:
    st.sidebar.error("❌ df1 머지 데이터 없음")
    df1_merged = pd.DataFrame()

# df3와 df1 매핑하여 최종 분석 데이터 생성
@st.cache_data(show_spinner=False)
def create_final_analysis_data(df3_merged, df1_merged):
    """df3 머지 데이터와 df1 머지 데이터를 결합하여 최종 분석 데이터 생성"""
    
    st.write("### 🔄 최종 분석 데이터 생성")
    
    # df3를 기본으로 사용
    final_data = df3_merged.copy()
    
    st.write(f"**df3 기본 데이터:** {len(final_data)}행")
    st.write(f"**df3 컬럼:** {final_data.columns.tolist()}")
    
    # 출고일자 처리
    if '출고일자' in final_data.columns:
        final_data['출고일자'] = pd.to_datetime(final_data['출고일자'], errors='coerce')
        final_data['출고년월'] = final_data['출고일자'].dt.to_period('M')
    
    # 수리비 처리
    cost_col = None
    for col in ['출고금액', '금액', '단가', '수리비']:
        if col in final_data.columns:
            cost_col = col
            break
    
    if cost_col and cost_col != '수리비':
        final_data['수리비'] = pd.to_numeric(final_data[cost_col], errors='coerce').fillna(0)
    elif '수리비' in final_data.columns:
        final_data['수리비'] = pd.to_numeric(final_data['수리비'], errors='coerce').fillna(0)
    else:
        final_data['수리비'] = 0
    
    # 관리번호 정리
    if '관리번호' in final_data.columns:
        final_data['관리번호'] = final_data['관리번호'].astype(str).str.strip()
    
    # df1에서 추가 정보 가져오기 (업체명, 작업유형)
    if not df1_merged.empty:
        st.write("### 🔍 df1에서 추가 정보 매핑")
        
        # df1 전처리
        df1_temp = df1_merged.copy()
        if '정비일자' in df1_temp.columns:
            df1_temp['정비일자'] = pd.to_datetime(df1_temp['정비일자'], errors='coerce')
            df1_temp['정비년월'] = df1_temp['정비일자'].dt.to_period('M')
        
        if '관리번호' in df1_temp.columns:
            df1_temp['관리번호'] = df1_temp['관리번호'].astype(str).str.strip()
        
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
            st.write("✅ 작업유형 통합 완료")
        
        # 업체명 컬럼 찾기
        client_col = None
        for col in ['현장명', '업체명', '현장']:
            if col in df1_temp.columns:
                client_col = col
                break
        
        # 매핑할 정보 준비
        mapping_info = ['관리번호']
        if client_col:
            mapping_info.append(client_col)
        if '작업유형_통합' in df1_temp.columns:
            mapping_info.append('작업유형_통합')
        
        # 년월 기준 매핑
        if '정비년월' in df1_temp.columns and '출고년월' in final_data.columns:
            mapping_info.append('정비년월')
            df1_mapping = df1_temp[mapping_info].drop_duplicates()
            
            final_data = pd.merge(
                final_data,
                df1_mapping,
                left_on=['관리번호', '출고년월'],
                right_on=['관리번호', '정비년월'],
                how='left'
            )
            
            # 정비년월 컬럼 제거
            if '정비년월' in final_data.columns:
                final_data = final_data.drop('정비년월', axis=1)
        else:
            # 관리번호만으로 매핑
            df1_mapping = df1_temp[mapping_info].drop_duplicates().groupby('관리번호').first().reset_index()
            
            final_data = pd.merge(
                final_data,
                df1_mapping,
                on='관리번호',
                how='left'
            )
        
        # 컬럼명 정리
        if client_col and client_col in final_data.columns:
            final_data['업체명'] = final_data[client_col]
            if client_col != '업체명':
                final_data = final_data.drop(client_col, axis=1)
        
        if '작업유형_통합' in final_data.columns:
            final_data['작업유형'] = final_data['작업유형_통합']
            final_data = final_data.drop('작업유형_통합', axis=1)
        
        # 매핑 결과 확인
        if '업체명' in final_data.columns:
            mapped_clients = final_data['업체명'].notna().sum()
            st.write(f"**업체명 매핑: {mapped_clients}건**")
        
        if '작업유형' in final_data.columns:
            mapped_work_types = final_data['작업유형'].notna().sum()
            st.write(f"**작업유형 매핑: {mapped_work_types}건**")
    
    st.success(f"✅ 최종 분석 데이터 생성 완료: {len(final_data)}행")
    return final_data

# 최종 분석 데이터 생성
final_analysis_data = create_final_analysis_data(df3_merged, df1_merged)

# 파트 컬럼 확인
if '파트' not in final_analysis_data.columns or final_analysis_data['파트'].isna().all():
    st.error("파트 정보가 없습니다.")
    st.stop()

# 사이드바 필터
st.sidebar.header("🔧 분석 옵션")

# 기간 필터
date_col = '출고일자' if '출고일자' in final_analysis_data.columns else '정비일자'
if date_col in final_analysis_data.columns and final_analysis_data[date_col].notna().any():
    min_date = final_analysis_data[date_col].min().date()
    max_date = final_analysis_data[date_col].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        final_analysis_data = final_analysis_data[
            (final_analysis_data[date_col].dt.date >= start_date) & 
            (final_analysis_data[date_col].dt.date <= end_date)
        ]

# 파트별 현황 확인
st.write("### 📊 파트별 데이터 현황")
part_counts = final_analysis_data['파트'].value_counts()
st.write(f"**총 파트 수:** {len(part_counts)}개")

col1, col2 = st.columns(2)
with col1:
    st.write("**상위 파트 (데이터 수 기준):**")
    for part, count in part_counts.head(5).items():
        st.write(f"- {part}: {count}건")

with col2:
    st.write("**파트별 총 출고금액:**")
    part_costs = final_analysis_data.groupby('파트')['수리비'].sum().sort_values(ascending=False).head(5)
    for part, cost in part_costs.items():
        st.write(f"- {part}: {cost:,.0f}원")

# 파트별 전체 현황
st.header("📊 파트별 전체 현황 (df3 기준)")

# 파트별 통계 계산
part_stats = final_analysis_data.groupby('파트').agg({
    '관리번호': 'count',
    '수리비': ['sum', 'mean'],
    '자재명': lambda x: ', '.join(x.dropna().astype(str).unique()[:3]) if '자재명' in final_analysis_data.columns else ''
}).round(2)

# 컬럼명 정리
part_stats.columns = ['출고건수', '총출고금액', '평균출고금액', '주요자재']
part_stats = part_stats.reset_index()

# 직급, 직책 정보 추가
for info_col in ['직급', '직책']:
    if info_col in final_analysis_data.columns:
        part_info = final_analysis_data.groupby('파트')[info_col].first().reset_index()
        part_stats = pd.merge(part_stats, part_info, on='파트', how='left')

# 효율성 지표 추가
part_stats['건당출고금액'] = part_stats['총출고금액'] / part_stats['출고건수']
part_stats['효율성점수'] = (part_stats['출고건수'] / part_stats['총출고금액'] * 1000000).round(2)
part_stats = part_stats.sort_values('총출고금액', ascending=False)

# 상위 파트 시각화
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 파트별 총 출고금액")
    top_parts = part_stats.head(10)
    
    fig = px.bar(
        top_parts, 
        x='총출고금액', 
        y='파트',
        orientation='h',
        color='총출고금액',
        color_continuous_scale='Reds',
        title="파트별 총 출고금액"
    )
    fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 파트별 출고건수")
    
    fig2 = px.bar(
        top_parts,
        x='출고건수',
        y='파트', 
        orientation='h',
        color='출고건수',
        color_continuous_scale='Blues',
        title="파트별 출고건수"
    )
    fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig2, use_container_width=True)

# 파트별 상세 통계 테이블
st.subheader("📋 파트별 상세 통계")

# 컬럼 순서 정리
display_columns = ['파트', '출고건수', '총출고금액', '건당출고금액']

for col in ['직급', '직책']:
    if col in part_stats.columns:
        display_columns.append(col)

display_columns.extend(['주요자재', '효율성점수'])

display_stats = part_stats[[col for col in display_columns if col in part_stats.columns]]

# 포맷팅
format_dict = {
    '출고건수': '{:,}건',
    '총출고금액': '{:,.0f}원',
    '건당출고금액': '{:,.0f}원',
    '효율성점수': '{:.2f}'
}

st.dataframe(
    display_stats.style.format(format_dict),
    use_container_width=True
)

st.markdown("---")

# 파트 선택 및 상세 분석
st.header("🔍 파트별 상세 분석")

available_parts = final_analysis_data['파트'].dropna().unique()
selected_parts = st.multiselect(
    "상세 분석할 파트 선택",
    available_parts,
    default=available_parts[:2] if len(available_parts) >= 2 else available_parts
)

if selected_parts:
    for i, part in enumerate(selected_parts):
        if i > 0:
            st.markdown("---")
        
        part_data = final_analysis_data[final_analysis_data['파트'] == part]
        
        st.subheader(f"🔧 {part} 파트 상세 분석")
        
        # 파트 KPI
        cols = st.columns(5)
        
        with cols[0]:
            total_cases = len(part_data)
            st.metric("총 출고건수", f"{total_cases:,}건")
        
        with cols[1]:
            total_cost = part_data['수리비'].sum()
            st.metric("총 출고금액", f"{total_cost:,.0f}원")
        
        with cols[2]:
            avg_cost = part_data['수리비'].mean() if total_cases > 0 else 0
            st.metric("평균 출고금액", f"{avg_cost:,.0f}원")
        
        with cols[3]:
            unique_equipment = part_data['관리번호'].nunique()
            st.metric("관련 장비", f"{unique_equipment}대")
        
        with cols[4]:
            unique_clients = part_data['업체명'].nunique() if '업체명' in part_data.columns else 0
            st.metric("관련 업체", f"{unique_clients}개")
        
        # 파트 정보 표시
        info_cols = ['직급', '직책']
        available_info = [col for col in info_cols if col in part_data.columns]
        
        if available_info:
            st.write("**👤 파트 정보**")
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                if '직급' in available_info:
                    position = part_data['직급'].iloc[0] if not part_data['직급'].isna().all() else "정보 없음"
                    st.write(f"• **직급**: {position}")
            
            with info_col2:
                if '직책' in available_info:
                    role = part_data['직책'].iloc[0] if not part_data['직책'].isna().all() else "정보 없음"
                    st.write(f"• **직책**: {role}")
        
        # 파트별 세부 분석
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**🔨 주요 작업 유형**")
            if '작업유형' in part_data.columns and part_data['작업유형'].notna().any():
                valid_work_types = part_data['작업유형'].dropna()
                valid_work_types = valid_work_types[valid_work_types != '미분류']
                valid_work_types = valid_work_types[valid_work_types.str.strip() != '']
                
                if not valid_work_types.empty:
                    work_types = valid_work_types.value_counts().head(5)
                    for work, count in work_types.items():
                        percentage = (count / len(part_data) * 100)
                        work_short = work[:30] + "..." if len(str(work)) > 30 else str(work)
                        st.write(f"• {work_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("유효한 작업유형 데이터 없음")
            else:
                st.write("작업유형 데이터 없음")
        
        with col2:
            st.write("**⚙️ 주요 정비 대상 (자재)**")
            if '자재명' in part_data.columns and part_data['자재명'].notna().any():
                valid_materials = part_data['자재명'].dropna()
                valid_materials = valid_materials[valid_materials.str.strip() != '']
                
                if not valid_materials.empty:
                    materials = valid_materials.value_counts().head(5)
                    for material, count in materials.items():
                        percentage = (count / len(part_data) * 100)
                        material_short = material[:25] + "..." if len(str(material)) > 25 else str(material)
                        st.write(f"• {material_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("유효한 자재명 데이터 없음")
            else:
                st.write("자재명 데이터 없음")
        
        with col3:
            st.write("**🏢 주요 담당 업체**")
            if '업체명' in part_data.columns and part_data['업체명'].notna().any():
                valid_clients = part_data['업체명'].dropna()
                valid_clients = valid_clients[valid_clients.str.strip() != '']
                
                if not valid_clients.empty:
                    clients = valid_clients.value_counts().head(5)
                    for client, count in clients.items():
                        percentage = (count / len(part_data) * 100)
                        client_short = str(client)[:15] + "..." if len(str(client)) > 15 else str(client)
                        st.write(f"• {client_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.write("유효한 업체명 데이터 없음")
            else:
                st.write("업체명 데이터 없음")
        
        # 주의 케이스
        st.write("**🚨 주의 깊게 봐야 할 케이스들**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 고액 출고 케이스
            if part_data['수리비'].sum() > 0:
                high_cost_threshold = part_data['수리비'].quantile(0.9)
                high_cost_cases = part_data[part_data['수리비'] > high_cost_threshold]
                
                if not high_cost_cases.empty:
                    st.write("🔴 **고액 출고 케이스 (상위 10%):**")
                    for idx, (_, case) in enumerate(high_cost_cases.head(3).iterrows()):
                        관리번호 = case.get('관리번호', 'N/A')
                        자재명 = case.get('자재명', 'N/A')
                        출고금액 = case.get('수리비', 0)
                        
                        자재명_short = 자재명[:20] + "..." if len(str(자재명)) > 20 else str(자재명)
                        
                        st.write(f"• {관리번호} - {자재명_short}")
                        st.write(f"  💰 {출고금액:,.0f}원")
                else:
                    st.write("고액 출고 케이스 없음")
            else:
                st.write("출고금액 데이터 없음")
        
        with col2:
            # 반복 출고 장비
            if '관리번호' in part_data.columns:
                repeat_cases = part_data['관리번호'].value_counts()
                repeat_cases = repeat_cases[repeat_cases > 1].head(3)
                
                if not repeat_cases.empty:
                    st.write("🔄 **반복 출고 장비:**")
                    for 관리번호, 횟수 in repeat_cases.items():
                        equipment_info = part_data[part_data['관리번호'] == 관리번호].iloc[-1]
                        업체명 = equipment_info.get('업체명', 'N/A')
                        업체명_short = str(업체명)[:15] + "..." if len(str(업체명)) > 15 else str(업체명)
                        
                        st.write(f"• {관리번호}")
                        st.write(f"  📊 {횟수}회 출고 ({업체명_short})")
                else:
                    st.write("반복 출고 장비 없음")
            else:
                st.write("관리번호 데이터 없음")

# 파트 성과 랭킹
st.markdown("---")
st.header("🏆 파트 성과 랭킹")

cols = st.columns(3)

with cols[0]:
    st.subheader("💰 출고금액 효율성 랭킹")
    efficiency_ranking = part_stats.nsmallest(10, '건당출고금액')[['파트', '건당출고금액', '출고건수']]
    
    for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['파트']}**")
        st.write(f"   건당 출고금액: {row['건당출고금액']:,.0f}원 ({row['출고건수']}건)")

with cols[1]:
    st.subheader("📊 출고량 랭킹")
    volume_ranking = part_stats.nlargest(10, '출고건수')[['파트', '출고건수', '총출고금액']]
    
    for idx, (_, row) in enumerate(volume_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['파트']}**")
        st.write(f"   출고건수: {row['출고건수']:,}건 (총 {row['총출고금액']:,.0f}원)")

with cols[2]:
    st.subheader("💎 총 출고금액 랭킹")
    cost_ranking = part_stats.nlargest(10, '총출고금액')[['파트', '총출고금액', '출고건수']]
    
    for idx, (_, row) in enumerate(cost_ranking.iterrows()):
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
        st.write(f"{medal} **{row['파트']}**")
        st.write(f"   총 출고금액: {row['총출고금액']:,.0f}원 ({row['출고건수']}건)")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2, col3 = st.columns(3)

with col1:
    # 파트별 통계 다운로드
    excel_data = to_excel_download(part_stats, "파트별_상세통계.xlsx")
    st.download_button(
        label="📊 파트별 통계 다운로드 (Excel)",
        data=excel_data,
        file_name="파트별_상세통계.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col2:
    # 최종 분석 데이터 다운로드
    excel_data2 = to_excel_download(final_analysis_data, "df3_최종분석데이터.xlsx")
    st.download_button(
        label="📄 df3 최종 분석 데이터 (Excel)",
        data=excel_data2,
        file_name="df3_최종분석데이터.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col3:
    # 선택된 파트 데이터
    if selected_parts:
        selected_data = final_analysis_data[final_analysis_data['파트'].isin(selected_parts)]
        excel_data3 = to_excel_download(selected_data, "선택된_파트_데이터.xlsx")
        st.download_button(
            label="🎯 선택된 파트 데이터 (Excel)",
            data=excel_data3,
            file_name="선택된_파트_데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# 원본 데이터 비교 (디버깅용)
if st.sidebar.checkbox("📊 원본 데이터 비교"):
    st.subheader("📊 df1 vs df3 데이터 비교")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**df1 머지 데이터 정보:**")
        if not df1_merged.empty:
            st.write(f"- 행 수: {len(df1_merged):,}건")
            st.write(f"- 컬럼 수: {len(df1_merged.columns)}개")
            if '정비자소속' in df1_merged.columns:
                df1_parts = df1_merged['정비자소속'].value_counts().head(5)
                st.write("**상위 정비자소속:**")
                for part, count in df1_parts.items():
                    st.write(f"  - {part}: {count}건")
        else:
            st.write("df1 데이터 없음")
    
    with col2:
        st.write("**df3 머지 데이터 정보:**")
        st.write(f"- 행 수: {len(df3_merged):,}건")
        st.write(f"- 컬럼 수: {len(df3_merged.columns)}개")
        if '파트' in df3_merged.columns:
            df3_parts = df3_merged['파트'].value_counts().head(5)
            st.write("**상위 파트:**")
            for part, count in df3_parts.items():
                st.write(f"  - {part}: {count}건")
