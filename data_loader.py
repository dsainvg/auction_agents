from typing import Literal, Dict, List
from utils import AgentState, Player, AIMessage
import csv
import os

def load_player_data() -> Dict[Literal['M1', 'M2', 'AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10', 'BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'FA1', 'FA2', 'FA3', 'FA4', 'FA5', 'FA6', 'FA7', 'FA8', 'FA9', 'FA10', 'SP1', 'SP2', 'SP3', 'WK1', 'WK2', 'WK3', 'WK4', 'UAL1', 'UAL2', 'UAL3', 'UAL4', 'UAL5', 'UAL6', 'UAL7', 'UAL8', 'UAL9', 'UAL10', 'UAL11', 'UAL12', 'UAL13', 'UAL14', 'UAL15', 'UBA1', 'UBA2', 'UBA3', 'UBA4', 'UBA5', 'UBA6', 'UBA7', 'UBA8', 'UBA9', 'UFA1', 'UFA2', 'UFA3', 'UFA4', 'UFA5', 'UFA6', 'UFA7', 'UFA8', 'UFA9', 'UFA10', 'USP1', 'USP2', 'USP3', 'USP4', 'USP5', 'UWK1', 'UWK2', 'UWK3', 'UWK4', 'UWK5', 'UWK6'], List[Player]]:
    """Load player data from CSV file in DB folder, grouped by set.
    Returns:
        Dictionary mapping set names (e.g., 'M1', 'M2', 'AL1') to list of players in that set.
    """
    
    # Initialize empty lists for all IPL 2025 auction sets
    players_by_set = {
        # Marquee
        'M1': [], 'M2': [],
        # Capped Allrounders
        'AL1': [], 'AL2': [], 'AL3': [], 'AL4': [], 'AL5': [], 'AL6': [], 'AL7': [], 'AL8': [], 'AL9': [], 'AL10': [],
        # Capped Batters
        'BA1': [], 'BA2': [], 'BA3': [], 'BA4': [], 'BA5': [],
        # Capped Fast Bowlers
        'FA1': [], 'FA2': [], 'FA3': [], 'FA4': [], 'FA5': [], 'FA6': [], 'FA7': [], 'FA8': [], 'FA9': [], 'FA10': [],
        # Capped Spinners
        'SP1': [], 'SP2': [], 'SP3': [],
        # Capped Wicketkeepers
        'WK1': [], 'WK2': [], 'WK3': [], 'WK4': [],
        # Uncapped Allrounders
        'UAL1': [], 'UAL2': [], 'UAL3': [], 'UAL4': [], 'UAL5': [], 'UAL6': [], 'UAL7': [], 'UAL8': [], 'UAL9': [], 'UAL10': [],
        'UAL11': [], 'UAL12': [], 'UAL13': [], 'UAL14': [], 'UAL15': [],
        # Uncapped Batters
        'UBA1': [], 'UBA2': [], 'UBA3': [], 'UBA4': [], 'UBA5': [], 'UBA6': [], 'UBA7': [], 'UBA8': [], 'UBA9': [],
        # Uncapped Fast Bowlers
        'UFA1': [], 'UFA2': [], 'UFA3': [], 'UFA4': [], 'UFA5': [], 'UFA6': [], 'UFA7': [], 'UFA8': [], 'UFA9': [], 'UFA10': [],
        # Uncapped Spinners
        'USP1': [], 'USP2': [], 'USP3': [], 'USP4': [], 'USP5': [],
        # Uncapped Wicketkeepers
        'UWK1': [], 'UWK2': [], 'UWK3': [], 'UWK4': [], 'UWK5': [], 'UWK6': [],
    }
    csv_path = os.path.join(os.path.dirname(__file__), "DB", "players.csv")
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            row_count = 0
            for row in reader:
                row_count += 1
                try:
                    serial_no = int(float(row['Serial_No'])) if 'Serial_No' in row and row['Serial_No'] else 0
                    
                    # Load stats from stats folder based on serial number
                    stats_content = ""
                    if serial_no > 0:
                        stats_file = os.path.join(os.path.dirname(__file__), "DB", "stats", f"{serial_no}.txt")
                        if os.path.exists(stats_file):
                            try:
                                with open(stats_file, 'r', encoding='utf-8', errors='ignore') as f:
                                    stats_content = f.read()
                            except Exception:
                                # Fallback to binary read if UTF-8 fails
                                try:
                                    with open(stats_file, 'rb') as fb:
                                        stats_content = fb.read().decode('utf-8', errors='ignore')
                                except Exception:
                                    stats_content = "Stats file could not be read."
                    
                    player = Player(
                        name=row['Name'],
                        specialism=row['Specialism'],
                        batting_style=row['Batting_Style'],
                        bowling_style=row['Bowling_Style'],
                        test_caps=int(float(row['Test_Caps'])) if row['Test_Caps'] else 0,
                        odi_caps=int(float(row['ODI_Caps'])) if row['ODI_Caps'] else 0,
                        t20_caps=int(float(row['T20_Caps'])) if row['T20_Caps'] else 0,
                        ipl_matches=int(float(row['IPL_Matches'])) if row['IPL_Matches'] else 0,
                        player_status=row['Player_Status'],
                        reserve_price_lakh=float(row['Reserve_Price_Lakh']) if row['Reserve_Price_Lakh'] else 0.0,
                        set=row['Set'],
                        stats=stats_content,
                        status=False,
                        sold_price=0.0
                    )
                    
                    # Group players by set
                    player_set = row['Set']
                    if player_set not in players_by_set:
                        players_by_set[player_set] = []
                    players_by_set[player_set].append(player)
                except Exception as e:
                    print(f"Error loading player row {row_count} ({row.get('Name', 'unknown')}): {e}")
                    continue
            
            # Count loaded players
            total_players = sum(len(players) for players in players_by_set.values())
            print(f"[DATA_LOADER] Loaded {total_players} players across {len([s for s, p in players_by_set.items() if p])} sets")
                
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_path}")
    except Exception as e:
        print(f"Error loading player data: {e}")
    
    return players_by_set

def load_retained_players() -> Dict[Literal['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH'], List[Player]]:
    """Load retained players from retained_players.csv and assign them to teams.
    
    Returns:
        Dictionary mapping team names to list of retained players.
    """
    retained_by_team = {
        'CSK': [], 'DC': [], 'GT': [], 'KKR': [], 'LSG': [],
        'MI': [], 'PBKS': [], 'RR': [], 'RCB': [], 'SRH': []
    }
    
    csv_path = os.path.join(os.path.dirname(__file__), "DB", "retained_players.csv")
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                team = row['Team']
                sold_price = float(row['Sold']) if row['Sold'] else 0.0
                
                # Create a Player object for retained player with minimal info
                player = Player(
                    name=row['Players'],
                    specialism=row['Type'],  # BAT, BOWL, AR
                    batting_style="",
                    bowling_style="",
                    test_caps=0,
                    odi_caps=0,
                    t20_caps=0,
                    ipl_matches=0,
                    player_status="Retained",
                    reserve_price_lakh=0.0,
                    set="Retained",
                    stats="",
                    status=True,  # Already sold
                    sold_price=sold_price,
                    sold_team=team,
                    reason_for_purchase="Retained"
                )
                
                if team in retained_by_team:
                    retained_by_team[team].append(player)
    
    except FileNotFoundError:
        print(f"Error: Retained players CSV file not found at {csv_path}")
    except Exception as e:
        print(f"Error loading retained players: {e}")
    
    return retained_by_team

def initialize_auction(state: AgentState) -> AgentState:
    """Initialize auction state by loading all player data and retained players."""
    
    print("[DATA_LOADER] Loading player data from CSV...")
    players_by_set = load_player_data()
    
    print("[DATA_LOADER] Loading retained players...")
    retained_by_team = load_retained_players()
    
    # Calculate budgets after retentions (starting budget is 160 Cr)
    starting_budget = 160.0
    budgets = {}
    
    for team in ['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH']:
        retained_cost = sum(p.sold_price for p in retained_by_team[team])
        budgets[f"{team}_Budget"] = starting_budget - retained_cost
        print(f"[DATA_LOADER] {team}: {len(retained_by_team[team])} retained players, {retained_cost:.2f} Cr spent, {budgets[f'{team}_Budget']:.2f} Cr remaining")
    
    # Initialize state
    state['RemainingPlayers'] = players_by_set
    state['RemainingSets'] = ['M1', 'M2', 'AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10', 
                               'BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'FA1', 'FA2', 'FA3', 'FA4', 'FA5', 'FA6', 'FA7', 'FA8', 'FA9', 'FA10',
                               'SP1', 'SP2', 'SP3', 'WK1', 'WK2', 'WK3', 'WK4',
                               'UAL1', 'UAL2', 'UAL3', 'UAL4', 'UAL5', 'UAL6', 'UAL7', 'UAL8', 'UAL9', 'UAL10', 'UAL11', 'UAL12', 'UAL13', 'UAL14', 'UAL15',
                               'UBA1', 'UBA2', 'UBA3', 'UBA4', 'UBA5', 'UBA6', 'UBA7', 'UBA8', 'UBA9',
                               'UFA1', 'UFA2', 'UFA3', 'UFA4', 'UFA5', 'UFA6', 'UFA7', 'UFA8', 'UFA9', 'UFA10',
                               'USP1', 'USP2', 'USP3', 'USP4', 'USP5',
                               'UWK1', 'UWK2', 'UWK3', 'UWK4', 'UWK5', 'UWK6']
    state['CurrentSet'] = None
    state['RemainingPlayersInSet'] = None
    state['AuctionStatus'] = False
    state['CurrentPlayer'] = None
    state['CurrentBid'] = None
    state['OtherTeamBidding'] = None
    state['Round'] = 0
    
    # Assign retained players to teams
    for team in ['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH']:
        state[team] = retained_by_team[team]
    
    state['UnsoldPlayers'] = []
    
    # Set budgets
    for key, value in budgets.items():
        state[key] = value
    
    state['Messages'] = [AIMessage(content="Auction initialized with player data and retained players loaded.")]
    
    print("[DATA_LOADER] Auction initialization complete")
    
    return state
