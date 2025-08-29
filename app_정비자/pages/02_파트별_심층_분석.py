# 2. 상세 분석 페이지들
# pages/02_파트별_심층_분석.py

st.title("🔍 파트별 심층 분석")

# 파트 선택
selected_parts = st.multiselect("분석할 파트 선택", df['정비자소속'].unique())

if selected_parts:
    for part in selected_parts:
        part_data = df[df['정비자소속'] == part]
        
        st.subheader(f"📊 {part} 파트 상세 분석")
        
        # 해당 파트가 주로 하는 일
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**주요 작업 유형**")
            work_types = part_data['작업유형'].value_counts().head(5)
            for work, count in work_types.items():
                st.write(f"• {work}: {count}건")
        
        with col2:
            st.write("**주요 정비 대상**")
            targets = part_data['정비대상'].value_counts().head(5)
            for target, count in targets.items():
                st.write(f"• {target}: {count}건")
        
        with col3:
            st.write("**주요 브랜드**")
            brands = part_data['브랜드'].value_counts().head(5)
            for brand, count in brands.items():
                st.write(f"• {brand}: {count}건")
        
        # 파트별 월별 트렌드
        part_monthly = part_data.groupby('년월').agg({
            '수리비': 'sum',
            '관리번호': 'count'
        })
        
        # 상세 분석을 위한 드릴다운 기능
        st.write("**상세 분석이 필요한 케이스들:**")
        
        # 고비용 케이스 찾기
        high_cost_cases = part_data[part_data['수리비'] > part_data['수리비'].quantile(0.9)]
        if not high_cost_cases.empty:
            st.write("🔴 **고비용 수리 케이스들:**")
            for idx, case in high_cost_cases.head(5).iterrows():
                st.write(f"• {case.get('현장명', 'N/A')} - {case.get('브랜드', 'N/A')} {case.get('모델명', 'N/A')} - {case['수리비']:,.0f}원")
                if '사용부품' in case and pd.notna(case['사용부품']):
                    st.write(f"  └ 사용부품: {case['사용부품']}")