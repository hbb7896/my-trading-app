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

# --- [유지] 한국 종목 리스트 가져오기 ---
@st.cache_data(ttl=3600)
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Market']]
    except Exception as e:
        return pd.DataFrame()

# --- [유지] PF 점수표 ---
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
        
        for col in ['P_L_Amount', 'ROI_Percent']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
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
    st.caption("🧠 심리 및 원칙 분석 (신규 입력부터 적용)")
    
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
    st.sidebar.caption("⚠️ 리스트 로딩 실패 (수동 입력만 가능)")
else:
    st.sidebar.caption(f"✅ {len(krx_list):,}개 종목 연결됨")

# --- 메인 화면 ---
st.title("💎 Trading Master Dashboard")

if not df.empty:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 차트 대시보드", "📅 월별 분석", "📆 연도별 분석", "📋 데이터 원본", "❌ 습관 분석", "🛡️ 수익쿠션"])
    
    df['Year'] = df['Date'].dt.year
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
    
    total_trades = len(df)
    wins = df[df['ROI_Percent'] > 0]
    losses = df[df['ROI_Percent'] <= 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_roi = df['ROI_Percent'].mean()

    # === TAB 1: 차트 ===
    with tab1:
        st.subheader("📍 Overall Performance")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("총 누적 손익", f"{df['P_L_Amount'].sum():,.0f}원")
        kpi2.metric("승률", f"{win_rate:.1f}%")
        kpi3.metric("평균 수익률", f"{avg_roi:.2f}%")
        
        avg_loss_val = abs(losses['ROI_Percent'].mean()) if not losses.empty else 0
        avg_win_val = wins['ROI_Percent'].mean() if not wins.empty else 0
        rr = avg_win_val / avg_loss_val if avg_loss_val > 0 else 0
        kpi4.metric("평균 손익비", f"{rr:.2f}")
        
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
            monthly_stats.append({
                "기간": ym, "총 손익": group['P_L_Amount'].sum(), "승률": f"{(len(g_wins)/len(group))*100:.1f}%", "PF": f"{pf:.2f}"
            })
        st.dataframe(pd.DataFrame(monthly_stats).sort_values("기간", ascending=False).style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='RdYlGn'), use_container_width=True)
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
            yearly_stats.append({
                "연도": y, "총 손익": group['P_L_Amount'].sum(), "승률": f"{(len(g_wins)/len(group))*100:.1f}%", "PF": f"{pf:.2f}"
            })
        st.dataframe(pd.DataFrame(yearly_stats).sort_values("연도", ascending=False).style.format({"총 손익": "{:,.0f}원"}).background_gradient(subset=['총 손익'], cmap='Greens'), use_container_width=True)
        show_pf_guide()

    # === TAB 4: 원본 ===
    with tab4:
        st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)

    # === TAB 5: 습관 분석 ===
    with tab5:
        st.subheader("🧠 나의 트레이딩 습관 분석 (오답노트)")
        valid_tags = df['Mistake_Tags'].dropna()
        valid_tags = valid_tags[valid_tags != ""]
        valid_disc = df['Discipline'].dropna()
        valid_disc = valid_disc[valid_disc != ""]

        c1, c2 = st.columns(2)
        with c1:
            st.write("🛑 **손실 원인 TOP 5**")
            if not valid_tags.empty:
                all_tags = valid_tags.astype(str).str.split(', ').explode()
                tag_counts = all_tags.value_counts().reset_index()
                tag_counts.columns = ['원인', '횟수']
                base = alt.Chart(tag_counts).encode(
                    x=alt.X('횟수:Q'), y=alt.Y('원인:N', sort='-x'),
                    color=alt.condition(alt.datum.원인 == '정상매매', alt.value('green'), alt.value('red'))
                )
                st.altair_chart(base.mark_bar(), use_container_width=True)
            else:
                st.info("분석할 신규 데이터가 없습니다.")

        with c2:
            st.write("⚖️ **원칙 준수율**")
            if not valid_disc.empty:
                d_counts = valid_disc.value_counts().reset_index()
                d_counts.columns = ['상태', '횟수']
                pie = alt.Chart(d_counts).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="횟수", type="quantitative"),
                    color=alt.Color(field="상태", type="nominal", scale=alt.Scale(range=['#ff4b4b', '#36bd62']))
                )
                st.altair_chart(pie, use_container_width=True)
            else:
                st.info("분석할 신규 데이터가 없습니다.")

        st.divider()
        bad = df[df['ROI_Percent'] < 0].sort_values('Date', ascending=False)
        if not bad.empty:
            for i, row in bad.iterrows():
                with st.expander(f"{row['Date'].strftime('%Y-%m-%d')} | {row['Ticker']} | {row['P_L_Amount']:,.0f}원"):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**😡 원인:** {row.get('Mistake_Tags', '-')}")
                    c2.markdown(f"**⚖️ 원칙:** {row.get('Discipline', '-')}")
                    st.info(f"📝 메모: {row['Memo']}")
        else:
            st.success("손실 기록이 없습니다!")

    # === [NEW] TAB 6: 수익 쿠션 계산기 (러프한 계산 기능 추가) ===
    with tab6:
        st.subheader("🛡️ 수익 쿠션 (Profit Cushion) 계산기")
        st.caption("현재 보유 중인 종목의 총 매입금액을 입력하면, 자동으로 오픈 리스크(Open Risk)를 계산해 줍니다.")
        
        st.divider()
        
        # 1. 올해 실현 손익 (자동)
        this_year = datetime.now().year
        ytd_df = df[df['Year'] == this_year]
        realized_ytd = ytd_df['P_L_Amount'].sum()
        
        col_calc1, col_calc2 = st.columns(2)
        
        with col_calc1:
            st.write("📊 **포지션 정보 입력**")
            
            # 입력 방식 선택 (라디오 버튼)
            calc_mode = st.radio("계산 방식 선택", ["⚡ 간편 입력 (총 매입금액만 입력)", "📝 상세 입력 (리스크 직접 설정)"], horizontal=True)
            
            if calc_mode == "⚡ 간편 입력 (총 매입금액만 입력)":
                total_buy = st.number_input("총 매입금액 합계 (원)", min_value=0, value=0, step=1000000)
                risk_pct = st.number_input("예상 손절률 (%)", value=6.0, step=0.5, help="평균적으로 적용할 손절 %입니다. (기본값: -6%)")
                
                # 자동 계산된 리스크
                open_risk = total_buy * (risk_pct / 100)
                st.info(f"💡 예상 오픈 리스크: **-{open_risk:,.0f}원** (매입금액의 {risk_pct}%)")
                
            else:
                # 상세 입력 모드 (기존 방식)
                open_risk = st.number_input("총 오픈 리스크 (손절 시 잃을 금액)", min_value=0, value=0)
                st.caption("※ 각 종목별 손절 금액을 모두 더해서 입력하세요.")

            open_profit = st.number_input("총 미실현 수익 (현재 평가수익금)", value=0)
            
        with col_calc2:
            st.write("🧮 **쿠션 진단 결과**")
            
            # 쿠션 계산
            cushion = realized_ytd + open_profit - open_risk
            
            st.markdown(f"**💰 올해 실현 수익 (YTD):** `{realized_ytd:,.0f}원`")
            st.markdown(f"**📈 미실현 수익 (Open Profit):** `{open_profit:,.0f}원`")
            st.markdown(f"**💀 오픈 리스크 (Open Risk):** `-{open_risk:,.0f}원`")
            st.divider()
            
            if cushion > 0:
                st.success(f"### 🎉 수익 쿠션: +{cushion:,.0f}원")
                st.write("✅ **안전함 (Safe)**")
                st.write("시장에서 번 돈으로 리스크를 완벽하게 커버하고 있습니다.")
            elif cushion == 0:
                st.warning(f"### 😐 수익 쿠션: 0원 (본전)")
                st.write("⚠️ **주의 (Caution)**")
                st.write("여유 자금이 없습니다. 손실이 나면 원금이 줄어듭니다.")
            else:
                st.error(f"### 🚨 수익 쿠션: {cushion:,.0f}원")
                st.write("🛑 **위험 (Danger)**")
                st.write("원금 손실 구간입니다. 포지션 크기를 줄이고 방어적으로 매매하세요.")

else:
    st.info("👈 사이드바에 매매 기록을 입력하면 대시보드가 활성화됩니다.")
