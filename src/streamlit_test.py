import streamlit as st
import pandas as pd
from pathlib import Path

DATA_PATH = Path("../data/202507-divvy-tripdata/202507-divvy-tripdata.csv")

# get data
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce")
    df["ended_at"] = pd.to_datetime(df["ended_at"], errors="coerce")
    df["start_hour"] = df["started_at"].dt.floor("H")
    df["end_hour"] = df["ended_at"].dt.floor("H")
    df = df.dropna(subset=["start_station_id", "end_station_id", "start_hour", "end_hour"])
    return df

df = load_data(DATA_PATH)

# station ID Name mapping
stations_df = pd.concat([
    df[["start_station_id", "start_station_name"]].rename(columns={
        "start_station_id": "station_id",
        "start_station_name": "station_name"
    }),
    df[["end_station_id", "end_station_name"]].rename(columns={
        "end_station_id": "station_id",
        "end_station_name": "station_name"
    })
]).drop_duplicates().dropna(subset=["station_id"])

# Hourly balance
'''
tmp looks like e.g.:
station_id  hour                      delta
4           1234 2023-07-01 00:00:00      1
1           1234 2023-07-01 01:00:00      1
2           1234 2023-07-01 02:00:00     -1
5           5678 2023-07-01 00:00:00      1
4           5678 2023-07-01 01:00:00     -1

'''
tmp = pd.concat([
    pd.DataFrame({
        "station_id": df["start_station_id"],
        "hour": df["start_hour"],
        "delta": 1
    }),
    pd.DataFrame({
        "station_id": df["end_station_id"],
        "hour": df["end_hour"],
        "delta": -1
    })
], ignore_index=True).dropna(subset=["station_id", "hour"])

# Sum deltas per station+hour, then cumulative sum per station
'''
hourly looks like e.g.:
    hour                       station_id   delta
0    2023-07-01 00:00:00       1234         1
1    2023-07-01 01:00:00       1234         1 
2    2023-07-01 02:00:00       1234        -1
'''
hourly = (
    tmp.groupby(["hour", "station_id"], as_index=False)["delta"]
       .sum()
       .sort_values(["station_id", "hour"])
)

# add cumulative sum and starting balance (10)
hourly["balance"] = hourly.groupby("station_id")["delta"].cumsum() + 10

# ----------------------------------------------------
# App layout
# ----------------------------------------------------

# Streamlit setup
st.set_page_config(page_title="Bike Balance Monitor", layout="wide")
st.title("🚲 Bike Balances")

if "current_hour_index" not in st.session_state:
    st.session_state.current_hour_index = 8 # 8 just for testing
if "adjustments" not in st.session_state:
    st.session_state.adjustments = {}

all_hours = sorted(hourly["hour"].unique())
if not all_hours:
    st.error("No data found.")
    st.stop()

current_hour = all_hours[st.session_state.current_hour_index]

# Sidebar simulation
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
    st.session_state.current_hour_index = 0
    st.session_state.adjustments = {}
    st.rerun()

# Apply adjustments
def apply_adjustments(df, adjustments):
    if not adjustments:
        return df
    df = df.copy()
    for sid, adj in adjustments.items():
        mask = df["station_id"] == sid
        df.loc[mask, "balance"] += adj
    return df

hourly_adj = apply_adjustments(hourly, st.session_state.adjustments)
now = hourly_adj[hourly_adj["hour"] == current_hour].merge(stations_df, on="station_id", how="left")

# =====================================================
# 5. Show stations with negative / positive balances (side-by-side + clickable)
# =====================================================
negatives = now[now["balance"] < 10].sort_values("balance").head(10)
positives = now[now["balance"] > 10].sort_values("balance", ascending=False).head(10)

def colorize(val: int) -> str:
    if val < 10:
        return f"<span style='color:red;'>▼ {val}</span>"
    elif val > 10:
        return f"<span style='color:green;'>▲ {val}</span>"
    return f"<span style='color:gray;'>{val}</span>"

st.markdown(f"### 🕒 Balances at {current_hour}")
st.caption("Click on a station ID to add it to your adjustment list.")

col1, col2 = st.columns(2)

def clickable_station_table(df, label, color_icon, suffix):
    """Renders a simple clickable table of stations."""
    st.markdown(f"#### {color_icon} {label}")
    if df.empty:
        st.info("No stations in this category.")
        return []

    clicked = []
    for _, row in df.iterrows():
        sid = row["station_id"]
        name = row["station_name"]
        val = int(row["balance"])
        col_a, col_b, col_c = st.columns([2, 5, 2])
        # unique key includes suffix and current_hour
        key = f"add_{sid}_{suffix}_{current_hour}"
        if col_a.button(f"{sid}", key=key):
            clicked.append(sid)
        col_b.write(name)
        col_c.markdown(colorize(val), unsafe_allow_html=True)
    return clicked

with col1:
    added_low = clickable_station_table(negatives, "Stations Below Starting Balance", "🚨", "low")
with col2:
    added_high = clickable_station_table(positives, "Stations Above Starting Balance", "🟢", "high")

clicked_ids = set(added_low + added_high)

# =====================================================
# 6. Manual adjustments (auto-add clicked IDs)
# =====================================================
st.markdown("---")
st.subheader("🧰 Manual Adjustments")

if "selected_stations" not in st.session_state:
    st.session_state.selected_stations = []

# Add clicked stations if not already selected
for sid in clicked_ids:
    if sid not in st.session_state.selected_stations:
        st.session_state.selected_stations.append(sid)

# Keep only valid stations (in case data changed)
valid_ids = set(now["station_id"].unique())
st.session_state.selected_stations = [
    sid for sid in st.session_state.selected_stations if sid in valid_ids
]

# Show adjustment UI
if not st.session_state.selected_stations:
    st.info("Click on a station ID above to add it here for adjustment.")
else:
    st.caption("Positive = add bikes, Negative = remove bikes.")

    adjust_values = {}
    for sid in st.session_state.selected_stations:
        row = now[now["station_id"] == sid].iloc[0]
        name = row["station_name"]
        balance = int(row["balance"])

        cols = st.columns([2, 6, 2])
        cols[0].write(f"**{sid}**")
        cols[1].write(name)
        cols[2].markdown(colorize(balance), unsafe_allow_html=True)

        adjust_values[sid] = st.number_input(
            f"Adjust {sid}", value=0, step=1, key=f"adj_{sid}_{current_hour}", label_visibility="collapsed"
        )

    if st.button("✅ Apply Adjustments"):
        # apply adjustments
        for sid, val in adjust_values.items():
            if val != 0:
                st.session_state.adjustments[sid] = st.session_state.adjustments.get(sid, 0) + val

        # reset everything
        st.session_state.selected_stations = []
        # clear number inputs for next cycle
        for k in list(st.session_state.keys()):
            if k.startswith("adj_"):
                del st.session_state[k]
        st.success("Adjustments applied and form reset.")
        st.rerun()