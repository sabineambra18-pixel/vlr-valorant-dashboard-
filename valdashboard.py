import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import re
from datetime import datetime

# --- Configuration ---
st.set_page_config(page_title="VAL Dashboard", layout="wide", page_icon="⚔️")

# --- Clean CSS with mobile support ---
st.markdown("""
<style>
    /* Base */
    .stApp { background-color: #0a0e1a; }
    .stMarkdown, .stDataFrame { color: #e8ecf1; }
    div[data-testid="stMetricValue"] { font-size: 22px; color: #e8ecf1; }
    div[data-testid="stMetricLabel"] { color: #9fb3c8; font-size: 13px; }

    /* Cards */
    .card {
        background: linear-gradient(135deg, #121a29 0%, #0f1520 100%);
        border: 1px solid #1e2a3a; border-radius: 10px;
        padding: 16px; margin-bottom: 12px;
    }
    .card h3 {
        margin-top: 0; color: #cbd5e1; font-size: 16px;
        border-bottom: 1px solid #1e2a3a; padding-bottom: 8px; margin-bottom: 12px;
    }

    /* Match card */
    .match-card {
        background: #121a29; border: 1px solid #1e2a3a; border-radius: 8px;
        padding: 12px 16px; margin-bottom: 8px;
        display: flex; align-items: center; justify-content: space-between;
        flex-wrap: wrap; gap: 8px;
    }
    .match-card .date { color: #64748b; font-size: 12px; min-width: 80px; }
    .match-card .teams { flex: 1; text-align: center; font-size: 15px; }
    .match-card .maps-row { font-size: 12px; width: 100%; text-align: center; margin-top: 4px; }

    /* Pills */
    .pill {
        display: inline-block; background: #1b2332;
        padding: 3px 8px; border-radius: 999px;
        margin: 2px; font-size: 11px; border: 1px solid #1e2a3a; color: #e8ecf1;
    }
    .map-pill {
        display: inline-block; border: 1px solid #333;
        padding: 2px 8px; border-radius: 6px; margin: 1px 2px; font-size: 12px;
    }

    /* Win/Loss */
    .win { color: #4ade80 !important; font-weight: 700; font-size: 1.05em; }
    .loss { color: #64748b !important; font-weight: 400; }

    /* Team headers */
    .team-header-left { border-left: 3px solid #4FC3F7; padding-left: 12px; }
    .team-header-right { border-left: 3px solid #FFB74D; padding-left: 12px; }

    /* Stat box */
    .stat-box {
        background: #1b2332; padding: 8px 12px; border-radius: 6px;
        margin: 3px 0; border: 1px solid #1e2a3a; font-size: 14px;
    }
    .legend-text {
        background-color: #121a29; padding: 10px; border-radius: 8px;
        border: 1px solid #1e2a3a; text-align: center; margin-bottom: 10px;
        font-family: monospace;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #0d1117; }

    /* Compact tabs - visible on dark bg */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #1e2a3a; }
    .stTabs [data-baseweb="tab"] { padding: 8px 14px; font-size: 13px; color: #9fb3c8 !important; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { color: #e8ecf1 !important; border-bottom: 2px solid #4FC3F7; }
    .stTabs [data-baseweb="tab"]:hover { color: #e8ecf1 !important; }

    /* Mobile */
    @media (max-width: 768px) {
        .match-card { flex-direction: column; text-align: center; }
        div[data-testid="stMetricValue"] { font-size: 18px; }
        .stTabs [data-baseweb="tab"] { padding: 6px 8px; font-size: 11px; }
        .stat-box { font-size: 12px; }
    }

    /* Cleaner */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
DATA_PATH = "./web/data.json"
if not os.path.exists(DATA_PATH):
    DATA_PATH = "web/data.json"
if not os.path.exists(DATA_PATH):
    DATA_PATH = "../web/data.json"
if not os.path.exists(DATA_PATH):
    st.error("❌ Cannot find data.json!")
    st.stop()

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
    for t in REGION_TEAMS.get(region, []):
        if normalize_name(t) == normalize_name(team_name): return True
    return False

@st.cache_data
def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return sorted(data.get("teams", [])), data.get("matches", [])

all_teams, matches_raw = load_data()

def safe_int(v, d=0):
    if v is None: return d
    try: return int(v)
    except: return d

def clean_map_name(mn):
    if not mn or not isinstance(mn, str): return "Unknown"
    c = re.sub(r'[\t\n\r\x00-\x1f\x7f-\x9f]', '', mn)
    return c[:15] if len(c) > 15 else (c or "Unknown")

def calc_wr(w, l):
    return (w / (w + l) * 100) if (w + l) > 0 else 0

# --- Core Stats Engine ---
def get_team_stats(team, matches):
    stats = {
        "maps": {},
        "series_played": 0, "series_wins": 0, "series_losses": 0,
        "total_map_wins": 0, "total_map_losses": 0,
        "pistol_wins": 0, "pistol_losses": 0,
        "atk_rounds": 0, "def_rounds": 0,
        "atk_rounds_lost": 0, "def_rounds_lost": 0,
        "ban_1st": {}, "ban_2nd": {},
    }
    matches_played = []

    for m in matches:
        is_left = m.get("left") == team
        is_right = m.get("right") == team
        if not (is_left or is_right): continue

        matches_played.append(m)
        stats["series_played"] += 1
        winner = m.get("winner")
        if winner == team: stats["series_wins"] += 1
        elif winner: stats["series_losses"] += 1

        for p in m.get("played", []):
            map_name = p.get("map")
            if not map_name or not isinstance(map_name, str) or len(map_name) > 20: continue
            if '\t' in map_name or '\n' in map_name: continue

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

            ls = safe_int(p.get("ls", 0)); rs = safe_int(p.get("rs", 0))
            my_score = ls if is_left else rs
            opp_score = rs if is_left else ls
            ms["round_wins"] += my_score; ms["round_losses"] += opp_score

            if my_score > opp_score:
                ms["wins"] += 1; stats["total_map_wins"] += 1
            else:
                ms["losses"] += 1; stats["total_map_losses"] += 1

            pistols = p.get("pistols", {})
            if pistols and isinstance(pistols, dict):
                my_p = safe_int(pistols.get("left" if is_left else "right", 0))
                opp_p = safe_int(pistols.get("right" if is_left else "left", 0))
                ms["pistol_wins"] += my_p; ms["pistol_losses"] += opp_p
                ms["pistol_rounds"] += (my_p + opp_p)
                stats["pistol_wins"] += my_p; stats["pistol_losses"] += opp_p

            sides = p.get("sides", {})
            if sides and isinstance(sides, dict):
                if is_left:
                    my_atk, my_def = safe_int(sides.get("left_atk", 0)), safe_int(sides.get("left_def", 0))
                    opp_atk, opp_def = safe_int(sides.get("right_atk", 0)), safe_int(sides.get("right_def", 0))
                else:
                    my_atk, my_def = safe_int(sides.get("right_atk", 0)), safe_int(sides.get("right_def", 0))
                    opp_atk, opp_def = safe_int(sides.get("left_atk", 0)), safe_int(sides.get("left_def", 0))
                ms["atk_rounds_won"] += my_atk; ms["def_rounds_won"] += my_def
                ms["atk_rounds_lost"] += opp_atk; ms["def_rounds_lost"] += opp_def
                stats["atk_rounds"] += my_atk; stats["def_rounds"] += my_def
                stats["atk_rounds_lost"] += opp_atk; stats["def_rounds_lost"] += opp_def

            my_agents = p.get("left_agents" if is_left else "right_agents", [])
            for ag in my_agents:
                if ag: ms["agents"][ag] = ms["agents"].get(ag, 0) + 1

            opponent = m.get("right" if is_left else "left")
            ms["history"].append({
                "date": p.get("date") or m.get("date"),
                "opponent": opponent,
                "score": f"{my_score}-{opp_score}",
                "agents": my_agents
            })

        # Veto: picks, bans, 1st/2nd ban tracking
        veto = m.get("veto", {})
        team_ban_count = 0
        for event in veto.get("events", []):
            map_v = event.get("map"); evt_type = event.get("type"); evt_team = event.get("team")
            if map_v and map_v in stats["maps"] and evt_team == team:
                if evt_type == "pick": stats["maps"][map_v]["picks"] += 1
                elif evt_type == "ban": stats["maps"][map_v]["bans"] += 1
            if evt_type == "ban" and evt_team == team and map_v:
                team_ban_count += 1
                if team_ban_count == 1:
                    stats["ban_1st"][map_v] = stats["ban_1st"].get(map_v, 0) + 1
                elif team_ban_count == 2:
                    stats["ban_2nd"][map_v] = stats["ban_2nd"].get(map_v, 0) + 1

    return stats, matches_played

# --- Guard ---
if not all_teams or not matches_raw:
    st.error("⚠️ No data found. Run scraper & build_data_json.py first!")
    st.stop()

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.markdown("## ⚔️ VAL Dashboard")
    st.markdown("---")

    region = st.selectbox("🌍 Region", ["All Regions"] + list(REGION_TEAMS.keys()))
    region_filtered_teams = [t for t in all_teams if is_team_in_region(t, region)]

    # Search only filters the team DROPDOWNS, not the match feed
    search_term = st.text_input("🔎 Filter team list", placeholder="Type to narrow dropdowns...")
    dropdown_teams = region_filtered_teams
    if search_term:
        dropdown_teams = [t for t in region_filtered_teams if search_term.lower() in t.lower()]
    # Ensure we always have at least the full list as fallback
    if not dropdown_teams:
        dropdown_teams = region_filtered_teams
        st.caption(f"No match for '{search_term}' — showing all")

    st.markdown("---")

    team1 = st.selectbox("Team 1", dropdown_teams, key="t1")
    team2 = st.selectbox("Team 2", dropdown_teams, key="t2",
                         index=min(1, len(dropdown_teams) - 1))

    st.markdown("---")

    date_filter = st.checkbox("📅 Filter by date range")
    min_date = max_date = None
    if date_filter:
        for m in matches_raw:
            d = m.get("date")
            if d:
                if min_date is None or d < min_date: min_date = d
                if max_date is None or d > max_date: max_date = d
        if min_date and max_date:
            start_date = st.date_input("From", datetime.fromisoformat(min_date))
            end_date = st.date_input("To", datetime.fromisoformat(max_date))
        else:
            date_filter = False

    st.markdown("---")
    st.caption(f"{len(all_teams)} teams · {len(matches_raw)} matches")

# =============================================
# APPLY FILTERS
# =============================================
filtered_matches = []
for m in matches_raw:
    if not (is_team_in_region(m.get("left"), region) or is_team_in_region(m.get("right"), region)):
        continue
    if date_filter and min_date and max_date:
        md = m.get("date")
        if md and not (str(start_date) <= md <= str(end_date)): continue
    filtered_matches.append(m)

team1_matches = [m for m in filtered_matches if m.get("left") == team1 or m.get("right") == team1]
team2_matches = [m for m in filtered_matches if m.get("left") == team2 or m.get("right") == team2]
h2h_matches = [m for m in filtered_matches if {m.get("left"), m.get("right")} == {team1, team2}]

t1_stats, _ = get_team_stats(team1, team1_matches)
t2_stats, _ = get_team_stats(team2, team2_matches)

# =============================================
# ALL TABS — same as original, cleaned up
# =============================================
tab_home, tab_leaderboard, tab_overview, tab_history, tab_h2h, tab_map, tab_comp = st.tabs([
    "🏠 Home", "🏆 Leaderboard", "📊 Overview", "📜 History", "⚔️ Head-to-Head", "🗺️ Map Deep Dive", "📈 Comparison"
])

# ========== HOME ==========
with tab_home:
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Teams", len(all_teams))
    with c2: st.metric("Matches", len(filtered_matches))
    with c3:
        st.metric("Maps Played", sum(len(m.get("played", [])) for m in filtered_matches))

    st.markdown("---")
    st.subheader("Recent Matches")

    recent = sorted(filtered_matches, key=lambda x: x.get("date", ""), reverse=True)[:15]
    for match in recent:
        left, right = match.get("left", ""), match.get("right", "")
        winner = match.get("winner", "")
        date = match.get("date", "")
        played = match.get("played", [])
        lw = sum(1 for p in played if safe_int(p.get("ls")) > safe_int(p.get("rs")))
        rw = sum(1 for p in played if safe_int(p.get("rs")) > safe_int(p.get("ls")))

        # Map pills - always from WINNER's perspective
        pills = []
        winner_is_left = (winner == left)
        for p in played:
            mn = clean_map_name(p.get("map", ""))
            ls_v, rs_v = safe_int(p.get("ls")), safe_int(p.get("rs"))
            # Show winner's score first
            if winner:
                w_score = ls_v if winner_is_left else rs_v
                l_score = rs_v if winner_is_left else ls_v
                if w_score > l_score:
                    clr = "#4ade80"  # winner won this map
                else:
                    clr = "#f87171"  # winner lost this map
                pills.append(f"<span class='map-pill' style='color:{clr}'>{mn} {w_score}-{l_score}</span>")
            else:
                pills.append(f"<span class='map-pill' style='color:#94a3b8'>{mn} {ls_v}-{rs_v}</span>")

        # Winner in green+bold, loser in muted gray — winner listed first
        if winner == left:
            team_html = f"<span class='win'>{left}</span> <b>{lw}</b> - <b>{rw}</b> <span class='loss'>{right}</span>"
        elif winner == right:
            team_html = f"<span class='win'>{right}</span> <b>{rw}</b> - <b>{lw}</b> <span class='loss'>{left}</span>"
        else:
            team_html = f"<span>{left}</span> <b>{lw}</b> - <b>{rw}</b> <span>{right}</span>"

        st.markdown(f"""<div class='match-card'>
            <span class='date'>{date}</span>
            <span class='teams'>{team_html}</span>
            <div class='maps-row'>{"".join(pills)}</div>
        </div>""", unsafe_allow_html=True)

# ========== LEADERBOARD ==========
with tab_leaderboard:
    st.subheader("Team Rankings")
    lb_data = []
    for team in all_teams:
        tm = [m for m in filtered_matches if m.get("left") == team or m.get("right") == team]
        if not tm: continue
        wins = sum(1 for m in tm if m.get("winner") == team)
        losses = len(tm) - wins
        map_w = map_l = pw = pt = rw = rl = 0
        for match in tm:
            is_left = match.get("left") == team
            for mp in match.get("played", []):
                ls_v, rs_v = safe_int(mp.get("ls", 0)), safe_int(mp.get("rs", 0))
                my_s = ls_v if is_left else rs_v
                op_s = rs_v if is_left else ls_v
                if my_s > op_s: map_w += 1
                else: map_l += 1
                pw += safe_int(mp.get("pistols", {}).get("left" if is_left else "right", 0))
                pt += 2; rw += my_s; rl += op_s
        lb_data.append({
            "Team": team, "Matches": len(tm), "W-L": f"{wins}-{losses}",
            "Win %": calc_wr(wins, losses),
            "Map W-L": f"{map_w}-{map_l}", "Map %": calc_wr(map_w, map_l),
            "Round W-L": f"{rw}-{rl}", "Round %": calc_wr(rw, rl),
            "Pistol W-L": f"{pw}-{pt - pw}", "Pistol %": calc_wr(pw, pt - pw),
        })
    lb_data.sort(key=lambda x: x["Win %"], reverse=True)
    for i, row in enumerate(lb_data, 1): row["#"] = i
    df_lb = pd.DataFrame(lb_data)
    df_lb = df_lb[["#", "Team", "Matches", "W-L", "Win %", "Map W-L", "Map %", "Round W-L", "Round %", "Pistol W-L", "Pistol %"]]
    st.dataframe(df_lb, use_container_width=True, hide_index=True, height=600,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Win %": st.column_config.NumberColumn("Win %", format="%.1f%%"),
            "Map %": st.column_config.NumberColumn("Map %", format="%.1f%%"),
            "Round %": st.column_config.NumberColumn("Round %", format="%.1f%%"),
            "Pistol %": st.column_config.NumberColumn("Pistol %", format="%.1f%%"),
        })
    st.download_button("📥 Download CSV", df_lb.to_csv(index=False), "valorant_rankings.csv", "text/csv")

# ========== OVERVIEW ==========
with tab_overview:
    col_left, col_right = st.columns(2)

    def render_team_overview(col, team_name, stats, color):
        with col:
            st.markdown(f"<h2 style='color:{color}; text-align:center;'>{team_name}</h2>", unsafe_allow_html=True)

            # Key stats
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Series", f"{stats['series_wins']}-{stats['series_losses']}")
            with c2:
                st.metric("Maps", f"{stats['total_map_wins']}-{stats['total_map_losses']}")
            with c3:
                wr = calc_wr(stats['series_wins'], stats['series_losses'])
                st.metric("Win Rate", f"{wr:.1f}%")
            st.markdown("</div>", unsafe_allow_html=True)

            # Pistol + ATK/DEF in one compact row
            pt_total = stats['pistol_wins'] + stats['pistol_losses']
            atk_t = stats['atk_rounds'] + stats['atk_rounds_lost']
            def_t = stats['def_rounds'] + stats['def_rounds_lost']

            if pt_total > 0 or atk_t > 0:
                with st.expander("Pistol & Side Stats", expanded=False):
                    if pt_total > 0:
                        pwr = calc_wr(stats['pistol_wins'], stats['pistol_losses'])
                        st.markdown(f"<div class='stat-box'><b>Pistol:</b> {pwr:.1f}% ({stats['pistol_wins']}-{stats['pistol_losses']})</div>", unsafe_allow_html=True)
                    if atk_t > 0:
                        atk_wr = calc_wr(stats['atk_rounds'], stats['atk_rounds_lost'])
                        def_wr = calc_wr(stats['def_rounds'], stats['def_rounds_lost'])
                        st.markdown(f"<div class='stat-box'><b>Attack:</b> {atk_wr:.1f}% ({stats['atk_rounds']}-{stats['atk_rounds_lost']})</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='stat-box'><b>Defense:</b> {def_wr:.1f}% ({stats['def_rounds']}-{stats['def_rounds_lost']})</div>", unsafe_allow_html=True)

            # Map Win Rates
            map_wr_data = []
            for mn, d in stats['maps'].items():
                w, l = d['wins'], d['losses']
                if w + l > 0:
                    pw_v, pl_v = d.get('pistol_wins', 0), d.get('pistol_losses', 0)
                    rec = f"{w}-{l}"
                    if pw_v + pl_v > 0: rec += f" | P:{pw_v}-{pl_v}"
                    map_wr_data.append({"Map": mn, "Win Rate": calc_wr(w, l), "Record": rec})
            if map_wr_data:
                df = pd.DataFrame(map_wr_data).sort_values("Win Rate", ascending=False)
                fig = px.bar(df, x="Map", y="Win Rate", text="Record", color="Win Rate",
                             color_continuous_scale=[[0, '#f87171'], [0.5, '#FFB74D'], [1, '#4ade80']])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                  font_color='#e8ecf1', showlegend=False, yaxis=dict(range=[0, 115]),
                                  margin=dict(t=10, b=10), height=300)
                fig.update_traces(textposition='outside', textfont_size=11)
                st.plotly_chart(fig, use_container_width=True, key=f"mwr_{team_name}")

            # Ban Tendencies
            ban_1st = stats.get("ban_1st", {})
            ban_2nd = stats.get("ban_2nd", {})
            if ban_1st or ban_2nd:
                with st.expander("🚫 Ban Tendencies", expanded=True):
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if ban_1st:
                            total_1 = sum(ban_1st.values())
                            b1 = [{"Map": m, "Count": c, "Rate": f"{c/total_1*100:.0f}%"}
                                  for m, c in sorted(ban_1st.items(), key=lambda x: x[1], reverse=True)]
                            fig_b1 = px.bar(pd.DataFrame(b1), x="Map", y="Count", text="Rate",
                                            title=f"1st Ban ({total_1} series)")
                            fig_b1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                                 font_color='#e8ecf1', showlegend=False,
                                                 yaxis=dict(range=[0, max(ban_1st.values()) * 1.4]),
                                                 margin=dict(t=30, b=10), height=260)
                            fig_b1.update_traces(marker_color='#f87171', textposition='outside')
                            st.plotly_chart(fig_b1, use_container_width=True, key=f"b1_{team_name}")
                    with bc2:
                        if ban_2nd:
                            total_2 = sum(ban_2nd.values())
                            b2 = [{"Map": m, "Count": c, "Rate": f"{c/total_2*100:.0f}%"}
                                  for m, c in sorted(ban_2nd.items(), key=lambda x: x[1], reverse=True)]
                            fig_b2 = px.bar(pd.DataFrame(b2), x="Map", y="Count", text="Rate",
                                            title=f"2nd Ban ({total_2} series)")
                            fig_b2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                                 font_color='#e8ecf1', showlegend=False,
                                                 yaxis=dict(range=[0, max(ban_2nd.values()) * 1.4]),
                                                 margin=dict(t=30, b=10), height=260)
                            fig_b2.update_traces(marker_color='#FFB74D', textposition='outside')
                            st.plotly_chart(fig_b2, use_container_width=True, key=f"b2_{team_name}")

    render_team_overview(col_left, team1, t1_stats, '#4FC3F7')
    render_team_overview(col_right, team2, t2_stats, '#FFB74D')

# ========== HISTORY ==========
with tab_history:
    st.subheader(f"Match History: {team1}")
    history_data = []
    for m in sorted(team1_matches, key=lambda x: x.get("date") or "0000", reverse=True)[:20]:
        is_left = m["left"] == team1
        opp = m["right"] if is_left else m["left"]
        lw = rw = 0; map_details = []
        for p in m.get("played", []):
            ls_v, rs_v = safe_int(p.get("ls", 0)), safe_int(p.get("rs", 0))
            if ls_v > rs_v: lw += 1
            elif rs_v > ls_v: rw += 1
            my_s = ls_v if is_left else rs_v
            op_s = rs_v if is_left else ls_v
            clr = "#4ade80" if my_s > op_s else "#f87171"
            mn = clean_map_name(p.get('map', '?'))
            pist = p.get("pistols", {})
            if pist and isinstance(pist, dict):
                mp_v = safe_int(pist.get("left" if is_left else "right", 0))
                op_v = safe_int(pist.get("right" if is_left else "left", 0))
                map_details.append(f"<span style='color:{clr}'>{mn} {my_s}-{op_s} (P:{mp_v}-{op_v})</span>")
            else:
                map_details.append(f"<span style='color:{clr}'>{mn} {my_s}-{op_s}</span>")
        winner = m.get("winner")
        wl = "W" if winner == team1 else ("L" if winner else "-")
        wl_cls = "win" if wl == "W" else "loss"
        my_w = lw if is_left else rw; my_l = rw if is_left else lw
        history_data.append({
            "Date": m.get("date"), "Opponent": opp,
            "Result": f"<span class='{wl_cls}'>{wl}</span> {my_w}-{my_l}",
            "Maps": " | ".join(map_details)
        })
    if history_data:
        st.write(pd.DataFrame(history_data).to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No matches found.")

# ========== HEAD-TO-HEAD ==========
with tab_h2h:
    st.subheader(f"{team1} vs {team2}")
    if not h2h_matches:
        st.info("No direct matches found between these two teams.")
    else:
        h2stats, _ = get_team_stats(team1, h2h_matches)
        t2hstats, _ = get_team_stats(team2, h2h_matches)
        cl, cm, cr = st.columns([1, 0.4, 1])
        with cl:
            st.markdown(f"<div class='team-header-left'><h3>{team1}</h3></div>", unsafe_allow_html=True)
            st.metric("Series Wins", h2stats['series_wins'])
            st.metric("Map Wins", h2stats['total_map_wins'])
            pt1 = h2stats['pistol_wins'] + h2stats['pistol_losses']
            if pt1 > 0:
                st.metric("Pistol Wins", f"{h2stats['pistol_wins']}-{h2stats['pistol_losses']}",
                           f"{calc_wr(h2stats['pistol_wins'], h2stats['pistol_losses']):.0f}%")
        with cm:
            st.markdown("<div style='text-align:center; padding-top:40px'><h2 style='color:#475569'>VS</h2></div>", unsafe_allow_html=True)
        with cr:
            st.markdown(f"<div class='team-header-right'><h3>{team2}</h3></div>", unsafe_allow_html=True)
            st.metric("Series Wins", t2hstats['series_wins'])
            st.metric("Map Wins", t2hstats['total_map_wins'])
            pt2 = t2hstats['pistol_wins'] + t2hstats['pistol_losses']
            if pt2 > 0:
                st.metric("Pistol Wins", f"{t2hstats['pistol_wins']}-{t2hstats['pistol_losses']}",
                           f"{calc_wr(t2hstats['pistol_wins'], t2hstats['pistol_losses']):.0f}%")
        st.markdown("---")
        h2h_rows = []
        for m in sorted(h2h_matches, key=lambda x: x.get("date") or "0000", reverse=True):
            is_left = m["left"] == team1
            lw = rw = 0; pills = []
            for p in m.get("played", []):
                ls_v, rs_v = safe_int(p.get("ls", 0)), safe_int(p.get("rs", 0))
                if ls_v > rs_v: lw += 1
                elif rs_v > ls_v: rw += 1
                my_s = ls_v if is_left else rs_v
                op_s = rs_v if is_left else ls_v
                clr = "#4ade80" if my_s > op_s else "#f87171"
                mn = clean_map_name(p.get('map', '?'))
                pist = p.get("pistols", {})
                if pist and isinstance(pist, dict):
                    myp = safe_int(pist.get("left" if is_left else "right", 0))
                    opp = safe_int(pist.get("right" if is_left else "left", 0))
                    pills.append(f"<span class='map-pill' style='color:{clr}'>{mn} {my_s}-{op_s} (P:{myp}-{opp})</span>")
                else:
                    pills.append(f"<span class='map-pill' style='color:{clr}'>{mn} {my_s}-{op_s}</span>")
            my_w = lw if is_left else rw; my_l = rw if is_left else lw
            h2h_rows.append({"Date": m.get("date"), "Score": f"{my_w}-{my_l}", "Maps": " ".join(pills)})
        st.write(pd.DataFrame(h2h_rows).to_html(escape=False, index=False), unsafe_allow_html=True)

# ========== MAP DEEP DIVE ==========
with tab_map:
    all_maps = sorted(set(list(t1_stats["maps"].keys()) + list(t2_stats["maps"].keys())))
    selected_map = st.selectbox("Select Map", all_maps)
    if selected_map:
        col1, col2 = st.columns(2)

        def render_map_card(col, team_name, data, color_border):
            with col:
                st.markdown(f"<div class='card' style='border-top: 3px solid {color_border}'><h3>{team_name} on {selected_map}</h3></div>", unsafe_allow_html=True)
                if not data:
                    st.info("No data."); return
                w, l = data.get("wins", 0), data.get("losses", 0)
                wr = calc_wr(w, l)
                pw_v, pr = data.get("pistol_wins", 0), data.get("pistol_rounds", 0)
                pwr = (pw_v / pr * 100) if pr else 0
                ca, cb = st.columns(2)
                with ca:
                    st.metric("Win Rate", f"{wr:.1f}%", f"{w}W - {l}L")
                    st.metric("Picks", data.get("picks", 0))
                with cb:
                    st.metric("Pistol WR", f"{pwr:.1f}%", f"{pw_v}/{pr}" if pr else "N/A")
                    st.metric("Bans", data.get("bans", 0))

                atk_w, atk_l = data.get("atk_rounds_won", 0), data.get("atk_rounds_lost", 0)
                def_w, def_l = data.get("def_rounds_won", 0), data.get("def_rounds_lost", 0)
                if (atk_w + atk_l + def_w + def_l) > 0:
                    st.markdown(f"<div class='stat-box'><b>Attack:</b> {calc_wr(atk_w, atk_l):.1f}% ({atk_w}-{atk_l})</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='stat-box'><b>Defense:</b> {calc_wr(def_w, def_l):.1f}% ({def_w}-{def_l})</div>", unsafe_allow_html=True)

                agents = data.get("agents", {})
                if agents:
                    st.markdown("**Top Agents**")
                    st.markdown("".join([f"<span class='pill'>{k} ({v})</span>"
                                         for k, v in sorted(agents.items(), key=lambda x: x[1], reverse=True)[:5]]),
                                unsafe_allow_html=True)
                history = data.get("history", [])
                if history:
                    with st.expander("Recent Comps", expanded=False):
                        for h in history[:5]:
                            st.markdown(f"<span style='font-size:12px; color:#64748b'>{h['date']} vs {h['opponent']} ({h['score']})</span><br>"
                                        f"<span style='font-size:12px'>{', '.join(h['agents'])}</span>", unsafe_allow_html=True)

        render_map_card(col1, team1, t1_stats["maps"].get(selected_map, {}), "#4FC3F7")
        render_map_card(col2, team2, t2_stats["maps"].get(selected_map, {}), "#FFB74D")

# ========== COMPARISON ==========
with tab_comp:
    cl, cm, cr = st.columns([1, 0.2, 1])
    with cl:
        st.markdown(f"<h2 style='color:#4FC3F7; text-align:center;'>{team1}</h2>", unsafe_allow_html=True)
        st.metric("Series Win Rate", f"{calc_wr(t1_stats['series_wins'], t1_stats['series_losses']):.1f}%",
                  f"{t1_stats['series_wins']}-{t1_stats['series_losses']}")
        st.metric("Map Win Rate", f"{calc_wr(t1_stats['total_map_wins'], t1_stats['total_map_losses']):.1f}%",
                  f"{t1_stats['total_map_wins']}-{t1_stats['total_map_losses']}")
        st.metric("Pistol Win Rate", f"{calc_wr(t1_stats['pistol_wins'], t1_stats['pistol_losses']):.1f}%",
                  f"{t1_stats['pistol_wins']}-{t1_stats['pistol_losses']}")
    with cm:
        st.markdown("<br><br><h3 style='text-align:center; color:#475569;'>VS</h3>", unsafe_allow_html=True)
    with cr:
        st.markdown(f"<h2 style='color:#FFB74D; text-align:center;'>{team2}</h2>", unsafe_allow_html=True)
        st.metric("Series Win Rate", f"{calc_wr(t2_stats['series_wins'], t2_stats['series_losses']):.1f}%",
                  f"{t2_stats['series_wins']}-{t2_stats['series_losses']}")
        st.metric("Map Win Rate", f"{calc_wr(t2_stats['total_map_wins'], t2_stats['total_map_losses']):.1f}%",
                  f"{t2_stats['total_map_wins']}-{t2_stats['total_map_losses']}")
        st.metric("Pistol Win Rate", f"{calc_wr(t2_stats['pistol_wins'], t2_stats['pistol_losses']):.1f}%",
                  f"{t2_stats['pistol_wins']}-{t2_stats['pistol_losses']}")

    st.markdown("<div class='legend-text'>Map Record (W-L) | Pistol Record</div>", unsafe_allow_html=True)
    comp_data = []
    for mn in sorted(set(list(t1_stats["maps"].keys()) + list(t2_stats["maps"].keys()))):
        for t, d in [(team1, t1_stats["maps"].get(mn, {})), (team2, t2_stats["maps"].get(mn, {}))]:
            pw_v, pl_v = d.get('pistol_wins', 0), d.get('pistol_losses', 0)
            label = f"<b>{d.get('wins',0)}-{d.get('losses',0)}</b>"
            if pw_v + pl_v > 0: label += f" (P:{pw_v}-{pl_v})"
            comp_data.append({"Map": mn, "Team": t, "Win Rate": calc_wr(d.get("wins", 0), d.get("losses", 0)), "Label": label})
    if comp_data:
        fig = px.bar(pd.DataFrame(comp_data), x="Map", y="Win Rate", color="Team", barmode="group", text="Label",
                     color_discrete_map={team1: '#4FC3F7', team2: '#FFB74D'})
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#e8ecf1', yaxis=dict(range=[0, 130]),
                          margin=dict(t=10, b=10), height=400)
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)