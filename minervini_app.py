import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt

from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

import json
import re

# AI
import google.generativeai as genai
from PIL import Image


# =========================================================
# 1. PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Trading Master Dashboard",
    page_icon="💎",
    layout="wide"
)


# =========================================================
# 2. GOOGLE SHEETS
# =========================================================

conn = st.connection(
    "gsheets",
    type=GSheetsConnection
)


# =========================================================
# 3. DATA SCHEMA
# =========================================================

REQUIRED_COLUMNS = [
    "Date",
    "Ticker",

    # 거래금액
    "Buy_Amount",
    "Sell_Amount",
    "P_L_Amount",
    "ROI_Percent",

    # 리스크
    "Entry_Price",
    "Stop_Price",
    "Target_Price",
    "Risk_Amount",
    "R_Multiple",

    # 매매 기록
    "Strategy",
    "Entry_Reason",
    "Mistake_Tags",
    "Emotion",
    "Discipline",
    "Memo",

    # AI
    "AI_Analysis"
]


# =========================================================
# 4. LOAD DATA
# =========================================================

@st.cache_data(ttl=0)
def load_data():

    try:

        df = conn.read(
            worksheet=0,
            ttl=0
        )

        if df.empty:
            return pd.DataFrame(
                columns=REQUIRED_COLUMNS
            )

        df = df.copy()

        # -----------------------------------------
        # 없는 컬럼 자동 생성
        # -----------------------------------------

        for col in REQUIRED_COLUMNS:

            if col not in df.columns:
                df[col] = None

        # -----------------------------------------
        # 날짜
        # -----------------------------------------

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["Date"]
        )

        # -----------------------------------------
        # 숫자 컬럼
        # -----------------------------------------

        numeric_columns = [
            "Buy_Amount",
            "Sell_Amount",
            "P_L_Amount",
            "ROI_Percent",
            "Entry_Price",
            "Stop_Price",
            "Target_Price",
            "Risk_Amount",
            "R_Multiple"
        ]

        for col in numeric_columns:

            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
            )

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

        # -----------------------------------------
        # 매수금액으로부터 손익 추정
        # -----------------------------------------

        mask = (
            (df["Buy_Amount"] == 0)
            &
            (df["ROI_Percent"] != 0)
        )

        df.loc[mask, "Buy_Amount"] = (
            df.loc[mask, "P_L_Amount"]
            /
            (df.loc[mask, "ROI_Percent"] / 100)
        ).abs()

        # -----------------------------------------
        # 매도금액
        # -----------------------------------------

        mask_sell = (
            (df["Sell_Amount"] == 0)
            &
            (df["Buy_Amount"] != 0)
        )

        df.loc[
            mask_sell,
            "Sell_Amount"
        ] = (
            df.loc[mask_sell, "Buy_Amount"]
            +
            df.loc[mask_sell, "P_L_Amount"]
        )

        # -----------------------------------------
        # R 계산
        # -----------------------------------------

        loss_df = df[
            df["P_L_Amount"] < 0
        ]

        if not loss_df.empty:

            avg_loss = abs(
                loss_df["P_L_Amount"].mean()
            )

            if avg_loss > 0:

                mask_r = (
                    df["R_Multiple"] == 0
                )

                df.loc[
                    mask_r,
                    "R_Multiple"
                ] = (
                    df.loc[
                        mask_r,
                        "P_L_Amount"
                    ]
                    /
                    avg_loss
                )

        return df

    except Exception as e:

        st.error(
            f"데이터 로딩 오류: {e}"
        )

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )


# =========================================================
# 5. SAVE DATA
# =========================================================

def save_dataframe(df):

    save_df = df.copy()

    if "Date" in save_df.columns:

        save_df["Date"] = pd.to_datetime(
            save_df["Date"],
            errors="coerce"
        ).dt.strftime(
            "%Y-%m-%d"
        )

    conn.update(
        worksheet=0,
        data=save_df
    )


# =========================================================
# 6. KRX LIST
# =========================================================

@st.cache_data(ttl=3600)
def get_krx_list():

    try:

        df = fdr.StockListing(
            "KRX"
        )

        return df[
            ["Code", "Name", "Market"]
        ]

    except:

        return pd.DataFrame()


krx_list = get_krx_list()


# =========================================================
# 7. COMMON FUNCTIONS
# =========================================================

def color_profit_loss(value):

    try:

        value = float(value)

        if value > 0:
            return (
                "color: #FF4444; "
                "font-weight: bold;"
            )

        if value < 0:
            return (
                "color: #0066CC; "
                "font-weight: bold;"
            )

    except:
        pass

    return ""


def calculate_statistics(df):

    total = len(df)

    if total == 0:
        return {}

    wins = df[
        df["ROI_Percent"] > 0
    ]

    losses = df[
        df["ROI_Percent"] <= 0
    ]

    win_rate = (
        len(wins) / total * 100
    )

    avg_win = (
        wins["ROI_Percent"].mean()
        if not wins.empty
        else 0
    )

    avg_loss = (
        abs(losses["ROI_Percent"].mean())
        if not losses.empty
        else 0
    )

    rr = (
        avg_win / avg_loss
        if avg_loss > 0
        else 0
    )

    gross_profit = (
        wins["P_L_Amount"].sum()
    )

    gross_loss = abs(
        losses["P_L_Amount"].sum()
    )

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0
    )

    win_prob = (
        len(wins) / total
    )

    loss_prob = 1 - win_prob

    expectancy = (
        win_prob * avg_win
        -
        loss_prob * avg_loss
    )

    return {
        "total": total,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "rr": rr,
        "profit_factor": pf,
        "expectancy": expectancy
    }


# =========================================================
# 8. LOAD MAIN DATA
# =========================================================

df = load_data()


# =========================================================
# 9. SESSION STATE
# =========================================================

if "ai_ticker" not in st.session_state:
    st.session_state.ai_ticker = ""

if "ai_buy_amt" not in st.session_state:
    st.session_state.ai_buy_amt = 0

if "ai_roi" not in st.session_state:
    st.session_state.ai_roi = 0.0

if "ai_memo" not in st.session_state:
    st.session_state.ai_memo = ""


# =========================================================
# 10. SIDEBAR
# =========================================================

st.sidebar.title("💎 Trading Master")

st.sidebar.caption(
    "추세추종 매매 기록 & 성과 분석 시스템"
)


# =========================================================
# 11. AI RECEIPT
# =========================================================

with st.sidebar.expander(
    "📸 AI 영수증 자동 입력",
    expanded=False
):

    st.caption(
        "증권사 수익/손실 화면을 올리면 "
        "AI가 데이터를 추출합니다."
    )

    api_key = st.text_input(
        "Gemini API Key",
        type="password"
    )

    uploaded_file = st.file_uploader(
        "증권사 캡처",
        type=[
            "png",
            "jpg",
            "jpeg"
        ]
    )

    if st.button(
        "🔍 AI 데이터 추출",
        use_container_width=True
    ):

        if not api_key:

            st.error(
                "Gemini API Key를 입력하세요."
            )

        elif not uploaded_file:

            st.error(
                "이미지를 올려주세요."
            )

        else:

            try:

                with st.spinner(
                    "AI가 분석 중입니다..."
                ):

                    genai.configure(
                        api_key=api_key.strip()
                    )

                    model = genai.GenerativeModel(
                        "gemini-2.5-flash"
                    )

                    img = Image.open(
                        uploaded_file
                    )

                    if img.mode != "RGB":

                        img = img.convert(
                            "RGB"
                        )

                    img.thumbnail(
                        (1000, 1000)
                    )

                    prompt = """
                    한국 증권사 매매 화면을 분석하세요.

                    다음 값을 추출하세요.

                    1. 종목명
                    2. 매수금액
                    3. 수익률

                    수익률이 없다면

                    손익금액 / 매수금액 * 100

                    으로 계산하세요.

                    반드시 JSON만 출력하세요.

                    {
                      "ticker": "삼성전자",
                      "buy_amount": 1000000,
                      "roi": 5.2,
                      "memo": "AI 분석"
                    }
                    """

                    response = model.generate_content(
                        [
                            prompt,
                            img
                        ]
                    )

                    text = response.text.strip()

                    match = re.search(
                        r"\{.*\}",
                        text,
                        re.DOTALL
                    )

                    if match:
                        text = match.group(0)

                    data = json.loads(text)

                    st.session_state.ai_ticker = (
                        data.get(
                            "ticker",
                            ""
                        )
                    )

                    st.session_state.ai_buy_amt = int(
                        float(
                            data.get(
                                "buy_amount",
                                0
                            )
                        )
                    )

                    st.session_state.ai_roi = float(
                        data.get(
                            "roi",
                            0
                        )
                    )

                    st.session_state.ai_memo = (
                        data.get(
                            "memo",
                            "AI 분석 완료"
                        )
                    )

                    st.success(
                        "✅ AI 분석 완료"
                    )

            except Exception as e:

                st.error(
                    f"AI 분석 실패: {e}"
                )


# =========================================================
# 12. TRADE INPUT
# =========================================================

st.sidebar.divider()

st.sidebar.subheader(
    "📝 빠른 거래 입력"
)


with st.sidebar.form(
    "trade_form",
    clear_on_submit=False
):

    trade_date = st.date_input(
        "거래일",
        datetime.today()
    )

    ticker = st.text_input(
        "종목명",
        value=st.session_state.ai_ticker
    )

    st.markdown("### 💰 거래")

    buy_amount = st.number_input(
        "매수 금액",
        min_value=0,
        value=int(
            st.session_state.ai_buy_amt
        ),
        step=100000
    )

    roi = st.number_input(
        "수익률 (%)",
        value=float(
            st.session_state.ai_roi
        ),
        format="%.2f"
    )

    pnl = (
        buy_amount
        *
        roi
        /
        100
    )

    sell_amount = (
        buy_amount
        +
        pnl
    )

    st.info(
        f"""
        **예상 손익:** {pnl:,.0f}원

        **매도 금액:** {sell_amount:,.0f}원
        """
    )

    st.markdown("### 🎯 리스크")

    entry_price = st.number_input(
        "진입가",
        min_value=0.0,
        value=0.0,
        step=100.0
    )

    stop_price = st.number_input(
        "손절가",
        min_value=0.0,
        value=0.0,
        step=100.0
    )

    target_price = st.number_input(
        "목표가",
        min_value=0.0,
        value=0.0,
        step=100.0
    )

    risk_amount = 0.0

    if (
        entry_price > 0
        and stop_price > 0
        and buy_amount > 0
    ):

        risk_rate = (
            abs(
                entry_price
                -
                stop_price
            )
            /
            entry_price
        )

        risk_amount = (
            buy_amount
            *
            risk_rate
        )

        st.caption(
            f"예상 Risk: {risk_amount:,.0f}원"
        )

    r_multiple = (
        pnl / risk_amount
        if risk_amount > 0
        else 0
    )

    if risk_amount > 0:

        st.metric(
            "현재 거래 R",
            f"{r_multiple:+.2f}R"
        )

    st.markdown("### 🧠 매매 기록")

    strategy = st.selectbox(
        "전략",
        [
            "추세추종",
            "돌파",
            "신고가",
            "눌림목",
            "이동평균",
            "기타"
        ]
    )

    entry_reason = st.text_area(
        "진입 이유",
        height=80
    )

    emotion = st.selectbox(
        "감정 상태",
        [
            "차분함",
            "확신",
            "불안",
            "조급함",
            "공포",
            "탐욕",
            "복수매매"
        ]
    )

    discipline = st.selectbox(
        "원칙 준수",
        [
            "완벽",
            "대체로 준수",
            "일부 위반",
            "심각한 위반"
        ]
    )

    mistake_tags = st.multiselect(
        "실수 태그",
        [
            "추격매수",
            "손절지연",
            "과대포지션",
            "조기매도",
            "FOMO",
            "복수매매",
            "원칙위반",
            "없음"
        ]
    )

    memo = st.text_area(
        "메모",
        value=st.session_state.ai_memo,
        height=80
    )

    save_button = st.form_submit_button(
        "💾 거래 기록 저장",
        use_container_width=True
    )


# =========================================================
# 13. SAVE TRADE
# =========================================================

if save_button:

    if not ticker.strip():

        st.sidebar.error(
            "종목명을 입력하세요."
        )

    else:

        new_trade = pd.DataFrame(
            [
                {
                    "Date": trade_date,
                    "Ticker": ticker.strip(),

                    "Buy_Amount": buy_amount,
                    "Sell_Amount": sell_amount,
                    "P_L_Amount": pnl,
                    "ROI_Percent": roi,

                    "Entry_Price": entry_price,
                    "Stop_Price": stop_price,
                    "Target_Price": target_price,
                    "Risk_Amount": risk_amount,
                    "R_Multiple": r_multiple,

                    "Strategy": strategy,
                    "Entry_Reason": entry_reason,
                    "Mistake_Tags": ", ".join(
                        mistake_tags
                    ),
                    "Emotion": emotion,
                    "Discipline": discipline,
                    "Memo": memo,

                    "AI_Analysis": ""
                }
            ]
        )

        try:

            live_df = conn.read(
                worksheet=0,
                ttl=0
            )

            if live_df.empty:

                updated_df = new_trade

            else:

                for col in REQUIRED_COLUMNS:

                    if col not in live_df.columns:
                        live_df[col] = None

                updated_df = pd.concat(
                    [
                        live_df,
                        new_trade
                    ],
                    ignore_index=True
                )

            save_dataframe(
                updated_df
            )

            st.sidebar.success(
                f"✅ {ticker} 저장 완료"
            )

            st.session_state.ai_ticker = ""
            st.session_state.ai_buy_amt = 0
            st.session_state.ai_roi = 0.0
            st.session_state.ai_memo = ""

            st.cache_data.clear()

            st.rerun()

        except Exception as e:

            st.sidebar.error(
                f"저장 실패: {e}"
            )


# =========================================================
# 14. MAIN TITLE
# =========================================================

st.title(
    "💎 Trading Master Dashboard"
)

st.caption(
    "나의 추세추종 매매를 데이터로 관리한다."
)


# =========================================================
# 15. EMPTY STATE
# =========================================================

if df.empty:

    st.info(
        "👈 왼쪽에서 첫 번째 매매 기록을 입력하세요."
    )

    st.stop()


# =========================================================
# 16. BASIC DATA
# =========================================================

df = df.copy()

df["Year"] = (
    df["Date"]
    .dt.year
)

df["YearMonth"] = (
    df["Date"]
    .dt.strftime("%Y-%m")
)

df = df.sort_values(
    "Date"
)


# =========================================================
# 17. STATISTICS
# =========================================================

stats = calculate_statistics(
    df
)


# =========================================================
# 18. TABS
# =========================================================

(
    tab_dashboard,
    tab_trade,
    tab_month,
    tab_year,
    tab_r,
    tab_strategy,
    tab_raw
) = st.tabs(
    [
        "🏠 Dashboard",
        "📝 거래 기록",
        "📅 월별",
        "📆 연도별",
        "🎯 R 분석",
        "🧠 전략 분석",
        "📋 원본 데이터"
    ]
)


# =========================================================
# TAB 1
# DASHBOARD
# =========================================================

with tab_dashboard:

    st.subheader(
        "🏆 나의 트레이딩 성적표"
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "누적 손익",
        f"{df['P_L_Amount'].sum():,.0f}원"
    )

    c2.metric(
        "승률",
        f"{stats['win_rate']:.1f}%"
    )

    c3.metric(
        "Profit Factor",
        f"{stats['profit_factor']:.2f}"
    )

    c4.metric(
        "손익비",
        f"{stats['rr']:.2f}"
    )

    c5.metric(
        "기대값",
        f"{stats['expectancy']:+.2f}%"
    )

    st.divider()

    # -----------------------------------------------------
    # Money Performance
    # -----------------------------------------------------

    st.subheader(
        "💰 Money Performance"
    )

    wins = df[
        df["P_L_Amount"] > 0
    ]

    losses = df[
        df["P_L_Amount"] <= 0
    ]

    c1, c2, c3, c4 = st.columns(4)

    avg_profit = (
        wins["P_L_Amount"].mean()
        if not wins.empty
        else 0
    )

    avg_loss_money = (
        abs(
            losses["P_L_Amount"].mean()
        )
        if not losses.empty
        else 0
    )

    c1.metric(
        "평균 수익금",
        f"{avg_profit:,.0f}원"
    )

    c2.metric(
        "평균 손실금",
        f"{avg_loss_money:,.0f}원"
    )

    money_rr = (
        avg_profit / avg_loss_money
        if avg_loss_money > 0
        else 0
    )

    c3.metric(
        "금액 손익비",
        f"{money_rr:.2f}"
    )

    c4.metric(
        "총 매수금액",
        f"{df['Buy_Amount'].sum():,.0f}원"
    )

    st.divider()

    # -----------------------------------------------------
    # Equity Curve
    # -----------------------------------------------------

    st.subheader(
        "📈 누적 손익 곡선"
    )

    chart_df = (
        df.groupby("Date")[
            "P_L_Amount"
        ]
        .sum()
        .reset_index()
    )

    chart_df = chart_df.sort_values(
        "Date"
    )

    chart_df["Cumulative"] = (
        chart_df["P_L_Amount"]
        .cumsum()
    )

    chart = alt.Chart(
        chart_df
    ).mark_line(
        strokeWidth=3
    ).encode(
        x=alt.X(
            "Date:T",
            title="날짜"
        ),
        y=alt.Y(
            "Cumulative:Q",
            title="누적 손익"
        ),
        tooltip=[
            "Date:T",
            "Cumulative:Q"
        ]
    )

    st.altair_chart(
        chart,
        use_container_width=True
    )

    # -----------------------------------------------------
    # Monthly P/L
    # -----------------------------------------------------

    st.subheader(
        "📊 월별 손익"
    )

    monthly_chart_df = (
        df.groupby("YearMonth")[
            "P_L_Amount"
        ]
        .sum()
        .reset_index()
    )

    bar = alt.Chart(
        monthly_chart_df
    ).mark_bar().encode(
        x=alt.X(
            "YearMonth:N",
            sort=None,
            title="월"
        ),
        y=alt.Y(
            "P_L_Amount:Q",
            title="손익"
        ),
        tooltip=[
            "YearMonth",
            "P_L_Amount"
        ]
    )

    st.altair_chart(
        bar,
        use_container_width=True
    )


# =========================================================
# TAB 2
# TRADE RECORD
# =========================================================

with tab_trade:

    st.subheader(
        "📝 최근 매매 기록"
    )

    display_cols = [
        "Date",
        "Ticker",
        "Buy_Amount",
        "ROI_Percent",
        "P_L_Amount",
        "R_Multiple",
        "Strategy",
        "Emotion",
        "Discipline"
    ]

    trade_view = (
        df[
            display_cols
        ]
        .sort_values(
            "Date",
            ascending=False
        )
        .head(30)
    )

    styled = trade_view.style.map(
        color_profit_loss,
        subset=[
            "ROI_Percent",
            "P_L_Amount",
            "R_Multiple"
        ]
    )

    styled = styled.format(
        {
            "Buy_Amount": "{:,.0f}",
            "ROI_Percent": "{:+.2f}%",
            "P_L_Amount": "{:+,.0f}",
            "R_Multiple": "{:+.2f}R"
        }
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# TAB 3
# MONTHLY
# =========================================================

with tab_month:

    st.subheader(
        "📅 월별 성적표"
    )

    monthly_rows = []

    for ym, group in df.groupby(
        "YearMonth"
    ):

        wins_m = group[
            group["ROI_Percent"] > 0
        ]

        losses_m = group[
            group["ROI_Percent"] <= 0
        ]

        gross_profit = (
            wins_m["P_L_Amount"].sum()
        )

        gross_loss = abs(
            losses_m["P_L_Amount"].sum()
        )

        pf = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0
        )

        win_rate = (
            len(wins_m)
            /
            len(group)
            *
            100
        )

        avg_win = (
            wins_m["ROI_Percent"].mean()
            if not wins_m.empty
            else 0
        )

        avg_loss = (
            abs(
                losses_m[
                    "ROI_Percent"
                ].mean()
            )
            if not losses_m.empty
            else 0
        )

        rr = (
            avg_win / avg_loss
            if avg_loss > 0
            else 0
        )

        expectancy = (
            (
                len(wins_m)
                /
                len(group)
            )
            * avg_win
            -
            (
                len(losses_m)
                /
                len(group)
            )
            * avg_loss
        )

        monthly_rows.append(
            {
                "기간": ym,
                "총 손익": group[
                    "P_L_Amount"
                ].sum(),
                "거래횟수": len(group),
                "승률": win_rate,
                "손익비": rr,
                "PF": pf,
                "기대값": expectancy
            }
        )

    monthly_df = pd.DataFrame(
        monthly_rows
    ).sort_values(
        "기간",
        ascending=False
    )

    styled = monthly_df.style.map(
        color_profit_loss,
        subset=[
            "총 손익",
            "기대값"
        ]
    )

    styled = styled.format(
        {
            "총 손익": "{:+,.0f}원",
            "거래횟수": "{:,}회",
            "승률": "{:.1f}%",
            "손익비": "{:.2f}",
            "PF": "{:.2f}",
            "기대값": "{:+.2f}%"
        }
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# TAB 4
# YEARLY
# =========================================================

with tab_year:

    st.subheader(
        "📆 연도별 성적표"
    )

    yearly_rows = []

    for year, group in df.groupby(
        "Year"
    ):

        wins_y = group[
            group["ROI_Percent"] > 0
        ]

        losses_y = group[
            group["ROI_Percent"] <= 0
        ]

        gross_profit = (
            wins_y["P_L_Amount"].sum()
        )

        gross_loss = abs(
            losses_y["P_L_Amount"].sum()
        )

        pf = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0
        )

        win_rate = (
            len(wins_y)
            /
            len(group)
            *
            100
        )

        avg_win = (
            wins_y["ROI_Percent"].mean()
            if not wins_y.empty
            else 0
        )

        avg_loss = (
            abs(
                losses_y[
                    "ROI_Percent"
                ].mean()
            )
            if not losses_y.empty
            else 0
        )

        rr = (
            avg_win / avg_loss
            if avg_loss > 0
            else 0
        )

        yearly_rows.append(
            {
                "연도": int(year),
                "총 손익": group[
                    "P_L_Amount"
                ].sum(),
                "거래횟수": len(group),
                "승률": win_rate,
                "손익비": rr,
                "PF": pf
            }
        )

    yearly_df = pd.DataFrame(
        yearly_rows
    ).sort_values(
        "연도",
        ascending=False
    )

    styled = yearly_df.style.map(
        color_profit_loss,
        subset=[
            "총 손익"
        ]
    )

    styled = styled.format(
        {
            "총 손익": "{:+,.0f}원",
            "거래횟수": "{:,}회",
            "승률": "{:.1f}%",
            "손익비": "{:.2f}",
            "PF": "{:.2f}"
        }
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# TAB 5
# R ANALYSIS
# =========================================================

with tab_r:

    st.subheader(
        "🎯 R-배수 분석"
    )

    st.markdown(
        """
        **1R = 내가 한 번의 거래에서 감수하는 위험 금액**

        수익을 단순한 원화가 아니라
        **위험 대비 몇 배를 벌었는가**로 봅니다.
        """
    )

    r_df = df.copy()

    loss_df = r_df[
        r_df["P_L_Amount"] < 0
    ]

    if not loss_df.empty:

        one_r = abs(
            loss_df["P_L_Amount"].mean()
        )

    else:

        one_r = 1

    r_df["Calculated_R"] = (
        r_df["P_L_Amount"]
        /
        one_r
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "나의 1R",
        f"{one_r:,.0f}원"
    )

    c2.metric(
        "평균 R",
        f"{r_df['Calculated_R'].mean():+.2f}R"
    )

    c3.metric(
        "최고 R",
        f"{r_df['Calculated_R'].max():+.2f}R"
    )

    st.divider()

    r_chart_df = (
        r_df
        .sort_values("Date")
        .copy()
    )

    r_chart_df[
        "Trade_Number"
    ] = range(
        1,
        len(r_chart_df) + 1
    )

    r_chart_df[
        "Cumulative_R"
    ] = (
        r_chart_df[
            "Calculated_R"
        ]
        .cumsum()
    )

    r_chart = alt.Chart(
        r_chart_df
    ).mark_line(
        strokeWidth=3
    ).encode(
        x=alt.X(
            "Trade_Number:Q",
            title="거래 횟수"
        ),
        y=alt.Y(
            "Cumulative_R:Q",
            title="누적 R"
        ),
        tooltip=[
            "Date:T",
            "Ticker:N",
            "Calculated_R:Q",
            "Cumulative_R:Q"
        ]
    )

    st.altair_chart(
        r_chart,
        use_container_width=True
    )

    st.divider()

    st.subheader(
        "🎯 거래별 R 분포"
    )

    r_hist = alt.Chart(
        r_df
    ).mark_bar().encode(
        x=alt.X(
            "Calculated_R:Q",
            bin=alt.Bin(step=1),
            title="R"
        ),
        y=alt.Y(
            "count()",
            title="거래 수"
        ),
        tooltip=[
            "count()"
        ]
    )

    st.altair_chart(
        r_hist,
        use_container_width=True
    )


# =========================================================
# TAB 6
# STRATEGY ANALYSIS
# =========================================================

with tab_strategy:

    st.subheader(
        "🧠 전략별 분석"
    )

    strategy_df = df.copy()

    strategy_df[
        "Strategy"
    ] = strategy_df[
        "Strategy"
    ].fillna(
        "미분류"
    )

    strategy_rows = []

    for strategy, group in strategy_df.groupby(
        "Strategy"
    ):

        wins_s = group[
            group["P_L_Amount"] > 0
        ]

        losses_s = group[
            group["P_L_Amount"] <= 0
        ]

        gross_profit = (
            wins_s["P_L_Amount"].sum()
        )

        gross_loss = abs(
            losses_s["P_L_Amount"].sum()
        )

        pf = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0
        )

        win_rate = (
            len(wins_s)
            /
            len(group)
            *
            100
        )

        avg_r = (
            group["R_Multiple"].mean()
        )

        strategy_rows.append(
            {
                "전략": strategy,
                "거래횟수": len(group),
                "승률": win_rate,
                "총 손익": group[
                    "P_L_Amount"
                ].sum(),
                "PF": pf,
                "평균 R": avg_r
            }
        )

    strategy_result = pd.DataFrame(
        strategy_rows
    ).sort_values(
        "총 손익",
        ascending=False
    )

    styled = strategy_result.style.map(
        color_profit_loss,
        subset=[
            "총 손익",
            "평균 R"
        ]
    )

    styled = styled.format(
        {
            "거래횟수": "{:,}회",
            "승률": "{:.1f}%",
            "총 손익": "{:+,.0f}원",
            "PF": "{:.2f}",
            "평균 R": "{:+.2f}R"
        }
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader(
        "📊 전략별 누적 손익"
    )

    strategy_chart = alt.Chart(
        strategy_result
    ).mark_bar().encode(
        x=alt.X(
            "전략:N",
            title="전략"
        ),
        y=alt.Y(
            "총 손익:Q",
            title="총 손익"
        ),
        tooltip=[
            "전략",
            "거래횟수",
            "승률",
            "총 손익",
            "PF",
            "평균 R"
        ]
    )

    st.altair_chart(
        strategy_chart,
        use_container_width=True
    )


# =========================================================
# TAB 7
# RAW DATA
# =========================================================

with tab_raw:

    st.subheader(
        "📋 전체 매매 원본 데이터"
    )

    st.caption(
        "Google Sheets에 저장된 실제 거래 기록입니다."
    )

    raw_df = (
        df
        .sort_values(
            "Date",
            ascending=False
        )
        .copy()
    )

    styled = raw_df.style.map(
        color_profit_loss,
        subset=[
            "ROI_Percent",
            "P_L_Amount",
            "R_Multiple"
        ]
    )

    styled = styled.format(
        {
            "Buy_Amount": "{:,.0f}",
            "Sell_Amount": "{:,.0f}",
            "P_L_Amount": "{:+,.0f}",
            "ROI_Percent": "{:+.2f}%",
            "Entry_Price": "{:,.0f}",
            "Stop_Price": "{:,.0f}",
            "Target_Price": "{:,.0f}",
            "Risk_Amount": "{:,.0f}",
            "R_Multiple": "{:+.2f}R"
        }
    )

    st.dataframe(
        styled,
        use_container_width=True,
        height=600
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    f"💎 Trading Master | 총 {len(df):,}건의 거래 기록"
    )
