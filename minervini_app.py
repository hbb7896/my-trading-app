import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# 1. 페이지 설정
st.set_page_config(page_title="Trading Master Dashboard", page_icon="💎", layout="wide")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 한국 종목 리스트 ---
@st.cache_data(ttl=3600)
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Market']]
    except Exception as e:
        return pd.DataFrame()

# --- PF 가이드 ---
def show_pf_guide():
    with st.expander("ℹ️ 마크 미너비니의 PF(프로핏 팩터) 점수표 보기", expanded=False):
        st.markdown("""
        | PF 범위 | 상태 | 평가 |
        | :--- | :--- | :--- |
        | **1.0 이하** | 🚨 위험 | 손실이 더 큰 상태 |
        | **1.5 ~ 2.0** | 👍 훌륭함 | 안정적 수익 구간 |
        | **3.0 이상** | 💎 전설 | 초고수 (Legendary) |
        """)

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
        
        # 습관 분석용 컬럼 처리 (과거 데이터는 None으로 처리)
        if 'Mistake_Tags' not in df.columns: df['Mistake_Tags'] = None
        if 'Emotion' not in df.columns: df['Emotion'] = None
        if 'Discipline' not in df.columns: df['Discipline'] = None
        
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Ticker', 'P_L_Amount', 'ROI_Percent', 'Mistake_Tags', 'Emotion', 'Discipline', 'Memo'])

df = load_data()
krx_list = get_krx_list() 

# --- 사이드바 입력 ---
st.sidebar.header("📝 매매 기록 입력")
with st.sidebar.form("quick_input", clear_on_submit=True):
    date = st.date_input("일자", datetime.today())
    ticker = st.text_input("종목명 (예: 삼성전자)").strip()
    pn_l = st.number_input("손익금 (원)", value=0)
    roi = st.number_input("수익률 (%)", value=0.0, format="%.2f")
    
    st.divider()
    st.caption("🧠 습관 분석 (신규 입력부터 적용)")
    mistake_options = ["정상매매", "뇌동매매", "추격매수", "손절늦음", "익절너무빠름", "시장하락", "비중위반"]
    tags = st.multiselect("매매 특이사항", mistake_options, default=["정상매매"])
    tags_str = ", ".join(tags)
    
    emotion = st.selectbox("매수 당시 감정", ["평온함", "흥분/조급함(FOMO)", "공포", "복수심(화남)", "지루함"])
    discipline = st.radio("원칙을 지켰습니까?", ["Yes (잘한 매매)", "No (반성 필요)"], horizontal=True)
    
    memo = st.text_input("메모")
    
    submit = st.form_submit_button("기록 저장")

    if submit:
        if ticker:
            new_data = pd.DataFrame([{
                'Date': date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'P_L_Amount': pn_l,
                'ROI_Percent': roi,
                'Mistake_Tags': tags_str,
                'Emotion': emotion,
                'Discipline': discipline,
                'Memo': memo
            }])
            
            if df.empty: updated_df = new_data
            else:
                df_temp = load_data()
                df_temp['Date'] = df_temp['Date'].dt.strftime('%Y-%m-%d')
                updated_df = pd.concat([df_temp, new_data], ignore_index=True)

            conn.update(worksheet=0, data=updated_df)
            st.success(f"✅ {ticker} 저장 완료!"); st.rerun()
        else:
            st.error("종목명을 입력해주세요.")

if krx_list.empty:
    st.sidebar.caption("⚠️ 리스트 로딩 실패")
else:
    st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 차트", "📅 월별", "📆 연도별", "📋 원본", "❌ 습관분석", "🧮 수익쿠션"])
    
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_win = wins['ROI_Percent'].mean() if not wins.empty else 0
    avg_loss = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
    risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    avg_roi = df['ROI_Percent'].mean()

    # === TAB 1: 차트 ===
    with tab1:
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        kpi4.metric("평균 손익비", f"{risk_reward_ratio:.2f}")
        
        st.divider()
        st.subheader("🚀 내 계좌 vs KOSPI 지수")
        
        daily_df = df.groupby('Date')['P_L_Amount'].sum().reset_index().sort_values('Date')
        daily_df['Cumulative'] = daily_df['P_L_Amount'].cumsum()
        
        try:
            start = daily_df['Date'].min().strftime('%Y-%m-%d')
            kospi = yf.download("^KS11", start=start, progress=False)['Close'].reset_index()
            kospi.columns = ['Date', 'KOSPI']
            kospi['Date'] = pd.to_datetime(kospi['Date']).dt.tz_localize(None)
            
            base = alt.Chart(daily_df).encode(x='Date:T')
            my_chart = base.mark_line(color='#00AA00', strokeWidth=3).encode(y=alt.Y('Cumulative:Q', title='내 수익'), tooltip=['Date', 'Cumulative'])
            kospi_chart = alt.Chart(kospi).mark_line(color='#FF4444', strokeDash=[5,5]).encode(x='Date:T', y=alt.Y('KOSPI:Q', title='KOSPI', scale=alt.Scale(zero=False)))
            st.altair_chart(alt.layer(my_chart, kospi_chart).resolve_scale(y='independent'), use_container_width=True)
        except:
            st.line_chart(daily_df.set_index('Date')['Cumulative'])
        
        st.subheader("📊 월별 손익 흐름")
        st.bar_chart(df.groupby('YearMonth')['P_L_Amount'].sum())

    # === TAB 2: 월별 ===
    with tab2:
        st.subheader("📅 월별 상세 성적표")
        monthly_stats = []
        for ym, group in df.groupby('YearMonth'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            
            m_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            m_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            m_wl_ratio = m_avg_gain / m_avg_loss if m_avg_loss > 0 else 0
            
            monthly_stats.append({
                "기간": str(ym), 
                "총 손익": float(group['P_L_Amount'].sum()), 
                "승률": float((len(g_wins)/len(group))*100), 
                "손익비": float(m_wl_ratio),
                "PF": float(pf)
            })
        
        m_df = pd.DataFrame(monthly_stats).sort_values("기간", ascending=False)
        st.dataframe(
            m_df.style.format({
                "총 손익": "{:,.0f}원", 
                "승률": "{:.1f}%", 
                "손익비": "{:.2f}", 
                "PF": "{:.2f}"
            }).background_gradient(subset=['총 손익'], cmap='RdYlGn'), 
            use_container_width=True
        )
        show_pf_guide()

    # === TAB 3: 연도별 ===
    with tab3:
        st.subheader("📆 연도별 종합 성적표")
        yearly_stats = []
        for y, group in df.groupby('Year'):
            g_wins = group[group['ROI_Percent'] > 0]; g_losses = group[group['ROI_Percent'] <= 0]
            gross_profit = group[group['P_L_Amount'] > 0]['P_L_Amount'].sum()
            gross_loss = abs(group[group['P_L_Amount'] <= 0]['P_L_Amount'].sum())
            pf = gross_profit / gross_loss if gross_loss > 0 else 0
            
            y_avg_gain = g_wins['ROI_Percent'].mean() if not g_wins.empty else 0
            y_avg_loss = abs(g_losses['ROI_Percent'].mean()) if not g_losses.empty else 0
            y_wl_ratio = y_avg_gain / y_avg_loss if y_avg_loss > 0 else 0
            
            yearly_stats.append({
                "연도": int(y), 
                "총 손익": float(group['P_L_Amount'].sum()), 
                "승률": float((len(g_wins)/len(group))*100), 
                "손익비": float(y_wl_ratio),
                "PF": float(pf)
            })
            
        y_df = pd.DataFrame(yearly_stats).sort_values("연도", ascending=False)
        st.dataframe(
            y_df.style.format({
                "총 손익": "{:,.0f}원", 
                "승률": "{:.1f}%", 
                "손익비": "{:.2f}", 
                "PF": "{:.2f}"
            }).background_gradient(subset=['총 손익'], cmap='Greens'), 
            use_container_width=True
        )
        show_pf_guide()

    # === TAB 4: 원본 ===
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === TAB 5: 습관 분석 ===
    with tab5:
        st.subheader("🧠 나의 트레이딩 습관 분석 (오답노트)")
        valid_tags = df['Mistake_Tags'].dropna(); valid_tags = valid_tags[valid_tags != ""]
        valid_disc = df['Discipline'].dropna(); valid_disc = valid_disc[valid_disc != ""]

        c1, c2 = st.columns(2)
        with c1:
            st.write("🛑 **손실 원인 TOP 5 (신규)**")
            if not valid_tags.empty:
                all_tags = valid_tags.astype(str).str.split(', ').explode()
                tag_counts = all_tags.value_counts().reset_index()
                tag_counts.columns = ['원인', '횟수']
                base = alt.Chart(tag_counts).encode(x=alt.X('횟수:Q'), y=alt.Y('원인:N', sort='-x'), color=alt.condition(alt.datum.원인 == '정상매매', alt.value('green'), alt.value('red')))
                st.altair_chart(base.mark_bar(), use_container_width=True)
            else: st.info("데이터가 쌓이면 그래프가 표시됩니다.")

        with c2:
            st.write("⚖️ **원칙 준수율 (신규)**")
            if not valid_disc.empty:
                d_counts = valid_disc.value_counts().reset_index()
                d_counts.columns = ['상태', '횟수']
                pie = alt.Chart(d_counts).mark_arc(innerRadius=50).encode(theta=alt.Theta(field="횟수", type="quantitative"), color=alt.Color(field="상태", type="nominal", scale=alt.Scale(range=['#ff4b4b', '#36bd62'])))
                st.altair_chart(pie, use_container_width=True)
            else: st.info("데이터가 쌓이면 그래프가 표시됩니다.")

        st.divider(); st.write("📉 **손실 거래 복기**")
        bad = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        if not bad.empty:
            for i, row in bad.iterrows():
                tags_disp = row.get('Mistake_Tags') if row.get('Mistake_Tags') else "-"
                emo_disp = row.get('Emotion') if row.get('Emotion') else "-"
                disc_disp = row.get('Discipline') if row.get('Discipline') else "-"
                with st.expander(f"{row['Date'].strftime('%Y-%m-%d')} | {row['Ticker']} | {row['P_L_Amount']:,.0f}원 ({row['ROI_Percent']}%)"):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**😡 원인:** {tags_disp}"); c1.markdown(f"**🧠 감정:** {emo_disp}")
                    c2.markdown(f"**⚖️ 원칙:** {disc_disp}"); st.info(f"📝 메모: {row['Memo']}")
        else: st.success("손실 기록이 없습니다!")

    # === TAB 6: 수익쿠션 계산기 (안전율 + 역산기능 포함) ===
    with tab6:
        st.subheader("🧮 수익 쿠션 계산기 (Position Sizing)")
        st.info("💡 **수익 쿠션:** 시장이 하락하면 수익금도 줄어듭니다. 이를 대비해 '안전율(보수적 계산)'을 적용하여 베팅 금액을 산출하세요.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 1️⃣ 내 자산 입력")
            total_account = st.number_input("총 추정자산 (예수금+주식)", value=10000000, step=100000)
            open_profit = st.number_input("현재 총 수익금 (평가손익)", value=0, step=10000)
            
        with c2:
            st.markdown("### 2️⃣ 리스크 시뮬레이션")
            current_buy_amt = st.number_input("현재 보유주식 총 매수금액", value=5000000, step=100000)
            loss_cut_pct = st.number_input("평균 손절 계획 (%)", value=5.0, step=0.5)
            open_risk = current_buy_amt * (loss_cut_pct / 100)
            st.error(f"📉 예상 손실금: **-{open_risk:,.0f}원**")

        st.divider()
        
        # 안전율 슬라이더
        st.subheader("🛡️ 안전한 베팅 금액 계산 (역산)")
        safety_margin = st.slider("현재 수익금의 몇 %만 쿠션으로 사용할까요? (안전율)", 10, 100, 50, 10)
        
        if open_profit > 0:
            safe_cushion = open_profit * (safety_margin / 100)
            target_sl_pct = st.slider("신규 진입 종목의 손절폭 (%)", 1.0, 30.0, 5.0, 0.5)
            investable = safe_cushion / (target_sl_pct / 100)
            
            # 상태 판독
            cushion_percent = (open_profit / total_account) * 100
            st.markdown(f"""
            #### 📊 분석 결과
            * 현재 수익 쿠션: **{cushion_percent:.2f}%**
            * 확보된 안전 쿠션: **{safe_cushion:,.0f}원** (수익금의 {safety_margin}%)
            
            #### 💰 추천 매수 금액: **:blue[{investable:,.0f}원]**
            * 손절을 **-{target_sl_pct}%**로 잡았을 때, **{investable:,.0f}원**어치를 사면
            * 손절 시 정확히 안전 쿠션(**{safe_cushion:,.0f}원**) 내에서 방어됩니다.
            """)
            
            if open_profit > open_risk:
                st.success("💎 **House Money 상태!** 원금 손실 위험 0입니다.")
            else:
                st.warning(f"⚠️ **주의 필요:** 현재 리스크(-{open_risk:,.0f}원)가 수익금보다 큽니다.")
        else:
            st.warning("⚠️ 현재 수익 쿠션(평가수익)이 없어서 계산할 수 없습니다. (원금 방어에 집중하세요!)")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
