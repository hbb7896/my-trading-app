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

    sheet_df["Date"] = pd.to_datetime(
        sheet_df["Date"],
        errors="coerce"
    ).dt.strftime("%Y-%m-%d")

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

            ids = (
                raw_df["Trade_ID"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            if (
                (ids == "")
                |
                (ids.str.lower() == "nan")
            ).any():

                needs_migration = True

        if needs_migration:

            migrated = (
                normalize_trade_dataframe(
                    raw_df
                )
            )

            conn.update(
                worksheet=0,
                data=prepare_for_sheet(
                    migrated
                )
            )

    except Exception:
        pass


# ============================================================
# 8. MILESTONE 4 - TRADING COACH ENGINE
# ============================================================

def calculate_period_metrics(data):

    """
    어떤 기간의 거래 데이터가 들어와도
    동일한 방식으로 핵심 Trading Edge 지표를 계산한다.
    """

    empty_result = {
        "count": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "reward_risk": 0.0,
        "expectancy": 0.0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_profit": 0.0,
        "big_winner_threshold": 0.0,
        "big_winner_count": 0,
        "big_winner_rate": 0.0,
        "big_winner_contribution": 0.0
    }

    if data is None or data.empty:
        return empty_result

    work = data.copy()

    wins = work[
        work["P_L_Amount"] > 0
    ]

    losses = work[
        work["P_L_Amount"] < 0
    ]

    count = len(work)

    win_rate = (
        len(wins)
        / count
        * 100
        if count > 0
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

    net_profit = (
        work["P_L_Amount"].sum()
    )

    profit_factor = (
        gross_profit
        / gross_loss
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
        / avg_loss_pct
        if avg_loss_pct > 0
        else 0
    )

    win_probability = (
        len(wins)
        / count
        if count > 0
        else 0
    )

    loss_probability = (
        len(losses)
        / count
        if count > 0
        else 0
    )

    expectancy = (
        win_probability
        * avg_win_pct
        -
        loss_probability
        * avg_loss_pct
    )

    big_winner_threshold = (
        avg_loss_pct * 2
        if avg_loss_pct > 0
        else 10
    )

    big_winners = wins[
        wins["ROI_Percent"]
        >= big_winner_threshold
    ]

    big_winner_count = len(
        big_winners
    )

    big_winner_rate = (
        big_winner_count
        / count
        * 100
        if count > 0
        else 0
    )

    big_winner_profit = (
        big_winners[
            "P_L_Amount"
        ].sum()
        if not big_winners.empty
        else 0
    )

    big_winner_contribution = (
        big_winner_profit
        / gross_profit
        * 100
        if gross_profit > 0
        else 0
    )

    return {
        "count":
            count,

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

        "net_profit":
            net_profit,

        "big_winner_threshold":
            big_winner_threshold,

        "big_winner_count":
            big_winner_count,

        "big_winner_rate":
            big_winner_rate,

        "big_winner_contribution":
            big_winner_contribution
    }


def calculate_max_streaks(data):

    if data.empty:
        return 0, 0

    ordered = data.sort_values(
        [
            "Date",
            "Trade_ID"
        ]
    )

    max_win = 0
    max_loss = 0

    current_win = 0
    current_loss = 0

    for value in ordered["P_L_Amount"]:

        if value > 0:

            current_win += 1
            current_loss = 0

            max_win = max(
                max_win,
                current_win
            )

        elif value < 0:

            current_loss += 1
            current_win = 0

            max_loss = max(
                max_loss,
                current_loss
            )

        else:

            current_win = 0
            current_loss = 0

    return max_win, max_loss


def calculate_current_streak(data):

    if data.empty:
        return "none", 0

    ordered = data.sort_values(
        [
            "Date",
            "Trade_ID"
        ]
    )

    values = (
        ordered["P_L_Amount"]
        .tolist()
    )

    last_value = values[-1]

    if last_value > 0:
        streak_type = "win"

    elif last_value < 0:
        streak_type = "loss"

    else:
        return "none", 0

    streak = 0

    for value in reversed(values):

        if (
            streak_type == "win"
            and value > 0
        ):

            streak += 1

        elif (
            streak_type == "loss"
            and value < 0
        ):

            streak += 1

        else:

            break

    return streak_type, streak


def calculate_trading_dna(data):

    if data.empty:
        return {}

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

    total_metrics = (
        calculate_period_metrics(
            ordered
        )
    )

    total_count = len(
        ordered
    )

    wins = ordered[
        ordered["P_L_Amount"] > 0
    ].copy()

    losses = ordered[
        ordered["P_L_Amount"] < 0
    ].copy()


    # --------------------------------------------------------
    # 상위 10% 승자 집중도
    # --------------------------------------------------------

    if (
        not wins.empty
        and
        total_metrics[
            "gross_profit"
        ] > 0
    ):

        top_n = max(
            1,
            int(
                np.ceil(
                    len(wins)
                    * 0.10
                )
            )
        )

        top_profit = (
            wins
            .nlargest(
                top_n,
                "P_L_Amount"
            )[
                "P_L_Amount"
            ]
            .sum()
        )

        top10_contribution = (
            top_profit
            /
            total_metrics[
                "gross_profit"
            ]
            *
            100
        )

    else:

        top_n = 0
        top10_contribution = 0


    # --------------------------------------------------------
    # 전체 Big Winner
    # --------------------------------------------------------

    big_winner_threshold = (
        total_metrics[
            "big_winner_threshold"
        ]
    )

    big_winners = wins[
        wins["ROI_Percent"]
        >= big_winner_threshold
    ].copy()


    # --------------------------------------------------------
    # 손실 / 연승 연패
    # --------------------------------------------------------

    max_win_streak, max_loss_streak = (
        calculate_max_streaks(
            ordered
        )
    )

    current_streak_type, current_streak = (
        calculate_current_streak(
            ordered
        )
    )

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
    # 최근 20 / 직전 20
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

    recent_metrics = (
        calculate_period_metrics(
            recent_df
        )
    )

    if total_count >= 40:

        previous_df = (
            ordered
            .iloc[
                total_count - 40:
                total_count - 20
            ]
            .copy()
        )

    elif total_count > 20:

        previous_df = (
            ordered
            .iloc[
                :total_count - 20
            ]
            .tail(20)
            .copy()
        )

    else:

        previous_df = pd.DataFrame(
            columns=ordered.columns
        )

    previous_metrics = (
        calculate_period_metrics(
            previous_df
        )
    )


    # --------------------------------------------------------
    # 최근 vs 직전 변화
    # --------------------------------------------------------

    has_previous = (
        len(previous_df) >= 5
    )

    if has_previous:

        changes = {
            "win_rate":
                recent_metrics["win_rate"]
                -
                previous_metrics["win_rate"],

            "profit_factor":
                recent_metrics["profit_factor"]
                -
                previous_metrics["profit_factor"],

            "reward_risk":
                recent_metrics["reward_risk"]
                -
                previous_metrics["reward_risk"],

            "expectancy":
                recent_metrics["expectancy"]
                -
                previous_metrics["expectancy"],

            "avg_win_pct":
                recent_metrics["avg_win_pct"]
                -
                previous_metrics["avg_win_pct"],

            "avg_loss_pct":
                recent_metrics["avg_loss_pct"]
                -
                previous_metrics["avg_loss_pct"],

            "big_winner_rate":
                recent_metrics["big_winner_rate"]
                -
                previous_metrics["big_winner_rate"],

            "big_winner_contribution":
                recent_metrics[
                    "big_winner_contribution"
                ]
                -
                previous_metrics[
                    "big_winner_contribution"
                ]
        }

    else:

        changes = {
            "win_rate": 0,
            "profit_factor": 0,
            "reward_risk": 0,
            "expectancy": 0,
            "avg_win_pct": 0,
            "avg_loss_pct": 0,
            "big_winner_rate": 0,
            "big_winner_contribution": 0
        }


    # --------------------------------------------------------
    # Edge 상태
    # --------------------------------------------------------

    if not has_previous:

        edge_status = "데이터 축적 중"
        edge_icon = "🟡"

    else:

        score = 0

        if changes["expectancy"] > 0.75:
            score += 2

        elif changes["expectancy"] < -0.75:
            score -= 2

        if changes["profit_factor"] > 0.20:
            score += 1

        elif changes["profit_factor"] < -0.20:
            score -= 1

        if changes["reward_risk"] > 0.25:
            score += 1

        elif changes["reward_risk"] < -0.25:
            score -= 1

        # 평균 손실률은 낮아지는 것이 좋음
        if changes["avg_loss_pct"] < -0.50:
            score += 1

        elif changes["avg_loss_pct"] > 0.50:
            score -= 1

        if (
            changes[
                "big_winner_rate"
            ] > 2
        ):
            score += 1

        elif (
            changes[
                "big_winner_rate"
            ] < -2
        ):
            score -= 1

        if score >= 2:

            edge_status = "개선"
            edge_icon = "🟢"

        elif score <= -2:

            edge_status = "주의"
            edge_icon = "🔴"

        else:

            edge_status = "안정"
            edge_icon = "🟡"


    # --------------------------------------------------------
    # DNA 유형
    # --------------------------------------------------------

    win_rate = total_metrics[
        "win_rate"
    ]

    reward_risk = total_metrics[
        "reward_risk"
    ]

    if (
        reward_risk >= 2
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
        total_metrics[
            "big_winner_contribution"
        ] >= 60
    ):

        dna_type = "🚀 Big Winner Hunter"

        dna_description = (
            "소수의 큰 수익 거래가 전체 성과에 "
            "강한 영향을 주는 구조입니다."
        )

    else:

        dna_type = "🔬 Developing Edge"

        dna_description = (
            "현재 기록에서는 여러 수익 패턴이 "
            "혼합되어 있습니다."
        )


    return {
        "total_count":
            total_count,

        "win_rate":
            total_metrics["win_rate"],

        "profit_factor":
            total_metrics["profit_factor"],

        "reward_risk":
            total_metrics["reward_risk"],

        "expectancy":
            total_metrics["expectancy"],

        "avg_win_pct":
            total_metrics["avg_win_pct"],

        "avg_loss_pct":
            total_metrics["avg_loss_pct"],

        "gross_profit":
            total_metrics["gross_profit"],

        "gross_loss":
            total_metrics["gross_loss"],

        "top10_contribution":
            top10_contribution,

        "top_n":
            top_n,

        "big_winner_threshold":
            big_winner_threshold,

        "big_winner_count":
            len(big_winners),

        "big_winner_contribution":
            total_metrics[
                "big_winner_contribution"
            ],

        "max_win_streak":
            max_win_streak,

        "max_loss_streak":
            max_loss_streak,

        "current_streak_type":
            current_streak_type,

        "current_streak":
            current_streak,

        "max_loss_pct":
            max_loss_pct,

        "max_loss_amount":
            max_loss_amount,

        "recent_count":
            recent_n,

        "recent_df":
            recent_df,

        "previous_df":
            previous_df,

        "recent_metrics":
            recent_metrics,

        "previous_metrics":
            previous_metrics,

        "total_metrics":
            total_metrics,

        "changes":
            changes,

        "has_previous":
            has_previous,

        "edge_status":
            edge_status,

        "edge_icon":
            edge_icon,

        "edge_change":
            changes["expectancy"],

        "dna_type":
            dna_type,

        "dna_description":
            dna_description,

        "big_winners":
            big_winners
    }


# ============================================================
# 9. EDGE 변화 원인 분석
# ============================================================

def detect_edge_drivers(dna):

    if (
        not dna
        or
        not dna["has_previous"]
    ):

        return []

    c = dna["changes"]

    drivers = []

    # 긍정/부정 방향을 통일한 중요도 점수

    driver_candidates = [
        {
            "name": "승률",
            "raw": c["win_rate"],
            "impact": c["win_rate"] / 5,
            "text":
                f"승률 {c['win_rate']:+.1f}%p"
        },
        {
            "name": "Profit Factor",
            "raw": c["profit_factor"],
            "impact": c["profit_factor"] * 2,
            "text":
                f"PF {c['profit_factor']:+.2f}"
        },
        {
            "name": "손익비",
            "raw": c["reward_risk"],
            "impact": c["reward_risk"] * 1.5,
            "text":
                f"손익비 {c['reward_risk']:+.2f}"
        },
        {
            "name": "평균 수익률",
            "raw": c["avg_win_pct"],
            "impact": c["avg_win_pct"] / 2,
            "text":
                f"평균 수익률 {c['avg_win_pct']:+.2f}%p"
        },
        {
            "name": "평균 손실률",
            "raw": c["avg_loss_pct"],
            # 손실률 증가는 나쁜 변화
            "impact": -c["avg_loss_pct"] / 2,
            "text":
                f"평균 손실률 {c['avg_loss_pct']:+.2f}%p"
        },
        {
            "name": "Big Winner 비율",
            "raw": c["big_winner_rate"],
            "impact": c["big_winner_rate"] / 4,
            "text":
                f"Big Winner 비율 {c['big_winner_rate']:+.1f}%p"
        }
    ]

    driver_candidates = sorted(
        driver_candidates,
        key=lambda x:
            abs(x["impact"]),
        reverse=True
    )

    for item in driver_candidates[:3]:

        if abs(item["impact"]) < 0.15:
            continue

        direction = (
            "positive"
            if item["impact"] > 0
            else "negative"
        )

        drivers.append(
            {
                "name":
                    item["name"],

                "direction":
                    direction,

                "text":
                    item["text"]
            }
        )

    return drivers


# ============================================================
# 10. 코칭 체크포인트
# ============================================================

def generate_coach_checkpoints(dna):

    checkpoints = []

    if not dna:
        return checkpoints

    recent = dna[
        "recent_metrics"
    ]

    total = dna[
        "total_metrics"
    ]

    changes = dna[
        "changes"
    ]


    # 1. 손실 관리

    if (
        dna["has_previous"]
        and
        changes[
            "avg_loss_pct"
        ] > 0.75
    ):

        checkpoints.append(
            "🛡️ 최근 평균 손실률이 직전 구간보다 "
            f"{changes['avg_loss_pct']:+.2f}%p 확대됐습니다. "
            "다음 거래에서는 손절 기준 이탈 여부를 기록하세요."
        )


    # 2. Big Winner 감소

    if (
        dna["has_previous"]
        and
        changes[
            "big_winner_rate"
        ] < -3
    ):

        checkpoints.append(
            "🚀 최근 Big Winner 발생 비율이 "
            f"{abs(changes['big_winner_rate']):.1f}%p 감소했습니다. "
            "수익 거래를 너무 빨리 청산하고 있지 않은지 "
            "확인하세요."
        )


    # 3. 평균 수익 감소

    if (
        dna["has_previous"]
        and
        changes[
            "avg_win_pct"
        ] < -1
    ):

        checkpoints.append(
            "💎 최근 평균 수익률이 직전 구간보다 "
            f"{abs(changes['avg_win_pct']):.2f}%p 낮아졌습니다. "
            "큰 추세를 충분히 보유했는지 거래별로 확인하세요."
        )


    # 4. PF 하락

    if (
        dna["has_previous"]
        and
        changes[
            "profit_factor"
        ] < -0.25
    ):

        checkpoints.append(
            "📉 최근 Profit Factor가 직전 구간보다 "
            f"{abs(changes['profit_factor']):.2f} 하락했습니다. "
            "승률 하나보다 손실 크기와 Big Winner 감소를 "
            "함께 확인하세요."
        )


    # 5. 추세추종 특성

    if (
        total["reward_risk"] >= 2
        and
        total["win_rate"] < 50
    ):

        checkpoints.append(
            "🧬 당신의 장기 구조는 승률보다 손익비 의존도가 높습니다. "
            "연패를 피하려 하기보다 손실 제한과 큰 승자 보유가 "
            "유지되는지 관찰하세요."
        )


    # 6. 현재 연패

    if (
        dna["current_streak_type"]
        == "loss"
        and
        dna["current_streak"] >= 4
    ):

        checkpoints.append(
            "⚠️ 현재 "
            f"{dna['current_streak']}연속 손실 구간입니다. "
            "새로운 전략을 즉흥적으로 추가하기보다 최근 거래의 "
            "진입 조건과 손실 크기 변화를 먼저 확인하세요."
        )


    # 7. 특별한 문제 없을 때

    if len(checkpoints) == 0:

        checkpoints.append(
            "✅ 최근 통계에서 뚜렷한 구조 훼손 신호는 발견되지 않았습니다. "
            "현재 매매 규칙을 유지하면서 다음 20거래를 계속 기록하세요."
        )


    return checkpoints[:3]


# ============================================================
# 11. 기존 Trading DNA Insights
# ============================================================

def generate_rule_based_insights(dna):

    insights = []

    if not dna:
        return insights

    if dna["big_winner_contribution"] >= 60:

        insights.append(
            "🔥 큰 수익 거래가 전체 Gross Profit의 "
            f"{dna['big_winner_contribution']:.1f}%를 만들고 있습니다. "
            "큰 승자를 너무 일찍 정리하면 전체 성과에 "
            "큰 영향을 줄 수 있습니다."
        )

    elif dna["big_winner_contribution"] >= 35:

        insights.append(
            "🔥 Big Winner가 전체 수익에서 의미 있는 비중을 "
            "차지하고 있습니다."
        )

    else:

        insights.append(
            "📊 수익이 소수의 초대형 거래보다 여러 거래에 "
            "상대적으로 분산되어 있습니다."
        )

    if dna["top10_contribution"] >= 40:

        insights.append(
            "💎 상위 수익 거래의 기여도가 높습니다. "
            "최고 수익 거래의 공통점을 추적할 가치가 있습니다."
        )

    if (
        dna["reward_risk"] >= 2
        and
        dna["win_rate"] < 50
    ):

        insights.append(
            "🧬 승률보다 손익비가 성과를 만드는 구조입니다. "
            "평균 손실을 통제하면서 큰 승자를 확보하는 것이 "
            "핵심 특성입니다."
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
            "예외적 손실이 발생한 원인을 확인하세요."
        )

    if dna["max_loss_streak"] >= 6:

        insights.append(
            "🧠 과거 최대 연속 손실은 "
            f"{dna['max_loss_streak']}회입니다. "
            "이 정도의 연패 가능성을 포지션 사이징에 "
            "반영할 필요가 있습니다."
        )

    return insights


# ============================================================
# 12. ROI 구간 분석
# ============================================================

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

    bucket_df[
        "수익률 구간"
    ] = pd.cut(
        bucket_df[
            "ROI_Percent"
        ],
        bins=bins,
        labels=labels,
        right=False
    )

    return (
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


# ============================================================
# 13. 비교 테이블
# ============================================================

def create_edge_comparison_table(dna):

    total = dna[
        "total_metrics"
    ]

    previous = dna[
        "previous_metrics"
    ]

    recent = dna[
        "recent_metrics"
    ]

    rows = [
        {
            "지표": "승률",
            "전체": total["win_rate"],
            "직전 20": previous["win_rate"],
            "최근 20": recent["win_rate"],
            "변화": dna["changes"]["win_rate"],
            "단위": "%"
        },
        {
            "지표": "Profit Factor",
            "전체": total["profit_factor"],
            "직전 20": previous["profit_factor"],
            "최근 20": recent["profit_factor"],
            "변화": dna["changes"]["profit_factor"],
            "단위": ""
        },
        {
            "지표": "손익비",
            "전체": total["reward_risk"],
            "직전 20": previous["reward_risk"],
            "최근 20": recent["reward_risk"],
            "변화": dna["changes"]["reward_risk"],
            "단위": ""
        },
        {
            "지표": "기대값",
            "전체": total["expectancy"],
            "직전 20": previous["expectancy"],
            "최근 20": recent["expectancy"],
            "변화": dna["changes"]["expectancy"],
            "단위": "%"
        },
        {
            "지표": "평균 수익률",
            "전체": total["avg_win_pct"],
            "직전 20": previous["avg_win_pct"],
            "최근 20": recent["avg_win_pct"],
            "변화": dna["changes"]["avg_win_pct"],
            "단위": "%"
        },
        {
            "지표": "평균 손실률",
            "전체": total["avg_loss_pct"],
            "직전 20": previous["avg_loss_pct"],
            "최근 20": recent["avg_loss_pct"],
            "변화": dna["changes"]["avg_loss_pct"],
            "단위": "%"
        },
        {
            "지표": "Big Winner 비율",
            "전체": total["big_winner_rate"],
            "직전 20": previous["big_winner_rate"],
            "최근 20": recent["big_winner_rate"],
            "변화": dna["changes"]["big_winner_rate"],
            "단위": "%"
        }
    ]

    return pd.DataFrame(rows)


# ============================================================
# 14. Gemini AI Coach
# ============================================================

def build_ai_coach_prompt(dna, checkpoints, drivers):

    total = dna["total_metrics"]
    previous = dna["previous_metrics"]
    recent = dna["recent_metrics"]

    driver_text = "\n".join(
        [
            f"- {x['text']} ({x['direction']})"
            for x in drivers
        ]
    )

    checkpoint_text = "\n".join(
        [
            f"- {x}"
            for x in checkpoints
        ]
    )

    prompt = f"""
당신은 트레이딩 저널의 데이터 해석 코치입니다.

중요 규칙:
1. 아래 숫자는 Python이 실제 거래 기록에서 계산한 값입니다.
2. 새로운 숫자를 계산하거나 만들어내지 마세요.
3. 매수/매도 종목 추천을 하지 마세요.
4. 미래 수익을 예측하지 마세요.
5. 사용자의 전략을 단정적으로 좋다/나쁘다 평가하지 마세요.
6. 최근 행동 변화와 리스크 관리 관점에서만 해석하세요.
7. 한국어로 간결하고 실전적으로 작성하세요.
8. 추세추종 전략에서는 낮은 승률 자체를 문제라고 단정하지 마세요.
9. 큰 승자(Big Winner)와 평균 손실 관리의 변화를 중요하게 보세요.

[Trading DNA]
유형: {dna['dna_type']}
전체 거래수: {dna['total_count']}
Edge 상태: {dna['edge_status']}

[전체 기록]
승률: {total['win_rate']:.2f}%
PF: {total['profit_factor']:.2f}
손익비: {total['reward_risk']:.2f}
기대값: {total['expectancy']:.2f}%
평균 수익률: {total['avg_win_pct']:.2f}%
평균 손실률: {total['avg_loss_pct']:.2f}%
Big Winner 비율: {total['big_winner_rate']:.2f}%

[직전 구간]
거래수: {previous['count']}
승률: {previous['win_rate']:.2f}%
PF: {previous['profit_factor']:.2f}
손익비: {previous['reward_risk']:.2f}
기대값: {previous['expectancy']:.2f}%
평균 수익률: {previous['avg_win_pct']:.2f}%
평균 손실률: {previous['avg_loss_pct']:.2f}%
Big Winner 비율: {previous['big_winner_rate']:.2f}%

[최근 구간]
거래수: {recent['count']}
승률: {recent['win_rate']:.2f}%
PF: {recent['profit_factor']:.2f}
손익비: {recent['reward_risk']:.2f}
기대값: {recent['expectancy']:.2f}%
평균 수익률: {recent['avg_win_pct']:.2f}%
평균 손실률: {recent['avg_loss_pct']:.2f}%
Big Winner 비율: {recent['big_winner_rate']:.2f}%

[Python이 감지한 주요 변화]
{driver_text}

[Python이 생성한 체크포인트]
{checkpoint_text}

다음 형식으로 작성하세요.

### 🧠 AI Coach 진단
2~3문장.

### 💪 유지할 강점
1~2개.

### 🔍 최근 달라진 점
가장 중요한 변화 1~3개.

### 🎯 다음 10거래 체크포인트
구체적으로 관찰할 행동 3개 이하.

마지막에는 반드시 다음 문장을 넣으세요.

"이 분석은 매수·매도 추천이 아니라 본인의 매매 행동을 점검하기 위한 트레이딩 저널 분석입니다."
"""

    return prompt


def run_ai_coach(
    api_key,
    dna,
    checkpoints,
    drivers
):

    genai.configure(
        api_key=api_key.strip()
    )

    model = genai.GenerativeModel(
        "gemini-2.5-flash"
    )

    prompt = build_ai_coach_prompt(
        dna,
        checkpoints,
        drivers
    )

    response = (
        model.generate_content(
            prompt
        )
    )

    if not response.parts:
        raise ValueError(
            "AI Coach 응답이 없습니다."
        )

    return response.text.strip()


# ============================================================
# 15. 데이터 로딩
# ============================================================

migrate_trade_ids()

df = load_data()

krx_list = get_krx_list()


# ============================================================
# 16. 사이드바 AI 캡처
# ============================================================

st.sidebar.header(
    "📸 AI 영수증 자동 입력"
)

with st.sidebar.expander(
    "🤖 캡쳐 화면 올리기",
    expanded=False
):

    st.markdown(
        "수익/손실 화면을 올리면 종목명, "
        "매수금액, 수익률을 자동으로 읽습니다."
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
한국 주식 증권사 앱 캡쳐 화면에서
종목명, 총 매수금액, 수익률(%)을 추출하세요.

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

                    st.session_state[
                        "form_reset_trigger"
                    ] = (
                        st.session_state.get(
                            "form_reset_trigger",
                            0
                        )
                        + 1
                    )

                    st.success(
                        "✅ 분석 성공!"
                    )

                except Exception as e:

                    st.error(
                        "🚨 이미지 분석에 실패했습니다."
                    )

                    with st.expander(
                        "오류 확인"
                    ):

                        st.write(
                            str(e)
                        )


# ============================================================
# 17. 신규 거래 입력
# ============================================================

if "form_reset_trigger" not in st.session_state:
    st.session_state["form_reset_trigger"] = 0

fc = st.session_state[
    "form_reset_trigger"
]

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
        0
    )
)

def_memo = st.session_state.get(
    "ai_memo",
    ""
)


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
        roi
        /
        100
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
                        new_trade
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
                    f"🚨 거래 저장 실패: {e}"
                )


if krx_list.empty:

    st.sidebar.caption(
        "⚠️ KRX 종목 리스트 로딩 실패"
    )

else:

    st.sidebar.caption(
        f"✅ {len(krx_list):,}개 종목 연결됨"
    )


# ============================================================
# 18. 메인
# ============================================================

st.title(
    "💎 Trading Master Dashboard"
)


if df.empty:

    st.info(
        "👈 사이드바에서 매매 기록을 입력하면 "
        "대시보드가 활성화됩니다."
    )

    st.stop()


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


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader(
        "🏆 전체 종합 성적표 (Total Legend)"
    )

    metrics = (
        calculate_period_metrics(
            analysis_df
        )
    )

    total_pl = (
        analysis_df[
            "P_L_Amount"
        ].sum()
    )

    all_wins = analysis_df[
        analysis_df[
            "P_L_Amount"
        ] > 0
    ]

    all_losses = analysis_df[
        analysis_df[
            "P_L_Amount"
        ] < 0
    ]

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

    win_probability = (
        metrics["win_rate"]
        /
        100
    )

    if money_rr > 0:

        kelly_pct = max(
            0,
            (
                win_probability
                -
                (
                    (1 - win_probability)
                    /
                    money_rr
                )
            )
            * 100
        )

    else:

        kelly_pct = 0


    m1, m2, m3, m4, m5 = (
        st.columns(5)
    )

    m1.metric(
        "💰 누적 총 손익",
        f"{total_pl:,.0f}원"
    )

    m2.metric(
        "🎯 전체 승률",
        f"{metrics['win_rate']:.1f}%"
    )

    m3.metric(
        "🔮 기간 기댓값",
        f"{metrics['expectancy']:+.2f}%"
    )

    m4.metric(
        "💎 Profit Factor",
        f"{metrics['profit_factor']:.2f}"
    )

    m5.metric(
        "⚖️ 켈리 베팅 비중",
        f"{kelly_pct:.1f}%"
    )


    st.divider()

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
        "금액 손익비",
        f"{money_rr:.2f}"
    )

    c4.metric(
        "총 매수 대금",
        f"{analysis_df['Buy_Amount'].sum():,.0f}원"
    )


    c5, c6, c7, c8 = (
        st.columns(4)
    )

    c5.metric(
        "평균 수익률",
        f"+{metrics['avg_win_pct']:.2f}%"
    )

    c6.metric(
        "평균 손실률",
        f"-{metrics['avg_loss_pct']:.2f}%"
    )

    c7.metric(
        "기간 손익비",
        f"{metrics['reward_risk']:.2f}"
    )

    c8.metric(
        "총 거래 횟수",
        f"{metrics['count']}회"
    )


    st.divider()

    st.subheader(
        "🚀 내 계좌 vs KOSPI 지수"
    )

    daily_df = (
        analysis_df
        .groupby("Date")[
            "P_L_Amount"
        ]
        .sum()
        .reset_index()
        .sort_values("Date")
    )

    daily_df["Cumulative"] = (
        daily_df[
            "P_L_Amount"
        ].cumsum()
    )

    try:

        start_date = (
            daily_df["Date"]
            .min()
            .strftime("%Y-%m-%d")
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
                    kospi_raw["Close"]
                    .iloc[:, 0]
                )

            else:

                kospi_close = (
                    kospi_raw["Close"]
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
                .dt.tz_localize(None)
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
                    x="Date:T",
                    y=alt.Y(
                        "Cumulative:Q",
                        title="내 누적 손익"
                    )
                )
            )

            kospi_chart = (
                alt.Chart(
                    kospi
                )
                .mark_line(
                    color="#FF4444",
                    strokeDash=[5, 5]
                )
                .encode(
                    x="Date:T",
                    y=alt.Y(
                        "KOSPI:Q",
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


# ============================================================
# TAB 2 - 월별
# ============================================================

with tab2:

    st.subheader(
        "📅 월별 상세 성적표"
    )

    rows = []

    for ym, group in analysis_df.groupby(
        "YearMonth"
    ):

        m = calculate_period_metrics(
            group
        )

        wins = group[
            group["P_L_Amount"] > 0
        ]

        losses = group[
            group["P_L_Amount"] < 0
        ]

        rows.append(
            {
                "기간": ym,

                "총 손익":
                    group[
                        "P_L_Amount"
                    ].sum(),

                "평균수익":
                    wins[
                        "P_L_Amount"
                    ].mean()
                    if not wins.empty
                    else 0,

                "평균손실":
                    losses[
                        "P_L_Amount"
                    ].mean()
                    if not losses.empty
                    else 0,

                "거래횟수":
                    len(group),

                "승률":
                    m["win_rate"],

                "손익비":
                    m["reward_risk"],

                "PF":
                    m["profit_factor"],

                "기대수익":
                    m["expectancy"],

                "매수총액":
                    group[
                        "Buy_Amount"
                    ].sum()
            }
        )

    monthly_table = (
        pd.DataFrame(rows)
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


# ============================================================
# TAB 3 - 연도별
# ============================================================

with tab3:

    st.subheader(
        "📆 연도별 종합 성적표"
    )

    rows = []

    for year, group in analysis_df.groupby(
        "Year"
    ):

        m = calculate_period_metrics(
            group
        )

        wins = group[
            group["P_L_Amount"] > 0
        ]

        losses = group[
            group["P_L_Amount"] < 0
        ]

        rows.append(
            {
                "연도":
                    int(year),

                "총 손익":
                    group[
                        "P_L_Amount"
                    ].sum(),

                "평균수익":
                    wins[
                        "P_L_Amount"
                    ].mean()
                    if not wins.empty
                    else 0,

                "평균손실":
                    losses[
                        "P_L_Amount"
                    ].mean()
                    if not losses.empty
                    else 0,

                "거래횟수":
                    len(group),

                "승률":
                    m["win_rate"],

                "손익비":
                    m["reward_risk"],

                "PF":
                    m["profit_factor"],

                "기대수익":
                    m["expectancy"],

                "매수총액":
                    group[
                        "Buy_Amount"
                    ].sum()
            }
        )

    yearly_table = (
        pd.DataFrame(rows)
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


# ============================================================
# TAB 4 - 원본
# ============================================================

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


# ============================================================
# TAB 5 - 빅터
# ============================================================

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
            pd.Timestamp.today()
            .normalize()
            -
            timedelta(
                days=period_days[
                    vic_period
                ]
            )
        ]

    if not vic_df.empty:

        vm = (
            calculate_period_metrics(
                vic_df
            )
        )

        v1, v2, v3 = (
            st.columns(3)
        )

        v1.metric(
            "기간 손익비",
            f"{vm['reward_risk']:.2f} : 1"
        )

        v2.metric(
            "기간 기댓값",
            f"{vm['expectancy']:+.2f}%"
        )

        v3.metric(
            "목표 기준",
            "3.0 : 1"
        )

        target_roi = (
            vm["avg_loss_pct"]
            * 3
            if vm["avg_loss_pct"] > 0
            else 10
        )

        chart_df = vic_df.copy()

        chart_df[
            "Color_Hex"
        ] = np.select(
            [
                chart_df[
                    "ROI_Percent"
                ] >= target_roi,

                chart_df[
                    "ROI_Percent"
                ] > 0
            ],
            [
                "#00CC00",
                "#F1C40F"
            ],
            default="#FF4B4B"
        )

        scatter = (
            alt.Chart(
                chart_df
            )
            .mark_circle(
                size=100
            )
            .encode(
                x="Date:T",
                y="ROI_Percent:Q",
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

        rule = (
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
                strokeDash=[3, 3]
            )
            .encode(
                y="Target:Q"
            )
        )

        st.altair_chart(
            scatter + rule,
            use_container_width=True
        )


# ============================================================
# TAB 6 - R 배수
# ============================================================

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

        losses = r_df[
            r_df[
                "P_L_Amount"
            ] < 0
        ]

        one_r = (
            abs(
                losses[
                    "P_L_Amount"
                ].mean()
            )
            if not losses.empty
            else 1
        )

        if (
            pd.isna(one_r)
            or
            one_r <= 0
        ):

            one_r = 1

        r_df = r_df.copy()

        r_df["R_Value"] = (
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
            .sort_values("Date")
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

        st.line_chart(
            r_chart_df.set_index(
                "Trade_Num"
            )[
                "Cumulative_R"
            ]
        )


# ============================================================
# TAB 7 - 손익 분포
# ============================================================

with tab7:

    st.subheader(
        "🔔 손익 분포"
    )

    histogram = (
        alt.Chart(
            analysis_df
        )
        .mark_bar()
        .encode(
            x=alt.X(
                "ROI_Percent:Q",
                bin=alt.Bin(
                    step=2.5
                )
            ),
            y="count():Q",
            color=alt.condition(
                alt.datum.ROI_Percent > 0,
                alt.value("#00AA00"),
                alt.value("#FF4444")
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
        analysis_df[
            "ROI_Percent"
        ].skew()
    )

    if pd.isna(skewness):
        skewness = 0

    st.info(
        f"📊 Skewness: {skewness:.2f}"
    )


# ============================================================
# TAB 8 - 거래 관리
# ============================================================

with tab8:

    st.subheader(
        "🛠️ 거래 관리"
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
                )
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

        d1, d2, d3, d4 = (
            st.columns(4)
        )

        d1.metric(
            "종목",
            selected["Ticker"]
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


        st.divider()

        st.markdown(
            "### ✏️ 거래 수정"
        )

        with st.form(
            f"edit_{selected_trade_id}"
        ):

            edit_date = st.date_input(
                "거래일",
                value=selected[
                    "Date"
                ].date()
            )

            edit_ticker = st.text_input(
                "종목명",
                value=str(
                    selected["Ticker"]
                )
            )

            edit_buy = st.number_input(
                "매수금액",
                min_value=0,
                value=int(
                    round(
                        selected[
                            "Buy_Amount"
                        ]
                    )
                ),
                step=100000
            )

            edit_roi = st.number_input(
                "수익률 (%)",
                value=float(
                    selected[
                        "ROI_Percent"
                    ]
                ),
                format="%.2f"
            )

            edit_memo = st.text_area(
                "메모",
                value=str(
                    selected["Memo"]
                )
            )

            edit_pl = (
                edit_buy
                *
                edit_roi
                /
                100
            )

            edit_sell = (
                edit_buy
                +
                edit_pl
            )

            if st.form_submit_button(
                "💾 수정 내용 저장",
                use_container_width=True
            ):

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

                    mask = (
                        live_df[
                            "Trade_ID"
                        ].astype(str)
                        ==
                        str(
                            selected_trade_id
                        )
                    )

                    if not mask.any():

                        st.error(
                            "거래를 찾을 수 없습니다."
                        )

                    else:

                        idx = (
                            live_df[
                                mask
                            ].index[0]
                        )

                        live_df.at[
                            idx,
                            "Date"
                        ] = pd.Timestamp(
                            edit_date
                        )

                        live_df.at[
                            idx,
                            "Ticker"
                        ] = (
                            edit_ticker.strip()
                        )

                        live_df.at[
                            idx,
                            "Buy_Amount"
                        ] = float(
                            edit_buy
                        )

                        live_df.at[
                            idx,
                            "ROI_Percent"
                        ] = float(
                            edit_roi
                        )

                        live_df.at[
                            idx,
                            "P_L_Amount"
                        ] = float(
                            edit_pl
                        )

                        live_df.at[
                            idx,
                            "Sell_Amount"
                        ] = float(
                            edit_sell
                        )

                        live_df.at[
                            idx,
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
                        f"수정 실패: {e}"
                    )


        st.divider()

        delete_confirm = (
            st.checkbox(
                "이 거래를 정말 삭제하겠습니다."
            )
        )

        if st.button(
            "🗑️ 거래 영구 삭제",
            disabled=not delete_confirm,
            use_container_width=True
        ):

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

                conn.update(
                    worksheet=0,
                    data=prepare_for_sheet(
                        live_df
                    )
                )

                st.success(
                    "🗑️ 거래 삭제 완료!"
                )

                st.rerun()

            except Exception as e:

                st.error(
                    f"삭제 실패: {e}"
                )


# ============================================================
# TAB 9 - MILESTONE 4 TRADING DNA
# ============================================================

with tab9:

    st.subheader(
        "🧠 My Trading DNA"
    )

    st.caption(
        "장기 Trading DNA와 최근 Edge 변화를 "
        "실제 거래 데이터로 추적합니다."
    )

    dna = (
        calculate_trading_dna(
            analysis_df
        )
    )


    # --------------------------------------------------------
    # DNA TYPE
    # --------------------------------------------------------

    st.markdown(
        f"## {dna['dna_type']}"
    )

    st.info(
        dna["dna_description"]
    )

    st.caption(
        f"{dna['total_count']:,}건의 거래 기록 기반"
    )


    # --------------------------------------------------------
    # 핵심 DNA
    # --------------------------------------------------------

    st.markdown(
        "### 🧬 핵심 DNA"
    )

    d1, d2, d3, d4 = (
        st.columns(4)
    )

    d1.metric(
        "🎯 승률",
        f"{dna['win_rate']:.1f}%"
    )

    d2.metric(
        "⚖️ 평균 손익비",
        f"{dna['reward_risk']:.2f}"
    )

    d3.metric(
        "💎 Profit Factor",
        f"{dna['profit_factor']:.2f}"
    )

    d4.metric(
        "🔮 거래당 기대값",
        f"{dna['expectancy']:+.2f}%"
    )


    st.divider()


    # --------------------------------------------------------
    # Big Winner
    # --------------------------------------------------------

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


    if not dna[
        "big_winners"
    ].empty:

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


    # --------------------------------------------------------
    # Risk DNA
    # --------------------------------------------------------

    st.markdown(
        "### 🛡️ Risk DNA"
    )

    r1, r2, r3, r4 = (
        st.columns(4)
    )

    r1.metric(
        "평균 손실률",
        f"-{dna['avg_loss_pct']:.2f}%"
    )

    r2.metric(
        "최대 손실률",
        f"-{dna['max_loss_pct']:.2f}%"
    )

    r3.metric(
        "최대 연속 손실",
        f"{dna['max_loss_streak']}회"
    )

    r4.metric(
        "최대 연속 수익",
        f"{dna['max_win_streak']}회"
    )


    st.divider()


    # --------------------------------------------------------
    # NEW - EDGE STATUS
    # --------------------------------------------------------

    st.markdown(
        "### 📡 Edge Change Detection"
    )

    st.markdown(
        f"## {dna['edge_icon']} "
        f"현재 Edge 상태: **{dna['edge_status']}**"
    )

    recent = dna[
        "recent_metrics"
    ]

    previous = dna[
        "previous_metrics"
    ]

    c1, c2, c3, c4 = (
        st.columns(4)
    )

    c1.metric(
        "최근 20 승률",
        f"{recent['win_rate']:.1f}%",
        (
            f"{dna['changes']['win_rate']:+.1f}%p"
            if dna["has_previous"]
            else None
        )
    )

    c2.metric(
        "최근 20 PF",
        f"{recent['profit_factor']:.2f}",
        (
            f"{dna['changes']['profit_factor']:+.2f}"
            if dna["has_previous"]
            else None
        )
    )

    c3.metric(
        "최근 20 손익비",
        f"{recent['reward_risk']:.2f}",
        (
            f"{dna['changes']['reward_risk']:+.2f}"
            if dna["has_previous"]
            else None
        )
    )

    c4.metric(
        "최근 20 기대값",
        f"{recent['expectancy']:+.2f}%",
        (
            f"{dna['changes']['expectancy']:+.2f}%p"
            if dna["has_previous"]
            else None
        )
    )


    # --------------------------------------------------------
    # 전체 / 직전 / 최근 비교
    # --------------------------------------------------------

    st.markdown(
        "#### 🔬 전체 vs 직전 20 vs 최근 20"
    )

    if dna["has_previous"]:

        comparison = (
            create_edge_comparison_table(
                dna
            )
        )

        st.dataframe(
            comparison.style.format(
                {
                    "전체": "{:.2f}",
                    "직전 20": "{:.2f}",
                    "최근 20": "{:.2f}",
                    "변화": "{:+.2f}"
                }
            ),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "직전 구간과 안정적으로 비교하려면 "
            "최소 25~40건 정도의 거래 기록을 권장합니다."
        )


    # --------------------------------------------------------
    # 변화 원인
    # --------------------------------------------------------

    st.markdown(
        "### 🔍 Edge 변화 원인"
    )

    drivers = (
        detect_edge_drivers(
            dna
        )
    )

    if drivers:

        for driver in drivers:

            if (
                driver["direction"]
                ==
                "positive"
            ):

                st.success(
                    "📈 "
                    +
                    driver["text"]
                )

            else:

                st.warning(
                    "📉 "
                    +
                    driver["text"]
                )

    else:

        st.info(
            "현재 구간에서는 뚜렷한 Edge 변화 원인이 "
            "감지되지 않았습니다."
        )


    st.divider()


    # --------------------------------------------------------
    # ROI 구간
    # --------------------------------------------------------

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
                    sort=None
                ),
                y="총손익:Q",
                color=alt.condition(
                    alt.datum.총손익 > 0,
                    alt.value("#00AA00"),
                    alt.value("#FF4444")
                ),
                tooltip=[
                    "수익률 구간",
                    "거래수",
                    "총손익",
                    "평균수익률"
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


    # --------------------------------------------------------
    # Rule Based Coach
    # --------------------------------------------------------

    st.markdown(
        "### 🧠 Trading Coach Insights"
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


    # --------------------------------------------------------
    # NEW - 행동 체크포인트
    # --------------------------------------------------------

    st.markdown(
        "### 🎯 다음 거래 체크포인트"
    )

    checkpoints = (
        generate_coach_checkpoints(
            dna
        )
    )

    for index, checkpoint in enumerate(
        checkpoints,
        start=1
    ):

        st.markdown(
            f"**{index}.** {checkpoint}"
        )


    st.divider()


    # --------------------------------------------------------
    # NEW - REAL AI COACH
    # --------------------------------------------------------

    st.markdown(
        "### 🤖 AI Trading Coach"
    )

    st.caption(
        "Python이 먼저 실제 거래 통계를 계산하고, "
        "AI는 계산된 숫자만 해석합니다."
    )

    if not api_key:

        st.info(
            "👈 사이드바의 Gemini API Key를 입력하면 "
            "AI Coach를 사용할 수 있습니다."
        )

    else:

        if st.button(
            "🧠 내 Trading DNA AI 분석",
            use_container_width=True,
            type="primary"
        ):

            with st.spinner(
                "AI Coach가 Trading DNA와 최근 Edge 변화를 분석 중입니다..."
            ):

                try:

                    ai_report = (
                        run_ai_coach(
                            api_key,
                            dna,
                            checkpoints,
                            drivers
                        )
                    )

                    st.session_state[
                        "ai_coach_report"
                    ] = ai_report

                except Exception as e:

                    st.error(
                        "🚨 AI Coach 분석에 실패했습니다."
                    )

                    with st.expander(
                        "오류 확인"
                    ):

                        st.write(
                            str(e)
                        )


        if st.session_state.get(
            "ai_coach_report"
        ):

            st.success(
                "✅ AI Coach 분석 완료"
            )

            st.markdown(
                st.session_state[
                    "ai_coach_report"
                ]
            )


    st.caption(
        "⚠️ Trading Coach는 투자 추천이 아니라 "
        "본인의 매매 기록과 행동을 복기하기 위한 분석 도구입니다."
        )
