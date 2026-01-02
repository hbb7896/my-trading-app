import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet=0, ttl=0)
        if df.empty:
             return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])
        
        df = df.dropna(subset=['Date'])
        
        # 숫자 변환
        for col in ['P_L_Amount', 'ROI_Percent']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        # [NEW] 새 컬럼이 없으면 기본값으로 생성 (에러 방지)
        if 'Mistake_Tags' not in df.columns: df['Mistake_Tags'] = ""
        if 'Emotion' not in df.columns: df['Emotion'] = "평온함"
        if 'Discipline' not in df.columns: df['Discipline'] = "Yes"
        
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])

df = load_data()

# --- 사이드바 입력 (기능 업그레이드) ---
st.sidebar.header("📝 매매 기록")
with st.sidebar.form("input"):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명").strip()
    pn_l = st.number_input("손익금", step=1000)
    roi = st.number_input("수익률(%)", step=0.1, format="%.2f")
    
    st.divider()
    st.caption("🧠 심리 및 원칙 분석")
    
    # 1. 손실 원인 태그 (복수 선택 가능)
    mistake_options = ["정상매매", "뇌동매매", "추격매수", "손절늦음", "익절너무빠름", "시장하락", "비중위반"]
    tags = st.multiselect("매매 특이사항 (손실 원인)", mistake_options, default=["정상매매"])
    tags_str = ", ".join(tags) # 저장할 때는 문자열로 합침
    
    # 2. 감정 상태
    emotion = st.selectbox("매수 당시 감정", ["평온함", "흥분/조급함(FOMO)", "공포", "복수심(화남)", "지루함"])
    
    # 3. 원칙 준수 여부
    discipline = st.radio("원칙을 지켰습니까?", ["Yes (잘한 매매)", "No (반성 필요)"], horizontal=True)
    
    memo = st.text_input("상세 메모")
    
    if st.form_submit_button("저장"):
        new = pd.DataFrame([{
            'Date': date.strftime('%Y-%m-%d'), 'Ticker': ticker, 
            'P_L_Amount': pn_l, 'ROI_Percent': roi, 
            'Mistake_Tags': tags_str, 'Emotion': emotion, 
            'Discipline': discipline, 'Memo': memo
        }])
        conn.update(worksheet=0, data=pd.concat([load_data(), new], ignore_index=True))
        st.success("저장 완료!"); st.rerun()

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 차트", "📅 월별", "📆 연도별", "📋 원본", "❌ 습관 분석"])
    
    # 데이터 가공
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    df['Year'] = df['Date'].dt.year
    
    # === TAB 1: 차트 ===
    with tab1:
        st.subheader("📍 요약")
        c1, c2, c3, c4 = st.columns(4)
        wins = df[df['ROI_Percent']>0]
        losses = df[df['ROI_Percent']<=0]
        win_rate = len(wins)/len(df)*100 if len(df)>0 else 0
        avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
        rr = (wins['ROI_Percent'].mean()/avg_loss) if avg_loss>0 else 0
        
        c1.metric("총 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        c2.metric("승률", f"{win_rate:.1f}%")
        c3.metric("평균수익", f"{df['ROI_Percent'].mean():.2f}%")
        c4.metric("손익비", f"{rr:.2f}")

        st.divider()
        st.subheader("🚀 자산 우상향 곡선")
        daily = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily['Cum'] = daily['P_L_Amount'].cumsum()
        st.line_chart(daily.set_index('Date')['Cum'], color='#00AA00')

    # === TAB 2, 3: 통계 ===
    with tab2:
        st.subheader("월별 성적")
        monthly = []
        for ym, g in df.groupby('YearMonth'):
            p = g[g['P_L_Amount']>0]['P_L_Amount'].sum()
            l = abs(g[g['P_L_Amount']<=0]['P_L_Amount'].sum())
            pf = p/l if l>0 else 0
            monthly.append({'기간':ym, '손익':g['P_L_Amount'].sum(), 'PF':f"{pf:.2f}"})
        st.dataframe(pd.DataFrame(monthly).sort_values('기간', ascending=False).style.format({'손익':'{:,.0f}'}), use_container_width=True)
        
    with tab3:
        st.subheader("연도별 성적")
        yearly = []
        for y, g in df.groupby('Year'):
            p = g[g['P_L_Amount']>0]['P_L_Amount'].sum()
            l = abs(g[g['P_L_Amount']<=0]['P_L_Amount'].sum())
            pf = p/l if l>0 else 0
            yearly.append({'연도':y, '손익':g['P_L_Amount'].sum(), 'PF':f"{pf:.2f}"})
        st.dataframe(pd.DataFrame(yearly).sort_values('연도', ascending=False).style.format({'손익':'{:,.0f}'}), use_container_width=True)

    with tab4: st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === [핵심] TAB 5: 습관 분석 리포트 ===
    with tab5:
        st.subheader("🧠 나의 트레이딩 습관 분석 (오답노트)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("🛑 **가장 큰 손실 원인 (Top 5)**")
            # 태그 분리 및 카운트
            all_tags = df['Mistake_Tags'].astype(str).str.split(', ').explode()
            tag_counts = all_tags.value_counts().reset_index()
            tag_counts.columns = ['원인', '횟수']
            # 차트
            base = alt.Chart(tag_counts).encode(
                x=alt.X('횟수:Q'),
                y=alt.Y('원인:N', sort='-x'),
                color=alt.condition(
                    alt.datum.원인 == '정상매매', alt.value('green'), alt.value('red') # 정상매매는 초록, 나머지는 빨강
                )
            )
            st.altair_chart(base.mark_bar(), use_container_width=True)
            st.caption("▲ 빨간 막대가 길어질수록 그 습관을 고쳐야 합니다.")

        with col2:
            st.write("⚖️ **원칙 준수율**")
            if 'Discipline' in df.columns:
                disc_counts = df['Discipline'].value_counts().reset_index()
                disc_counts.columns = ['준수여부', '횟수']
                
                pie = alt.Chart(disc_counts).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="횟수", type="quantitative"),
                    color=alt.Color(field="준수여부", type="nominal", scale=alt.Scale(domain=['Yes (잘한 매매)', 'No (반성 필요)'], range=['#36bd62', '#ff4b4b']))
                )
                st.altair_chart(pie, use_container_width=True)
            else:
                st.info("데이터가 쌓이면 원칙 준수율이 표시됩니다.")

        st.divider()
        st.write("📉 **손실 거래 복기 (Bad Trades)**")
        bad_trades = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        
        if not bad_trades.empty:
            for idx, row in bad_trades.iterrows():
                with st.expander(f"{row['Date'].strftime('%Y-%m-%d')} | {row['Ticker']} | {row['P_L_Amount']:,.0f}원 ({row['ROI_Percent']}%)"):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**😡 손실 원인:** `{row.get('Mistake_Tags', '-')}`")
                    c1.markdown(f"**🧠 당시 감정:** {row.get('Emotion', '-')}")
                    c2.markdown(f"**⚖️ 원칙 준수:** {row.get('Discipline', '-')}")
                    st.info(f"📝 **메모:** {row['Memo']}")
        else:
            st.success("손실 기록이 없습니다. 완벽합니다!")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")

