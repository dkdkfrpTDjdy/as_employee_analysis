# 3. 업체별 디마케팅 분석
# pages/03_업체별_디마케팅_분석.py

st.title("🏢 업체별 디마케팅 분석")

# 업체별 종합 점수 계산
def calculate_client_score(client_data):
    # 여러 지표를 종합한 점수
    avg_cost_per_case = client_data['수리비'].sum() / len(client_data)
    case_frequency = len(client_data)  # 전체 기간 대비
    
    # 점수 계산 (낮을수록 좋음)
    cost_score = avg_cost_per_case / df['수리비'].mean()  # 평균 대비 배수
    frequency_score = case_frequency / (len(df) / df['현장명'].nunique())  # 평균 대비 배수
    
    total_score = (cost_score * 0.6) + (frequency_score * 0.4)
    return total_score, avg_cost_per_case, case_frequency

# 모든 업체 분석
client_analysis = []
for client in df['현장명'].unique():
    if pd.notna(client):
        client_data = df[df['현장명'] == client]
        score, avg_cost, frequency = calculate_client_score(client_data)
        
        client_analysis.append({
            '업체명': client,
            '종합점수': score,
            '총_수리비': client_data['수리비'].sum(),
            '평균_건당수리비': avg_cost,
            'AS_건수': frequency,
            '최근_수리일': client_data['정비일자'].max(),
        })

client_df = pd.DataFrame(client_analysis)

# 디마케팅 대상 업체 (점수 높은 순)
st.subheader("🚨 디마케팅 검토 대상 업체")

risky_clients = client_df.nlargest(10, '종합점수')

for idx, client in risky_clients.iterrows():
    risk_level = "🔴 HIGH" if client['종합점수'] > 2.0 else "🟡 MID" if client['종합점수'] > 1.5 else "🟢 LOW"
    
    with st.expander(f"{risk_level} {client['업체명']} (점수: {client['종합점수']:.2f})"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**총 수리비**: {client['총_수리비']:,.0f}원")
            st.write(f"**AS 건수**: {client['AS_건수']}건")
            st.write(f"**건당 평균**: {client['평균_건당수리비']:,.0f}원")
        
        with col2:
            st.write(f"**최근 수리일**: {client['최근_수리일'].strftime('%Y-%m-%d')}")
            
            # 해당 업체의 주요 문제점 분석
            client_detail = df[df['현장명'] == client['업체명']]
            
            # 주요 고장 유형
            main_faults = client_detail['작업유형'].value_counts().head(3)
            st.write("**주요 고장 유형**:")
            for fault, count in main_faults.items():
                st.write(f"• {fault}: {count}건")