from typing import Annotated, Sequence, TypedDict, List, Dict, Union, Literal, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
import random
import csv
import os
import itertools
import json
from pydantic import BaseModel, Field

# --- API Key Management ---
def load_api_keys():
    """Load Gemini API keys from environment variables based on NUM_GEMINI_API_KEYS."""
    
    load_dotenv()
    try:
        num_keys = int(os.getenv("NUM_GEMINI_API_KEYS", 0))
    except (ValueError, TypeError):
        num_keys = 0
        
    if num_keys == 0:
        # Fallback to the old single key if the new system isn't used
        single_key = os.getenv("GEMINI_API_KEY")
        if single_key:
            return [single_key]
        return []

    keys = [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, num_keys + 1)]
    return [key for key in keys if key]

api_keys = load_api_keys()
if not api_keys:
    raise ValueError("No Gemini API keys found. Please set GEMINI_API_KEY_1, etc. in your .env file.")

api_key_cycle = itertools.cycle(api_keys)

def get_next_api_key():
    """Get the next API key from the cycle."""
    return next(api_key_cycle)

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
    reason: str = "" # Reason for the bid

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

class BidderInput(BaseModel):
    is_raise: bool = Field(description="Whether this bid is a raise or just a call")
    is_normal: Optional[bool] = Field(
        default=None, 
        description="Whether this is a normal raise (fixed increment). Only applicable if is_raise is True"
    )
    raised_amount: Optional[float] = Field(
        default=None,
        description="The custom raise amount. Only applicable if is_raise is True and is_normal is False"
    )
    reason: str = Field(description="The reason for this pick")

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
        return 0.25  # Raise by 0.1 crore
    elif current_price < 5.0:
        return 0.75  # Raise by 0.75 crore
    else:
        return 1.5  # Raise by 1.5 crore

def competitiveBidMaker(team: Literal['TeamA', 'TeamB', 'TeamC'], player: Player, bid_decision: BidderInput) -> CompetitiveBidInfo:
    """Create a CompetitiveBidInfo object for a team's bid.
    
    Args:
        team: The team making the bid (TeamA, TeamB, or TeamC).
        player: The player being bid on.
        bid_decision: Bid decision in the format:
            {
                "is_raise": bool - Whether this is a raise,
                "is_normal": bool or None - Whether this is a normal raise (fixed increment). Only applicable if is_raise is True,
                "raised_amount": float or None - The custom raise amount. Only applicable if is_raise is True and is_normal is False
            }
    
    Returns:
        CompetitiveBidInfo: Object containing the competitive bid information.
    """
    return CompetitiveBidInfo(
        player=player,
        team=team,
        is_raise=bid_decision.is_raise,
        is_normal=bid_decision.is_normal,
        raised_amount=bid_decision.raised_amount,
        reason=bid_decision.reason
    )

def load_prompts(prompt_dir="PROMPTS"):
    prompts = {}
    for filename in os.listdir(prompt_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(prompt_dir, filename)
            with open(filepath, "r") as f:
                # Use the filename without extension as key.
                # Normalize key so callers can use keys like 'TeamA_sys'.
                raw_key = filename.split('.')[0]
                key = raw_key[0].upper() + raw_key[1:] if raw_key else raw_key
                prompts[key] = f.read()
    return prompts

def get_player_stats(player_name: str) -> str:
    """
    Get the stats of a player from the DB/stats directory.

    Args:
        player_name: The name of the player.

    Returns:
        The stats of the player as a string.
    """
    stats_dir = os.path.join(os.path.dirname(__file__), "DB", "stats")
    player_name_formatted = player_name.replace(" ", "").lower()
    for filename in os.listdir(stats_dir):
        if filename.endswith(".txt"):
            filename_formatted = filename.replace(".txt", "").replace(" ", "").lower()
            if filename_formatted == player_name_formatted:
                filepath = os.path.join(stats_dir, filename)
                with open(filepath, "r") as f:
                    return f.read()
    return "Stats not found for this player."