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
import google.generativeai as genai
from PIL import Image


# =========================================================
# 0. PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Trading Master 2.0",
    page_icon="💎",
    layout="wide"
)


# =========================================================
# 1. GOOGLE SHEETS CONNECTION
# =========================================================

conn = st.connection(
    "gsheets",
    type=GSheetsConnection
)


# =========================================================
# 2. DATA SCHEMA
# =========================================================

# STEP 1
# 거래 1건을 단순한 "수익률 기록"이 아니라
# 하나의 완전한 트레이딩 데이터로 저장한다.

REQUIRED_COLUMNS = [
    "Trade_ID",

    # 날짜
    "Entry_Date",
    "Exit_Date",

    # 종목
    "Ticker",

    # 가격
    "Entry_Price",
    "Exit_Price",

    # 금액
    "Buy_Amount",
    "Sell_Amount",
    "P_L_Amount",

    # 성과
    "ROI_Percent",

    # Risk / Reward
    "Stop_Price",
    "Target_Price",
    "Risk_Amount",
    "R_Multiple",

    # 시간
    "Holding_Days",

    # 전략
    "Strategy",
    "Entry_Reason",

    # 심리
    "Emotion",
    "Discipline",

    # 실수
    "Mistake_Tags",

    # 기타
    "Memo"
]


# =========================================================
# 3. DEFAULT DATAFRAME
# =========================================================

def empty_trade_df():
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


# =========================================================
# 4. HELPER FUNCTIONS
# =========================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        if pd.isna(value):
            return default

        value = str(value)
        value = value.replace(",", "")
        value = value.replace("%", "")

        return float(value)

    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(float(safe_float(value, default)))
    except Exception:
        return default


def generate_trade_id():
    """
    거래 ID 생성
    """

    now = datetime.now()

    return now.strftime(
        "%Y%m%d%H%M%S%f"
    )[:-3]


# =========================================================
# 5. DATA MIGRATION
# =========================================================

def migrate_dataframe(df):
    """
    기존 Google Sheets 데이터를 새로운 구조로 변환한다.

    기존 버전:
        Date
        Ticker
        Buy_Amount
        Sell_Amount
        P_L_Amount
        ROI_Percent
        Mistake_Tags
        Emotion
        Discipline
        Memo

    새로운 버전:
        Entry_Date
        Exit_Date
        Entry_Price
        Exit_Price
        Stop_Price
        Target_Price
        Risk_Amount
        R_Multiple
        Holding_Days
        Strategy
        Entry_Reason
        ...
    """

    if df is None or df.empty:
        return empty_trade_df()

    df = df.copy()

    # -----------------------------------------------------
    # 기존 Date → Entry_Date
    # -----------------------------------------------------

    if "Entry_Date" not in df.columns:

        if "Date" in df.columns:
            df["Entry_Date"] = df["Date"]

        else:
            df["Entry_Date"] = datetime.today().strftime(
                "%Y-%m-%d"
            )

    # -----------------------------------------------------
    # Exit_Date
    # -----------------------------------------------------

    if "Exit_Date" not in df.columns:
        df["Exit_Date"] = df["Entry_Date"]

    # -----------------------------------------------------
    # 숫자 컬럼
    # -----------------------------------------------------

    numeric_columns = [
        "Entry_Price",
        "Exit_Price",
        "Buy_Amount",
        "Sell_Amount",
        "P_L_Amount",
        "ROI_Percent",
        "Stop_Price",
        "Target_Price",
        "Risk_Amount",
        "R_Multiple",
        "Holding_Days"
    ]

    for col in numeric_columns:

        if col not in df.columns:
            df[col] = 0.0

        df[col] = df[col].apply(
            safe_float
        )

    # -----------------------------------------------------
    # 텍스트 컬럼
    # -----------------------------------------------------

    text_columns = [
        "Ticker",
        "Strategy",
        "Entry_Reason",
        "Emotion",
        "Discipline",
        "Mistake_Tags",
        "Memo"
    ]

    for col in text_columns:

        if col not in df.columns:
            df[col] = ""

        df[col] = df[col].fillna("").astype(str)

    # -----------------------------------------------------
    # Trade ID
    # -----------------------------------------------------

    if "Trade_ID" not in df.columns:

        df["Trade_ID"] = [
            generate_trade_id()
            for _ in range(len(df))
        ]

    else:

        df["Trade_ID"] = df["Trade_ID"].fillna("")

        for i in range(len(df)):

            if not str(df.loc[i, "Trade_ID"]).strip():

                df.loc[i, "Trade_ID"] = generate_trade_id()

    # -----------------------------------------------------
    # 기존 ROI 데이터로 Buy Amount 보정
    # -----------------------------------------------------

    mask = (
        (df["Buy_Amount"] == 0)
        &
        (df["ROI_Percent"] != 0)
        &
        (df["P_L_Amount"] != 0)
    )

    df.loc[mask, "Buy_Amount"] = (
        df.loc[mask, "P_L_Amount"]
        /
        (df.loc[mask, "ROI_Percent"] / 100)
    ).abs()

    # -----------------------------------------------------
    # Sell Amount
    # -----------------------------------------------------

    mask_sell = (
        (df["Sell_Amount"] == 0)
        &
        (df["Buy_Amount"] != 0)
    )

    df.loc[mask_sell, "Sell_Amount"] = (
        df.loc[mask_sell, "Buy_Amount"]
        +
        df.loc[mask_sell, "P_L_Amount"]
    )

    # -----------------------------------------------------
    # Date 처리
    # -----------------------------------------------------

    df["Entry_Date"] = pd.to_datetime(
        df["Entry_Date"],
        errors="coerce"
    )

    df["Exit_Date"] = pd.to_datetime(
        df["Exit_Date"],
        errors="coerce"
    )

    # Entry date가 없으면 오늘
    df["Entry_Date"] = df["Entry_Date"].fillna(
        pd.Timestamp.today()
    )

    # Exit date가 없으면 Entry date
    df["Exit_Date"] = df["Exit_Date"].fillna(
        df["Entry_Date"]
    )

    # -----------------------------------------------------
    # Holding Days
    # -----------------------------------------------------

    calculated_holding = (
        df["Exit_Date"] - df["Entry_Date"]
    ).dt.days

    df["Holding_Days"] = calculated_holding.fillna(
        df["Holding_Days"]
    )

    df["Holding_Days"] = (
        df["Holding_Days"]
        .clip(lower=0)
    )

    # -----------------------------------------------------
    # R Multiple
    # -----------------------------------------------------

    valid_risk = df["Risk_Amount"] > 0

    df.loc[valid_risk, "R_Multiple"] = (
        df.loc[valid_risk, "P_L_Amount"]
        /
        df.loc[valid_risk, "Risk_Amount"]
    )

    # -----------------------------------------------------
    # 기존 컬럼 제거
    # -----------------------------------------------------

    if "Date" in df.columns:
        df = df.drop(
            columns=["Date"]
        )

    # -----------------------------------------------------
    # 컬럼 순서
    # -----------------------------------------------------

    for col in REQUIRED_COLUMNS:

        if col not in df.columns:
            df[col] = ""

    df = df[REQUIRED_COLUMNS]

    return df


# =========================================================
# 6. LOAD DATA
# =========================================================

@st.cache_data(ttl=0)
def load_data():

    try:

        raw_df = conn.read(
            worksheet=0,
            ttl=0
        )

        if raw_df.empty:
            return empty_trade_df()

        return migrate_dataframe(
            raw_df
        )

    except Exception as e:

        st.warning(
            f"데이터를 불러오는 중 문제가 발생했습니다: {e}"
        )

        return empty_trade_df()


# =========================================================
# 7. SAVE DATA
# =========================================================

def save_trade(new_trade):

    try:

        live_df = conn.read(
            worksheet=0,
            ttl=0
        )

        if live_df.empty:

            updated_df = new_trade.copy()

        else:

            live_df = migrate_dataframe(
                live_df
            )

            updated_df = pd.concat(
                [
                    live_df,
                    new_trade
                ],
                ignore_index=True
            )

        # Google Sheet용 날짜 문자열
        updated_df["Entry_Date"] = (
            pd.to_datetime(
                updated_df["Entry_Date"]
            )
            .dt.strftime("%Y-%m-%d")
        )

        updated_df["Exit_Date"] = (
            pd.to_datetime(
                updated_df["Exit_Date"]
            )
            .dt.strftime("%Y-%m-%d")
        )

        conn.update(
            worksheet=0,
            data=updated_df
        )

        return True, ""

    except Exception as e:

        return False, str(e)


# =========================================================
# 8. KRX LIST
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

    except Exception:

        return pd.DataFrame(
            columns=[
                "Code",
                "Name",
                "Market"
            ]
        )


# =========================================================
# 9. COLOR FUNCTION
# =========================================================

def color_profit_loss(val):

    try:

        if pd.isna(val):
            return ""

        val = float(val)

        if val > 0:
            return (
                "color: #FF4444; "
                "font-weight: bold;"
            )

        if val < 0:
            return (
                "color: #0066CC; "
                "font-weight: bold;"
            )

    except Exception:
        pass

    return ""


# =========================================================
# 10. LOAD INITIAL DATA
# =========================================================

df = load_data()

krx_list = get_krx_list()


# =========================================================
# 11. SESSION STATE
# =========================================================

defaults = {

    "form_reset_trigger": 0,

    "ai_ticker": "",
    "ai_buy_amt": 0,
    "ai_roi": 0.0,
    "ai_memo": "",

    "entry_price": 0.0,
    "exit_price": 0.0,
    "stop_price": 0.0,
    "target_price": 0.0

}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 12. AI RECEIPT ANALYSIS
# =========================================================

st.sidebar.header(
    "📸 AI 영수증 자동 입력"
)

with st.sidebar.expander(
    "🤖 증권사 캡처 분석",
    expanded=False
):

    st.markdown(
        """
        증권사 수익률 화면을 올리면
        AI가 종목명, 매수금액, 수익률을 추출합니다.
        """
    )

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        key="sidebar_api"
    )

    uploaded_file = st.file_uploader(
        "증권사 캡처 이미지",
        type=[
            "png",
            "jpg",
            "jpeg"
        ],
        key="sidebar_uploader"
    )

    if st.button(
        "🔍 데이터 추출하기",
        use_container_width=True
    ):

        if not api_key:

            st.error(
                "Gemini API Key가 필요합니다."
            )

        elif not uploaded_file:

            st.error(
                "이미지를 올려주세요."
            )

        else:

            with st.spinner(
                "AI가 캡처를 분석하고 있습니다..."
            ):

                try:

                    clean_api_key = (
                        api_key.strip()
                    )

                    genai.configure(
                        api_key=clean_api_key
                    )

                    model = (
                        genai.GenerativeModel(
                            "gemini-2.5-flash"
                        )
                    )

                    img = Image.open(
                        uploaded_file
                    )

                    if img.mode != "RGB":
                        img = img.convert("RGB")

                    img.thumbnail(
                        (800, 800)
                    )

                    prompt = """
                    당신은 한국 주식 증권사 화면을
                    분석하는 AI입니다.

                    이미지에서 다음 정보를 추출하세요.

                    1. 종목명
                    2. 매수금액
                    3. 수익률

                    수익률이 없고 손익금액과 매수금액만 있다면
                    직접 계산하세요.

                    반드시 아래 JSON 형식만 반환하세요.

                    {
                        "ticker": "삼성전자",
                        "buy_amount": 1000000,
                        "roi": 3.25,
                        "memo": "AI 스캔 완료"
                    }
                    """

                    response = model.generate_content(
                        [
                            prompt,
                            img
                        ]
                    )

                    result_text = (
                        response.text.strip()
                    )

                    match = re.search(
                        r"\{.*\}",
                        result_text,
                        re.DOTALL
                    )

                    if match:

                        clean_json = (
                            match.group(0)
                        )

                    else:

                        clean_json = result_text

                    data = json.loads(
                        clean_json
                    )

                    st.session_state.ai_ticker = (
                        data.get(
                            "ticker",
                            ""
                        )
                    )

                    st.session_state.ai_buy_amt = (
                        safe_int(
                            data.get(
                                "buy_amount",
                                0
                            )
                        )
                    )

                    st.session_state.ai_roi = (
                        safe_float(
                            data.get(
                                "roi",
                                0
                            )
                        )
                    )

                    st.session_state.ai_memo = (
                        data.get(
                            "memo",
                            "📸 AI 분석 완료"
                        )
                    )

                    st.session_state.form_reset_trigger += 1

                    st.success(
                        "✅ AI 분석 완료!"
                    )

                except Exception as e:

                    st.error(
                        f"AI 분석 실패: {e}"
                    )


# =========================================================
# 13. QUICK DEFAULT VALUES
# =========================================================

def_ticker = st.session_state.ai_ticker
def_buy_amt = st.session_state.ai_buy_amt
def_roi = st.session_state.ai_roi
def_memo = st.session_state.ai_memo

fc = st.session_state.form_reset_trigger


# =========================================================
# 14. TRADE INPUT
# =========================================================

st.sidebar.markdown("---")

st.sidebar.header(
    "📝 새로운 매매 기록"
)

with st.sidebar.form(
    "trade_input",
    clear_on_submit=False
):

    # -----------------------------------------------------
    # SECTION 1
    # 기본 거래 정보
    # -----------------------------------------------------

    st.markdown(
        "### ① 기본 거래 정보"
    )

    entry_date = st.date_input(
        "진입일",
        value=datetime.today(),
        key=f"entry_date_{fc}"
    )

    exit_date = st.date_input(
        "청산일",
        value=datetime.today(),
        key=f"exit_date_{fc}"
    )

    ticker = st.text_input(
        "종목명",
        value=def_ticker,
        placeholder="예: 삼성전자",
        key=f"ticker_{fc}"
    ).strip()

    # -----------------------------------------------------
    # SECTION 2
    # 가격 정보
    # -----------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### ② 가격 정보"
    )

    entry_price = st.number_input(
        "매수가",
        min_value=0.0,
        value=float(
            st.session_state.get(
                "entry_price",
                0.0
            )
        ),
        step=100.0,
        key=f"entry_price_{fc}"
    )

    exit_price = st.number_input(
        "매도가",
        min_value=0.0,
        value=float(
            st.session_state.get(
                "exit_price",
                0.0
            )
        ),
        step=100.0,
        key=f"exit_price_{fc}"
    )

    # -----------------------------------------------------
    # SECTION 3
    # 금액
    # -----------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### ③ 금액"
    )

    buy_amt = st.number_input(
        "총 매수 금액",
        min_value=0,
        value=int(def_buy_amt),
        step=100000,
        key=f"buy_amt_{fc}"
    )

    # 매도가 입력이 있으면 자동 계산
    calculated_sell = 0.0

    if exit_price > 0 and entry_price > 0:

        calculated_sell = (
            buy_amt
            *
            (
                exit_price
                /
                entry_price
            )
        )

    default_sell = (
        calculated_sell
        if calculated_sell > 0
        else 0
    )

    sell_amt = st.number_input(
        "총 매도 금액",
        min_value=0,
        value=int(default_sell),
        step=100000,
        key=f"sell_amt_{fc}"
    )

    # 기존 AI ROI
    roi_from_ai = def_roi

    # -----------------------------------------------------
    # ROI 자동 계산
    # -----------------------------------------------------

    if buy_amt > 0 and sell_amt > 0:

        calculated_pl = (
            sell_amt
            -
            buy_amt
        )

        calculated_roi = (
            calculated_pl
            /
            buy_amt
            *
            100
        )

    else:

        calculated_pl = (
            buy_amt
            *
            roi_from_ai
            /
            100
        )

        calculated_roi = roi_from_ai

    st.info(
        f"""
        💰 손익금액: **{calculated_pl:,.0f}원**

        📈 수익률: **{calculated_roi:+.2f}%**
        """
    )

    # -----------------------------------------------------
    # SECTION 4
    # Risk / Reward
    # -----------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### ④ Risk / Reward"
    )

    stop_price = st.number_input(
        "손절가",
        min_value=0.0,
        value=0.0,
        step=100.0,
        help="진입 전에 계획했던 손절 가격"
    )

    target_price = st.number_input(
        "목표가",
        min_value=0.0,
        value=0.0,
        step=100.0,
        help="진입 전에 계획했던 목표 가격"
    )

    risk_amount = 0.0
    r_multiple = 0.0

    if (
        entry_price > 0
        and stop_price > 0
        and buy_amt > 0
    ):

        risk_percent = (
            (
                entry_price
                -
                stop_price
            )
            /
            entry_price
        )

        risk_amount = (
            buy_amt
            *
            risk_percent
        )

        if risk_amount > 0:

            r_multiple = (
                calculated_pl
                /
                risk_amount
            )

    if stop_price > 0:

        st.caption(
            f"계획된 위험금액: "
            f"{risk_amount:,.0f}원"
        )

        st.caption(
            f"현재 거래의 R: "
            f"{r_multiple:+.2f}R"
        )

    # -----------------------------------------------------
    # SECTION 5
    # Strategy
    # -----------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### ⑤ 매매 전략"

    )

    strategy = st.selectbox(
        "매매 전략",
        [
            "추세추종",
            "돌파",
            "눌림목",
            "신고가",
            "이평선",
            "거래량",
            "시장 주도주",
            "스윙",
            "기타"
        ]
    )

    entry_reason = st.text_area(
        "진입 근거",
        placeholder=(
            "왜 이 종목을 샀는지 적어주세요.\n"
            "예: 신고가 돌파 + 거래량 증가 + 시장 강세"
        )
    )

    # -----------------------------------------------------
    # SECTION 6
    # Psychology
    # -----------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### ⑥ 매매 심리"

    )

    emotion = st.selectbox(
        "진입 당시 감정",
        [
            "차분함",
            "확신",
            "기대",
            "조급함",
            "두려움",
            "FOMO",
            "복수매매",
            "욕심",
            "기타"
        ]
    )

    discipline = st.selectbox(
        "원칙 준수",
        [
            "완벽하게 지킴",
            "대부분 지킴",
            "일부 위반",
            "많이 위반",
            "완전히 위반"
        ]
    )

    mistake_tags = st.multiselect(
        "실수 태그",
        [
            "추격매수",
            "손절 지연",
            "과대 포지션",
            "FOMO",
            "너무 빠른 매도",
            "너무 늦은 매도",
            "물타기",
            "원칙 위반",
            "계획 없는 진입",
            "없음"
        ]
    )

    # -----------------------------------------------------
    # SECTION 7
    # Memo
    # -----------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### ⑦ 복기 메모"
    )

    memo = st.text_area(
        "메모",
        value=def_memo,
        placeholder=(
            "이번 매매에서 배운 점을 기록하세요."
        )
    )

    # -----------------------------------------------------
    # Holding Days
    # -----------------------------------------------------

    holding_days = (
        exit_date
        -
        entry_date
    ).days

    if holding_days < 0:
        holding_days = 0

    st.caption(
        f"📅 보유기간: {holding_days}일"
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    submitted = st.form_submit_button(
        "💾 매매 기록 저장",
        use_container_width=True
    )

    if submitted:

        if not ticker:

            st.error(
                "종목명을 입력해주세요."
            )

        else:

            trade_id = generate_trade_id()

            new_trade = pd.DataFrame(
                [
                    {
                        "Trade_ID": trade_id,

                        "Entry_Date": entry_date,

                        "Exit_Date": exit_date,

                        "Ticker": ticker,

                        "Entry_Price": entry_price,

                        "Exit_Price": exit_price,

                        "Buy_Amount": buy_amt,

                        "Sell_Amount": sell_amt,

                        "P_L_Amount": calculated_pl,

                        "ROI_Percent": calculated_roi,

                        "Stop_Price": stop_price,

                        "Target_Price": target_price,

                        "Risk_Amount": risk_amount,

                        "R_Multiple": r_multiple,

                        "Holding_Days": holding_days,

                        "Strategy": strategy,

                        "Entry_Reason": entry_reason,

                        "Emotion": emotion,

                        "Discipline": discipline,

                        "Mistake_Tags": ", ".join(
                            mistake_tags
                        ),

                        "Memo": memo
                    }
                ]
            )

            success, error = save_trade(
                new_trade
            )

            if success:

                st.success(
                    f"✅ {ticker} 거래가 저장되었습니다."
                )

                # AI 데이터 초기화
                st.session_state.ai_ticker = ""
                st.session_state.ai_buy_amt = 0
                st.session_state.ai_roi = 0.0
                st.session_state.ai_memo = ""

                # 캐시 초기화
                st.cache_data.clear()

                st.rerun()

            else:

                st.error(
                    "저장에 실패했습니다."
                )

                st.code(
                    error
                )


# =========================================================
# 15. SIDEBAR STATUS
# =========================================================

if krx_list.empty:

    st.sidebar.caption(
        "⚠️ KRX 종목 리스트 연결 실패"
    )

else:

    st.sidebar.caption(
        f"✅ KRX {len(krx_list):,}개 종목 연결"
    )

st.sidebar.markdown("---")

st.sidebar.caption(
    "Trading Master 2.0"
)

st.sidebar.caption(
    "STEP 1 + STEP 2"
)


# =========================================================
# 16. MAIN DASHBOARD
# =========================================================

st.title(
    "💎 Trading Master 2.0"
)

st.caption(
    "내 매매를 기록하고, 패턴을 찾고, "
    "나만의 트레이딩 시스템을 만드는 대시보드"
)


if df.empty:

    st.info(
        "👈 왼쪽에서 첫 번째 매매 기록을 입력해보세요."
    )

    st.stop()


# =========================================================
# 17. DATA PREPARATION
# =========================================================

df = migrate_dataframe(df)

df["Entry_Date"] = pd.to_datetime(
    df["Entry_Date"],
    errors="coerce"
)

df["Exit_Date"] = pd.to_datetime(
    df["Exit_Date"],
    errors="coerce"
)

df["Year"] = (
    df["Entry_Date"]
    .dt.year
)

df["YearMonth"] = (
    df["Entry_Date"]
    .dt.strftime("%Y-%m")
)


# =========================================================
# 18. GLOBAL METRICS
# =========================================================

total_trades = len(df)

wins = df[
    df["P_L_Amount"] > 0
]

losses = df[
    df["P_L_Amount"] <= 0
]

win_rate = (
    len(wins)
    /
    total_trades
    *
    100
    if total_trades > 0
    else 0
)

avg_win = (
    wins["ROI_Percent"].mean()
    if not wins.empty
    else 0
)

avg_loss = (
    abs(
        losses["ROI_Percent"].mean()
    )
    if not losses.empty
    else 0
)

risk_reward_ratio = (
    avg_win
    /
    avg_loss
    if avg_loss > 0
    else 0
)

avg_roi = (
    df["ROI_Percent"].mean()
)


# =========================================================
# 19. TABS
# =========================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "📊 차트",
        "📅 월별",
        "📆 연도별",
        "📋 거래 원본",
        "⚖️ 빅터 스페란데오",
        "🎯 R-배수",
        "🔔 손익 분포",
        "🧠 매매 패턴"
    ]
)


# =========================================================
# TAB 1
# =========================================================

with tab1:

    st.subheader(
        "🏆 전체 종합 성적표"
    )

    total_pl = (
        df["P_L_Amount"].sum()
    )

    gross_profit = (
        df[
            df["P_L_Amount"] > 0
        ]["P_L_Amount"]
        .sum()
    )

    gross_loss = abs(
        df[
            df["P_L_Amount"] <= 0
        ]["P_L_Amount"]
        .sum()
    )

    total_pf = (
        gross_profit
        /
        gross_loss
        if gross_loss > 0
        else 0
    )

    avg_profit_amt = (
        wins["P_L_Amount"].mean()
        if not wins.empty
        else 0
    )

    avg_loss_amt = (
        abs(
            losses["P_L_Amount"].mean()
        )
        if not losses.empty
        else 0
    )

    money_rr_ratio = (
        avg_profit_amt
        /
        avg_loss_amt
        if avg_loss_amt > 0
        else 0
    )

    win_prob = (
        len(wins)
        /
        total_trades
        if total_trades > 0
        else 0
    )

    loss_prob = (
        1 - win_prob
    )

    expectancy = (
        win_prob * avg_win
        -
        loss_prob * avg_loss
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "💰 누적 손익",
        f"{total_pl:,.0f}원"
    )

    c2.metric(
        "🎯 승률",
        f"{win_rate:.1f}%"
    )

    c3.metric(
        "🔮 기대값",
        f"{expectancy:+.2f}%"
    )

    c4.metric(
        "💎 Profit Factor",
        f"{total_pf:.2f}"
    )

    c5.metric(
        "⚖️ 금액 손익비",
        f"{money_rr_ratio:.2f}"
    )

    st.divider()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "평균 수익",
        f"{avg_profit_amt:,.0f}원"
    )

    c2.metric(
        "평균 손실",
        f"{avg_loss_amt:,.0f}원"
    )

    c3.metric(
        "평균 수익률",
        f"{avg_win:+.2f}%"
    )

    c4.metric(
        "평균 손실률",
        f"-{avg_loss:.2f}%"
    )

    st.divider()

    # 누적 손익
    daily_df = (
        df
        .groupby("Entry_Date")["P_L_Amount"]
        .sum()
        .reset_index()
        .sort_values("Entry_Date")
    )

    daily_df["Cumulative"] = (
        daily_df["P_L_Amount"]
        .cumsum()
    )

    st.subheader(
        "📈 누적 손익"
    )

    chart = (
        alt.Chart(daily_df)
        .mark_line(
            strokeWidth=3
        )
        .encode(
            x=alt.X(
                "Entry_Date:T",
                title="날짜"
            ),
            y=alt.Y(
                "Cumulative:Q",
                title="누적 손익"
            ),
            tooltip=[
                "Entry_Date:T",
                "Cumulative:Q"
            ]
        )
        .interactive()
    )

    st.altair_chart(
        chart,
        use_container_width=True
    )


# =========================================================
# TAB 2
# MONTHLY
# =========================================================

with tab2:

    st.subheader(
        "📅 월별 상세 성적표"
    )

    monthly_stats = []

    for ym, group in df.groupby(
        "YearMonth"
    ):

        g_wins = group[
            group["P_L_Amount"] > 0
        ]

        g_losses = group[
            group["P_L_Amount"] <= 0
        ]

        gross_profit = (
            g_wins["P_L_Amount"].sum()
        )

        gross_loss = abs(
            g_losses["P_L_Amount"].sum()
        )

        pf = (
            gross_profit
            /
            gross_loss
            if gross_loss > 0
            else 0
        )

        avg_gain = (
            g_wins["ROI_Percent"].mean()
            if not g_wins.empty
            else 0
        )

        avg_loss_m = (
            abs(
                g_losses[
                    "ROI_Percent"
                ].mean()
            )
            if not g_losses.empty
            else 0
        )

        wl_ratio = (
            avg_gain
            /
            avg_loss_m
            if avg_loss_m > 0
            else 0
        )

        count = len(group)

        win_prob_m = (
            len(g_wins)
            /
            count
            if count > 0
            else 0
        )

        expectancy_m = (
            win_prob_m * avg_gain
            -
            (1 - win_prob_m) * avg_loss_m
        )

        monthly_stats.append(
            {
                "기간": ym,
                "총 손익": group[
                    "P_L_Amount"
                ].sum(),
                "거래횟수": count,
                "승률": win_prob_m * 100,
                "손익비": wl_ratio,
                "PF": pf,
                "기대값": expectancy_m,
                "평균 R": group[
                    "R_Multiple"
                ].mean()
            }
        )

    monthly_df = pd.DataFrame(
        monthly_stats
    ).sort_values(
        "기간",
        ascending=False
    )

    st.dataframe(
        monthly_df.style.map(
            color_profit_loss,
            subset=[
                "총 손익",
                "기대값"
            ]
        ).format(
            {
                "총 손익": "{:+,.0f}원",
                "거래횟수": "{:,}회",
                "승률": "{:.1f}%",
                "손익비": "{:.2f}",
                "PF": "{:.2f}",
                "기대값": "{:+.2f}%",
                "평균 R": "{:+.2f}R"
            }
        ),
        use_container_width=True
    )


# =========================================================
# TAB 3
# YEARLY
# =========================================================

with tab3:

    st.subheader(
        "📆 연도별 종합 성적표"
    )

    yearly_stats = []

    for year, group in df.groupby(
        "Year"
    ):

        g_wins = group[
            group["P_L_Amount"] > 0
        ]

        g_losses = group[
            group["P_L_Amount"] <= 0
        ]

        gross_profit = (
            g_wins["P_L_Amount"].sum()
        )

        gross_loss = abs(
            g_losses["P_L_Amount"].sum()
        )

        pf = (
            gross_profit
            /
            gross_loss
            if gross_loss > 0
            else 0
        )

        avg_gain = (
            g_wins["ROI_Percent"].mean()
            if not g_wins.empty
            else 0
        )

        avg_loss_y = (
            abs(
                g_losses[
                    "ROI_Percent"
                ].mean()
            )
            if not g_losses.empty
            else 0
        )

        wl_ratio = (
            avg_gain
            /
            avg_loss_y
            if avg_loss_y > 0
            else 0
        )

        count = len(group)

        win_prob_y = (
            len(g_wins)
            /
            count
            if count > 0
            else 0
        )

        expectancy_y = (
            win_prob_y * avg_gain
            -
            (1 - win_prob_y) * avg_loss_y
        )

        yearly_stats.append(
            {
                "연도": int(year),
                "총 손익": group[
                    "P_L_Amount"
                ].sum(),
                "거래횟수": count,
                "승률": win_prob_y * 100,
                "손익비": wl_ratio,
                "PF": pf,
                "기대값": expectancy_y,
                "평균 R": group[
                    "R_Multiple"
                ].mean()
            }
        )

    yearly_df = pd.DataFrame(
        yearly_stats
    ).sort_values(
        "연도",
        ascending=False
    )

    st.dataframe(
        yearly_df.style.map(
            color_profit_loss,
            subset=[
                "총 손익",
                "기대값"
            ]
        ).format(
            {
                "총 손익": "{:+,.0f}원",
                "거래횟수": "{:,}회",
                "승률": "{:.1f}%",
                "손익비": "{:.2f}",
                "PF": "{:.2f}",
                "기대값": "{:+.2f}%",
                "평균 R": "{:+.2f}R"
            }
        ),
        use_container_width=True
    )


# =========================================================
# TAB 4
# RAW DATA
# =========================================================

with tab4:

    st.subheader(
        "📋 거래 원본 데이터"
    )

    display_df = df.sort_values(
        "Entry_Date",
        ascending=False
    ).copy()

    display_df = display_df[
        [
            "Trade_ID",
            "Entry_Date",
            "Exit_Date",
            "Ticker",
            "Entry_Price",
            "Exit_Price",
            "Buy_Amount",
            "Sell_Amount",
            "P_L_Amount",
            "ROI_Percent",
            "Stop_Price",
            "Target_Price",
            "Risk_Amount",
            "R_Multiple",
            "Holding_Days",
            "Strategy",
            "Entry_Reason",
            "Emotion",
            "Discipline",
            "Mistake_Tags",
            "Memo"
        ]
    ]

    styled = (
        display_df.style
        .map(
            color_profit_loss,
            subset=[
                "P_L_Amount",
                "ROI_Percent",
                "R_Multiple"
            ]
        )
        .format(
            {
                "Entry_Price": "{:,.0f}",
                "Exit_Price": "{:,.0f}",
                "Buy_Amount": "{:,.0f}",
                "Sell_Amount": "{:,.0f}",
                "P_L_Amount": "{:+,.0f}",
                "ROI_Percent": "{:+.2f}%",
                "Stop_Price": "{:,.0f}",
                "Target_Price": "{:,.0f}",
                "Risk_Amount": "{:,.0f}",
                "R_Multiple": "{:+.2f}R"
            }
        )
    )

    st.dataframe(
        styled,
        use_container_width=True,
        height=600
    )


# =========================================================
# TAB 5
# VICTOR SPERANDEO
# =========================================================

with tab5:

    st.subheader(
        "⚖️ Reward-to-Risk Analysis"
    )

    vic_period = st.radio(
        "분석 기간",
        [
            "전체",
            "최근 1개월",
            "최근 3개월",
            "최근 6개월",
            "최근 1년"
        ],
        horizontal=True,
        key="vic_radio"
    )

    vic_df = df.copy()

    today = pd.Timestamp.today()

    if vic_period == "최근 1개월":

        vic_df = vic_df[
            vic_df["Entry_Date"]
            >=
            today - timedelta(days=30)
        ]

    elif vic_period == "최근 3개월":

        vic_df = vic_df[
            vic_df["Entry_Date"]
            >=
            today - timedelta(days=90)
        ]

    elif vic_period == "최근 6개월":

        vic_df = vic_df[
            vic_df["Entry_Date"]
            >=
            today - timedelta(days=180)
        ]

    elif vic_period == "최근 1년":

        vic_df = vic_df[
            vic_df["Entry_Date"]
            >=
            today - timedelta(days=365)
        ]

    if vic_df.empty:

        st.info(
            "선택한 기간에 데이터가 없습니다."
        )

    else:

        v_wins = vic_df[
            vic_df["ROI_Percent"] > 0
        ]

        v_losses = vic_df[
            vic_df["ROI_Percent"] <= 0
        ]

        v_win_rate = (
            len(v_wins)
            /
            len(vic_df)
            *
            100
        )

        v_avg_win = (
            v_wins["ROI_Percent"].mean()
            if not v_wins.empty
            else 0
        )

        v_avg_loss = (
            abs(
                v_losses[
                    "ROI_Percent"
                ].mean()
            )
            if not v_losses.empty
            else 0
        )

        v_rr = (
            v_avg_win
            /
            v_avg_loss
            if v_avg_loss > 0
            else 0
        )

        v_expectancy = (
            (v_win_rate / 100)
            * v_avg_win
            -
            (1 - v_win_rate / 100)
            * v_avg_loss
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "승률",
            f"{v_win_rate:.1f}%"
        )

        c2.metric(
            "평균 손익비",
            f"{v_rr:.2f}:1"
        )

        c3.metric(
            "기대값",
            f"{v_expectancy:+.2f}%"
        )

        st.divider()

        scatter = (
            alt.Chart(vic_df)
            .mark_circle(size=100)
            .encode(
                x=alt.X(
                    "Entry_Date:T",
                    title="진입일"
                ),
                y=alt.Y(
                    "ROI_Percent:Q",
                    title="수익률"
                ),
                tooltip=[
                    "Ticker",
                    "Entry_Date",
                    "ROI_Percent",
                    "P_L_Amount"
                ]
            )
            .interactive()
        )

        st.altair_chart(
            scatter,
            use_container_width=True
        )


# =========================================================
# TAB 6
# R MULTIPLE
# =========================================================

with tab6:

    st.subheader(
        "🎯 R-배수 분석"
    )

    valid_r_df = df[
        df["Risk_Amount"] > 0
    ].copy()

    if valid_r_df.empty:

        st.info(
            "손절가를 입력한 거래가 아직 없습니다."
        )

        st.markdown(
            """
            ### R 분석을 사용하려면

            거래 입력 화면에서

            **매수가 → 손절가 → 매도**

            를 입력해주세요.

            그러면 앱이 자동으로

            `+2R`

            `-1R`

            `+3.5R`

            같은 방식으로 계산합니다.
            """
        )

    else:

        avg_r = (
            valid_r_df["R_Multiple"]
            .mean()
        )

        max_r = (
            valid_r_df["R_Multiple"]
            .max()
        )

        min_r = (
            valid_r_df["R_Multiple"]
            .min()
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "평균 R",
            f"{avg_r:+.2f}R"
        )

        c2.metric(
            "최고 R",
            f"{max_r:+.2f}R"
        )

        c3.metric(
            "최저 R",
            f"{min_r:+.2f}R"
        )

        st.divider()

        r_chart_df = (
            valid_r_df
            .sort_values("Entry_Date")
            .copy()
        )

        r_chart_df[
            "Cumulative_R"
        ] = (
            r_chart_df["R_Multiple"]
            .cumsum()
        )

        r_chart_df[
            "Trade_Number"
        ] = range(
            1,
            len(r_chart_df) + 1
        )

        chart = (
            alt.Chart(
                r_chart_df
            )
            .mark_line(
                strokeWidth=3
            )
            .encode(
                x=alt.X(
                    "Trade_Number:Q",
                    title="거래 횟수"
                ),
                y=alt.Y(
                    "Cumulative_R:Q",
                    title="누적 R"
                ),
                tooltip=[
                    "Ticker",
                    "R_Multiple",
                    "Cumulative_R"
                ]
            )
            .interactive()
        )

        st.altair_chart(
            chart,
            use_container_width=True
        )


# =========================================================
# TAB 7
# PROFIT / LOSS DISTRIBUTION
# =========================================================

with tab7:

    st.subheader(
        "🔔 손익 분포"
    )

    bin_step = st.slider(
        "구간 크기 (%)",
        0.5,
        10.0,
        2.5,
        0.5
    )

    hist_chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(
                "ROI_Percent",
                bin=alt.Bin(
                    step=bin_step
                ),
                title="수익률 (%)"
            ),
            y=alt.Y(
                "count()",
                title="거래 횟수"
            ),
            tooltip=[
                "count()"
            ]
        )
        .properties(
            height=400
        )
    )

    st.altair_chart(
        hist_chart,
        use_container_width=True
    )

    skew = (
        df["ROI_Percent"]
        .skew()
    )

    st.metric(
        "수익률 분포 왜도",
        f"{skew:.2f}"
    )

    if skew > 0.5:

        st.success(
            "수익 쪽 꼬리가 긴 분포입니다."
        )

    elif skew < -0.5:

        st.warning(
            "손실 쪽 꼬리가 긴 분포입니다."
        )

    else:

        st.info(
            "수익과 손실 분포가 비교적 대칭적입니다."
        )


# =========================================================
# TAB 8
# PERSONAL TRADING PATTERN
# =========================================================

with tab8:

    st.subheader(
        "🧠 나의 매매 패턴"
    )

    st.caption(
        "여기가 앞으로 Trading Master의 핵심 기능이 될 부분입니다."
    )

    # -----------------------------------------------------
    # Strategy Analysis
    # -----------------------------------------------------

    if (
        "Strategy" in df.columns
        and df["Strategy"].astype(str).str.strip().ne("").any()
    ):

        strategy_stats = []

        for strategy, group in df.groupby(
            "Strategy"
        ):

            strategy_wins = group[
                group["P_L_Amount"] > 0
            ]

            strategy_losses = group[
                group["P_L_Amount"] <= 0
            ]

            count = len(group)

            win_rate_s = (
                len(strategy_wins)
                /
                count
                *
                100
                if count > 0
                else 0
            )

            gross_profit_s = (
                strategy_wins[
                    "P_L_Amount"
                ].sum()
            )

            gross_loss_s = abs(
                strategy_losses[
                    "P_L_Amount"
                ].sum()
            )

            pf_s = (
                gross_profit_s
                /
                gross_loss_s
                if gross_loss_s > 0
                else 0
            )

            avg_roi_s = (
                group[
                    "ROI_Percent"
                ].mean()
            )

            avg_r_s = (
                group[
                    "R_Multiple"
                ]
                .replace(
                    [np.inf, -np.inf],
                    np.nan
                )
                .mean()
            )

            strategy_stats.append(
                {
                    "전략": strategy,
                    "거래횟수": count,
                    "승률": win_rate_s,
                    "PF": pf_s,
                    "평균수익률": avg_roi_s,
                    "평균R": avg_r_s,
                    "총손익": group[
                        "P_L_Amount"
                    ].sum()
                }
            )

        strategy_df = pd.DataFrame(
            strategy_stats
        ).sort_values(
            "총손익",
            ascending=False
        )

        st.markdown(
            "### 🎯 전략별 성적"
        )

        st.dataframe(
            strategy_df.style.map(
                color_profit_loss,
                subset=[
                    "총손익",
                    "평균수익률"
                ]
            ).format(
                {
                    "거래횟수": "{:,}",
                    "승률": "{:.1f}%",
                    "PF": "{:.2f}",
                    "평균수익률": "{:+.2f}%",
                    "평균R": "{:+.2f}R",
                    "총손익": "{:+,.0f}원"
                }
            ),
            use_container_width=True
        )

    # -----------------------------------------------------
    # Holding Period Analysis
    # -----------------------------------------------------

    st.markdown(
        "### 📅 보유기간별 성적"
    )

    holding_df = df.copy()

    holding_df["보유구간"] = pd.cut(
        holding_df["Holding_Days"],
        bins=[
            -1,
            1,
            3,
            5,
            10,
            20,
            99999
        ],
        labels=[
            "당일",
            "2~3일",
            "4~5일",
            "6~10일",
            "11~20일",
            "21일 이상"
        ]
    )

    holding_stats = (
        holding_df
        .groupby(
            "보유구간",
            observed=False
        )
        .agg(
            거래횟수=(
                "P_L_Amount",
                "count"
            ),
            평균수익률=(
                "ROI_Percent",
                "mean"
            ),
            평균R=(
                "R_Multiple",
                "mean"
            ),
            총손익=(
                "P_L_Amount",
                "sum"
            )
        )
        .reset_index()
    )

    st.dataframe(
        holding_stats.style.map(
            color_profit_loss,
            subset=[
                "평균수익률",
                "총손익"
            ]
        ).format(
            {
                "거래횟수": "{:,}",
                "평균수익률": "{:+.2f}%",
                "평균R": "{:+.2f}R",
                "총손익": "{:+,.0f}원"
            }
        ),
        use_container_width=True
    )

    # -----------------------------------------------------
    # Emotion Analysis
    # -----------------------------------------------------

    st.markdown(
        "### 🧠 감정별 성적"
    )

    emotion_df = (
        df[
            df["Emotion"]
            .astype(str)
            .str.strip()
            != ""
        ]
        .groupby("Emotion")
        .agg(
            거래횟수=(
                "P_L_Amount",
                "count"
            ),
            평균수익률=(
                "ROI_Percent",
                "mean"
            ),
            평균R=(
                "R_Multiple",
                "mean"
            ),
            총손익=(
                "P_L_Amount",
                "sum"
            )
        )
        .reset_index()
    )

    if not emotion_df.empty:

        st.dataframe(
            emotion_df.style.map(
                color_profit_loss,
                subset=[
                    "평균수익률",
                    "총손익"
                ]
            ).format(
                {
                    "거래횟수": "{:,}",
                    "평균수익률": "{:+.2f}%",
                    "평균R": "{:+.2f}R",
                    "총손익": "{:+,.0f}원"
                }
            ),
            use_container_width=True
        )

    # -----------------------------------------------------
    # Mistake Analysis
    # -----------------------------------------------------

    st.markdown(
        "### ⚠️ 실수 분석"
    )

    mistake_rows = []

    for _, row in df.iterrows():

        tags = str(
            row.get(
                "Mistake_Tags",
                ""
            )
        )

        if not tags:
            continue

        for tag in tags.split(","):

            tag = tag.strip()

            if tag:
                mistake_rows.append(
                    {
                        "실수": tag,
                        "손익": row[
                            "P_L_Amount"
                        ],
                        "수익률": row[
                            "ROI_Percent"
                        ]
                    }
                )

    if mistake_rows:

        mistake_df = (
            pd.DataFrame(
                mistake_rows
            )
            .groupby("실수")
            .agg(
                발생횟수=(
                    "손익",
                    "count"
                ),
                평균손익=(
                    "손익",
                    "mean"
                ),
                평균수익률=(
                    "수익률",
                    "mean"
                )
            )
            .reset_index()
            .sort_values(
                "발생횟수",
                ascending=False
            )
        )

        st.dataframe(
            mistake_df.style.map(
                color_profit_loss,
                subset=[
                    "평균손익",
                    "평균수익률"
                ]
            ).format(
                {
                    "발생횟수": "{:,}",
                    "평균손익": "{:+,.0f}원",
                    "평균수익률": "{:+.2f}%"
                }
            ),
            use_container_width=True
        )

    else:

        st.info(
            "아직 실수 태그 데이터가 없습니다."
        )


# =========================================================
# 20. FOOTER
# =========================================================

st.divider()

st.caption(
    "💎 Trading Master 2.0 | "
    "STEP 1 데이터 구조 개편 + STEP 2 거래 입력 화면"
        )
