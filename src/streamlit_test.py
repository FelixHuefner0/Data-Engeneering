import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import DatabaseConnection
from database.repositories import StationRepository, EventsHourlyRepository
from config.database import DB_PATH, INITIAL_BALANCE

start_at = 16  # just for testing
initial_balance = INITIAL_BALANCE

# ----------------------------------------------------
# 1. Load data from database
# ----------------------------------------------------
@st.cache_data
def load_stations_from_db() -> pd.DataFrame:
    """Load all stations from database."""
    db = DatabaseConnection(DB_PATH)
    with db.get_connection() as conn:
        station_repo = StationRepository(conn)
        stations = station_repo.get_all_stations(active_only=True)
        
    # Convert to DataFrame
    stations_data = [dict(row) for row in stations]
    df = pd.DataFrame(stations_data)
    
    # Rename columns to match existing logic
    df = df.rename(columns={"id": "station_id", "name": "station_name"})
    return df[["station_id", "station_name"]]


@st.cache_data
def load_hourly_events_from_db() -> pd.DataFrame:
    """Load all hourly events from database."""
    db = DatabaseConnection(DB_PATH)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT hour, station_id, delta_total as delta
            FROM events_hourly
            ORDER BY hour, station_id
        """)
        events = cursor.fetchall()
    
    # Convert to DataFrame
    events_data = [dict(row) for row in events]
    df = pd.DataFrame(events_data)
    
    # Convert hour to datetime
    df["hour"] = pd.to_datetime(df["hour"])
    
    return df


# Load data from database
stations_df = load_stations_from_db()
all_station_ids = stations_df["station_id"].unique()

hourly = load_hourly_events_from_db()

# ----------------------------------------------------
# 4. Streamlit setup & state
# ----------------------------------------------------
st.set_page_config(page_title="Bike Balance Monitor", layout="wide")
st.title("🚲 Bike Balances")

if "current_hour_index" not in st.session_state:
    st.session_state.current_hour_index = start_at

# adjustments: dict station_id -> cumulative adjustment (persistenter, zeitloser Offset)
if "adjustments" not in st.session_state:
    st.session_state.adjustments = {}

if "selected_stations" not in st.session_state:
    st.session_state.selected_stations = []

# ----------------------------------------------------
# 5. Hours / simulation controls + Popup Warning
# ----------------------------------------------------
all_hours = sorted(hourly["hour"].unique())
if not all_hours:
    st.error("No data found in database. Please run the ETL pipeline first: python -m src.batch_build_stations")
    st.stop()

current_hour = all_hours[st.session_state.current_hour_index]

# ⚠️ Popup-Zustand im Session State
if "show_popup" not in st.session_state:
    st.session_state.show_popup = False
if "popup_message" not in st.session_state:
    st.session_state.popup_message = ""

# Warnlogik
def check_balance_limits(balances_df):
    """Check if any station violates the balance limits and prepare formatted popup text."""
    low = balances_df[balances_df["balance"] < 5]
    high = balances_df[balances_df["balance"] > 30]
    if not low.empty or not high.empty:
        msg_parts = []
        if not low.empty:
            msg_parts.append("<h4 class='low'>🚲 Zu wenige Fahrräder:</h4><ul>")
            for _, row in low.iterrows():
                msg_parts.append(f"<li class='low'>{row['station_name']} — {int(row['balance'])} Fahrräder</li>")
            msg_parts.append("</ul>")
        if not high.empty:
            msg_parts.append("<h4 class='high'>🚲 Zu viele Fahrräder:</h4><ul>")
            for _, row in high.iterrows():
                msg_parts.append(f"<li class='high'>{row['station_name']} — {int(row['balance'])} Fahrräder</li>")
            msg_parts.append("</ul>")
        st.session_state.popup_message = "\n".join(msg_parts)
        st.session_state.show_popup = True

# ----------------------------------------------------
#  Helper function: Stunden fortschalten + Warnungen prüfen
# ----------------------------------------------------
def advance_hours(steps: int):
    """Advance the simulation by the given number of hours and check for balance warnings."""
    st.session_state.current_hour_index = min(
        st.session_state.current_hour_index + steps,
        len(all_hours) - 1
    )

    new_hour = all_hours[st.session_state.current_hour_index]

    cum_delta = (
        hourly[hourly["hour"] <= new_hour]
        .groupby("station_id")["delta"]
        .sum()
        .reindex(all_station_ids, fill_value=0)
    )
    adj_series = pd.Series(
        {sid: st.session_state.adjustments.get(sid, 0) for sid in all_station_ids},
        index=all_station_ids
    )
    balances_series = initial_balance + cum_delta + adj_series
    balances_df = pd.DataFrame({
        "station_id": balances_series.index,
        "balance": balances_series.values
    }).merge(stations_df, on="station_id", how="left")

    # Check limits (sets show_popup if needed)
    check_balance_limits(balances_df)

    # always rerun, even if popup appears
    st.rerun()


# Sidebar UI
st.sidebar.header("⏱️ Time Simulation")
st.sidebar.write(f"**Current Hour:** {current_hour}")
colA, colB = st.sidebar.columns(2)
with colA:
    if st.button("➡️ Next Hour"):
        advance_hours(1)
with colB:
    if st.button("⏩ +6 Hours"):
        advance_hours(6)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset Simulation"):
    st.session_state.current_hour_index = start_at
    st.session_state.adjustments = {}
    st.session_state.selected_stations = []
    st.session_state.show_popup = False
    st.session_state.popup_message = ""
    st.rerun()

# ⚠️ External popup window (not inside Streamlit page)
if st.session_state.show_popup:
    # escape backticks & linebreaks for JS string
    html_message = st.session_state.popup_message.replace("`", "\\`").replace("\n", "")
    popup_script = f"""
    <script>
    // Close any existing popup first
    if (window.bikePopup && !window.bikePopup.closed) {{
        window.bikePopup.close();
    }}

    // Open a new small external window
    const popupFeatures = "width=700,height=600,left=150,top=150,resizable=yes,scrollbars=yes";
    window.bikePopup = window.open("", "BikeWarning", popupFeatures);

    const htmlContent = `
        <html>
        <head>
            <meta charset='UTF-8'>
            <title>Stationswarnung</title>
            <style>
                body {{
                    background-color: #1e1e1e;
                    color: #f1f1f1;
                    font-family: sans-serif;
                    margin: 0;
                    padding: 30px;
                    line-height: 1.6;
                }}
                h2 {{ color: #ff4b4b; margin-top: 0; }}
                .low  {{ color: #ff6961; }}
                .high {{ color: #77dd77; }}
                .container {{
                    max-width: 640px;
                    margin: auto;
                    background: #2b2b2b;
                    border-radius: 10px;
                    padding: 25px;
                    box-shadow: 0 4px 25px rgba(0,0,0,0.5);
                }}
                button {{
                    background-color: #444;
                    color: white;
                    border: none;
                    padding: 10px 18px;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-top: 20px;
                    font-size: 15px;
                }}
                button:hover {{
                    background-color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>⚠️ Stationswarnung</h2>
                <p>Folgende Stationen haben kritische Bestände:</p>
                {html_message}
                <button onclick="window.close()">OK, verstanden</button>
            </div>
        </body>
        </html>
    `;

    window.bikePopup.document.write(htmlContent);
    window.bikePopup.document.close();
    </script>
    """
    st.components.v1.html(popup_script, height=0)
    st.session_state.show_popup = False

# ----------------------------------------------------
# 6. Deterministische Bestände: initial + Σ delta (<= current_hour) + adjustments
# ----------------------------------------------------
cum_delta = (
    hourly[hourly["hour"] <= current_hour]
    .groupby("station_id")["delta"]
    .sum()
    .reindex(all_station_ids, fill_value=0)
)

adj_series = pd.Series(
    {sid: st.session_state.adjustments.get(sid, 0) for sid in all_station_ids},
    index=all_station_ids
)

balances_series = initial_balance + cum_delta + adj_series

now = pd.DataFrame({
    "station_id": balances_series.index,
    "balance": balances_series.values
}).merge(stations_df, on="station_id", how="left")

# ----------------------------------------------------
# 7. Top-10 negatives / positives (side-by-side, click-to-add)
# ----------------------------------------------------
def colorize(val: int) -> str:
    if val < initial_balance:
        return f"<span style='color:red;'>▼ {val}</span>"
    elif val > initial_balance:
        return f"<span style='color:green;'>▲ {val}</span>"
    return f"<span style='color:gray;'>{val}</span>"

negatives = now[now["balance"] < initial_balance].sort_values("balance", ascending=True).head(10)
positives = now[now["balance"] > initial_balance].sort_values("balance", ascending=False).head(10)

st.markdown(f"### 🕒 Balances at {current_hour}")
st.caption("Click on a station ID to add it to your adjustment list.")

col1, col2 = st.columns(2)

def clickable_station_table(df, label, color_icon, suffix):
    st.markdown(f"#### {color_icon} {label}")
    if df.empty:
        st.info("No stations in this category.")
        return []

    clicked = []
    for idx, row in enumerate(df.itertuples(index=False), start=1):
        sid = row.station_id
        name = row.station_name
        val = int(row.balance)
        c1, c2, c3 = st.columns([2, 5, 2])
        key = f"add_{sid}_{suffix}_{current_hour}_{idx}"
        if c1.button(f"{sid}", key=key):
            clicked.append(sid)
        c2.write(name)
        c3.markdown(colorize(val), unsafe_allow_html=True)
    return clicked

with col1:
    added_low = clickable_station_table(negatives, "Stations Below Starting Balance", "🚨", "low")
with col2:
    added_high = clickable_station_table(positives, "Stations Above Starting Balance", "🟢", "high")

clicked_ids = set(added_low + added_high)

# ----------------------------------------------------
# 8. Manual adjustments UI (multi-station)
# ----------------------------------------------------
st.markdown("---")
st.subheader("🧰 Manual Adjustments")

for sid in clicked_ids:
    if sid not in st.session_state.selected_stations:
        st.session_state.selected_stations.append(sid)

valid_ids = set(now["station_id"].unique())
st.session_state.selected_stations = [sid for sid in st.session_state.selected_stations if sid in valid_ids]

if not st.session_state.selected_stations:
    st.info("Click on a station ID above to add it here for adjustment.")
else:
    st.caption("Positive = add bikes, Negative = remove bikes.")
    adjust_values = {}
    for sid in st.session_state.selected_stations:
        row = now[now["station_id"] == sid].iloc[0]
        name = row["station_name"]
        bal = int(row["balance"])

        c1, c2, c3 = st.columns([2, 6, 2])
        c1.write(f"**{sid}**")
        c2.write(name)
        c3.markdown(colorize(bal), unsafe_allow_html=True)

        adjust_values[sid] = st.number_input(
            f"Adjust {sid}",
            value=0, step=1,
            key=f"adj_{sid}_{current_hour}",
            label_visibility="collapsed"
        )

    if st.button("✅ Apply Adjustments"):
        for sid, val in adjust_values.items():
            if val != 0:
                st.session_state.adjustments[sid] = st.session_state.adjustments.get(sid, 0) + int(val)

        st.session_state.selected_stations = []
        for k in list(st.session_state.keys()):
            if k.startswith("adj_"):
                del st.session_state[k]

        st.success("Adjustments applied and form reset.")
        st.rerun()
