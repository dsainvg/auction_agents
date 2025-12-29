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
    """Load NVIDIA API keys from environment variables based on NUM_NVIDIA_API_KEYS."""
    
    load_dotenv()
    try:
        num_keys = int(os.getenv("NUM_NVIDIA_API_KEYS", 0))
    except (ValueError, TypeError):
        num_keys = 0
        
    if num_keys == 0:
        # Fallback to the old single key if the new system isn't used
        single_key = os.getenv("NVIDIA_API_KEY")
        if single_key:
            return [single_key]
        return []

    keys = [os.getenv(f"NVIDIA_API_KEY_{i}") for i in range(1, num_keys + 1)]
    return [key for key in keys if key]

api_keys = load_api_keys()
if not api_keys:
    raise ValueError("No NVIDIA API keys found. Please set NVIDIA_API_KEY_1, etc. in your .env file.")

api_key_cycle = itertools.cycle(api_keys)
# Maintain a parallel cycle of 1-based indices so callers can know which key was used
api_key_index_cycle = itertools.cycle(range(1, len(api_keys) + 1))

def get_next_api_key():
    """Get the next API key and its 1-based index from the cycle.

    Returns:
        tuple[str, int]: (api_key, api_key_index)
    """
    key = next(api_key_cycle)
    idx = next(api_key_index_cycle)
    return key, idx

class BidDecisionDict(TypedDict):
    """Expected format for bid_decision parameter."""
    is_raise: bool
    is_normal: bool
    raised_amount: float

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
    sold_team: Union[Literal['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH'], None] = None
    # Reason why the player was purchased (populated by AI reasoner at purchase time)
    reason_for_purchase: Union[str, None] = None
    # Store all team bid decisions/messages during auction rounds for this player
    # Format: {"CSK": [{"round": 1, "reason": "...", "decision": "raise/pass"}], ...}
    team_bid_history: Dict[str, List[Dict[str, Union[int, str, float]]]] = field(default_factory=dict)
    

@dataclass
class BidInfo:
    player: Player
    team: Literal['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH']
        
@dataclass
class CurrentBidInfo(BidInfo):
    current_bid_amount: float
    current_raise_amount: float # Amount by which the current bid should be raised

@dataclass
class CompetitiveBidInfo(BidInfo):
    is_raise: bool = False # Is there a raise in bid
    is_normal: bool = True # Is it a normal raise i.e fixed increment
    raised_amount: float = 0.0 # Custom raised amount; ignored if not applicable
    reason: str = "" # Rationale for the bid decision
    
@dataclass
class Team:
    Name: Literal['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH']
    Captain: Player
    WicketKeeper: Player
    StrikingOpener: Player
    NonStrikingOpener: Player
    OneDownBatsman: Player
    TwoDownBatsman: Player
    ThreeDownBatsman: Player
    FourDownBatsman: Player
    FiveDownBatsman: Player
    SixDownBatsman: Player
    SevenDownBatsman: Player
    EightDownBatsman: Player
    NineDownBatsman: Player
    PowerplayBowlers: List[Player]
    MiddleOversBowlers: List[Player]
    DeathOversBowlers: List[Player]
    PlayersNotInPlayingXI: List[Player] 
class AgentState(TypedDict):
    """State schema for the agent."""
    RemainingPlayers: Dict[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'],List[Player]]
    RemainingSets: List[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC']]
    CurrentSet: Union[Literal['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'], None]
    RemainingPlayersInSet: Union[List[Player], None]
    AuctionStatus: bool = False
    CurrentPlayer: Union[Player, None] = None
    CurrentBid: Union[CurrentBidInfo, None] = None
    OtherTeamBidding: Optional[CompetitiveBidInfo] = None
    Round :int = 0
    CSK: Union[List[Player],Team] = []
    DC: Union[List[Player],Team] = []
    GT: Union[List[Player],Team] = []
    KKR: Union[List[Player],Team] = []
    LSG: Union[List[Player],Team] = []
    MI: Union[List[Player],Team] = []
    PBKS: Union[List[Player],Team] = []
    RR: Union[List[Player],Team] = []
    RCB: Union[List[Player],Team] = []
    SRH: Union[List[Player],Team] = []
    UnsoldPlayers: List[Player] = []
    CSK_Budget: float
    DC_Budget: float
    GT_Budget: float
    KKR_Budget: float
    LSG_Budget: float
    MI_Budget: float
    PBKS_Budget: float
    RR_Budget: float
    RCB_Budget: float
    SRH_Budget: float
    Messages: Annotated[Sequence[Union[HumanMessage, AIMessage, ToolMessage, BaseMessage]], add_messages] 
class BidderInput(BaseModel):
    is_raise: bool = Field(default=False, description="Whether this bid is a raise or just a call. If not applicable, leave false.")
    is_normal: bool = Field(default=True, description="Whether this is a normal raise (fixed increment). If not applicable, false.")
    raised_amount: float = Field(default=0.0, description="The custom raise amount to add to the current price. If not applicable, 0.0.")
    reason: str = Field(default="", description="Short rationale for the decision. Empty string if none.")

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

        # Special handling for Team objects for a cleaner display
        if key in ['TeamA', 'TeamB', 'TeamC'] and isinstance(value, Team):
            print(f"  Team: {value.Name}")
            
            unique_players = set()

            def get_player_details_str(player: Player, include_in_count: bool = True) -> str:
                """Format a player string and optionally count toward playing XI."""
                if player:
                    if include_in_count:
                        unique_players.add(player.name)
                    return f"{player.name} ({player.role}, sold for {player.sold_price:.2f} Cr)"
                return "None"

            # Display each role and player
            for field_name, field_value in value.__dict__.items():
                if field_name == 'Name':
                    continue
                
                is_bench = field_name == 'PlayersNotInPlayingXI'

                if isinstance(field_value, Player):
                    print(f"  - {field_name}: {get_player_details_str(field_value, not is_bench)}")
                elif isinstance(field_value, list):
                    print(f"  - {field_name}:")
                    if not field_value:
                        print("    - (empty)")
                    else:
                        for player in field_value:
                            print(f"    - {get_player_details_str(player, not is_bench)}")

            num_unique_players = len(unique_players)
            print(f"\n  Unique Players in Team: {num_unique_players}")
            if num_unique_players > 11:
                print(f"  WARNING: Team has {num_unique_players} players, which is more than the typical 11.")

        elif key == "Messages":
            if not value:
                print("  (empty)")
            else:
                for i, msg in enumerate(value, 1):
                    print(f"  {i}. [{type(msg).__name__}] {msg.content}")
        
        elif isinstance(value, list):
            # Handles lists like UnsoldPlayers or initial empty team lists
            if not value:
                print("  (empty)")
            else:
                is_player_list = all(isinstance(item, Player) for item in value)
                for i, item in enumerate(value, 1):
                    if is_player_list:
                        print(f"  {i}. {item.name} ({item.role}) - INR {item.sold_price:.2f}Cr")
                    else:
                        print(f"  {i}. {item}")

        elif isinstance(value, dict):
            # Handles RemainingPlayers dictionary
            for set_name, players in value.items():
                if isinstance(players, list):
                    if players and isinstance(players[0], Player):
                        print(f"  {set_name}: {len(players)} players")
                    else:
                        print(f"  {set_name}: []")
                else:
                    print(f"  {set_name}: {players}")
        
        else:
            # Generic print for other types
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
                "is_normal": bool - Whether this is a normal raise (fixed increment). Only applicable if is_raise is True,
                "raised_amount": float - The custom raise amount. Only applicable if is_raise is True and is_normal is False
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
    # Load prompt filenames (case-insensitive) first
    files = [f for f in os.listdir(prompt_dir) if f.lower().endswith('.txt')]
    name_map = {os.path.splitext(f)[0].lower(): f for f in files}

    # If both global Sys and Human exist, use them for all teams and ignore other files
    if 'sys' in name_map and 'human' in name_map:
        prompts = {}
        sys_path = os.path.join(prompt_dir, name_map['sys'])
        human_path = os.path.join(prompt_dir, name_map['human'])
        with open(sys_path, 'r', encoding='utf-8') as f:
            sys_content = f.read()
        with open(human_path, 'r', encoding='utf-8') as f:
            human_content = f.read()

        # Apply to all teams
        for team in ['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH']:
            prompts[f"{team}_sys"] = sys_content
            prompts[f"{team}_human"] = human_content

        # Also expose generic keys for compatibility
        prompts['Sys'] = sys_content
        prompts['Human'] = human_content
        return prompts

    # Fallback: load all individual prompt files as before
    prompts = {}
    for filename in files:
        filepath = os.path.join(prompt_dir, filename)
        key_raw = os.path.splitext(filename)[0]
        # Keep capitalization of first char for backward compatibility
        key = key_raw[0].upper() + key_raw[1:] if key_raw else key_raw
        with open(filepath, 'r', encoding='utf-8') as f:
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
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        return f.read()
                except Exception:
                    # As a very tolerant fallback, read in binary and decode utf-8 ignoring
                    with open(filepath, "rb") as fb:
                        return fb.read().decode("utf-8", errors="ignore")
    return "Stats not found for this player."

SET_ABBREVIATION_MAPPING = {
    'SBC': "Star Batsman Capped",
    'SAC': "Star All-Rounder Capped",
    'SBwC': "Star Bowler Capped",
    'EBC': "Established Batsman Capped",
    'EAC': "Established All-Rounder Capped",
    'EBwC': "Established Bowler Capped",
    'MBC': "Mid-tier Batsman Capped",
    'MAC': "Mid-tier All-Rounder Capped",
    'MBwC': "Mid-tier Bowler Capped",
    'EmBwU': "Emerging Bowler Uncapped",
    'EmAU': "Emerging All-Rounder Uncapped",
    'EmBC': "Emerging Batsman Capped",
}

def get_set_name(set_abbreviation: Union[str, List[str]]) -> Union[str, List[str]]:
    """Converts a set abbreviation or a list of abbreviations to its full name."""
    if isinstance(set_abbreviation, list):
        return [SET_ABBREVIATION_MAPPING.get(abbr, "Unknown Set") for abbr in set_abbreviation]
    return SET_ABBREVIATION_MAPPING.get(set_abbreviation, "Unknown Set")

def safe_prin(s):
    print(s.encode('utf-8', errors='ignore').decode('utf-8'))

