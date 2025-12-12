from typing import TypedDict, Optional, List, Dict, Union, Literal
from dataclasses import dataclass
import csv
import os
import logging

logger = logging.getLogger(__name__)



@dataclass
class Player:
    name: str
    role: str
    base_price: float
    previous_sold_price: float
    category: str
    experience: str
    set: str
    status: bool = False
    sold_price: float = 0.0
    sold_team: Union[Literal['TeamA', 'TeamB', 'TeamC'], None] = None

@dataclass
class BidInfo:
    player: Player
    team: Literal['TeamA', 'TeamB', 'TeamC']
        
@dataclass
class CurrentBidInfo(BidInfo):
    current_bid_amount: float
    current_raise_amount: float # Amount by which the current bid should be raised

@dataclass
class CompetitiveBidInfo(BidInfo):
    is_raise: bool # Is there a raise in bid
    is_normal: Union[bool, None] # Is it a normal raise i.e fixed increment (current bid info raise amount) Only if is_raise is true
    raised_amount: Union[float, None] = None # Only if is_raise is true and is_normal is False 
   

class AgentState(TypedDict):
    """State schema for the agent."""
    RemainingPlayers: Dict[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'],List[Player]]
    RemainingSets: List[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC']]
    CurrentSet: Union[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'], None]
    RemainingPlayersInSet: Union[List[Player], None]
    AuctionStatus: bool = False
    CurrentPlayer: Union[Player, None] = None
    CurrentBid: Union[CurrentBidInfo, None] = None
    OtherTeamBidding: Union[Dict[Literal['TeamA', 'TeamB', 'TeamC'], CompetitiveBidInfo], None] = None
    Round :int = 0
    TeamA: List[Player] = []
    TeamB: List[Player] = []
    TeamC: List[Player] = []
    UnsoldPlayers: List[Player] = []
    TeamA_Budget: float
    TeamB_Budget: float
    TeamC_Budget: float

    
def load_player_data() -> dict[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'], list[Player]]:
    """Load player data from CSV file in DB folder, grouped by set.
    
    Returns:
        Dictionary mapping set names (e.g., 'SBC', 'SAC') to list of players in that set.
    """
    # Initialize empty lists for all sets
    players_by_set = {
        'SBC': [],
        'SAC': [],
        'SBwC': [],
        'EBC': [],
        'EAC': [],
        'EBwC': [],
        'MBC': [],
        'MAC': [],
        'MBwC': [],
        'EmBwU': [],
        'EmAU': [],
        'EmBC': []
    }
    csv_path = os.path.join(os.path.dirname(__file__), "DB", "players.csv")
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                player = Player(
                    name=row['Players'],
                    role=row['Type'],
                    base_price=float(row['Base']),  # Price in crores
                    previous_sold_price=float(row['Sold_Price']),  # Price in crores
                    category=row['Category'],
                    experience=row['Experience'],
                    set=row['Set'],
                    status=False,
                    sold_price=0.0
                )
                
                # Group players by set
                player_set = row['Set']
                if player_set not in players_by_set:
                    players_by_set[player_set] = []
                players_by_set[player_set].append(player)
                
    except FileNotFoundError:
        logger.error(f"Error: CSV file not found at {csv_path}")
    except Exception as e:
        logger.error(f"Error loading player data: {e}")
    
    return players_by_set

def prettyprint(agent_state: AgentState) -> None:
    """Pretty print the agent state."""
    logger.info("\n" + "="*60)
    logger.info("AGENT STATE")
    logger.info("="*60)
    for key, value in agent_state.items():
        logger.info(f"\n{key.upper()}:")
        if isinstance(value, list):
            # Handle list of players (TeamA, TeamB, TeamC)
            if not value:
                logger.info("  (empty)")
            else:
                for i, item in enumerate(value, 1):
                    if isinstance(item, Player):
                        logger.info(f"  {i}. {item.name} ({item.role}) - ₹{item.sold_price:.2f}Cr")
                    else:
                        logger.info(f"  {i}. {item}")
        elif isinstance(value, dict):
            # Handle dict of sets with player lists (RemainingPlayers)
            for set_name, players in value.items():
                if isinstance(players, list) and players and isinstance(players[0], Player):
                    logger.info(f"  {set_name}: {len(players)} players")
                    for i, player in enumerate(players, 1):
                        logger.info(f"    {i}. {player.name} ({player.role}) - Base: ₹{player.base_price:.2f}Cr, Prev: ₹{player.previous_sold_price:.2f}Cr")
                else:
                    logger.info(f"  {set_name}: {players}")
        else:
            logger.info(f"  {value}")
    logger.info("="*60 + "\n")

def get_raise_amount(current_price: float) -> float:
    """Determine the raise amount based on current price."""
    if current_price < 2.0:
        return 0.1  # Raise by 0.1 crore
    elif current_price < 20.0:
        return 0.25  # Raise by 0.25 crore
    else:
        return 0.5  # Raise by 0.5 crore