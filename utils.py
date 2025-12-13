from typing import Annotated, Sequence, TypedDict, List, Dict, Union, Literal
from dataclasses import dataclass
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
import random
import csv
import os

class BidDecisionDict(TypedDict):
    """Expected format for bid_decision parameter."""
    is_raise: bool
    is_normal: Union[bool, None]
    raised_amount: Union[float, None]

class BidResponseDict(TypedDict):
    """Expected format for API response containing bid decision."""
    status: str
    bid_decision: BidDecisionDict

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
    Messages: Annotated[Sequence[Union[HumanMessage, AIMessage, ToolMessage, BaseMessage]], add_messages]

    
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
        print(f"Error: CSV file not found at {csv_path}")
    except Exception as e:
        print(f"Error loading player data: {e}")
    
    return players_by_set

def prettyprint(agent_state: AgentState) -> None:
    """Pretty print the agent state."""
    print("\n" + "="*60)
    print("AGENT STATE")
    print("="*60)
    for key, value in agent_state.items():
        print(f"\n{key.upper()}:")
        if key == "Messages":
            if not value:
                print("  (empty)")
            else:
                for i, msg in enumerate(value, 1):
                    print(f"  {i}. [{type(msg).__name__}] {msg.content}")
        elif isinstance(value, list):
            # Handle list of players (TeamA, TeamB, TeamC)
            if not value:
                print("  (empty)")
            else:
                for i, item in enumerate(value, 1):
                    if isinstance(item, Player):
                        print(f"  {i}. {item.name} ({item.role}) - INR {item.sold_price:.2f}Cr")
                    else:
                        print(f"  {i}. {item}")
        elif isinstance(value, dict):
            # Handle dict of sets with player lists (RemainingPlayers)
            for set_name, players in value.items():
                if isinstance(players, list) and players and isinstance(players[0], Player):
                    print(f"  {set_name}: {len(players)} players")
                    for i, player in enumerate(players, 1):
                        print(f"    {i}. {player.name} ({player.role}) - Base: INR {player.base_price:.2f}Cr, Prev: INR {player.previous_sold_price:.2f}Cr")
                else:
                    print(f"  {set_name}: {players}")
        else:
            print(f"  {value}")
    print("="*60 + "\n")

def get_raise_amount(current_price: float) -> float:
    """Determine the raise amount based on current price."""
    if current_price < 2.0:
        return 0.1  # Raise by 0.1 crore
    elif current_price < 20.0:
        return 0.25  # Raise by 0.25 crore
    else:
        return 0.5  # Raise by 0.5 crore

def decide_bid(team_budget: float, current_bid: float, base_price: float) -> bool:
	"""
	Hardcoded bidding intelligence.
	Decides whether to bid based on budget and price.
	"""
	# Safety check
	if team_budget <= 0:
		return False
	
	# Don't bid if we can't afford the next raise (approx)
	if current_bid >= team_budget:
		return False
		
	# Strategy:
	# 1. Don't spend more than 30% of total budget on one player (simple rule)
	if current_bid > (team_budget * 0.3):
		return False
		
	# 2. Don't pay more than 15x base price (unless it's very low)
	if current_bid > (base_price * 15):
		return False
		
	# Random factor: 50% chance to skip bidding even if logical conditions are met
	# This simulates hesitation or strategic pausing
	if random.random() < 0.50:
		return False

	return 

def competitiveBidMaker(team: Literal['TeamA', 'TeamB', 'TeamC'], player: Player, bid_decision: BidDecisionDict) -> CompetitiveBidInfo:
    """Create a CompetitiveBidInfo object for a team's bid.
    
    Args:
        team: The team making the bid (TeamA, TeamB, or TeamC).
        player: The player being bid on.
        bid_decision: Bid decision in the format:
            {
                "is_raise": bool - Whether this bid is a raise,
                "is_normal": bool or None - Whether this is a normal raise (fixed increment). Only applicable if is_raise is True,
                "raised_amount": float or None - The custom raise amount. Only applicable if is_raise is True and is_normal is False
            }
    
    Returns:
        CompetitiveBidInfo: Object containing the competitive bid information.
    """
    return CompetitiveBidInfo(
        player=player,
        team=team,
        is_raise=bid_decision['is_raise'],
        is_normal=bid_decision['is_normal'],
        raised_amount=bid_decision.get('raised_amount')
    )

