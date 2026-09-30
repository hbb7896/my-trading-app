import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import altair as alt
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import random
import json
import re
import hashlib
import google.generativeai as genai
from PIL import Image


# ============================================================
# 1. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="Trading Master Dashboard",
    page_icon="💎",
    layout="wide"
)


# ============================================================
# 2. Google Sheets 연결
# ============================================================

conn = st.connection(
    "gsheets",
    type=GSheetsConnection
)


# ============================================================
# 3. 기본 컬럼
# ============================================================

REQUIRED_COLUMNS = [
    "Trade_ID",
    "Date",
    "Ticker",
    "Buy_Amount",
    "Sell_Amount",
    "P_L_Amount",
    "ROI_Percent",
    "Mistake_Tags",
    "Emotion",
    "Discipline",
    "Memo"
]


# ============================================================
# 4. Trade ID
# ============================================================

def create_legacy_trade_id(row, index):

    values = [
        str(index),
        str(row.get("Date", "")),
        str(row.get("Ticker", "")),
        str(row.get("Buy_Amount", "")),
        str(row.get("Sell_Amount", "")),
        str(row.get("P_L_Amount", "")),
        str(row.get("ROI_Percent", "")),
        str(row.get("Memo", ""))
    ]

    raw = "|".join(values)

    digest = hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:12]

    return f"LEGACY_{digest}"


def create_new_trade_id():

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S%f"
    )

    random_number = random.randint(
        1000,
        9999
    )

    return f"TRD_{timestamp}_{random_number}"


# ============================================================
# 5. 설정
# ============================================================

def load_status():

    try:

        df_config = conn.read(
            worksheet=1,
            ttl=0
        )

        if df_config.empty:
            return 20000000, 5000000, []

        row = df_config.iloc[0]

        equity = int(
            row.get(
                "Total_Equity",
                20000000
            )
        )

        max_pos = int(
            row.get(
                "Max_Position",
                5000000
            )
        )

        history_str = str(
            row.get(
                "History",
                ""
            )
        )

        if (
            history_str
            and
            history_str != "nan"
        ):

            history = history_str.split(",")

        else:

            history = []

        return equity, max_pos, history

    except Exception:

        return 20000000, 5000000, []


def save_status(
    equity,
    max_pos,
    history
):

    try:

        history_str = ",".join(
            [str(x) for x in history]
        )

        df_config = conn.read(
            worksheet=1,
            ttl=0
        )

        if not df_config.empty:

            new_df = df_config.copy()

            new_df.at[
                0,
                "Total_Equity"
            ] = equity

            new_df.at[
                0,
                "Max_Position"
            ] = max_pos

            new_df.at[
                0,
                "History"
            ] = history_str

        else:

            new_df = pd.DataFrame(
                [{
                    "Total_Equity": equity,
                    "Max_Position": max_pos,
                    "History": history_str
                }]
            )

        conn.update(
            worksheet=1,
            data=new_df
        )

    except Exception as e:

        st.error(
            f"설정 저장 실패: {e}"
        )


@st.cache_data(ttl=0)
def load_settings():

    try:

        config_df = conn.read(
            worksheet=1,
            ttl=0
        )

        if not config_df.empty:

            return (
                config_df
                .iloc[0]
                .to_dict()
            )

    except Exception:

        pass

    return {}


saved_config = load_settings()


# ============================================================
# 6. KRX 종목 리스트
# ============================================================

@st.cache_data(ttl=3600)
def get_krx_list():

    try:

        krx_df = fdr.StockListing(
            "KRX"
        )

        return krx_df[
            [
                "Code",
                "Name",
                "Market"
            ]
        ]

    except Exception:

        return pd.DataFrame()


# ============================================================
# 7. 거래 데이터 정리
# ============================================================

def normalize_trade_dataframe(raw_df):

    if raw_df is None or raw_df.empty:

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )

    clean_df = raw_df.copy()

    if "Date" not in clean_df.columns:
        clean_df["Date"] = None

    clean_df = clean_df.dropna(
        subset=["Date"]
    ).copy()

    if clean_df.empty:

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )

    defaults = {
        "Trade_ID": "",
        "Ticker": "",
        "Buy_Amount": 0.0,
        "Sell_Amount": 0.0,
        "P_L_Amount": 0.0,
        "ROI_Percent": 0.0,
        "Mistake_Tags": "",
        "Emotion": "",
        "Discipline": "",
        "Memo": ""
    }

    for col, default_value in defaults.items():

        if col not in clean_df.columns:
            clean_df[col] = default_value

    numeric_columns = [
        "P_L_Amount",
        "ROI_Percent",
        "Buy_Amount",
        "Sell_Amount"
    ]

    for col in numeric_columns:

        clean_df[col] = (
            clean_df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace("원", "", regex=False)
            .str.strip()
        )

        clean_df[col] = pd.to_numeric(
            clean_df[col],
            errors="coerce"
        ).fillna(0.0)

    clean_df["Date"] = pd.to_datetime(
        clean_df["Date"],
        errors="coerce"
    )

    clean_df = clean_df.dropna(
        subset=["Date"]
    ).copy()

    string_columns = [
        "Ticker",
        "Mistake_Tags",
        "Emotion",
        "Discipline",
        "Memo"
    ]

    for col in string_columns:

        clean_df[col] = (
            clean_df[col]
            .fillna("")
            .astype(str)
        )

        clean_df.loc[
            clean_df[col].str.lower() == "nan",
            col
        ] = ""

    recovery_mask = (
        (clean_df["Buy_Amount"] == 0)
        &
        (clean_df["ROI_Percent"] != 0)
    )

    if recovery_mask.any():

        calculated_buy = (
            clean_df.loc[
                recovery_mask,
                "P_L_Amount"
            ]
            /
            (
                clean_df.loc[
                    recovery_mask,
                    "ROI_Percent"
                ]
                / 100
            )
        ).abs()

        clean_df.loc[
            recovery_mask,
            "Buy_Amount"
        ] = calculated_buy

        clean_df.loc[
            recovery_mask,
            "Sell_Amount"
        ] = (
            clean_df.loc[
                recovery_mask,
                "Buy_Amount"
            ]
            +
            clean_df.loc[
                recovery_mask,
                "P_L_Amount"
            ]
        )

    for position, idx in enumerate(
        clean_df.index
    ):

        current_id = clean_df.at[
            idx,
            "Trade_ID"
        ]

        if (
            pd.isna(current_id)
            or
            str(current_id).strip() == ""
            or
            str(current_id).lower() == "nan"
        ):

            clean_df.at[
                idx,
                "Trade_ID"
            ] = create_legacy_trade_id(
                clean_df.loc[idx],
                position
            )

        else:

            clean_df.at[
                idx,
                "Trade_ID"
            ] = str(current_id)

    for col in REQUIRED_COLUMNS:

        if col not in clean_df.columns:
            clean_df[col] = ""

    clean_df = clean_df[
        REQUIRED_COLUMNS
    ].copy()

    clean_df.reset_index(
        drop=True,
        inplace=True
    )

    return clean_df


def prepare_for_sheet(dataframe):

    sheet_df = dataframe.copy()

    if "Date" in sheet_df.columns:

        sheet_df["Date"] = pd.to_datetime(
            sheet_df["Date"],
            errors="coerce"
        ).dt.strftime(
            "%Y-%m-%d"
        )

    for col in REQUIRED_COLUMNS:

        if col not in sheet_df.columns:
            sheet_df[col] = ""

    sheet_df = sheet_df[
        REQUIRED_COLUMNS
    ]

    sheet_df = sheet_df.replace(
        {
            np.nan: "",
            np.inf: "",
            -np.inf: ""
        }
    )

    return sheet_df


def load_data():

    try:

        raw_df = conn.read(
            worksheet=0,
            ttl=0
        )

        return normalize_trade_dataframe(
            raw_df
        )

    except Exception as e:

        st.error(
            f"데이터 불러오기 실패: {e}"
        )

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )


def migrate_trade_ids():

    try:

        raw_df = conn.read(
            worksheet=0,
            ttl=0
        )

        if raw_df.empty:
            return

        needs_migration = False

        if "Trade_ID" not in raw_df.columns:

            needs_migration = True

        else:

            trade_id_series = (
                raw_df["Trade_ID"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            if (
                (trade_id_series == "")
                |
                (
                    trade_id_series
                    .str.lower()
                    == "nan"
                )
            ).any():

                needs_migration = True

        if needs_migration:

            migrated_df = (
                normalize_trade_dataframe(
                    raw_df
                )
            )

            sheet_df = (
                prepare_for_sheet(
                    migrated_df
                )
            )

            conn.update(
                worksheet=0,
                data=sheet_df
            )

    except Exception:
        pass


# ============================================================
# 8. TRADING DNA 분석 엔진
# ============================================================

def calculate_expectancy(data):

    if data.empty:
        return 0.0

    wins = data[
        data["ROI_Percent"] > 0
    ]

    losses = data[
        data["ROI_Percent"] <= 0
    ]

    total = len(data)

    win_prob = (
        len(wins) / total
        if total > 0
        else 0
    )

    loss_prob = 1 - win_prob

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

    return (
        win_prob * avg_win
        -
        loss_prob * avg_loss
    )


def calculate_max_streaks(data):

    if data.empty:
        return 0, 0

    ordered = data.sort_values(
        [
            "Date",
            "Trade_ID"
        ]
    )

    max_win_streak = 0
    max_loss_streak = 0

    current_win = 0
    current_loss = 0

    for value in ordered["P_L_Amount"]:

        if value > 0:

            current_win += 1
            current_loss = 0

            max_win_streak = max(
                max_win_streak,
                current_win
            )

        elif value < 0:

            current_loss += 1
            current_win = 0

            max_loss_streak = max(
                max_loss_streak,
                current_loss
            )

        else:

            current_win = 0
            current_loss = 0

    return (
        max_win_streak,
        max_loss_streak
    )


def calculate_trading_dna(data):

    result = {}

    if data.empty:
        return result

    ordered = (
        data
        .sort_values(
            [
                "Date",
                "Trade_ID"
            ]
        )
        .copy()
    )

    wins = ordered[
        ordered["P_L_Amount"] > 0
    ].copy()

    losses = ordered[
        ordered["P_L_Amount"] < 0
    ].copy()

    total_count = len(ordered)

    win_count = len(wins)
    loss_count = len(losses)

    win_rate = (
        win_count
        /
        total_count
        *
        100
        if total_count > 0
        else 0
    )

    gross_profit = (
        wins["P_L_Amount"].sum()
        if not wins.empty
        else 0
    )

    gross_loss = (
        abs(
            losses["P_L_Amount"].sum()
        )
        if not losses.empty
        else 0
    )

    profit_factor = (
        gross_profit
        /
        gross_loss
        if gross_loss > 0
        else 0
    )

    avg_win_pct = (
        wins["ROI_Percent"].mean()
        if not wins.empty
        else 0
    )

    avg_loss_pct = (
        abs(
            losses["ROI_Percent"].mean()
        )
        if not losses.empty
        else 0
    )

    reward_risk = (
        avg_win_pct
        /
        avg_loss_pct
        if avg_loss_pct > 0
        else 0
    )

    expectancy = calculate_expectancy(
        ordered
    )

    # --------------------------------------------------------
    # 수익 상위 10% 집중도
    # 분모는 Gross Profit
    # --------------------------------------------------------

    if not wins.empty and gross_profit > 0:

        top_n = max(
            1,
            int(
                np.ceil(
                    len(wins) * 0.10
                )
            )
        )

        top_profit = (
            wins
            .nlargest(
                top_n,
                "P_L_Amount"
            )["P_L_Amount"]
            .sum()
        )

        top10_contribution = (
            top_profit
            /
            gross_profit
            *
            100
        )

    else:

        top_n = 0
        top10_contribution = 0


    # --------------------------------------------------------
    # Big Winner
    # 평균 손실률의 2배 이상 수익 거래
    # --------------------------------------------------------

    big_winner_threshold = (
        avg_loss_pct * 2
        if avg_loss_pct > 0
        else 10
    )

    big_winners = wins[
        wins["ROI_Percent"]
        >=
        big_winner_threshold
    ].copy()

    big_winner_profit = (
        big_winners[
            "P_L_Amount"
        ].sum()
        if not big_winners.empty
        else 0
    )

    big_winner_contribution = (
        big_winner_profit
        /
        gross_profit
        *
        100
        if gross_profit > 0
        else 0
    )


    # --------------------------------------------------------
    # 최대 연승 / 연패
    # --------------------------------------------------------

    max_win_streak, max_loss_streak = (
        calculate_max_streaks(
            ordered
        )
    )


    # --------------------------------------------------------
    # 최대 손실
    # --------------------------------------------------------

    max_loss_pct = (
        abs(
            losses[
                "ROI_Percent"
            ].min()
        )
        if not losses.empty
        else 0
    )

    max_loss_amount = (
        abs(
            losses[
                "P_L_Amount"
            ].min()
        )
        if not losses.empty
        else 0
    )


    # --------------------------------------------------------
    # 최근 20거래 vs 직전 20거래
    # --------------------------------------------------------

    recent_n = min(
        20,
        total_count
    )

    recent_df = (
        ordered
        .tail(
            recent_n
        )
        .copy()
    )

    recent_expectancy = (
        calculate_expectancy(
            recent_df
        )
    )

    recent_wins = recent_df[
        recent_df[
            "P_L_Amount"
        ] > 0
    ]

    recent_losses = recent_df[
        recent_df[
            "P_L_Amount"
        ] < 0
    ]

    recent_win_rate = (
        len(recent_wins)
        /
        len(recent_df)
        *
        100
        if len(recent_df) > 0
        else 0
    )

    recent_gp = (
        recent_wins[
            "P_L_Amount"
        ].sum()
        if not recent_wins.empty
        else 0
    )

    recent_gl = (
        abs(
            recent_losses[
                "P_L_Amount"
            ].sum()
        )
        if not recent_losses.empty
        else 0
    )

    recent_pf = (
        recent_gp
        /
        recent_gl
        if recent_gl > 0
        else 0
    )


    if total_count > recent_n:

        previous_df = (
            ordered
            .iloc[
                max(
                    0,
                    total_count
                    -
                    recent_n * 2
                ):
                total_count
                -
                recent_n
            ]
            .copy()
        )

    else:

        previous_df = pd.DataFrame(
            columns=ordered.columns
        )

    previous_expectancy = (
        calculate_expectancy(
            previous_df
        )
        if not previous_df.empty
        else expectancy
    )

    edge_change = (
        recent_expectancy
        -
        previous_expectancy
    )


    # --------------------------------------------------------
    # 트레이더 DNA 유형
    # --------------------------------------------------------

    if (
        reward_risk >= 2.0
        and
        win_rate < 50
    ):

        dna_type = "🧬 Trend Follower"

        dna_description = (
            "낮은 승률을 감수하고 큰 수익 거래로 "
            "전체 성과를 만드는 추세추종형 구조입니다."
        )

    elif (
        win_rate >= 60
        and
        reward_risk < 1.5
    ):

        dna_type = "🎯 High Accuracy Trader"

        dna_description = (
            "높은 승률을 기반으로 수익을 누적하는 "
            "고승률형 구조입니다."
        )

    elif (
        reward_risk >= 1.5
        and
        win_rate >= 45
    ):

        dna_type = "⚖️ Balanced Trader"

        dna_description = (
            "승률과 손익비가 비교적 균형을 이루는 "
            "밸런스형 구조입니다."
        )

    elif (
        top10_contribution >= 60
        or
        big_winner_contribution >= 60
    ):

        dna_type = "🚀 Big Winner Hunter"

        dna_description = (
            "소수의 큰 수익 거래가 전체 성과에 "
            "강한 영향을 주는 구조입니다."
        )

    else:

        dna_type = "🔬 Developing Edge"

        dna_description = (
            "현재 거래 기록에서는 한 가지 뚜렷한 "
            "수익 구조보다 여러 패턴이 혼합되어 있습니다."
        )


    result = {
        "total_count":
            total_count,

        "win_rate":
            win_rate,

        "profit_factor":
            profit_factor,

        "reward_risk":
            reward_risk,

        "expectancy":
            expectancy,

        "avg_win_pct":
            avg_win_pct,

        "avg_loss_pct":
            avg_loss_pct,

        "gross_profit":
            gross_profit,

        "gross_loss":
            gross_loss,

        "top10_contribution":
            top10_contribution,

        "top_n":
            top_n,

        "big_winner_threshold":
            big_winner_threshold,

        "big_winner_count":
            len(big_winners),

        "big_winner_contribution":
            big_winner_contribution,

        "max_win_streak":
            max_win_streak,

        "max_loss_streak":
            max_loss_streak,

        "max_loss_pct":
            max_loss_pct,

        "max_loss_amount":
            max_loss_amount,

        "recent_count":
            recent_n,

        "recent_expectancy":
            recent_expectancy,

        "recent_win_rate":
            recent_win_rate,

        "recent_pf":
            recent_pf,

        "previous_expectancy":
            previous_expectancy,

        "edge_change":
            edge_change,

        "dna_type":
            dna_type,

        "dna_description":
            dna_description,

        "big_winners":
            big_winners,

        "recent_df":
            recent_df
    }

    return result


def generate_rule_based_insights(dna):

    insights = []

    if not dna:
        return insights

    if dna["big_winner_contribution"] >= 60:

        insights.append(
            "🔥 큰 수익 거래가 전체 Gross Profit의 "
            f"{dna['big_winner_contribution']:.1f}%를 만들고 있습니다. "
            "큰 승자를 너무 일찍 정리하는 행동이 전체 성과에 "
            "큰 영향을 줄 수 있는 구조입니다."
        )

    elif dna["big_winner_contribution"] >= 35:

        insights.append(
            "🔥 Big Winner가 전체 수익에서 의미 있는 비중을 "
            "차지하고 있습니다. 큰 수익 거래를 어떻게 관리했는지 "
            "계속 기록할 가치가 있습니다."
        )

    else:

        insights.append(
            "📊 현재 수익은 소수의 초대형 거래보다 여러 수익 거래에 "
            "상대적으로 분산되어 있습니다."
        )


    if dna["top10_contribution"] >= 60:

        insights.append(
            "💎 수익 거래 중 상위 10%가 Gross Profit의 "
            f"{dna['top10_contribution']:.1f}%를 차지합니다. "
            "상위 승자들의 공통점을 찾는 것이 중요한 분석 과제입니다."
        )

    elif dna["top10_contribution"] >= 40:

        insights.append(
            "💎 상위 수익 거래의 기여도가 높은 편입니다. "
            "최고 수익 거래에서 반복되는 진입·보유·청산 조건을 "
            "추적하면 전략 개선에 도움이 됩니다."
        )


    if (
        dna["reward_risk"] >= 2
        and
        dna["win_rate"] < 50
    ):

        insights.append(
            "🧬 승률보다 손익비가 성과를 만드는 구조입니다. "
            "연패 자체보다 평균 손실을 통제하면서 큰 승자를 "
            "확보하는지가 더 중요한 특성으로 나타납니다."
        )

    elif (
        dna["win_rate"] >= 55
        and
        dna["reward_risk"] < 1.5
    ):

        insights.append(
            "🎯 높은 승률 의존도가 상대적으로 높습니다. "
            "큰 손실 한 번이 여러 번의 작은 수익을 훼손하는지 "
            "계속 확인할 필요가 있습니다."
        )


    if (
        dna["avg_loss_pct"] > 0
        and
        dna["max_loss_pct"]
        >=
        dna["avg_loss_pct"] * 2.5
    ):

        insights.append(
            "⚠️ 최대 손실이 평균 손실보다 상당히 큽니다. "
            "일부 예외적 손실이 전체 성과를 훼손하는지 "
            "확인할 필요가 있습니다."
        )

    else:

        insights.append(
            "🛡️ 최대 손실이 평균 손실에서 과도하게 이탈하는지 "
            "지속적으로 모니터링하세요."
        )


    if dna["recent_count"] >= 10:

        if dna["edge_change"] > 1:

            insights.append(
                "📈 최근 거래의 기댓값이 직전 구간보다 "
                f"{dna['edge_change']:+.2f}%p 개선되었습니다."
            )

        elif dna["edge_change"] < -1:

            insights.append(
                "📉 최근 거래의 기댓값이 직전 구간보다 "
                f"{dna['edge_change']:+.2f}%p 낮아졌습니다. "
                "최근 거래에서 달라진 행동이나 시장 환경을 "
                "점검할 구간입니다."
            )

        else:

            insights.append(
                "➡️ 최근 거래의 기댓값은 직전 구간과 "
                "큰 차이가 없습니다."
            )


    if dna["max_loss_streak"] >= 6:

        insights.append(
            "🧠 과거 최대 연속 손실은 "
            f"{dna['max_loss_streak']}회입니다. "
            "이 정도의 연패가 전략상 발생할 수 있다는 사실을 "
            "포지션 사이징에 반영할 필요가 있습니다."
        )

    return insights


def create_roi_bucket_table(data):

    if data.empty:

        return pd.DataFrame()

    bucket_df = data.copy()

    bins = [
        -np.inf,
        -10,
        -5,
        0,
        5,
        10,
        20,
        np.inf
    ]

    labels = [
        "-10% 이하",
        "-10 ~ -5%",
        "-5 ~ 0%",
        "0 ~ +5%",
        "+5 ~ +10%",
        "+10 ~ +20%",
        "+20% 이상"
    ]

    bucket_df["수익률 구간"] = pd.cut(
        bucket_df["ROI_Percent"],
        bins=bins,
        labels=labels,
        right=False
    )

    summary = (
        bucket_df
        .groupby(
            "수익률 구간",
            observed=False
        )
        .agg(
            거래수=(
                "Trade_ID",
                "count"
            ),
            총손익=(
                "P_L_Amount",
                "sum"
            ),
            평균수익률=(
                "ROI_Percent",
                "mean"
            )
        )
        .reset_index()
    )

    return summary


# ============================================================
# 9. 데이터 로딩
# ============================================================

migrate_trade_ids()

df = load_data()

krx_list = get_krx_list()


# ============================================================
# 10. 사이드바 AI 캡처 분석
# ============================================================

st.sidebar.header(
    "📸 AI 영수증 자동 입력"
)

with st.sidebar.expander(
    "🤖 캡쳐 화면 올리기",
    expanded=False
):

    st.markdown(
        "수익/손실 화면을 올리면 "
        "종목명, 매수금액, 수익률을 자동으로 읽습니다."
    )

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        key="sidebar_api"
    )

    uploaded_file = st.file_uploader(
        "증권사 캡쳐 이미지",
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
                "AI가 캡쳐를 분석 중입니다..."
            ):

                try:

                    genai.configure(
                        api_key=api_key.strip()
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

                        img = img.convert(
                            "RGB"
                        )

                    img.thumbnail(
                        (800, 800)
                    )

                    prompt = """
당신은 한국 주식 증권사 앱 캡쳐 화면을 분석하는
트레이딩 기록 보조 AI입니다.

이미지에서 다음 데이터를 추출하세요.

1. 종목명
2. 총 매수금액
3. 수익률(%)

규칙:
- 금액의 쉼표와 원은 제거
- % 기호 제거
- 손실은 음수
- 수익률이 없고 손익금액과 매수금액이 있으면 계산
- 수익률은 소수점 둘째 자리까지

반드시 JSON만 출력하세요.

{
  "ticker": "두산퓨얼셀",
  "buy_amount": 2991450,
  "roi": 0.04,
  "memo": "AI 스캔 완료"
}
"""

                    response = (
                        model.generate_content(
                            [
                                prompt,
                                img
                            ]
                        )
                    )

                    if not response.parts:

                        st.error(
                            "🚨 AI 응답이 없습니다."
                        )

                    else:

                        result_text = (
                            response.text.strip()
                        )

                        match = re.search(
                            r"\{.*\}",
                            result_text,
                            re.DOTALL
                        )

                        clean_json = (
                            match.group(0)
                            if match
                            else result_text
                        )

                        data = json.loads(
                            clean_json
                        )

                        ticker_value = str(
                            data.get(
                                "ticker",
                                ""
                            )
                        ).strip()

                        buy_value = (
                            str(
                                data.get(
                                    "buy_amount",
                                    0
                                )
                            )
                            .replace(",", "")
                            .replace("원", "")
                            .strip()
                        )

                        roi_value = (
                            str(
                                data.get(
                                    "roi",
                                    0
                                )
                            )
                            .replace(",", "")
                            .replace("%", "")
                            .strip()
                        )

                        st.session_state[
                            "ai_ticker"
                        ] = ticker_value

                        st.session_state[
                            "ai_buy_amt"
                        ] = int(
                            float(
                                buy_value or 0
                            )
                        )

                        st.session_state[
                            "ai_roi"
                        ] = float(
                            roi_value or 0
                        )

                        st.session_state[
                            "ai_memo"
                        ] = str(
                            data.get(
                                "memo",
                                "📸 AI 분석 자동 입력"
                            )
                        )

                        if (
                            "form_reset_trigger"
                            not in st.session_state
                        ):

                            st.session_state[
                                "form_reset_trigger"
                            ] = 0

                        st.session_state[
                            "form_reset_trigger"
                        ] += 1

                        st.success(
                            "✅ 분석 성공!"
                        )

                except Exception as e:

                    error_msg = str(e)

                    if (
                        "429" in error_msg
                        or
                        "quota"
                        in error_msg.lower()
                    ):

                        st.error(
                            "🚨 API 사용량 제한에 도달했습니다."
                        )

                    else:

                        st.error(
                            "🚨 이미지 분석에 실패했습니다."
                        )

                        with st.expander(
                            "🛠️ 오류 확인"
                        ):

                            st.write(
                                str(e)
                            )


# ============================================================
# 11. AI 입력 상태
# ============================================================

if (
    "form_reset_trigger"
    not in st.session_state
):

    st.session_state[
        "form_reset_trigger"
    ] = 0


def_ticker = st.session_state.get(
    "ai_ticker",
    ""
)

def_buy_amt = int(
    st.session_state.get(
        "ai_buy_amt",
        0
    )
)

def_roi = float(
    st.session_state.get(
        "ai_roi",
        0.0
    )
)

def_memo = st.session_state.get(
    "ai_memo",
    ""
)

fc = st.session_state[
    "form_reset_trigger"
]


# ============================================================
# 12. 신규 거래 입력
# ============================================================

st.sidebar.markdown("---")

st.sidebar.header(
    "📝 매매 기록 입력"
)

with st.sidebar.form(
    "quick_input",
    clear_on_submit=True
):

    date = st.date_input(
        "일자",
        datetime.today()
    )

    ticker = st.text_input(
        "종목명",
        value=def_ticker,
        key=f"ticker_{fc}"
    ).strip()

    st.markdown("---")

    buy_amt = st.number_input(
        "총 매수 금액 (원)",
        min_value=0,
        value=max(
            0,
            def_buy_amt
        ),
        step=100000,
        key=f"buy_{fc}"
    )

    roi = st.number_input(
        "수익률 (%)",
        value=def_roi,
        format="%.2f",
        key=f"roi_{fc}"
    )

    pn_l = (
        buy_amt
        *
        (roi / 100)
    )

    sell_amt = (
        buy_amt
        +
        pn_l
    )

    if buy_amt > 0:

        st.info(
            f"""
🧮 **자동 계산**

수익/손실금: **{pn_l:+,.0f}원**

매도금액: **{sell_amt:,.0f}원**
"""
        )

    memo = st.text_input(
        "메모",
        value=def_memo,
        key=f"memo_{fc}"
    )

    save_button = (
        st.form_submit_button(
            "💾 기록 저장",
            use_container_width=True
        )
    )

    if save_button:

        if not ticker:

            st.error(
                "종목명을 입력해주세요."
            )

        elif buy_amt <= 0:

            st.error(
                "매수금액을 입력해주세요."
            )

        else:

            try:

                new_trade = pd.DataFrame(
                    [{
                        "Trade_ID":
                            create_new_trade_id(),

                        "Date":
                            date.strftime(
                                "%Y-%m-%d"
                            ),

                        "Ticker":
                            ticker,

                        "Buy_Amount":
                            float(buy_amt),

                        "Sell_Amount":
                            float(sell_amt),

                        "P_L_Amount":
                            float(pn_l),

                        "ROI_Percent":
                            float(roi),

                        "Mistake_Tags":
                            "",

                        "Emotion":
                            "",

                        "Discipline":
                            "",

                        "Memo":
                            memo
                    }]
                )

                live_raw = conn.read(
                    worksheet=0,
                    ttl=0
                )

                if live_raw.empty:

                    updated_df = (
                        new_trade.copy()
                    )

                else:

                    live_df = (
                        normalize_trade_dataframe(
                            live_raw
                        )
                    )

                    updated_df = pd.concat(
                        [
                            live_df,
                            new_trade
                        ],
                        ignore_index=True
                    )

                updated_df = (
                    normalize_trade_dataframe(
                        updated_df
                    )
                )

                conn.update(
                    worksheet=0,
                    data=prepare_for_sheet(
                        updated_df
                    )
                )

                st.session_state[
                    "ai_ticker"
                ] = ""

                st.session_state[
                    "ai_buy_amt"
                ] = 0

                st.session_state[
                    "ai_roi"
                ] = 0.0

                st.session_state[
                    "ai_memo"
                ] = ""

                st.session_state[
                    "form_reset_trigger"
                ] += 1

                st.success(
                    f"✅ {ticker} 저장 완료!"
                )

                st.rerun()

            except Exception as e:

                st.error(
                    "🚨 거래 저장에 실패했습니다."
                )

                st.write(
                    f"오류: {e}"
                )


# ============================================================
# 13. 상태 표시
# ============================================================

if krx_list.empty:

    st.sidebar.caption(
        "⚠️ KRX 종목 리스트 로딩 실패"
    )

else:

    st.sidebar.caption(
        f"✅ {len(krx_list):,}개 종목 연결됨"
    )


# ============================================================
# 14. 메인
# ============================================================

st.title(
    "💎 Trading Master Dashboard"
)


if not df.empty:

    def color_profit_loss(val):

        try:

            if pd.isna(val):
                return ""

            number = float(val)

            if number > 0:

                return (
                    "color: #FF4444; "
                    "font-weight: bold;"
                )

            elif number < 0:

                return (
                    "color: #0066CC; "
                    "font-weight: bold;"
                )

        except Exception:
            pass

        return ""


    analysis_df = df.copy()

    analysis_df["Year"] = (
        analysis_df["Date"].dt.year
    )

    analysis_df["YearMonth"] = (
        analysis_df[
            "Date"
        ].dt.strftime(
            "%Y-%m"
        )
    )


    (
        tab1,
        tab2,
        tab3,
        tab4,
        tab5,
        tab6,
        tab7,
        tab8,
        tab9
    ) = st.tabs(
        [
            "📊 차트",
            "📅 월별",
            "📆 연도별",
            "📋 원본",
            "⚖️ 빅터",
            "🎯 R-배수",
            "🔔 손익 분포",
            "🛠️ 거래 관리",
            "🧠 Trading DNA"
        ]
    )


    # ========================================================
    # TAB 1 - 전체 성적
    # ========================================================

    with tab1:

        st.subheader(
            "🏆 전체 종합 성적표 (Total Legend)"
        )

        total_cnt = len(
            analysis_df
        )

        total_pl = (
            analysis_df[
                "P_L_Amount"
            ].sum()
        )

        all_wins = analysis_df[
            analysis_df[
                "ROI_Percent"
            ] > 0
        ]

        all_losses = analysis_df[
            analysis_df[
                "ROI_Percent"
            ] <= 0
        ]

        win_rate = (
            len(all_wins)
            /
            total_cnt
            *
            100
            if total_cnt > 0
            else 0
        )

        gross_profit = (
            all_wins[
                "P_L_Amount"
            ].sum()
        )

        gross_loss = abs(
            all_losses[
                "P_L_Amount"
            ].sum()
        )

        total_pf = (
            gross_profit
            /
            gross_loss
            if gross_loss > 0
            else 0
        )

        avg_profit_amt = (
            all_wins[
                "P_L_Amount"
            ].mean()
            if not all_wins.empty
            else 0
        )

        avg_loss_amt = (
            abs(
                all_losses[
                    "P_L_Amount"
                ].mean()
            )
            if not all_losses.empty
            else 0
        )

        money_rr = (
            avg_profit_amt
            /
            avg_loss_amt
            if avg_loss_amt > 0
            else 0
        )

        avg_profit_pct = (
            all_wins[
                "ROI_Percent"
            ].mean()
            if not all_wins.empty
            else 0
        )

        avg_loss_pct = (
            abs(
                all_losses[
                    "ROI_Percent"
                ].mean()
            )
            if not all_losses.empty
            else 0
        )

        period_rr = (
            avg_profit_pct
            /
            avg_loss_pct
            if avg_loss_pct > 0
            else 0
        )

        win_probability = (
            len(all_wins)
            /
            total_cnt
            if total_cnt > 0
            else 0
        )

        loss_probability = (
            1
            -
            win_probability
        )

        expectancy = (
            win_probability
            *
            avg_profit_pct
        ) - (
            loss_probability
            *
            avg_loss_pct
        )

        if money_rr > 0:

            kelly_fraction = (
                win_probability
                -
                (
                    loss_probability
                    /
                    money_rr
                )
            )

            kelly_pct = max(
                0.0,
                kelly_fraction * 100
            )

        else:

            kelly_pct = 0.0


        m1, m2, m3, m4, m5 = (
            st.columns(5)
        )

        m1.metric(
            "💰 누적 총 손익",
            f"{total_pl:,.0f}원"
        )

        m2.metric(
            "🎯 전체 승률",
            f"{win_rate:.1f}%"
        )

        m3.metric(
            "🔮 기간 기댓값",
            f"{expectancy:.2f}%"
        )

        m4.metric(
            "💎 Profit Factor",
            f"{total_pf:.2f}"
        )

        m5.metric(
            "⚖️ 켈리 베팅 비중",
            f"{kelly_pct:.1f}%"
        )


        st.divider()

        st.markdown(
            "##### 💵 금액(Money) 성적표"
        )

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        c1.metric(
            "평균 수익금",
            f"{avg_profit_amt:,.0f}원"
        )

        c2.metric(
            "평균 손실금",
            f"{avg_loss_amt:,.0f}원"
        )

        c3.metric(
            "⚖️ 금액 손익비",
            f"{money_rr:.2f}"
        )

        c4.metric(
            "🛒 총 매수 대금",
            f"{analysis_df['Buy_Amount'].sum():,.0f}원"
        )


        st.markdown(
            "##### 📊 기간(Technical) 성적표"
        )

        c5, c6, c7, c8 = (
            st.columns(4)
        )

        c5.metric(
            "평균 수익률",
            f"+{avg_profit_pct:.2f}%"
        )

        c6.metric(
            "평균 손실률",
            f"-{avg_loss_pct:.2f}%"
        )

        c7.metric(
            "⚖️ 기간 손익비",
            f"{period_rr:.2f}"
        )

        c8.metric(
            "📝 총 거래 횟수",
            f"{total_cnt:,}회"
        )


        st.divider()

        st.subheader(
            "🚀 내 계좌 vs KOSPI 지수"
        )

        daily_df = (
            analysis_df
            .groupby(
                "Date"
            )[
                "P_L_Amount"
            ]
            .sum()
            .reset_index()
            .sort_values(
                "Date"
            )
        )

        daily_df[
            "Cumulative"
        ] = (
            daily_df[
                "P_L_Amount"
            ].cumsum()
        )

        try:

            start_date = (
                daily_df[
                    "Date"
                ]
                .min()
                .strftime(
                    "%Y-%m-%d"
                )
            )

            kospi_raw = yf.download(
                "^KS11",
                start=start_date,
                progress=False,
                auto_adjust=False
            )

            if (
                kospi_raw is not None
                and
                not kospi_raw.empty
            ):

                if isinstance(
                    kospi_raw.columns,
                    pd.MultiIndex
                ):

                    kospi_close = (
                        kospi_raw[
                            "Close"
                        ]
                        .iloc[:, 0]
                    )

                else:

                    kospi_close = (
                        kospi_raw[
                            "Close"
                        ]
                    )

                kospi = (
                    kospi_close
                    .reset_index()
                )

                kospi.columns = [
                    "Date",
                    "KOSPI"
                ]

                kospi["Date"] = (
                    pd.to_datetime(
                        kospi["Date"]
                    )
                    .dt.tz_localize(
                        None
                    )
                )

                my_chart = (
                    alt.Chart(
                        daily_df
                    )
                    .mark_line(
                        color="#00AA00",
                        strokeWidth=3
                    )
                    .encode(
                        x=alt.X(
                            "Date:T",
                            title="Date"
                        ),
                        y=alt.Y(
                            "Cumulative:Q",
                            title="내 누적 손익"
                        ),
                        tooltip=[
                            alt.Tooltip(
                                "Date:T"
                            ),
                            alt.Tooltip(
                                "Cumulative:Q",
                                format=",.0f"
                            )
                        ]
                    )
                )

                kospi_chart = (
                    alt.Chart(
                        kospi
                    )
                    .mark_line(
                        color="#FF4444",
                        strokeDash=[
                            5,
                            5
                        ]
                    )
                    .encode(
                        x=alt.X(
                            "Date:T"
                        ),
                        y=alt.Y(
                            "KOSPI:Q",
                            title="KOSPI",
                            scale=alt.Scale(
                                zero=False
                            )
                        )
                    )
                )

                st.altair_chart(
                    alt.layer(
                        my_chart,
                        kospi_chart
                    ).resolve_scale(
                        y="independent"
                    ),
                    use_container_width=True
                )

            else:

                st.line_chart(
                    daily_df.set_index(
                        "Date"
                    )[
                        "Cumulative"
                    ]
                )

        except Exception:

            st.line_chart(
                daily_df.set_index(
                    "Date"
                )[
                    "Cumulative"
                ]
            )


        st.subheader(
            "📊 월별 손익 흐름"
        )

        monthly_chart_data = (
            analysis_df
            .groupby(
                "YearMonth"
            )[
                "P_L_Amount"
            ]
            .sum()
        )

        st.bar_chart(
            monthly_chart_data
        )


    # ========================================================
    # TAB 2 - 월별
    # ========================================================

    with tab2:

        st.subheader(
            "📅 월별 상세 성적표"
        )

        monthly_stats = []

        for ym, group in analysis_df.groupby(
            "YearMonth"
        ):

            g_wins = group[
                group[
                    "ROI_Percent"
                ] > 0
            ]

            g_losses = group[
                group[
                    "ROI_Percent"
                ] <= 0
            ]

            gp = group[
                group[
                    "P_L_Amount"
                ] > 0
            ]["P_L_Amount"].sum()

            gl = abs(
                group[
                    group[
                        "P_L_Amount"
                    ] <= 0
                ]["P_L_Amount"].sum()
            )

            avg_profit_amount = (
                g_wins[
                    "P_L_Amount"
                ].mean()
                if not g_wins.empty
                else 0
            )

            avg_loss_amount = (
                g_losses[
                    "P_L_Amount"
                ].mean()
                if not g_losses.empty
                else 0
            )

            pf = (
                gp / gl
                if gl > 0
                else 0
            )

            avg_gain_pct = (
                g_wins[
                    "ROI_Percent"
                ].mean()
                if not g_wins.empty
                else 0
            )

            avg_loss_pct_month = (
                abs(
                    g_losses[
                        "ROI_Percent"
                    ].mean()
                )
                if not g_losses.empty
                else 0
            )

            rr = (
                avg_gain_pct
                /
                avg_loss_pct_month
                if avg_loss_pct_month > 0
                else 0
            )

            count = len(group)

            win_prob = (
                len(g_wins)
                /
                count
                if count > 0
                else 0
            )

            exp_value = (
                win_prob
                *
                avg_gain_pct
            ) - (
                (1 - win_prob)
                *
                avg_loss_pct_month
            )

            monthly_stats.append(
                {
                    "기간":
                        str(ym),

                    "총 손익":
                        group[
                            "P_L_Amount"
                        ].sum(),

                    "평균수익":
                        avg_profit_amount,

                    "평균손실":
                        avg_loss_amount,

                    "거래횟수":
                        count,

                    "승률":
                        win_prob * 100,

                    "손익비":
                        rr,

                    "PF":
                        pf,

                    "기대수익":
                        exp_value,

                    "매수총액":
                        group[
                            "Buy_Amount"
                        ].sum()
                }
            )

        monthly_table = pd.DataFrame(
            monthly_stats
        )

        if not monthly_table.empty:

            monthly_table = (
                monthly_table
                .sort_values(
                    "기간",
                    ascending=False
                )
            )

            st.dataframe(
                monthly_table.style.format(
                    {
                        "총 손익":
                            "{:+,.0f}원",
                        "평균수익":
                            "{:,.0f}원",
                        "평균손실":
                            "{:,.0f}원",
                        "거래횟수":
                            "{:,}회",
                        "승률":
                            "{:.1f}%",
                        "손익비":
                            "{:.2f}",
                        "PF":
                            "{:.2f}",
                        "기대수익":
                            "{:+.2f}%",
                        "매수총액":
                            "{:,.0f}원"
                    }
                ),
                use_container_width=True
            )


    # ========================================================
    # TAB 3 - 연도별
    # ========================================================

    with tab3:

        st.subheader(
            "📆 연도별 종합 성적표"
        )

        yearly_stats = []

        for year, group in analysis_df.groupby(
            "Year"
        ):

            g_wins = group[
                group[
                    "ROI_Percent"
                ] > 0
            ]

            g_losses = group[
                group[
                    "ROI_Percent"
                ] <= 0
            ]

            gp = g_wins[
                "P_L_Amount"
            ].sum()

            gl = abs(
                g_losses[
                    "P_L_Amount"
                ].sum()
            )

            avg_profit_amount = (
                g_wins[
                    "P_L_Amount"
                ].mean()
                if not g_wins.empty
                else 0
            )

            avg_loss_amount = (
                g_losses[
                    "P_L_Amount"
                ].mean()
                if not g_losses.empty
                else 0
            )

            pf = (
                gp / gl
                if gl > 0
                else 0
            )

            avg_gain_pct = (
                g_wins[
                    "ROI_Percent"
                ].mean()
                if not g_wins.empty
                else 0
            )

            avg_loss_pct_year = (
                abs(
                    g_losses[
                        "ROI_Percent"
                    ].mean()
                )
                if not g_losses.empty
                else 0
            )

            rr = (
                avg_gain_pct
                /
                avg_loss_pct_year
                if avg_loss_pct_year > 0
                else 0
            )

            count = len(group)

            win_prob = (
                len(g_wins)
                /
                count
                if count > 0
                else 0
            )

            exp_value = (
                win_prob
                *
                avg_gain_pct
            ) - (
                (1 - win_prob)
                *
                avg_loss_pct_year
            )

            yearly_stats.append(
                {
                    "연도":
                        int(year),

                    "총 손익":
                        group[
                            "P_L_Amount"
                        ].sum(),

                    "평균수익":
                        avg_profit_amount,

                    "평균손실":
                        avg_loss_amount,

                    "거래횟수":
                        count,

                    "승률":
                        win_prob * 100,

                    "손익비":
                        rr,

                    "PF":
                        pf,

                    "기대수익":
                        exp_value,

                    "매수총액":
                        group[
                            "Buy_Amount"
                        ].sum()
                }
            )

        yearly_table = pd.DataFrame(
            yearly_stats
        )

        if not yearly_table.empty:

            yearly_table = (
                yearly_table
                .sort_values(
                    "연도",
                    ascending=False
                )
            )

            st.dataframe(
                yearly_table.style.format(
                    {
                        "총 손익":
                            "{:+,.0f}원",
                        "평균수익":
                            "{:,.0f}원",
                        "평균손실":
                            "{:,.0f}원",
                        "거래횟수":
                            "{:,}회",
                        "승률":
                            "{:.1f}%",
                        "손익비":
                            "{:.2f}",
                        "PF":
                            "{:.2f}",
                        "기대수익":
                            "{:+.2f}%",
                        "매수총액":
                            "{:,.0f}원"
                    }
                ),
                use_container_width=True
            )


    # ========================================================
    # TAB 4 - 원본
    # ========================================================

    with tab4:

        st.subheader(
            "📋 전체 거래 기록"
        )

        original_table = (
            analysis_df
            .sort_values(
                "Date",
                ascending=False
            )
            [
                [
                    "Date",
                    "Ticker",
                    "Buy_Amount",
                    "Sell_Amount",
                    "P_L_Amount",
                    "ROI_Percent",
                    "Memo"
                ]
            ]
            .copy()
        )

        st.dataframe(
            original_table.style.format(
                {
                    "Buy_Amount":
                        "{:,.0f}원",
                    "Sell_Amount":
                        "{:,.0f}원",
                    "P_L_Amount":
                        "{:+,.0f}원",
                    "ROI_Percent":
                        "{:+.2f}%"
                }
            ),
            use_container_width=True
        )


    # ========================================================
    # TAB 5 - 빅터
    # ========================================================

    with tab5:

        st.subheader(
            "⚖️ Victor Sperandeo Reward-to-Risk Analysis"
        )

        st.markdown(
            "**목표 기준: 평균 수익 / 평균 손실 = 3 : 1**"
        )

        vic_period = st.radio(
            "📅 분석 기간",
            [
                "전체",
                "최근 1개월",
                "최근 3개월",
                "최근 6개월",
                "최근 1년"
            ],
            horizontal=True,
            key="vic_period"
        )

        vic_df = analysis_df.copy()

        today = (
            pd.Timestamp.today()
            .normalize()
        )

        period_days = {
            "최근 1개월": 30,
            "최근 3개월": 90,
            "최근 6개월": 180,
            "최근 1년": 365
        }

        if vic_period in period_days:

            vic_df = vic_df[
                vic_df["Date"]
                >=
                today
                -
                timedelta(
                    days=period_days[
                        vic_period
                    ]
                )
            ]

        if not vic_df.empty:

            v_wins = vic_df[
                vic_df[
                    "ROI_Percent"
                ] > 0
            ]

            v_losses = vic_df[
                vic_df[
                    "ROI_Percent"
                ] <= 0
            ]

            v_win_rate = (
                len(v_wins)
                /
                len(vic_df)
                *
                100
            )

            v_avg_win = (
                v_wins[
                    "ROI_Percent"
                ].mean()
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
                (
                    v_win_rate
                    /
                    100
                )
                *
                v_avg_win
            ) - (
                (
                    1
                    -
                    v_win_rate
                    /
                    100
                )
                *
                v_avg_loss
            )

            v1, v2, v3 = (
                st.columns(3)
            )

            v1.metric(
                "기간 손익비",
                f"{v_rr:.2f} : 1"
            )

            v2.metric(
                "기간 기댓값",
                f"{v_expectancy:.2f}%"
            )

            v3.metric(
                "목표 기준",
                "3.0 : 1"
            )

            target_roi = (
                v_avg_loss * 3
                if v_avg_loss > 0
                else 10
            )

            vic_chart_df = (
                vic_df.copy()
            )

            vic_chart_df[
                "Color_Hex"
            ] = np.select(
                [
                    vic_chart_df[
                        "ROI_Percent"
                    ] >= target_roi,

                    vic_chart_df[
                        "ROI_Percent"
                    ] > 0
                ],
                [
                    "#00CC00",
                    "#F1C40F"
                ],
                default="#FF4B4B"
            )

            scatter_chart = (
                alt.Chart(
                    vic_chart_df
                )
                .mark_circle(
                    size=100
                )
                .encode(
                    x=alt.X(
                        "Date:T",
                        title="거래 일자"
                    ),
                    y=alt.Y(
                        "ROI_Percent:Q",
                        title="수익률 (%)"
                    ),
                    color=alt.Color(
                        "Color_Hex:N",
                        scale=None,
                        legend=None
                    ),
                    tooltip=[
                        "Ticker",
                        "Date",
                        "ROI_Percent",
                        "P_L_Amount"
                    ]
                )
                .interactive()
            )

            rule_chart = (
                alt.Chart(
                    pd.DataFrame(
                        {
                            "Target": [
                                target_roi
                            ]
                        }
                    )
                )
                .mark_rule(
                    color="blue",
                    strokeDash=[
                        3,
                        3
                    ]
                )
                .encode(
                    y="Target:Q"
                )
            )

            st.altair_chart(
                scatter_chart
                +
                rule_chart,
                use_container_width=True
            )

        else:

            st.info(
                "선택한 기간에 거래 기록이 없습니다."
            )


    # ========================================================
    # TAB 6 - R 배수
    # ========================================================

    with tab6:

        st.subheader(
            "🎯 R-배수 분석"
        )

        st.caption(
            "1R = 선택 기간의 평균 손실금"
        )

        r_period = st.radio(
            "📅 분석 기간",
            [
                "전체",
                "최근 1개월",
                "최근 3개월",
                "최근 6개월",
                "최근 1년"
            ],
            horizontal=True,
            key="r_period"
        )

        r_df = analysis_df.copy()

        period_days = {
            "최근 1개월": 30,
            "최근 3개월": 90,
            "최근 6개월": 180,
            "최근 1년": 365
        }

        if r_period in period_days:

            r_df = r_df[
                r_df["Date"]
                >=
                pd.Timestamp.today()
                .normalize()
                -
                timedelta(
                    days=period_days[
                        r_period
                    ]
                )
            ]

        if not r_df.empty:

            r_losses = r_df[
                r_df[
                    "P_L_Amount"
                ] < 0
            ]

            if not r_losses.empty:

                one_r = abs(
                    r_losses[
                        "P_L_Amount"
                    ].mean()
                )

            else:

                all_loss_data = (
                    analysis_df[
                        analysis_df[
                            "P_L_Amount"
                        ] < 0
                    ]
                )

                one_r = (
                    abs(
                        all_loss_data[
                            "P_L_Amount"
                        ].mean()
                    )
                    if not all_loss_data.empty
                    else 1
                )

            if (
                pd.isna(one_r)
                or
                one_r <= 0
            ):

                one_r = 1

            r_df[
                "R_Value"
            ] = (
                r_df[
                    "P_L_Amount"
                ]
                /
                one_r
            )

            r1, r2, r3 = (
                st.columns(3)
            )

            r1.metric(
                "나의 1R",
                f"{one_r:,.0f}원"
            )

            r2.metric(
                "평균 R-배수",
                f"{r_df['R_Value'].mean():.2f}R"
            )

            r3.metric(
                "최고 R-배수",
                f"{r_df['R_Value'].max():.2f}R"
            )

            r_chart_df = (
                r_df
                .sort_values(
                    "Date"
                )
                .copy()
            )

            r_chart_df[
                "Cumulative_R"
            ] = (
                r_chart_df[
                    "R_Value"
                ].cumsum()
            )

            r_chart_df[
                "Trade_Num"
            ] = range(
                1,
                len(r_chart_df) + 1
            )

            r_chart = (
                alt.Chart(
                    r_chart_df
                )
                .mark_line(
                    color="blue"
                )
                .encode(
                    x=alt.X(
                        "Trade_Num:Q",
                        title="거래 횟수"
                    ),
                    y=alt.Y(
                        "Cumulative_R:Q",
                        title="누적 R"
                    ),
                    tooltip=[
                        "Date",
                        "Ticker",
                        "R_Value",
                        "Cumulative_R"
                    ]
                )
            )

            st.altair_chart(
                r_chart,
                use_container_width=True
            )

        else:

            st.info(
                "선택한 기간에 거래 기록이 없습니다."
            )


    # ========================================================
    # TAB 7 - 분포
    # ========================================================

    with tab7:

        st.subheader(
            "🔔 손익 분포"
        )

        st.markdown(
            "**손실은 짧게, 수익은 길게.**"
        )

        distribution_df = (
            analysis_df.copy()
        )

        histogram = (
            alt.Chart(
                distribution_df
            )
            .mark_bar()
            .encode(
                x=alt.X(
                    "ROI_Percent:Q",
                    bin=alt.Bin(
                        step=2.5
                    ),
                    title="수익률 구간 (%)"
                ),
                y=alt.Y(
                    "count():Q",
                    title="거래 횟수"
                ),
                color=alt.condition(
                    alt.datum.ROI_Percent > 0,
                    alt.value(
                        "#00AA00"
                    ),
                    alt.value(
                        "#FF4444"
                    )
                )
            )
            .properties(
                height=400
            )
        )

        st.altair_chart(
            histogram,
            use_container_width=True
        )

        skewness = (
            distribution_df[
                "ROI_Percent"
            ].skew()
        )

        if pd.isna(skewness):
            skewness = 0

        st.info(
            f"📊 Skewness: {skewness:.2f}"
        )

        if skewness > 0.5:

            st.success(
                "✅ 수익 쪽 꼬리가 더 긴 Positive Skew입니다."
            )

        elif skewness < -0.5:

            st.error(
                "🚨 손실 쪽 꼬리가 더 긴 Negative Skew입니다."
            )

        else:

            st.warning(
                "⚠️ 수익과 손실 분포가 비교적 대칭적입니다."
            )


    # ========================================================
    # TAB 8 - 거래 관리
    # ========================================================

    with tab8:

        st.subheader(
            "🛠️ 거래 관리"
        )

        st.caption(
            "거래를 선택해 상세 내용을 확인하고 "
            "수정하거나 삭제할 수 있습니다."
        )

        manage_df = (
            analysis_df
            .sort_values(
                [
                    "Date",
                    "Trade_ID"
                ],
                ascending=[
                    False,
                    False
                ]
            )
            .copy()
        )

        manage_df[
            "Display_Name"
        ] = (
            manage_df[
                "Date"
            ].dt.strftime(
                "%Y-%m-%d"
            )
            +
            " | "
            +
            manage_df[
                "Ticker"
            ].astype(str)
            +
            " | "
            +
            manage_df[
                "ROI_Percent"
            ].map(
                lambda x:
                    f"{x:+.2f}%"
            )
            +
            " | "
            +
            manage_df[
                "P_L_Amount"
            ].map(
                lambda x:
                    f"{x:+,.0f}원"
            )
        )

        display_map = dict(
            zip(
                manage_df[
                    "Trade_ID"
                ].astype(str),

                manage_df[
                    "Display_Name"
                ]
            )
        )

        selected_trade_id = (
            st.selectbox(
                "📋 수정/삭제할 거래 선택",
                options=list(
                    display_map.keys()
                ),
                format_func=lambda x:
                    display_map.get(
                        x,
                        x
                    ),
                key="selected_trade_id"
            )
        )

        selected_rows = manage_df[
            manage_df[
                "Trade_ID"
            ].astype(str)
            ==
            str(
                selected_trade_id
            )
        ]

        if not selected_rows.empty:

            selected = (
                selected_rows.iloc[0]
            )

            st.divider()

            st.markdown(
                "### 🔎 거래 상세보기"
            )

            d1, d2, d3, d4 = (
                st.columns(4)
            )

            d1.metric(
                "종목",
                str(
                    selected[
                        "Ticker"
                    ]
                )
            )

            d2.metric(
                "거래일",
                selected[
                    "Date"
                ].strftime(
                    "%Y-%m-%d"
                )
            )

            d3.metric(
                "수익률",
                f"{selected['ROI_Percent']:+.2f}%"
            )

            d4.metric(
                "손익",
                f"{selected['P_L_Amount']:+,.0f}원"
            )

            d5, d6 = st.columns(2)

            d5.metric(
                "매수금액",
                f"{selected['Buy_Amount']:,.0f}원"
            )

            d6.metric(
                "매도금액",
                f"{selected['Sell_Amount']:,.0f}원"
            )

            if str(
                selected[
                    "Memo"
                ]
            ).strip():

                st.info(
                    f"📝 {selected['Memo']}"
                )


            st.divider()

            st.markdown(
                "### ✏️ 거래 수정"
            )

            with st.form(
                f"edit_form_{selected_trade_id}"
            ):

                edit_date = (
                    st.date_input(
                        "거래일",
                        value=selected[
                            "Date"
                        ].date()
                    )
                )

                edit_ticker = (
                    st.text_input(
                        "종목명",
                        value=str(
                            selected[
                                "Ticker"
                            ]
                        )
                    )
                )

                edit_col1, edit_col2 = (
                    st.columns(2)
                )

                with edit_col1:

                    edit_buy = (
                        st.number_input(
                            "매수금액 (원)",
                            min_value=0,
                            value=max(
                                0,
                                int(
                                    round(
                                        selected[
                                            "Buy_Amount"
                                        ]
                                    )
                                )
                            ),
                            step=100000
                        )
                    )

                with edit_col2:

                    edit_roi = (
                        st.number_input(
                            "수익률 (%)",
                            value=float(
                                selected[
                                    "ROI_Percent"
                                ]
                            ),
                            format="%.2f"
                        )
                    )

                edit_pl = (
                    edit_buy
                    *
                    (
                        edit_roi
                        /
                        100
                    )
                )

                edit_sell = (
                    edit_buy
                    +
                    edit_pl
                )

                st.info(
                    f"""
🧮 **수정 후 계산**

손익: **{edit_pl:+,.0f}원**

매도금액: **{edit_sell:,.0f}원**
"""
                )

                edit_memo = (
                    st.text_area(
                        "메모",
                        value=str(
                            selected[
                                "Memo"
                            ]
                        ),
                        height=100
                    )
                )

                update_trade = (
                    st.form_submit_button(
                        "💾 수정 내용 저장",
                        use_container_width=True
                    )
                )

                if update_trade:

                    if not edit_ticker.strip():

                        st.error(
                            "종목명을 입력해주세요."
                        )

                    elif edit_buy <= 0:

                        st.error(
                            "매수금액을 입력해주세요."
                        )

                    else:

                        try:

                            live_raw = (
                                conn.read(
                                    worksheet=0,
                                    ttl=0
                                )
                            )

                            live_df = (
                                normalize_trade_dataframe(
                                    live_raw
                                )
                            )

                            target_mask = (
                                live_df[
                                    "Trade_ID"
                                ].astype(str)
                                ==
                                str(
                                    selected_trade_id
                                )
                            )

                            if not target_mask.any():

                                st.error(
                                    "🚨 수정하려는 거래를 찾을 수 없습니다."
                                )

                            else:

                                target_index = (
                                    live_df[
                                        target_mask
                                    ].index[0]
                                )

                                live_df.at[
                                    target_index,
                                    "Date"
                                ] = pd.Timestamp(
                                    edit_date
                                )

                                live_df.at[
                                    target_index,
                                    "Ticker"
                                ] = (
                                    edit_ticker.strip()
                                )

                                live_df.at[
                                    target_index,
                                    "Buy_Amount"
                                ] = float(
                                    edit_buy
                                )

                                live_df.at[
                                    target_index,
                                    "Sell_Amount"
                                ] = float(
                                    edit_sell
                                )

                                live_df.at[
                                    target_index,
                                    "P_L_Amount"
                                ] = float(
                                    edit_pl
                                )

                                live_df.at[
                                    target_index,
                                    "ROI_Percent"
                                ] = float(
                                    edit_roi
                                )

                                live_df.at[
                                    target_index,
                                    "Memo"
                                ] = edit_memo

                                conn.update(
                                    worksheet=0,
                                    data=prepare_for_sheet(
                                        live_df
                                    )
                                )

                                st.success(
                                    "✅ 거래 수정 완료!"
                                )

                                st.rerun()

                        except Exception as e:

                            st.error(
                                f"🚨 거래 수정 실패: {e}"
                            )


            st.divider()

            st.markdown(
                "### 🗑️ 거래 삭제"
            )

            st.warning(
                f"""
삭제 대상

**{selected['Ticker']}**

{selected['Date'].strftime('%Y-%m-%d')}

수익률: **{selected['ROI_Percent']:+.2f}%**

손익: **{selected['P_L_Amount']:+,.0f}원**

삭제하면 Google Sheets에서도 제거됩니다.
"""
            )

            delete_confirm = (
                st.checkbox(
                    "이 거래를 정말 삭제하겠습니다.",
                    key=f"delete_confirm_{selected_trade_id}"
                )
            )

            delete_button = (
                st.button(
                    "🗑️ 거래 영구 삭제",
                    disabled=not delete_confirm,
                    use_container_width=True,
                    key=f"delete_button_{selected_trade_id}"
                )
            )

            if delete_button:

                try:

                    live_raw = conn.read(
                        worksheet=0,
                        ttl=0
                    )

                    live_df = (
                        normalize_trade_dataframe(
                            live_raw
                        )
                    )

                    before_count = len(
                        live_df
                    )

                    live_df = (
                        live_df[
                            live_df[
                                "Trade_ID"
                            ].astype(str)
                            !=
                            str(
                                selected_trade_id
                            )
                        ]
                        .copy()
                    )

                    if (
                        before_count
                        ==
                        len(live_df)
                    ):

                        st.error(
                            "🚨 삭제할 거래를 찾을 수 없습니다."
                        )

                    else:

                        conn.update(
                            worksheet=0,
                            data=prepare_for_sheet(
                                live_df
                            )
                        )

                        st.success(
                            "🗑️ 거래가 삭제되었습니다."
                        )

                        st.rerun()

                except Exception as e:

                    st.error(
                        f"🚨 거래 삭제 실패: {e}"
                    )


    # ========================================================
    # TAB 9 - TRADING DNA
    # ========================================================

    with tab9:

        st.subheader(
            "🧠 My Trading DNA"
        )

        st.caption(
            "실제 거래 기록에서 당신의 수익 구조와 "
            "반복 패턴을 찾아냅니다."
        )

        dna = calculate_trading_dna(
            analysis_df
        )

        if not dna:

            st.info(
                "Trading DNA를 분석할 데이터가 부족합니다."
            )

        else:

            # ------------------------------------------------
            # DNA TYPE
            # ------------------------------------------------

            st.markdown(
                f"## {dna['dna_type']}"
            )

            st.info(
                dna[
                    "dna_description"
                ]
            )

            st.caption(
                f"현재 {dna['total_count']:,}건의 "
                "거래 기록을 기반으로 계산했습니다."
            )


            # ------------------------------------------------
            # 핵심 DNA
            # ------------------------------------------------

            st.markdown(
                "### 🧬 핵심 DNA"
            )

            dna1, dna2, dna3, dna4 = (
                st.columns(4)
            )

            dna1.metric(
                "🎯 승률",
                f"{dna['win_rate']:.1f}%"
            )

            dna2.metric(
                "⚖️ 평균 손익비",
                f"{dna['reward_risk']:.2f}"
            )

            dna3.metric(
                "💎 Profit Factor",
                f"{dna['profit_factor']:.2f}"
            )

            dna4.metric(
                "🔮 거래당 기대값",
                f"{dna['expectancy']:+.2f}%"
            )


            st.divider()


            # ------------------------------------------------
            # BIG WINNER
            # ------------------------------------------------

            st.markdown(
                "### 🚀 Big Winner DNA"
            )

            b1, b2, b3, b4 = (
                st.columns(4)
            )

            b1.metric(
                "🔥 Big Winner 기여도",
                f"{dna['big_winner_contribution']:.1f}%"
            )

            b2.metric(
                "🚀 Big Winner 수",
                f"{dna['big_winner_count']}건"
            )

            b3.metric(
                "💎 상위 10% 수익 기여",
                f"{dna['top10_contribution']:.1f}%"
            )

            b4.metric(
                "🎯 Big Winner 기준",
                f"+{dna['big_winner_threshold']:.2f}%"
            )

            st.caption(
                "Big Winner는 현재 평균 손실률의 "
                "2배 이상 수익을 기록한 거래로 정의했습니다. "
                "기여도는 Gross Profit 기준입니다."
            )


            if (
                not dna[
                    "big_winners"
                ].empty
            ):

                st.markdown(
                    "#### 🏆 나의 Big Winners"
                )

                big_table = (
                    dna[
                        "big_winners"
                    ]
                    .sort_values(
                        "P_L_Amount",
                        ascending=False
                    )
                    [
                        [
                            "Date",
                            "Ticker",
                            "ROI_Percent",
                            "P_L_Amount"
                        ]
                    ]
                    .copy()
                )

                st.dataframe(
                    big_table.style.format(
                        {
                            "ROI_Percent":
                                "{:+.2f}%",
                            "P_L_Amount":
                                "{:+,.0f}원"
                        }
                    ),
                    use_container_width=True
                )


            st.divider()


            # ------------------------------------------------
            # 손실 DNA
            # ------------------------------------------------

            st.markdown(
                "### 🛡️ Risk DNA"
            )

            risk1, risk2, risk3, risk4 = (
                st.columns(4)
            )

            risk1.metric(
                "평균 손실률",
                f"-{dna['avg_loss_pct']:.2f}%"
            )

            risk2.metric(
                "최대 손실률",
                f"-{dna['max_loss_pct']:.2f}%"
            )

            risk3.metric(
                "최대 연속 손실",
                f"{dna['max_loss_streak']}회"
            )

            risk4.metric(
                "최대 연속 수익",
                f"{dna['max_win_streak']}회"
            )


            st.divider()


            # ------------------------------------------------
            # 최근 Edge
            # ------------------------------------------------

            st.markdown(
                "### 📡 최근 Edge Monitor"
            )

            recent1, recent2, recent3, recent4 = (
                st.columns(4)
            )

            recent1.metric(
                f"최근 {dna['recent_count']}거래 승률",
                f"{dna['recent_win_rate']:.1f}%"
            )

            recent2.metric(
                f"최근 {dna['recent_count']}거래 PF",
                f"{dna['recent_pf']:.2f}"
            )

            recent3.metric(
                f"최근 {dna['recent_count']}거래 기대값",
                f"{dna['recent_expectancy']:+.2f}%"
            )

            recent4.metric(
                "직전 구간 대비",
                f"{dna['edge_change']:+.2f}%p"
            )


            if dna["edge_change"] > 1:

                st.success(
                    "📈 최근 거래의 통계적 Edge가 "
                    "직전 구간보다 개선되고 있습니다."
                )

            elif dna["edge_change"] < -1:

                st.warning(
                    "📉 최근 거래의 기댓값이 "
                    "직전 구간보다 낮아졌습니다. "
                    "최근 매매 행동이나 시장 환경이 "
                    "달라졌는지 확인해보세요."
                )

            else:

                st.info(
                    "➡️ 최근 Edge는 직전 구간과 "
                    "비슷한 수준입니다."
                )


            st.divider()


            # ------------------------------------------------
            # 수익률 구간
            # ------------------------------------------------

            st.markdown(
                "### 📊 어디에서 돈을 벌고 잃는가?"
            )

            bucket_table = (
                create_roi_bucket_table(
                    analysis_df
                )
            )

            if not bucket_table.empty:

                bucket_chart = (
                    alt.Chart(
                        bucket_table
                    )
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "수익률 구간:N",
                            sort=None,
                            title="수익률 구간"
                        ),
                        y=alt.Y(
                            "총손익:Q",
                            title="총 손익"
                        ),
                        color=alt.condition(
                            alt.datum.총손익 > 0,
                            alt.value(
                                "#00AA00"
                            ),
                            alt.value(
                                "#FF4444"
                            )
                        ),
                        tooltip=[
                            "수익률 구간",
                            "거래수",
                            alt.Tooltip(
                                "총손익:Q",
                                format=",.0f"
                            ),
                            alt.Tooltip(
                                "평균수익률:Q",
                                format=".2f"
                            )
                        ]
                    )
                    .properties(
                        height=380
                    )
                )

                st.altair_chart(
                    bucket_chart,
                    use_container_width=True
                )

                st.dataframe(
                    bucket_table.style.format(
                        {
                            "거래수":
                                "{:,.0f}건",
                            "총손익":
                                "{:+,.0f}원",
                            "평균수익률":
                                "{:+.2f}%"
                        }
                    ),
                    use_container_width=True,
                    hide_index=True
                )


            st.divider()


            # ------------------------------------------------
            # RULE BASED COACH
            # ------------------------------------------------

            st.markdown(
                "### 🧠 Trading Coach Insights"
            )

            st.caption(
                "아래 내용은 AI의 추측이 아니라 "
                "현재 거래 데이터에서 계산된 통계 규칙을 "
                "기반으로 생성됩니다."
            )

            insights = (
                generate_rule_based_insights(
                    dna
                )
            )

            for insight in insights:

                st.markdown(
                    f"- {insight}"
                )


            st.divider()


            # ------------------------------------------------
            # 다음 제품 단계 예고
            # ------------------------------------------------

            st.markdown(
                "### 🤖 AI Coach"
            )

            st.info(
                """
현재 버전은 **Trading DNA 분석 엔진**입니다.

다음 버전에서는 이 계산 결과를 AI Coach가 읽고,

**강점 → 약점 → 반복되는 실수 → 다음 거래에서 관찰할 행동**

형태의 개인화 리포트를 생성하도록 확장할 예정입니다.
"""
            )


# ============================================================
# 데이터 없음
# ============================================================

else:

    st.info(
        "👈 사이드바에서 매매 기록을 입력하면 "
        "대시보드가 활성화됩니다."
    )
