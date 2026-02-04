import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import re
from datetime import datetime

# --- Configuration & Styling ---
st.set_page_config(page_title="Valorant Dashboard", layout="wide", page_icon="⚔️")

st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; }
    .css-1r6slb0, .stMarkdown, .stDataFrame { color: #e8ecf1; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #e8ecf1; }
    div[data-testid="stMetricLabel"] { color: #9fb3c8; }
    .card {
        background: linear-gradient(135deg, #121a29 0%, #0f1520 100%);
        border: 1px solid #2a3347; border-radius: 12px;
        padding: 20px; margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .card h3 {
        margin-top: 0; color: #cbd5e1; font-size: 18px;
        border-bottom: 1px solid #2a3347; padding-bottom: 10px; margin-bottom: 15px;
    }
    .pill {
        display: inline-block; background: #1b2332;
        padding: 4px 10px; border-radius: 999px;
        margin: 2px; font-size: 12px; border: 1px solid #2a3347; color: #e8ecf1;
    }
    .win { color: #81C784 !important; font-weight: bold; }
    .loss { color: #e57373 !important; font-weight: bold; }
    .team-header-left { border-left: 4px solid #4FC3F7; padding-left: 10px; }
    .team-header-right { border-left: 4px solid #FFB74D; padding-left: 10px; }
    .legend-text {
        background-color: #121a29; padding: 10px; border-radius: 8px; 
        border: 1px solid #2a3347; text-align: center; margin-bottom: 10px;
        font-family: monospace;
    }
    .stat-box {
        background: #1b2332; padding: 8px; border-radius: 6px;
        margin: 4px 0; border: 1px solid #2a3347;
    }
</style>
""", unsafe_allow_html=True)

DATA_PATH = "./web/data.json"

# Try multiple possible paths for Streamlit Cloud
if not os.path.exists(DATA_PATH):
    DATA_PATH = "web/data.json"
if not os.path.exists(DATA_PATH):
    DATA_PATH = "../web/data.json"

# DEBUG: Show what files exist
if not os.path.exists(DATA_PATH):
    st.error(f"❌ Cannot find data.json! Checked paths: ./web/data.json, web/data.json, ../web/data.json")
    st.info(f"Current directory: {os.getcwd()}")
    st.info(f"Files in current dir: {os.listdir('.')}")
    if os.path.exists('web'):
        st.info(f"Files in web/: {os.listdir('web')}")
    st.stop()

# Updated Region Definitions with Full Canonical Names
REGION_TEAMS = {
  "Americas": [
    "Sentinels", "NRG", "Cloud9", "100 Thieves", "Evil Geniuses", "LOUD",
    "FURIA", "MIBR", "Leviatán", "KRÜ Esports", "G2 Esports", "Envy"
  ],
  "EMEA": [
    "Team Liquid", "Team Vitality", "Team Heretics", "Fnatic", 
    "FUT Esports", "BBL Esports", "GIANTX", "Karmine Corp", 
    "Natus Vennere", "Gentle Mates", "PCIFIC Esports", "ULF Esports"
  ],
  "Pacific": [
    "T1", "NS RedForce", "DRX", "FULL SENSE", "Paper Rex", "ZETA", 
    "RRQ", "DetonatioN FocusMe", "Talon Esports", "Team Secret", 
    "Global Esports", "Gen.G"
  ],
  "China": [
    "EDward Gaming", "FunPlus Phoenix", "Trace Esports", "Bilibili Gaming", 
    "Wolves Esports", "TYLOO", "All Gamers", "JDG Esports", 
    "Titan Esports Club", "Dragon Ranger Gaming", "Xi Lai Gaming", "Nova Esports"
  ]
}

def normalize_name(name):
    if not name: return ""
    n = name.lower()
    n = re.sub(r'\b(team|esports|gaming)\b', '', n)
    n = re.sub(r'[^\w\s]', '', n)
    return re.sub(r'\s+', ' ', n).strip()

def is_team_in_region(team_name, region):
    if not region or region == "All Regions": return True
    target_list = REGION_TEAMS.get(region, [])
    norm_team = normalize_name(team_name)
    for t in target_list:
        if normalize_name(t) == norm_team:
            return True
    return False

@st.cache_data
def load_data():
    if not os.path.exists(DATA_PATH):
        st.error(f"❌ Cannot find data.json at: {DATA_PATH}")
        st.info(f"📁 Current directory: {os.getcwd()}")
        st.info(f"📄 Files in current dir: {os.listdir('.')}")
        if os.path.exists('web'):
            st.info(f"📄 Files in web/: {os.listdir('web')}")
        else:
            st.warning("⚠️ web/ folder does not exist!")
        return None, None
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return sorted(data.get("teams", [])), data.get("matches", [])

all_teams, matches_raw = load_data()

def safe_int(value, default=0):
    """Safely convert value to int, handling None and invalid values"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def clean_map_name_display(map_name):
    """Clean map name for display - remove control characters"""
    if not map_name or not isinstance(map_name, str):
        return "Unknown"
    # Remove tabs, newlines, and other control characters
    cleaned = re.sub(r'[\t\n\r\x00-\x1f\x7f-\x9f]', '', map_name)
    # If it's still too long or weird, truncate
    if len(cleaned) > 15:
        cleaned = cleaned[:15] + "..."
    return cleaned if cleaned else "Unknown"

def get_team_stats(team, matches):
    stats = {
        "maps": {}, 
        "series_played": 0, 
        "series_wins": 0, 
        "series_losses": 0,
        "total_map_wins": 0, 
        "total_map_losses": 0,
        "pistol_wins": 0, 
        "pistol_losses": 0,
        "atk_rounds": 0,
        "def_rounds": 0,
        "atk_rounds_lost": 0,
        "def_rounds_lost": 0
    }
    matches_played = []
    
    for m in matches:
        is_left = m.get("left") == team
        is_right = m.get("right") == team
        if not (is_left or is_right): continue
        
        matches_played.append(m)
        stats["series_played"] += 1
        winner = m.get("winner")
        if winner == team: 
            stats["series_wins"] += 1
        elif winner: 
            stats["series_losses"] += 1 
        
        for p in m.get("played", []):
            map_name = p.get("map")
            # Skip if map name is empty or invalid
            if not map_name or not isinstance(map_name, str) or len(map_name) == 0:
                continue
            
            # Validate map name doesn't contain weird characters
            if len(map_name) > 20 or '\t' in map_name or '\n' in map_name:
                continue
                
            if map_name not in stats["maps"]:
                stats["maps"][map_name] = {
                    "played": 0, "wins": 0, "losses": 0, 
                    "round_wins": 0, "round_losses": 0, 
                    "picks": 0, "bans": 0, 
                    "pistol_wins": 0, "pistol_losses": 0, "pistol_rounds": 0,
                    "atk_rounds_won": 0, "def_rounds_won": 0,
                    "atk_rounds_lost": 0, "def_rounds_lost": 0,
                    "agents": {}, "history": []
                }
            ms = stats["maps"][map_name]
            ms["played"] += 1
            
            # Use safe_int for all score values
            ls = safe_int(p.get("ls", 0))
            rs = safe_int(p.get("rs", 0))
            
            my_score = ls if is_left else rs
            opp_score = rs if is_left else ls
            
            ms["round_wins"] += my_score
            ms["round_losses"] += opp_score
            
            if my_score > opp_score: 
                ms["wins"] += 1
                stats["total_map_wins"] += 1
            else: 
                ms["losses"] += 1
                stats["total_map_losses"] += 1
            
            # Handle pistol data safely
            pistols = p.get("pistols", {})
            if pistols and isinstance(pistols, dict):
                p_left = safe_int(pistols.get("left", 0))
                p_right = safe_int(pistols.get("right", 0))
                my_pistols = p_left if is_left else p_right
                opp_pistols = p_right if is_left else p_left
                
                ms["pistol_wins"] += my_pistols
                ms["pistol_losses"] += opp_pistols
                ms["pistol_rounds"] += (my_pistols + opp_pistols)
                stats["pistol_wins"] += my_pistols
                stats["pistol_losses"] += opp_pistols
            
            # NEW: Handle attack/defense data
            sides = p.get("sides", {})
            if sides and isinstance(sides, dict):
                if is_left:
                    my_atk = safe_int(sides.get("left_atk", 0))
                    my_def = safe_int(sides.get("left_def", 0))
                    opp_atk = safe_int(sides.get("right_atk", 0))
                    opp_def = safe_int(sides.get("right_def", 0))
                else:
                    my_atk = safe_int(sides.get("right_atk", 0))
                    my_def = safe_int(sides.get("right_def", 0))
                    opp_atk = safe_int(sides.get("left_atk", 0))
                    opp_def = safe_int(sides.get("left_def", 0))
                
                ms["atk_rounds_won"] += my_atk
                ms["def_rounds_won"] += my_def
                ms["atk_rounds_lost"] += opp_atk
                ms["def_rounds_lost"] += opp_def
                
                stats["atk_rounds"] += my_atk
                stats["def_rounds"] += my_def
                stats["atk_rounds_lost"] += opp_atk
                stats["def_rounds_lost"] += opp_def
            
            # Track agents
            my_agents = p.get("left_agents" if is_left else "right_agents", [])
            for ag in my_agents:
                if ag:
                    ms["agents"][ag] = ms["agents"].get(ag, 0) + 1
            
            # Track match history
            opponent = m.get("right" if is_left else "left")
            ms["history"].append({
                "date": p.get("date") or m.get("date"),
                "opponent": opponent,
                "score": f"{my_score}-{opp_score}",
                "agents": my_agents
            })
        
        # Parse veto for picks/bans
        veto = m.get("veto", {})
        for event in veto.get("events", []):
            map_v = event.get("map")
            evt_type = event.get("type")
            evt_team = event.get("team")
            if map_v and map_v in stats["maps"] and evt_team == team:
                if evt_type == "pick": stats["maps"][map_v]["picks"] += 1
                elif evt_type == "ban": stats["maps"][map_v]["bans"] += 1
    
    return stats, matches_played

if not all_teams or not matches_raw:
    st.error("⚠️ No data found. Run scraper & build_data_json.py first!")
    st.stop()

st.title("⚔️ Valorant Team Analysis Dashboard")

# Create tabs - Home and Leaderboard first, then existing tabs

# Create tabs with Home and Leaderboard
tab_home, tab_leaderboard, tab_overview, tab_history, tab_h2h, tab_map, tab_comp = st.tabs([
    "🏠 Home", "🏆 Leaderboard", "📊 Overview", "📜 History", "⚔️ Head-to-Head", "🗺️ Map Deep Dive", "📈 Comparison"
])

# Sidebar filters
with st.sidebar:
    st.header("🔍 Filters")
    
    # Search box for quick team finding
    search_term = st.text_input("🔎 Search Teams", placeholder="Type team name...")
    
    region = st.selectbox("Region", ["All Regions"] + list(REGION_TEAMS.keys()))
    
    # Filter teams by region
    region_filtered_teams = [t for t in all_teams if is_team_in_region(t, region)]
    
    # Further filter by search term
    if search_term:
        region_filtered_teams = [t for t in region_filtered_teams if search_term.lower() in t.lower()]
    
    team1 = st.selectbox("Team 1", region_filtered_teams, key="t1")
    team2 = st.selectbox("Team 2", region_filtered_teams, key="t2", index=min(1, len(region_filtered_teams)-1))
    
    date_filter = st.checkbox("Filter by Date Range")
    if date_filter:
        min_date, max_date = None, None
        for m in matches_raw:
            d = m.get("date")
            if d:
                if min_date is None or d < min_date: min_date = d
                if max_date is None or d > max_date: max_date = d
        if min_date and max_date:
            start_date = st.date_input("Start Date", datetime.fromisoformat(min_date))
            end_date = st.date_input("End Date", datetime.fromisoformat(max_date))
        else:
            date_filter = False

# Apply filters
filtered_matches = []
for m in matches_raw:
    left_match = is_team_in_region(m.get("left"), region)
    right_match = is_team_in_region(m.get("right"), region)
    if not (left_match or right_match): continue
    
    if date_filter and min_date and max_date:
        md = m.get("date")
        if md and not (str(start_date) <= md <= str(end_date)): continue
    
    filtered_matches.append(m)

# Team-specific matches
team1_matches = [m for m in filtered_matches if m.get("left") == team1 or m.get("right") == team1]
team2_matches = [m for m in filtered_matches if m.get("left") == team2 or m.get("right") == team2]
h2h_matches = [m for m in filtered_matches if {m.get("left"), m.get("right")} == {team1, team2}]

# Compute stats
t1_stats, _ = get_team_stats(team1, team1_matches)
t2_stats, _ = get_team_stats(team2, team2_matches)

# Tabs

# Create tabs with new Home and Leaderboard
# ========== HOME TAB ==========
with tab_home:
    st.header("🏠 Tournament Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Teams", len(all_teams))
    with col2:
        st.metric("Total Matches", len(filtered_matches))
    with col3:
        total_maps = sum(len(m.get("maps", [])) for m in filtered_matches)
        st.metric("Maps Played", total_maps)
    with col4:
        regions_represented = len(set(r for r in REGION_TEAMS.keys() 
                                      if any(is_team_in_region(t, r) for t in all_teams)))
        st.metric("Regions", regions_represented)
    
    st.markdown("---")
    
    # Recent Matches
    st.subheader("📅 Recent Matches")
    recent = sorted(filtered_matches, key=lambda m: m.get("date", ""), reverse=True)[:10]
    
    for match in recent:
        left, right = match.get("left", ""), match.get("right", "")
        winner = match.get("winner", "")
        date = match.get("date", "N/A")
        
        # Calculate scores from played maps
        played_maps = match.get("played", [])
        left_wins = sum(1 for m in played_maps if m.get("ls", 0) > m.get("rs", 0))
        right_wins = sum(1 for m in played_maps if m.get("rs", 0) > m.get("ls", 0))
        
        st.markdown(f"""
        <div class='card'>
            <strong>{date}</strong><br/>
            <span class='{"win" if winner == left else "loss"}'>{left}</span> 
            <strong>{left_wins}</strong> - <strong>{right_wins}</strong> 
            <span class='{"win" if winner == right else "loss"}'>{right}</span>
        </div>
        """, unsafe_allow_html=True)

# ========== LEADERBOARD TAB ==========
with tab_leaderboard:
    st.header("🏆 Team Rankings")
    
    st.markdown("""
    Click column headers to sort.
    """)
    
    # Build leaderboard data
    leaderboard_data = []
    for team in all_teams:
        team_matches = [m for m in filtered_matches if m.get("left") == team or m.get("right") == team]
        
        # Skip teams with no matches
        if len(team_matches) == 0:
            continue
        
        # Match stats
        wins = sum(1 for m in team_matches if m.get("winner") == team)
        losses = len(team_matches) - wins
        win_rate = (wins / len(team_matches) * 100) if team_matches else 0
        
        # Map stats
        map_wins, map_losses = 0, 0
        pistol_wins, pistol_total = 0, 0
        round_wins, round_losses = 0, 0
        
        for match in team_matches:
            is_left = match.get("left") == team
            for mp in match.get("played", []):
                left_score = mp.get("ls", 0)
                right_score = mp.get("rs", 0)
                
                if is_left:
                    # Map wins/losses
                    if left_score > right_score:
                        map_wins += 1
                    else:
                        map_losses += 1
                    # Pistol rounds
                    pistol_wins += mp.get("pistols", {}).get("left", 0)
                    pistol_total += 2
                    # Individual rounds
                    round_wins += left_score
                    round_losses += right_score
                else:
                    # Map wins/losses
                    if right_score > left_score:
                        map_wins += 1
                    else:
                        map_losses += 1
                    # Pistol rounds
                    pistol_wins += mp.get("pistols", {}).get("right", 0)
                    pistol_total += 2
                    # Individual rounds
                    round_wins += right_score
                    round_losses += left_score
        
        map_win_rate = (map_wins / (map_wins + map_losses) * 100) if (map_wins + map_losses) > 0 else 0
        pistol_rate = (pistol_wins / pistol_total * 100) if pistol_total > 0 else 0
        round_rate = (round_wins / (round_wins + round_losses) * 100) if (round_wins + round_losses) > 0 else 0
        
        leaderboard_data.append({
            "Team": team,
            "Matches": len(team_matches),
            "W-L": f"{wins}-{losses}",
            "Win %": win_rate,
            "Map W-L": f"{map_wins}-{map_losses}",
            "Map Win %": map_win_rate,
            "Round W-L": f"{round_wins}-{round_losses}",
            "Round %": round_rate,
            "Pistol W-L": f"{pistol_wins}-{pistol_total - pistol_wins}",
            "Pistol %": pistol_rate
        })
    
    # Sort by win rate
    leaderboard_data.sort(key=lambda x: x["Win %"], reverse=True)
    
    # Add rank
    for i, row in enumerate(leaderboard_data, 1):
        row["Rank"] = i
    
    # Reorder columns
    df_leaderboard = pd.DataFrame(leaderboard_data)
    df_leaderboard = df_leaderboard[["Rank", "Team", "Matches", "W-L", "Win %", "Map W-L", "Map Win %", "Round W-L", "Round %", "Pistol W-L", "Pistol %"]]
    
    # Format percentages
    df_leaderboard["Win %"] = df_leaderboard["Win %"].apply(lambda x: f"{x:.1f}%")
    df_leaderboard["Map Win %"] = df_leaderboard["Map Win %"].apply(lambda x: f"{x:.1f}%")
    df_leaderboard["Round %"] = df_leaderboard["Round %"].apply(lambda x: f"{x:.1f}%")
    df_leaderboard["Pistol %"] = df_leaderboard["Pistol %"].apply(lambda x: f"{x:.1f}%")
    
    st.dataframe(df_leaderboard, use_container_width=True, hide_index=True, height=600)
    
    # Download button
    csv = df_leaderboard.to_csv(index=False)
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name="valorant_leaderboard.csv",
        mime="text/csv"
    )



    col_left, col_right = st.columns(2)
    
    def render_team_overview(col, team_name, stats, color):
        with col:
            st.markdown(f"<h2 style='color:{color}; text-align: center;'>{team_name}</h2>", unsafe_allow_html=True)
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Series Played", stats['series_played'])
                st.metric("Series Wins", stats['series_wins'])
            with c2:
                st.metric("Map Wins", stats['total_map_wins'])
                st.metric("Map Losses", stats['total_map_losses'])
            with c3:
                wr = (stats['series_wins']/(stats['series_played']) * 100) if stats['series_played'] else 0
                st.metric("Win Rate", f"{wr:.1f}%")
                
                # Only show pistol record if we have data
                pistol_total = stats['pistol_wins'] + stats['pistol_losses']
                if pistol_total > 0:
                    pwr = (stats['pistol_wins']/pistol_total * 100) if pistol_total else 0
                    st.metric("Pistol Win Rate", f"{pwr:.1f}%", f"{stats['pistol_wins']}-{stats['pistol_losses']}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Only show Attack/Defense if we have data
            atk_total = stats['atk_rounds'] + stats['atk_rounds_lost']
            def_total = stats['def_rounds'] + stats['def_rounds_lost']
            
            if atk_total > 0 or def_total > 0:
                st.markdown("#### ⚔️ Attack / Defense Performance")
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                atk_wr = (stats['atk_rounds']/atk_total * 100) if atk_total else 0
                def_wr = (stats['def_rounds']/def_total * 100) if def_total else 0
                
                ac1, ac2 = st.columns(2)
                with ac1:
                    st.markdown(f"<div class='stat-box'><b>Attack WR:</b> {atk_wr:.1f}% ({stats['atk_rounds']}-{stats['atk_rounds_lost']})</div>", unsafe_allow_html=True)
                with ac2:
                    st.markdown(f"<div class='stat-box'><b>Defense WR:</b> {def_wr:.1f}% ({stats['def_rounds']}-{stats['def_rounds_lost']})</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("#### 🗺️ Map Win Rates")
            map_wr_data = []
            for map_name, data in stats['maps'].items():
                wins, losses = data['wins'], data['losses']
                if wins + losses > 0:
                    wr = (wins / (wins + losses)) * 100
                    
                    # Only include pistol record if we have pistol data
                    p_wins = data.get('pistol_wins', 0)
                    p_losses = data.get('pistol_losses', 0)
                    
                    if p_wins + p_losses > 0:
                        record = f"{wins}-{losses} | P:{p_wins}-{p_losses}"
                    else:
                        record = f"{wins}-{losses}"
                    
                    map_wr_data.append({"Map": map_name, "Win Rate": wr, "Record": record})
            
            if map_wr_data:
                df = pd.DataFrame(map_wr_data).sort_values("Win Rate", ascending=False)
                fig = px.bar(df, x="Map", y="Win Rate", text="Record", color="Win Rate",
                            color_continuous_scale=[[0, '#e57373'], [0.5, '#FFB74D'], [1, '#81C784']])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                font_color='#e8ecf1', showlegend=False, yaxis=dict(range=[0, 110]))
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True, key=f"map_wr_{team_name}")
    
    render_team_overview(col_left, team1, t1_stats, '#4FC3F7')
    render_team_overview(col_right, team2, t2_stats, '#FFB74D')

with tab_history:
    st.title(f"Match History: {team1}")
    history_data = []
    for m in sorted(team1_matches, key=lambda x: x.get("date") or "0000", reverse=True)[:20]:
        is_left = m["left"] == team1
        opp = m["right"] if is_left else m["left"]
        l_wins, r_wins = 0, 0
        map_details = []
        for p in m.get("played", []):
            ls = safe_int(p.get("ls", 0))
            rs = safe_int(p.get("rs", 0))
            if ls > rs: l_wins += 1
            elif rs > ls: r_wins += 1
            ms, os = (ls, rs) if is_left else (rs, ls)
            color = "green" if ms > os else "#e57373"
            map_name = clean_map_name_display(p.get('map', 'Unknown'))
            
            # NEW: Include pistol info
            pistols = p.get("pistols", {})
            if pistols:
                p_left = safe_int(pistols.get("left", 0))
                p_right = safe_int(pistols.get("right", 0))
                my_p = p_left if is_left else p_right
                opp_p = p_right if is_left else p_left
                map_details.append(f"<span style='color:{color}'>{map_name} {ms}-{os} (P:{my_p}-{opp_p})</span>")
            else:
                map_details.append(f"<span style='color:{color}'>{map_name} {ms}-{os}</span>")
        
        winner = m.get("result", {}).get("winner")
        wl = "W" if winner == team1 else ("L" if winner else "-")
        wl_color = "win" if wl == "W" else "loss"
        history_data.append({
            "Date": m.get("date"), 
            "Opponent": opp, 
            "Result": f"<span class='{wl_color}'>{wl}</span> {l_wins if is_left else r_wins}-{r_wins if is_left else l_wins}", 
            "Maps": " | ".join(map_details)
        })
    if history_data: 
        st.write(pd.DataFrame(history_data).to_html(escape=False, index=False, classes="table"), unsafe_allow_html=True)
    else: 
        st.write("No matches found.")

with tab_h2h:
    st.title(f"Head-to-Head: {team1} vs {team2}")
    if not h2h_matches: 
        st.warning("No direct matches found between these two teams.")
    else:
        h2stats, _ = get_team_stats(team1, h2h_matches)
        t2hstats, _ = get_team_stats(team2, h2h_matches)
        col_l, col_mid, col_r = st.columns([1, 0.5, 1])
        with col_l:
            st.markdown(f"<div class='team-header-left'><h3>{team1}</h3></div>", unsafe_allow_html=True)
            st.metric("Series Wins", h2stats['series_wins'])
            st.metric("Map Wins", h2stats['total_map_wins'])
            
            # Only show pistol record if we have data
            p_total = h2stats['pistol_wins'] + h2stats['pistol_losses']
            if p_total > 0:
                p_wr = (h2stats['pistol_wins']/p_total*100) if p_total else 0
                st.metric("Pistol Wins", f"{h2stats['pistol_wins']}-{h2stats['pistol_losses']}", f"{p_wr:.0f}%")
        with col_mid: 
            st.markdown("<div style='text-align: center; padding-top: 50px;'><h1>VS</h1></div>", unsafe_allow_html=True)
        with col_r:
            st.markdown(f"<div class='team-header-right'><h3>{team2}</h3></div>", unsafe_allow_html=True)
            st.metric("Series Wins", t2hstats['series_wins'])
            st.metric("Map Wins", t2hstats['total_map_wins'])
            
            p_total2 = t2hstats['pistol_wins'] + t2hstats['pistol_losses']
            if p_total2 > 0:
                p_wr2 = (t2hstats['pistol_wins']/p_total2*100) if p_total2 else 0
                st.metric("Pistol Wins", f"{t2hstats['pistol_wins']}-{t2hstats['pistol_losses']}", f"{p_wr2:.0f}%")
        st.markdown("---")
        h2h_rows = []
        for m in sorted(h2h_matches, key=lambda x: x.get("date") or "0000", reverse=True):
            is_left = m["left"] == team1
            l_w, r_w, map_pills = 0, 0, []
            for p in m.get("played", []):
                ls = safe_int(p.get("ls", 0))
                rs = safe_int(p.get("rs", 0))
                if ls > rs: l_w += 1
                elif rs > ls: r_w += 1
                my_s, op_s = (ls, rs) if is_left else (rs, ls)
                c = "#81C784" if my_s > op_s else "#e57373"
                pist = p.get("pistols", {})
                if pist and isinstance(pist, dict):
                    myp = safe_int(pist.get("left" if is_left else "right", 0))
                    opp = safe_int(pist.get("right" if is_left else "left", 0))
                else:
                    myp, opp = 0, 0
                map_name = clean_map_name_display(p.get('map', 'Unknown'))
                
                map_pills.append(f"<span style='border:1px solid #444; padding:2px 6px; border-radius:4px; color:{c}'>{map_name} {my_s}-{op_s} (P:{myp}-{opp})</span>")
            h2h_rows.append({
                "Date": m.get("date"), 
                "Score": f"{l_w if is_left else r_w}-{r_w if is_left else l_w}", 
                "Maps": " ".join(map_pills)
            })
        st.write(pd.DataFrame(h2h_rows).to_html(escape=False, index=False), unsafe_allow_html=True)

with tab_map:
    all_maps = sorted(list(set(list(t1_stats["maps"].keys()) + list(t2_stats["maps"].keys()))))
    selected_map = st.selectbox("Select Map", all_maps)
    if selected_map:
        m1, m2 = t1_stats["maps"].get(selected_map, {}), t2_stats["maps"].get(selected_map, {})
        col1, col2 = st.columns(2)
        def render_map_card(col, team_name, data, color_border):
            with col:
                st.markdown(f"<div class='card' style='border-top: 4px solid {color_border}'><h3>{team_name} on {selected_map}</h3></div>", unsafe_allow_html=True)
                if not data: 
                    st.write("No data.")
                    return
                c_a, c_b = st.columns(2)
                wins, losses = data.get("wins", 0), data.get("losses", 0)
                wr = (wins/(wins+losses)*100) if (wins+losses) else 0
                pw, pr = data.get("pistol_wins", 0), data.get("pistol_rounds", 0)
                pwr = (pw/pr*100) if pr else 0
                with c_a: 
                    st.metric("Win Rate", f"{wr:.1f}%", f"{wins}W - {losses}L")
                    st.metric("Picks", data.get("picks", 0))
                with c_b: 
                    st.metric("Pistol WR", f"{pwr:.1f}%", f"{pw}/{pr}")
                    st.metric("Bans", data.get("bans", 0))
                
                # Only show attack/defense if we have data
                atk_w = data.get("atk_rounds_won", 0)
                atk_l = data.get("atk_rounds_lost", 0)
                def_w = data.get("def_rounds_won", 0)
                def_l = data.get("def_rounds_lost", 0)
                
                if (atk_w + atk_l + def_w + def_l) > 0:
                    st.markdown("#### Attack / Defense")
                    atk_wr = (atk_w/(atk_w+atk_l)*100) if (atk_w+atk_l) else 0
                    def_wr = (def_w/(def_w+def_l)*100) if (def_w+def_l) else 0
                    
                    st.markdown(f"<div class='stat-box'><b>Attack:</b> {atk_wr:.1f}% ({atk_w}-{atk_l})</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='stat-box'><b>Defense:</b> {def_wr:.1f}% ({def_w}-{def_l})</div>", unsafe_allow_html=True)
                
                st.markdown("#### Most Played Agents")
                agents = data.get("agents", {})
                if agents: 
                    st.markdown("".join([f"<span class='pill'>{k} ({v})</span>" for k,v in sorted(agents.items(), key=lambda x: x[1], reverse=True)[:5]]), unsafe_allow_html=True)
                st.markdown("#### Recent Comps")
                for h in data.get("history", [])[:5]: 
                    st.markdown(f"<div style='font-size:13px; color:#aaa;'>{h['date']} vs {h['opponent']} ({h['score']})</div><div>{', '.join(h['agents'])}</div>", unsafe_allow_html=True)
        render_map_card(col1, team1, m1, "#4FC3F7")
        render_map_card(col2, team2, m2, "#FFB74D")

with tab_comp:
    c_l, c_m, c_r = st.columns([1, 0.2, 1])
    def calc_wr(w, l): 
        return (w/(w+l)*100) if (w+l) > 0 else 0
    with c_l:
        st.markdown(f"<h2 style='color:#4FC3F7; text-align:center;'>{team1}</h2>", unsafe_allow_html=True)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.metric("Series Win Rate", f"{calc_wr(t1_stats['series_wins'], t1_stats['series_losses']):.1f}%", f"{t1_stats['series_wins']}-{t1_stats['series_losses']}")
        st.metric("Map Win Rate", f"{calc_wr(t1_stats['total_map_wins'], t1_stats['total_map_losses']):.1f}%", f"{t1_stats['total_map_wins']}-{t1_stats['total_map_losses']}")
        st.metric("Pistol Win Rate", f"{calc_wr(t1_stats['pistol_wins'], t1_stats['pistol_losses']):.1f}%", f"{t1_stats['pistol_wins']}-{t1_stats['pistol_losses']}")
        st.markdown("</div>", unsafe_allow_html=True)
    with c_m: 
        st.markdown("<br><br><h3 style='text-align:center; color:#666;'>VS</h3>", unsafe_allow_html=True)
    with c_r:
        st.markdown(f"<h2 style='color:#FFB74D; text-align:center;'>{team2}</h2>", unsafe_allow_html=True)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.metric("Series Win Rate", f"{calc_wr(t2_stats['series_wins'], t2_stats['series_losses']):.1f}%", f"{t2_stats['series_wins']}-{t2_stats['series_losses']}")
        st.metric("Map Win Rate", f"{calc_wr(t2_stats['total_map_wins'], t2_stats['total_map_losses']):.1f}%", f"{t2_stats['total_map_wins']}-{t2_stats['total_map_losses']}")
        st.metric("Pistol Win Rate", f"{calc_wr(t2_stats['pistol_wins'], t2_stats['pistol_losses']):.1f}%", f"{t2_stats['pistol_wins']}-{t2_stats['pistol_losses']}")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='legend-text'>Map Record (Wins-Losses) | Pistol Record</div>", unsafe_allow_html=True)
    map_comp_data = []
    for m in sorted(list(set(list(t1_stats["maps"].keys()) + list(t2_stats["maps"].keys())))):
        for t, d, color in [(team1, t1_stats["maps"].get(m, {}), '#4FC3F7'), (team2, t2_stats["maps"].get(m, {}), '#FFB74D')]:
            # Get pistol data
            p_wins = d.get('pistol_wins', 0)
            p_losses = d.get('pistol_losses', 0)
            
            # Only show pistols if there's data
            if p_wins + p_losses > 0:
                label = f"<b>{d.get('wins',0)}-{d.get('losses',0)}</b> (P:{p_wins}-{p_losses})"
            else:
                label = f"<b>{d.get('wins',0)}-{d.get('losses',0)}</b>"
            
            map_comp_data.append({
                "Map": m, 
                "Team": t, 
                "Win Rate": calc_wr(d.get("wins",0), d.get("losses",0)), 
                "Label": label
            })
    if map_comp_data:
        fig_comp = px.bar(
            pd.DataFrame(map_comp_data), 
            x="Map", 
            y="Win Rate", 
            color="Team", 
            barmode="group", 
            text="Label", 
            color_discrete_map={team1: '#4FC3F7', team2: '#FFB74D'}
        )
        fig_comp.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)', 
            font_color='#e8ecf1', 
            yaxis=dict(range=[0, 130])
        )
        fig_comp.update_traces(textposition='outside')
        st.plotly_chart(fig_comp, use_container_width=True)