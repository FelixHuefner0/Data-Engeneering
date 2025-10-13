import streamlit as st
import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR.parent / "data" / "202507-divvy-tripdata" / "202507-divvy-tripdata.csv"

start_at = 16  # just for testing
initial_balance = 20

# ----------------------------------------------------
# 1. Load data
# ----------------------------------------------------
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce")
    df["ended_at"] = pd.to_datetime(df["ended_at"], errors="coerce")
    df["start_hour"] = df["started_at"].dt.floor("h")
    df["end_hour"] = df["ended_at"].dt.floor("h")
    # KEIN Drop beider Seiten gleichzeitig; wir filtern getrennt bei Events
    return df

df = load_data(DATA_PATH)

# ----------------------------------------------------
# 2. Station mapping (unique station_id)
# ----------------------------------------------------
stations_df = pd.concat([
    df[["start_station_id", "start_station_name"]].rename(columns={
        "start_station_id": "station_id",
        "start_station_name": "station_name"
    }),
    df[["end_station_id", "end_station_name"]].rename(columns={
        "end_station_id": "station_id",
        "end_station_name": "station_name"
    })
]).dropna(subset=["station_id"]).drop_duplicates(subset=["station_id"])

all_station_ids = stations_df["station_id"].unique()

# ----------------------------------------------------
# 3. Compute hourly deltas (closed-system event log)
#    -1 at start station at start_hour, +1 at end station at end_hour
#    Start/End getrennt behandeln, damit "halbe" Fahrten nicht wegfallen
# ----------------------------------------------------
tmp_start = df.dropna(subset=["start_station_id", "start_hour"])
tmp_end   = df.dropna(subset=["end_station_id", "end_hour"])

# array(['CHI00285', Timestamp('2025-07-05 17:00:00'), -1], dtype=object)
# array(['CHI00400', Timestamp('2025-07-01 13:00:00'), -1], dtype=object)
# array(['CHI00420', Timestamp('2025-07-31 16:00:00'), -1], dtype=object) ...
# shape is half delta -1 half delta +1


events = pd.concat([
    pd.DataFrame({
        "station_id": tmp_start["start_station_id"],
        "hour": tmp_start["start_hour"],
        "delta": -1
    }),
    pd.DataFrame({
        "station_id": tmp_end["end_station_id"],
        "hour": tmp_end["end_hour"],
        "delta": 1
    })
], ignore_index=True)# .dropna(subset=["station_id", "hour"]) delets events happening in the same station and same hour

print(events)
# Aggregation pro (hour, station)
hourly = (
    events.groupby(["hour", "station_id"], as_index=False)["delta"]
          .sum()
          .sort_values(["station_id", "hour"])
)
def test_data():
    print(df["started_at"].isna().sum(), "NaT in started_at")
    print(df["ended_at"].isna().sum(), "NaT in ended_at")
    print(df["start_hour"].isna().sum(), "NaT in start_hour")
    print(df["end_hour"].isna().sum(), "NaT in end_hour")
    print("Free floating bikes:") # 25$ payment baby
    print(df["start_station_id"].isna().sum(), "NaN in start_station_id")
    print(df["end_station_id"].isna().sum(), "NaN in end_station_id")
    check = (events.groupby("hour")["delta"].sum()).sum()
    print(f"Imbalance hours: {check}")
# test_data()




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
# 5. Hours / simulation controls
# ----------------------------------------------------
all_hours = sorted(hourly["hour"].unique())
if not all_hours:
    st.error("No data found.")
    st.stop()

current_hour = all_hours[st.session_state.current_hour_index]

st.sidebar.header("⏱️ Time Simulation")
st.sidebar.write(f"**Current Hour:** {current_hour}")
colA, colB = st.sidebar.columns(2)
with colA:
    if st.button("➡️ Next Hour"):
        st.session_state.current_hour_index = min(
            st.session_state.current_hour_index + 1, len(all_hours) - 1
        )
        st.rerun()
with colB:
    if st.button("⏩ +6 Hours"):
        st.session_state.current_hour_index = min(
            st.session_state.current_hour_index + 6, len(all_hours) - 1
        )
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset Simulation"):
    st.session_state.current_hour_index = start_at
    st.session_state.adjustments = {}
    st.session_state.selected_stations = []
    st.rerun()

# ----------------------------------------------------
# 6. Deterministische Bestände: initial + Σ delta (<= current_hour) + adjustments
# ----------------------------------------------------
# Summe der Deltas bis zur aktuellen Stunde
cum_delta = (
    hourly[hourly["hour"] <= current_hour] # filtert alle Events bis current_hour
    .groupby("station_id")["delta"]
    .sum()
    .reindex(all_station_ids, fill_value=0) # fill missing stations with 0
)

# Persistente manuelle Anpassungen
adj_series = pd.Series(
    {sid: st.session_state.adjustments.get(sid, 0) for sid in all_station_ids},
    index=all_station_ids
)

balances_series = initial_balance + cum_delta + adj_series

# Anzeige-DF
now = pd.DataFrame({
    "station_id": balances_series.index,
    "balance": balances_series.values
}).merge(stations_df, on="station_id", how="left") # merge in names

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
        key = f"add_{sid}_{suffix}_{current_hour}_{idx}"  # garantiert eindeutig
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

# Add clicked stations to selection
for sid in clicked_ids:
    if sid not in st.session_state.selected_stations:
        st.session_state.selected_stations.append(sid)

# Ensure validity
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
        # apply cumulatively to the adjustments dict (not to balances directly)
        for sid, val in adjust_values.items():
            if val != 0:
                st.session_state.adjustments[sid] = st.session_state.adjustments.get(sid, 0) + int(val)

        # reset UI selections & inputs
        st.session_state.selected_stations = []
        for k in list(st.session_state.keys()):
            if k.startswith("adj_"):
                del st.session_state[k]

        st.success("Adjustments applied and form reset.")
        st.rerun()
