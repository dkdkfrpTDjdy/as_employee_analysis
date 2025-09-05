#2. pages/02_파트별_심층_분석.py 전체 코드
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="파트별 심층 분석", layout="wide")
st.title("🔍 파트별 심층 분석")

# 데이터 확인
if 'df1_with_costs' not in st.session_state:
    st.warning("데이터를 먼저 업로드해주세요.")
    st.stop()

df = st.session_state.df1_with_costs

# 데이터 전처리
if '정비일자' in df.columns:
    df['년월'] = df['정비일자'].dt.to_period('M')

# 사이드바 필터
st.sidebar.header("🔧 분석 옵션")

# 기간 필터
if '정비일자' in df.columns and df['정비일자'].notna().any():
    min_date = df['정비일자'].min().date()
    max_date = df['정비일자'].max().date()
    
    date_range = st.sidebar.date_input(
        "분석 기간 선택",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[(df['정비일자'].dt.date >= start_date) & 
                (df['정비일자'].dt.date <= end_date)]

# 파트별 전체 현황
st.header("📊 파트별 전체 현황")

if '정비자소속' in df.columns:
    # 파트별 통계 계산
    part_stats = df.groupby('정비자소속').agg({
        '관리번호': 'count',
        '수리비': ['sum', 'mean'],
        '수리시간': 'mean' if '수리시간' in df.columns else lambda x: 0
    }).round(0)
    
    part_stats.columns = ['AS건수', '총수리비', '평균수리비', '평균수리시간']
    part_stats = part_stats.reset_index()
    part_stats = part_stats.sort_values('총수리비', ascending=False)
    
    # 상위 파트들 시각화
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("파트별 총 수리비 (상위 10개)")
        top_parts = part_stats.head(10)
        
        fig = px.bar(
            top_parts, 
            x='총수리비', 
            y='정비자소속',
            orientation='h',
            title="파트별 총 수리비",
            color='총수리비',
            color_continuous_scale='Reds'
        )
        fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("파트별 AS 건수 (상위 10개)")
        
        fig2 = px.bar(
            top_parts,
            x='AS건수',
            y='정비자소속', 
            orientation='h',
            title="파트별 AS 건수",
            color='AS건수',
            color_continuous_scale='Blues'
        )
        fig2.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)

    # 파트별 상세 통계 테이블
    st.subheader("📋 파트별 상세 통계")
    
    # 효율성 지표 추가
    part_stats['건당수리비'] = part_stats['총수리비'] / part_stats['AS건수']
    part_stats['효율성점수'] = (part_stats['AS건수'] / part_stats['총수리비'] * 1000000).round(2)
    
    # 컬럼 순서 정리
    display_stats = part_stats[['정비자소속', 'AS건수', '총수리비', '건당수리비', '평균수리시간', '효율성점수']]
    
    # 수치 포맷팅
    styled_stats = display_stats.style.format({
        'AS건수': '{:,}건',
        '총수리비': '{:,.0f}원',
        '건당수리비': '{:,.0f}원',
        '평균수리시간': '{:.1f}시간',
        '효율성점수': '{:.2f}'
    })
    
    st.dataframe(styled_stats, use_container_width=True)

    st.markdown("---")

    # 파트 선택 및 상세 분석
    st.header("🔍 파트별 상세 분석")
    
    available_parts = df['정비자소속'].dropna().unique()
    selected_parts = st.multiselect(
        "상세 분석할 파트 선택 (최대 3개 권장)", 
        available_parts,
        default=available_parts[:2] if len(available_parts) >= 2 else available_parts
    )

    if selected_parts:
        for i, part in enumerate(selected_parts):
            if i > 0:
                st.markdown("---")
                
            part_data = df[df['정비자소속'] == part]
            
            st.subheader(f"🔧 {part} 파트 상세 분석")
            
            # 파트 KPI
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_cases = len(part_data)
                st.metric("총 AS 건수", f"{total_cases:,}건")
            
            with col2:
                total_cost = part_data['수리비'].sum()
                st.metric("총 수리비", f"{total_cost:,.0f}원")
            
            with col3:
                avg_cost = part_data['수리비'].mean() if total_cases > 0 else 0
                st.metric("평균 수리비", f"{avg_cost:,.0f}원")
            
            with col4:
                avg_time = part_data['수리시간'].mean() if '수리시간' in part_data.columns else 0
                st.metric("평균 수리시간", f"{avg_time:.1f}시간")

            # 파트별 세부 분석
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**🔨 주요 작업 유형**")
                if '작업유형' in part_data.columns:
                    work_types = part_data['작업유형'].value_counts().head(5)
                    for work, count in work_types.items():
                        percentage = (count / len(part_data) * 100)
                        st.write(f"• {work}: {count}건 ({percentage:.1f}%)")
                else:
                    st.info("작업유형 데이터 없음")
            
            with col2:
                st.write("**⚙️ 주요 정비 대상**")
                if '정비대상' in part_data.columns:
                    targets = part_data['정비대상'].value_counts().head(5)
                    for target, count in targets.items():
                        percentage = (count / len(part_data) * 100)
                        st.write(f"• {target}: {count}건 ({percentage:.1f}%)")
                else:
                    st.info("정비대상 데이터 없음")
            
            with col3:
                st.write("**🏢 주요 담당 업체**")
                # 현장명 우선 사용
                if '현장명' in part_data.columns:
                    clients = part_data['현장명'].value_counts().head(5)
                    for client, count in clients.items():
                        percentage = (count / len(part_data) * 100)
                        client_short = client[:15] + "..." if len(str(client)) > 15 else str(client)
                        st.write(f"• {client_short}: {count}건 ({percentage:.1f}%)")
                elif '업체명' in part_data.columns:
                    clients = part_data['업체명'].value_counts().head(5)
                    for client, count in clients.items():
                        percentage = (count / len(part_data) * 100)
                        client_short = client[:15] + "..." if len(str(client)) > 15 else str(client)
                        st.write(f"• {client_short}: {count}건 ({percentage:.1f}%)")
                else:
                    st.info("업체 데이터 없음")

            # 파트별 월별 트렌드
            if '년월' in part_data.columns:
                st.write("**📈 월별 활동 트렌드**")
                
                part_monthly = part_data.groupby('년월').agg({
                    '수리비': 'sum',
                    '관리번호': 'count'
                }).reset_index()
                part_monthly['년월_str'] = part_monthly['년월'].astype(str)
                
                if not part_monthly.empty:
                    fig = go.Figure()
                    
                    # 수리비 트렌드
                    fig.add_trace(go.Scatter(
                        x=part_monthly['년월_str'],
                        y=part_monthly['수리비'],
                        mode='lines+markers',
                        name='월별 수리비',
                        line=dict(color='#FF6B6B', width=2),
                        yaxis='y'
                    ))
                    
                    # AS 건수 트렌드 (보조 축)
                    fig.add_trace(go.Scatter(
                        x=part_monthly['년월_str'],
                        y=part_monthly['관리번호'],
                        mode='lines+markers',
                        name='월별 AS 건수',
                        line=dict(color='#4ECDC4', width=2),
                        yaxis='y2'
                    ))
                    
                    fig.update_layout(
                        title=f"{part} 파트 월별 트렌드",
                        xaxis_title="월",
                        yaxis=dict(title="수리비 (원)", side="left"),
                        yaxis2=dict(title="AS 건수", side="right", overlaying="y"),
                        height=300
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)

            # 상세 분석이 필요한 케이스들
            st.write("**🚨 주의 깊게 봐야 할 케이스들**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 고비용 케이스 찾기
                if part_data['수리비'].sum() > 0:
                    high_cost_threshold = part_data['수리비'].quantile(0.9)
                    high_cost_cases = part_data[part_data['수리비'] > high_cost_threshold]
                    
                    if not high_cost_cases.empty:
                        st.write("🔴 **고비용 수리 케이스들 (상위 10%):**")
                        for idx, case in high_cost_cases.head(5).iterrows():
                            # 업체명 우선 순위: 현장명 > 업체명
                            if '현장명' in case and pd.notna(case['현장명']):
                                업체명 = str(case['현장명'])
                            elif '업체명' in case and pd.notna(case['업체명']):
                                업체명 = str(case['업체명'])
                            else:
                                업체명 = 'N/A'
                            
                            브랜드 = case.get('브랜드', 'N/A')
                            모델명 = case.get('모델명', 'N/A')
                            수리비 = case.get('수리비', 0)
                            
                            업체명_short = 업체명[:15] + "..." if len(업체명) > 15 else 업체명
                            st.write(f"• {업체명_short} - {브랜드} {모델명}")
                            st.write(f"  💰 수리비: {수리비:,.0f}원")
                            
                            if '사용부품' in case and pd.notna(case['사용부품']) and case['사용부품']:
                                parts_list = str(case['사용부품'])[:50] + "..." if len(str(case['사용부품'])) > 50 else str(case['사용부품'])
                                st.write(f"  🔧 사용부품: {parts_list}")
                    else:
                        st.info("고비용 케이스 없음")
                else:
                    st.info("수리비 데이터 없음")
            
            with col2:
                # 반복 수리 케이스
                if '관리번호' in part_data.columns:
                    repeat_cases = part_data['관리번호'].value_counts()
                    repeat_cases = repeat_cases[repeat_cases > 1].head(5)
                    
                    if not repeat_cases.empty:
                        st.write("🔄 **반복 수리 장비들:**")
                        for 관리번호, 횟수 in repeat_cases.items():
                            # 해당 장비의 최신 정보 가져오기
                            equipment_info = part_data[part_data['관리번호'] == 관리번호].iloc[-1]
                            
                            # 업체명 우선 순위: 현장명 > 업체명
                            if '현장명' in equipment_info and pd.notna(equipment_info['현장명']):
                                업체명 = str(equipment_info['현장명'])
                            elif '업체명' in equipment_info and pd.notna(equipment_info['업체명']):
                                업체명 = str(equipment_info['업체명'])
                            else:
                                업체명 = 'N/A'
                            
                            브랜드 = equipment_info.get('브랜드', 'N/A')
                            모델명 = equipment_info.get('모델명', 'N/A')
                            
                            업체명_short = 업체명[:15] + "..." if len(업체명) > 15 else 업체명
                            st.write(f"• {관리번호} ({업체명_short})")
                            st.write(f"  📊 수리횟수: {횟수}회")
                            st.write(f"  🏭 장비: {브랜드} {모델명}")
                    else:
                        st.info("반복 수리 케이스 없음")

            # 파트 성과 요약 (기존 코드)
            st.write("**📊 성과 요약 및 개선 포인트**")
            
            # 전체 평균과 비교
            전체_평균수리비 = df['수리비'].mean()
            파트_평균수리비 = part_data['수리비'].mean()
            
            if 파트_평균수리비 > 전체_평균수리비 * 1.2:
                st.warning(f"⚠️ 평균 수리비가 전체 평균({전체_평균수리비:,.0f}원)보다 {((파트_평균수리비/전체_평균수리비-1)*100):.1f}% 높습니다.")
            elif 파트_평균수리비 < 전체_평균수리비 * 0.8:
                st.success(f"✅ 평균 수리비가 전체 평균보다 {((1-파트_평균수리비/전체_평균수리비)*100):.1f}% 낮습니다.")
            else:
                st.info("💡 평균 수리비가 전체 평균 수준입니다.")

            # 만족도 분석 추가
            if '만족도_평균' in part_data.columns and part_data['만족도_평균'].notna().any():
                st.write("**😊 고객 만족도 분석**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    avg_satisfaction = part_data['만족도_평균'].mean()
                    satisfaction_count = part_data['만족도_평균'].notna().sum()
                    
                    satisfaction_color = "🟢" if avg_satisfaction >= 4.5 else "🟡" if avg_satisfaction >= 4.0 else "🟠" if avg_satisfaction >= 3.5 else "🔴"
                    st.write(f"{satisfaction_color} **평균 만족도**: {avg_satisfaction:.2f}점 ({satisfaction_count}건 응답)")
                    
                    # 전체 평균과 비교
                    전체_평균만족도 = df['만족도_평균'].mean() if '만족도_평균' in df.columns else 0
                    if 전체_평균만족도 > 0:
                        if avg_satisfaction > 전체_평균만족도 * 1.1:
                            st.success(f"✅ 전체 평균({전체_평균만족도:.2f}점)보다 높은 만족도")
                        elif avg_satisfaction < 전체_평균만족도 * 0.9:
                            st.warning(f"⚠️ 전체 평균({전체_평균만족도:.2f}점)보다 낮은 만족도")
                        else:
                            st.info("💡 전체 평균 수준의 만족도")
                
                with col2:
                    # 질문별 만족도 세부 점수
                    satisfaction_detail_cols = [col for col in part_data.columns if '만족도_' in col and col != '만족도_평균']
                    if satisfaction_detail_cols:
                        st.write("**질문별 세부 점수:**")
                        for col in satisfaction_detail_cols:
                            category = col.replace('만족도_', '')
                            score = part_data[col].mean()
                            if score > 0:
                                score_icon = "🟢" if score >= 4.5 else "🟡" if score >= 4.0 else "🔴"
                                st.write(f"  {score_icon} {category}: {score:.2f}점")
                
                # 만족도가 낮은 케이스 분석
                low_satisfaction_cases = part_data[part_data['만족도_평균'] < 3.5]
                if not low_satisfaction_cases.empty:
                    st.write(f"**😞 낮은 만족도 케이스**: {len(low_satisfaction_cases)}건")
                    
                    # 낮은 만족도의 주요 원인 분석
                    if '작업유형' in low_satisfaction_cases.columns:
                        low_work_types = low_satisfaction_cases['작업유형'].value_counts().head(3)
                        st.write("주요 작업 유형:")
                        for work_type, count in low_work_types.items():
                            st.write(f"  • {work_type}: {count}건")
else:
    st.error("정비자소속 데이터가 없습니다. 데이터를 확인해주세요.")

# 파트 간 비교 분석
if 'selected_parts' in locals() and len(selected_parts) > 1:
    st.markdown("---")
    st.header("⚖️ 선택된 파트 간 비교 분석")
    
    comparison_data = []
    for part in selected_parts:
        part_data = df[df['정비자소속'] == part]
        comparison_data.append({
            '파트': part,
            'AS건수': len(part_data),
            '총수리비': part_data['수리비'].sum(),
            '평균수리비': part_data['수리비'].mean(),
            '평균수리시간': part_data['수리시간'].mean() if '수리시간' in part_data.columns else 0
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    # 비교 차트
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='총수리비',
            title="파트별 총 수리비 비교",
            color='총수리비',
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            comparison_df,
            x='파트',
            y='평균수리비',
            title="파트별 평균 수리비 비교",
            color='평균수리비',
            color_continuous_scale='Plasma'
        )
        st.plotly_chart(fig, use_container_width=True)

# 전체 파트 성과 랭킹
st.markdown("---")
st.header("🏆 파트 성과 랭킹")

if '정비자소속' in df.columns:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 수리비 효율성 랭킹 (낮을수록 좋음)")
        efficiency_ranking = part_stats.nsmallest(10, '건당수리비')[['정비자소속', '건당수리비', 'AS건수']]
        
        for idx, (_, row) in enumerate(efficiency_ranking.iterrows()):
            medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
            st.write(f"{medal} **{row['정비자소속']}**")
            st.write(f"   건당 수리비: {row['건당수리비']:,.0f}원 ({row['AS건수']}건)")
    
    with col2:
        st.subheader("📊 업무량 랭킹 (AS 건수 기준)")
        volume_ranking = part_stats.nlargest(10, 'AS건수')[['정비자소속', 'AS건수', '총수리비']]
        
        for idx, (_, row) in enumerate(volume_ranking.iterrows()):
            medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx+1}."
            st.write(f"{medal} **{row['정비자소속']}**")
            st.write(f"   AS 건수: {row['AS건수']:,}건 (총 {row['총수리비']:,.0f}원)")

# 데이터 다운로드
st.markdown("---")
st.subheader("📥 분석 결과 다운로드")

col1, col2 = st.columns(2)

with col1:
    if not part_stats.empty:
        csv_data = part_stats.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 파트별 통계 다운로드 (CSV)",
            data=csv_data,
            file_name="파트별_상세통계.csv",
            mime="text/csv"
        )

with col2:
    if '정비자소속' in df.columns:
        detailed_data = df[['정비자소속', '관리번호', '정비일자', '수리비', '작업유형', '정비대상', '현장명']].copy()
        detailed_csv = detailed_data.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📄 상세 데이터 다운로드 (CSV)",
            data=detailed_csv,
            file_name="파트별_상세데이터.csv",
            mime="text/csv"
        )
