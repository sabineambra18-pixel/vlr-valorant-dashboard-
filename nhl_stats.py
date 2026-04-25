import requests
from bs4 import BeautifulSoup
import pandas as pd
from flask import Flask, render_template_string, request

class NHLStatsScraper:
    def __init__(self):
        self.team_base_url = "https://www.naturalstattrick.com/teamtable.php"
        self.player_base_url = "https://www.naturalstattrick.com/playerteams.php"
        
        self.team_base_params = {
            'fromseason': '20252026',
            'thruseason': '20252026',
            'stype': '2',
            'score': 'all',
            'rate': 'y',
            'team': 'all',
            'loc': 'B',
            'gpf': '410',
            'fd': '',
            'td': ''
        }
        
        self.player_base_params = {
            'fromseason': '20252026',
            'thruseason': '20252026',
            'stype': '2',
            'score': 'all',
            'stdoi': 'std',
            'team': 'ALL',
            'pos': 'S',
            'loc': 'B',
            'toi': '0',
            'gpfilt': 'none',
            'fd': '',
            'td': '',
            'tgp': '410',
            'lines': 'single',
            'draftteam': 'ALL'
        }
        
        # Team stats we want
        self.team_desired_stats = [
            'Team', 'GP', 'TOI', 'TOI/GP',
            'xGF%', 'xGF/60', 'xGA/60', 'xGD/60',
            'CF%', 'FF%', 'CF/60', 'CA/60',
            'HDCF/60', 'HDCA/60', 'HDCF%', 'HDSH%', 'HDSV%',
            'SH%', 'SV%', 'PDO'
        ]
        
        # Player stats for different situations
        self.player_stats_5v5_totals = [
            'Player', 'Team', 'Position', 'TOI', 'Goals', 'Total Assists', 
            'First Assists', 'Second Assists', 'Total Points', 'IPP', 
            'Shots', 'SH%', 'ixG', 'iCF', 'iFF', 'iSCF', 'iHDCF', 'Blocked'
        ]
        
        self.player_stats_5v5_rates = [
            'Player', 'Team', 'Position', 'TOI', 'Goals/60', 'Total Assists/60',
            'First Assists/60', 'Second Assists/60', 'Total Points/60', 'IPP',
            'Shots/60', 'SH%', 'ixG/60', 'iCF/60', 'iFF/60', 'iSCF/60', 'iHDCF/60', 'Blocked/60'
        ]
        
        self.player_stats_5v4_totals = [
            'Player', 'Team', 'Position', 'TOI', 'Goals', 'Total Assists',
            'First Assists', 'Second Assists', 'Total Points', 'IPP',
            'Shots', 'SH%', 'ixG', 'iCF', 'iFF', 'iSCF', 'iHDCF'
        ]
        
        self.player_stats_5v4_rates = [
            'Player', 'Team', 'Position', 'TOI', 'Goals/60', 'Total Assists/60',
            'First Assists/60', 'Second Assists/60', 'Total Points/60', 'IPP',
            'Shots/60', 'SH%', 'ixG/60', 'iCF/60', 'iFF/60', 'iSCF/60', 'iHDCF/60'
        ]
        
        self.player_stats_4v5 = [
            'Player', 'Team', 'Position', 'TOI', 'Blocked'
        ]
    
    def scrape_team_situation(self, situation_code):
        """Scrape team stats for a specific situation"""
        params = self.team_base_params.copy()
        params['sit'] = situation_code
        
        try:
            response = requests.get(self.team_base_url, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'teams'})
            
            if not table:
                return None
            
            headers = []
            header_row = table.find('thead').find_all('tr')[-1]
            for th in header_row.find_all('th'):
                headers.append(th.get_text(strip=True))
            
            data = []
            tbody = table.find('tbody')
            for row in tbody.find_all('tr'):
                row_data = []
                for td in row.find_all('td'):
                    row_data.append(td.get_text(strip=True))
                if row_data:
                    data.append(row_data)
            
            df = pd.DataFrame(data, columns=headers)
            available_cols = [col for col in self.team_desired_stats if col in df.columns]
            df_filtered = df[available_cols].copy()
            
            return df_filtered
        
        except Exception as e:
            print(f"Error scraping team data for {situation_code}: {e}")
            return None
    
    def scrape_player_data(self, situation, rate_type, desired_cols):
        """Scrape player stats for a specific situation and rate type"""
        params = self.player_base_params.copy()
        params['sit'] = situation
        params['rate'] = rate_type
        
        try:
            response = requests.get(self.player_base_url, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return None
            
            headers = []
            header_row = table.find('thead').find_all('tr')[-1]
            for th in header_row.find_all('th'):
                headers.append(th.get_text(strip=True))
            
            data = []
            tbody = table.find('tbody')
            for row in tbody.find_all('tr'):
                row_data = []
                for td in row.find_all('td'):
                    row_data.append(td.get_text(strip=True))
                if row_data:
                    data.append(row_data)
            
            df = pd.DataFrame(data, columns=headers)
            available_cols = [col for col in desired_cols if col in df.columns]
            df_filtered = df[available_cols].copy()
            
            return df_filtered
        
        except Exception as e:
            print(f"Error scraping player data for {situation} ({rate_type}): {e}")
            return None
    
    def scrape_all_team_situations(self):
        """Scrape team stats for all three situations"""
        situations = {
            '5v5': 'sva',
            '5v4': '5v4',
            '4v5': '4v5'
        }
        
        all_data = {}
        for name, code in situations.items():
            print(f"Scraping team {name} data...")
            df = self.scrape_team_situation(code)
            if df is not None:
                all_data[name] = df
                print(f"  ✓ Successfully scraped {len(df)} teams")
        
        return all_data
    
    def scrape_all_player_data(self):
        """Scrape player stats for all situations"""
        all_data = {}
        
        print("Scraping player 5v5 totals...")
        df = self.scrape_player_data('5v5', 'n', self.player_stats_5v5_totals)
        if df is not None:
            all_data['5v5_totals'] = df
            print(f"  ✓ Successfully scraped {len(df)} players")
        
        print("Scraping player 5v5 rates...")
        df = self.scrape_player_data('5v5', 'y', self.player_stats_5v5_rates)
        if df is not None:
            all_data['5v5_rates'] = df
            print(f"  ✓ Successfully scraped {len(df)} players")
        
        print("Scraping player 5v4 totals...")
        df = self.scrape_player_data('5v4', 'n', self.player_stats_5v4_totals)
        if df is not None:
            all_data['5v4_totals'] = df
            print(f"  ✓ Successfully scraped {len(df)} players")
        
        print("Scraping player 5v4 rates...")
        df = self.scrape_player_data('5v4', 'y', self.player_stats_5v4_rates)
        if df is not None:
            all_data['5v4_rates'] = df
            print(f"  ✓ Successfully scraped {len(df)} players")
        
        print("Scraping player 4v5 data...")
        df = self.scrape_player_data('4v5', 'n', self.player_stats_4v5)
        if df is not None:
            all_data['4v5'] = df
            print(f"  ✓ Successfully scraped {len(df)} players")
        
        return all_data

app = Flask(__name__)

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>NHL Stats Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 20px;
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .subtitle {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .container {
            max-width: 1800px;
            margin: 0 auto;
        }
        .main-nav {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-bottom: 30px;
        }
        .main-nav-button {
            padding: 15px 40px;
            background: white;
            color: #1e3c72;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
            font-weight: 700;
            transition: all 0.3s;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .main-nav-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.2);
        }
        .main-nav-button.active {
            background: #4CAF50;
            color: white;
        }
        .main-section {
            display: none;
        }
        .main-section.active {
            display: block;
        }
        .controls {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .control-row {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        label {
            font-weight: 600;
            color: #2c3e50;
            min-width: 70px;
        }
        select, input {
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            min-width: 180px;
            transition: border-color 0.3s;
        }
        select:focus, input:focus {
            outline: none;
            border-color: #4CAF50;
        }
        button {
            padding: 12px 24px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.3s;
        }
        button:hover {
            background-color: #45a049;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .refresh-btn {
            background-color: #2196F3;
        }
        .refresh-btn:hover {
            background-color: #0b7dda;
        }
        .situation-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid rgba(255,255,255,0.3);
        }
        .tab-button {
            padding: 12px 24px;
            background: transparent;
            color: white;
            border: none;
            border-bottom: 3px solid transparent;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .tab-button:hover {
            background-color: rgba(255,255,255,0.1);
            transform: none;
            box-shadow: none;
        }
        .tab-button.active {
            color: #4CAF50;
            border-bottom-color: #4CAF50;
            background-color: rgba(255,255,255,0.1);
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .team-card, .player-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        .team-card:hover, .player-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }
        .team-card h2, .player-card h2 {
            color: #1e3c72;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 3px solid #4CAF50;
            font-size: 1.5em;
        }
        .situation-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            margin-left: 10px;
        }
        .badge-5v5 { background: #4CAF50; color: white; }
        .badge-5v4 { background: #2196F3; color: white; }
        .badge-4v5 { background: #FF9800; color: white; }
        .stat-category {
            margin-bottom: 20px;
        }
        .category-title {
            font-weight: 700;
            color: #2c3e50;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 2px solid #e0e0e0;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 5px;
            border-bottom: 1px solid #f0f0f0;
        }
        .stat-row:last-child {
            border-bottom: none;
        }
        .stat-label {
            font-weight: 500;
            color: #555;
        }
        .stat-value {
            font-weight: 600;
            color: #2c3e50;
        }
        .all-teams-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .all-teams-section h2 {
            color: #1e3c72;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        .table-wrapper {
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 12px 8px;
            text-align: left;
            position: sticky;
            top: 0;
            font-weight: 600;
            white-space: nowrap;
            z-index: 10;
        }
        td {
            padding: 10px 8px;
            border-bottom: 1px solid #e0e0e0;
            white-space: nowrap;
        }
        tr:hover {
            background-color: #f5f9ff;
        }
        tr:nth-child(even) {
            background-color: #fafafa;
        }
        tr:nth-child(even):hover {
            background-color: #f5f9ff;
        }
        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .info-box p {
            margin: 5px 0;
            color: #1976D2;
            font-size: 0.9em;
        }
        .info-box strong {
            color: #0d47a1;
        }
        .filter-section {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .filter-section input {
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏒 NHL Advanced Stats Dashboard</h1>
            <div class="subtitle">Complete Team & Player Analysis | 2025-26 Season</div>
        </div>
        
        <div class="main-nav">
            <button class="main-nav-button active" onclick="showMainSection('teams')">Teams</button>
            <button class="main-nav-button" onclick="showMainSection('players')">Players</button>
        </div>
        
        <!-- TEAMS SECTION -->
        <div id="section-teams" class="main-section active">
            {% include 'teams_section.html' %}
        </div>
        
        <!-- PLAYERS SECTION -->
        <div id="section-players" class="main-section">
            {% include 'players_section.html' %}
        </div>
    </div>
    
    <script>
        function showMainSection(section) {
            document.querySelectorAll('.main-section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.main-nav-button').forEach(b => b.classList.remove('active'));
            
            document.getElementById('section-' + section).classList.add('active');
            event.target.classList.add('active');
        }
        
        function showTab(situation) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                if (tab.id.startsWith('tab-')) {
                    tab.classList.remove('active');
                }
            });
            document.getElementById('tab-' + situation).classList.add('active');
            
            const parent = event.target.closest('.situation-tabs');
            parent.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
        }
        
        function showTableTab(situation) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                if (tab.id.startsWith('table-')) {
                    tab.classList.remove('active');
                }
            });
            document.getElementById('table-' + situation).classList.add('active');
            
            const tableTabs = document.querySelectorAll('.situation-tabs')[1];
            if (tableTabs) {
                tableTabs.querySelectorAll('.tab-button').forEach(btn => {
                    btn.classList.remove('active');
                });
            }
            event.target.classList.add('active');
        }
        
        function showPlayerTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => {
                if (t.id.startsWith('player-')) {
                    t.classList.remove('active');
                }
            });
            document.getElementById('player-' + tab).classList.add('active');
            
            const parent = event.target.closest('.situation-tabs');
            parent.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
        }
        
        function filterPlayers() {
            const searchTerm = document.getElementById('playerSearch').value.toLowerCase();
            const teamFilter = document.getElementById('teamFilter').value;
            const posFilter = document.getElementById('posFilter').value;
            
            document.querySelectorAll('table tr').forEach((row, index) => {
                if (index === 0) return; // Skip header
                
                const cells = row.getElementsByTagName('td');
                if (cells.length === 0) return;
                
                const player = cells[0].textContent.toLowerCase();
                const team = cells[1].textContent;
                const pos = cells[2].textContent;
                
                const matchesSearch = player.includes(searchTerm);
                const matchesTeam = !teamFilter || team === teamFilter;
                const matchesPos = !posFilter || pos === posFilter;
                
                row.style.display = (matchesSearch && matchesTeam && matchesPos) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
'''

TEAMS_SECTION = '''
<div class="controls">
    <div class="info-box">
        <p><strong>5v5:</strong> Even strength, score-adjusted | <strong>5v4 (PP):</strong> Power play | <strong>4v5 (PK):</strong> Penalty kill</p>
        <p><strong>Key Metrics:</strong> xGF% = quality control | CF% = volume control | HDCF% = danger control | PDO = luck (100 = neutral)</p>
    </div>
    
    <div class="control-row">
        <form method="POST" action="/refresh_teams" style="display: inline;">
            <button type="submit" class="refresh-btn">↻ Refresh Team Data</button>
        </form>
    </div>
    
    <form method="POST" action="/compare_teams">
        <div class="control-row">
            <label>Team 1:</label>
            <select name="team1" required>
                <option value="">Select Team</option>
                {% for team in teams %}
                <option value="{{ team }}">{{ team }}</option>
                {% endfor %}
            </select>
            
            <label>Team 2:</label>
            <select name="team2" required>
                <option value="">Select Team</option>
                {% for team in teams %}
                <option value="{{ team }}">{{ team }}</option>
                {% endfor %}
            </select>
            
            <label>Team 3:</label>
            <select name="team3">
                <option value="">Optional</option>
                {% for team in teams %}
                <option value="{{ team }}">{{ team }}</option>
                {% endfor %}
            </select>
            
            <button type="submit">Compare Teams</button>
        </div>
    </form>
</div>

{% if team_comparison %}
<div class="situation-tabs">
    <button class="tab-button active" onclick="showTab('5v5')">5v5</button>
    <button class="tab-button" onclick="showTab('5v4')">5v4 PP</button>
    <button class="tab-button" onclick="showTab('4v5')">4v5 PK</button>
</div>

{% for situation in ['5v5', '5v4', '4v5'] %}
<div id="tab-{{ situation }}" class="tab-content {% if situation == '5v5' %}active{% endif %}">
    <div class="stats-grid">
        {% for team_name in team_comparison.keys() %}
        {% if situation in team_comparison[team_name] %}
        {% set stats = team_comparison[team_name][situation] %}
        <div class="team-card">
            <h2>{{ team_name }}<span class="situation-badge badge-{{ situation }}">{{ situation }}</span></h2>
            
            <div class="stat-category">
                <div class="category-title">Ice Time</div>
                {% for stat in ['GP', 'TOI', 'TOI/GP'] %}
                {% if stat in stats %}
                <div class="stat-row">
                    <span class="stat-label">{{ stat }}:</span>
                    <span class="stat-value">{{ stats[stat] }}</span>
                </div>
                {% endif %}
                {% endfor %}
            </div>
            
            <div class="stat-category">
                <div class="category-title">Expected Goals</div>
                {% for stat in ['xGF%', 'xGF/60', 'xGA/60', 'xGD/60'] %}
                {% if stat in stats %}
                <div class="stat-row">
                    <span class="stat-label">{{ stat }}:</span>
                    <span class="stat-value">{{ stats[stat] }}</span>
                </div>
                {% endif %}
                {% endfor %}
            </div>
            
            <div class="stat-category">
                <div class="category-title">Shot Metrics</div>
                {% for stat in ['CF%', 'FF%', 'CF/60', 'CA/60'] %}
                {% if stat in stats %}
                <div class="stat-row">
                    <span class="stat-label">{{ stat }}:</span>
                    <span class="stat-value">{{ stats[stat] }}</span>
                </div>
                {% endif %}
                {% endfor %}
            </div>
            
            <div class="stat-category">
                <div class="category-title">High Danger</div>
                {% for stat in ['HDCF/60', 'HDCA/60', 'HDCF%', 'HDSH%', 'HDSV%'] %}
                {% if stat in stats %}
                <div class="stat-row">
                    <span class="stat-label">{{ stat }}:</span>
                    <span class="stat-value">{{ stats[stat] }}</span>
                </div>
                {% endif %}
                {% endfor %}
            </div>
            
            <div class="stat-category">
                <div class="category-title">Shooting & Saves</div>
                {% for stat in ['SH%', 'SV%', 'PDO'] %}
                {% if stat in stats %}
                <div class="stat-row">
                    <span class="stat-label">{{ stat }}:</span>
                    <span class="stat-value">{{ stats[stat] }}</span>
                </div>
                {% endif %}
                {% endfor %}
            </div>
        </div>
        {% endif %}
        {% endfor %}
    </div>
</div>
{% endfor %}
{% endif %}

<div class="situation-tabs">
    <button class="tab-button active" onclick="showTableTab('5v5')">5v5 All Teams</button>
    <button class="tab-button" onclick="showTableTab('5v4')">5v4 All Teams</button>
    <button class="tab-button" onclick="showTableTab('4v5')">4v5 All Teams</button>
</div>

{% for situation in ['5v5', '5v4', '4v5'] %}
<div id="table-{{ situation }}" class="tab-content all-teams-section {% if situation == '5v5' %}active{% endif %}">
    <h2>{{ situation }} - All Teams</h2>
    <div class="table-wrapper">
        {% if team_tables and situation in team_tables %}
        {{ team_tables[situation]|safe }}
        {% endif %}
    </div>
</div>
{% endfor %}
'''

# Global variables to store data
team_stats_data = {}
player_stats_data = {}

@app.route('/')
def index():
    global team_stats_data, player_stats_data
    
    # Load team data if not already loaded
    if not team_stats_data:
        scraper = NHLStatsScraper()
        team_stats_data = scraper.scrape_all_team_situations()
    
    # Load player data if not already loaded
    if not player_stats_data:
        scraper = NHLStatsScraper()
        player_stats_data = scraper.scrape_all_player_data()
    
    if not team_stats_data or '5v5' not in team_stats_data:
        return "Error loading data. Please refresh."
    
    # Get teams from 5v5 data
    teams = sorted(team_stats_data['5v5'].iloc[:, 0].unique().tolist())
    
    # Create team tables
    team_tables = {}
    for situation, df in team_stats_data.items():
        team_tables[situation] = df.to_html(index=False, classes='stats-table')
    
    # Create player tables
    player_tables = {}
    for data_key, df in player_stats_data.items():
        player_tables[data_key] = df.to_html(index=False, classes='stats-table')
    
    return render_template_string(
        MAIN_TEMPLATE,
        teams=teams,
        team_tables=team_tables,
        player_tables=player_tables,
        team_comparison=None
    )

@app.route('/compare_teams', methods=['POST'])
def compare_teams():
    global team_stats_data, player_stats_data
    
    team1 = request.form.get('team1')
    team2 = request.form.get('team2')
    team3 = request.form.get('team3')
    
    teams = sorted(team_stats_data['5v5'].iloc[:, 0].unique().tolist())
    
    # Create team tables
    team_tables = {}
    for situation, df in team_stats_data.items():
        team_tables[situation] = df.to_html(index=False, classes='stats-table')
    
    # Create player tables
    player_tables = {}
    for data_key, df in player_stats_data.items():
        player_tables[data_key] = df.to_html(index=False, classes='stats-table')
    
    team_comparison = {}
    
    for team in [team1, team2, team3]:
        if team and team != "":
            team_comparison[team] = {}
            
            for situation, df in team_stats_data.items():
                team_row = df[df.iloc[:, 0] == team]
                if not team_row.empty:
                    team_stats = team_row.iloc[0].to_dict()
                    team_comparison[team][situation] = team_stats
    
    return render_template_string(
        MAIN_TEMPLATE,
        teams=teams,
        team_tables=team_tables,
        player_tables=player_tables,
        team_comparison=team_comparison
    )

@app.route('/refresh_teams', methods=['POST'])
def refresh_teams():
    global team_stats_data
    scraper = NHLStatsScraper()
    team_stats_data = scraper.scrape_all_team_situations()
    return index()

@app.route('/refresh_players', methods=['POST'])
def refresh_players():
    global player_stats_data
    scraper = NHLStatsScraper()
    player_stats_data = scraper.scrape_all_player_data()
    return index()

# Template loader for Jinja
from jinja2 import Environment, BaseLoader

template_env = Environment(loader=BaseLoader())
template_env.globals['include'] = lambda name: {
    'teams_section.html': TEAMS_SECTION,
    'players_section.html': PLAYERS_SECTION
}.get(name, '')

@app.template_filter('safe')
def safe_filter(text):
    from markupsafe import Markup
    return Markup(text)

if __name__ == '__main__':
    print("=" * 70)
    print(" NHL ADVANCED STATS DASHBOARD")
    print("=" * 70)
    print("\nInitializing data scraper...")
    print("This will take a few moments as we fetch:")
    print("  • Team stats (5v5, 5v4, 4v5)")
    print("  • Player stats (5v5 totals, 5v5 rates, 5v4 totals, 5v4 rates, 4v5)")
    print("\n" + "-" * 70)
    
    scraper = NHLStatsScraper()
    
    print("\n📊 SCRAPING TEAM DATA")
    print("-" * 70)
    team_stats_data = scraper.scrape_all_team_situations()
    
    print("\n👤 SCRAPING PLAYER DATA")
    print("-" * 70)
    player_stats_data = scraper.scrape_all_player_data()
    
    if team_stats_data and player_stats_data:
        print("\n" + "=" * 70)
        print("✓ DATA SCRAPING COMPLETE!")
        print("=" * 70)
        print(f"\n📈 Loaded {len(team_stats_data['5v5'])} teams")
        print(f"👥 Loaded {len(player_stats_data.get('5v5_totals', []))} players")
        print("\n" + "-" * 70)
        print("Starting web server...")
        print("=" * 70)
        print("\n🌐 OPEN YOUR BROWSER: http://localhost:5000")
        print("\n" + "=" * 70)
        print("\nFeatures:")
        print("  • Toggle between TEAMS and PLAYERS")
        print("  • Compare teams side-by-side")
        print("  • Filter players by name, team, or position")
        print("  • View totals and per-60 rates")
        print("  • Separate refresh buttons for teams and players")
        print("=" * 70 + "\n")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("\n✗ Failed to scrape data. Please check your internet connection.")
        print("   Make sure Natural Stat Trick is accessible.")


PLAYERS_SECTION = '''
<div class="controls">
    <div class="info-box">
        <p><strong>Individual Stats (i-prefix):</strong> Player's own shots, chances, and expected goals</p>
        <p><strong>IPP:</strong> Individual Points Percentage - % of team's goals the player was directly involved in while on ice</p>
        <p><strong>Totals vs Rates:</strong> Totals show raw production, /60 rates normalize for ice time</p>
    </div>
    
    <div class="control-row">
        <form method="POST" action="/refresh_players" style="display: inline;">
            <button type="submit" class="refresh-btn">↻ Refresh Player Data</button>
        </form>
    </div>
</div>

<div class="situation-tabs">
    <button class="tab-button active" onclick="showPlayerTab('5v5-totals')">5v5 Totals</button>
    <button class="tab-button" onclick="showPlayerTab('5v5-rates')">5v5 Rates</button>
    <button class="tab-button" onclick="showPlayerTab('5v4-totals')">5v4 Totals</button>
    <button class="tab-button" onclick="showPlayerTab('5v4-rates')">5v4 Rates</button>
    <button class="tab-button" onclick="showPlayerTab('4v5')">4v5 PK</button>
</div>

<div class="filter-section">
    <label>Search Player:</label>
    <input type="text" id="playerSearch" placeholder="Type player name..." onkeyup="filterPlayers()">
    
    <label>Team:</label>
    <select id="teamFilter" onchange="filterPlayers()">
        <option value="">All Teams</option>
        {% for team in teams %}
        <option value="{{ team }}">{{ team }}</option>
        {% endfor %}
    </select>
    
    <label>Position:</label>
    <select id="posFilter" onchange="filterPlayers()">
        <option value="">All Positions</option>
        <option value="C">Center</option>
        <option value="L">Left Wing</option>
        <option value="R">Right Wing</option>
        <option value="D">Defense</option>
    </select>
</div>

{% for data_key, title in [('5v5_totals', '5v5 Totals'), ('5v5_rates', '5v5 Per 60'), ('5v4_totals', '5v4 Totals'), ('5v4_rates', '5v4 Per 60'), ('4v5', '4v5 Penalty Kill')] %}
<div id="player-{{ data_key }}" class="tab-content all-teams-section {% if data_key == '5v5_totals' %}active{% endif %}">
    <h2>{{ title }}</h2>
    <div class="table-wrapper">
        {% if player_tables and data_key in player_tables %}
        {{ player_tables[data_key]|safe }}
        {% endif %}
    </div>
</div>
{% endfor %}
'''