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
    specialism: str
    batting_style: str
    bowling_style: str
    test_caps: int
    odi_caps: int
    t20_caps: int
    ipl_matches: int
    player_status: str
    reserve_price_lakh: float
    set: str
    stats: str = ""
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
    
class AgentState(TypedDict):
    """State schema for the agent."""
    RemainingPlayers: Dict[Literal['M1', 'M2', 'AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10', 'BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'FA1', 'FA2', 'FA3', 'FA4', 'FA5', 'FA6', 'FA7', 'FA8', 'FA9', 'FA10', 'SP1', 'SP2', 'SP3', 'WK1', 'WK2', 'WK3', 'WK4', 'UAL1', 'UAL2', 'UAL3', 'UAL4', 'UAL5', 'UAL6', 'UAL7', 'UAL8', 'UAL9', 'UAL10', 'UAL11', 'UAL12', 'UAL13', 'UAL14', 'UAL15', 'UBA1', 'UBA2', 'UBA3', 'UBA4', 'UBA5', 'UBA6', 'UBA7', 'UBA8', 'UBA9', 'UFA1', 'UFA2', 'UFA3', 'UFA4', 'UFA5', 'UFA6', 'UFA7', 'UFA8', 'UFA9', 'UFA10', 'USP1', 'USP2', 'USP3', 'USP4', 'USP5', 'UWK1', 'UWK2', 'UWK3', 'UWK4', 'UWK5', 'UWK6'],List[Player]]
    RemainingSets: List[Literal['M1', 'M2', 'AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10', 'BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'FA1', 'FA2', 'FA3', 'FA4', 'FA5', 'FA6', 'FA7', 'FA8', 'FA9', 'FA10', 'SP1', 'SP2', 'SP3', 'WK1', 'WK2', 'WK3', 'WK4', 'UAL1', 'UAL2', 'UAL3', 'UAL4', 'UAL5', 'UAL6', 'UAL7', 'UAL8', 'UAL9', 'UAL10', 'UAL11', 'UAL12', 'UAL13', 'UAL14', 'UAL15', 'UBA1', 'UBA2', 'UBA3', 'UBA4', 'UBA5', 'UBA6', 'UBA7', 'UBA8', 'UBA9', 'UFA1', 'UFA2', 'UFA3', 'UFA4', 'UFA5', 'UFA6', 'UFA7', 'UFA8', 'UFA9', 'UFA10', 'USP1', 'USP2', 'USP3', 'USP4', 'USP5', 'UWK1', 'UWK2', 'UWK3', 'UWK4', 'UWK5', 'UWK6']]
    CurrentSet: Union[Literal['M1', 'M2', 'AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10', 'BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'FA1', 'FA2', 'FA3', 'FA4', 'FA5', 'FA6', 'FA7', 'FA8', 'FA9', 'FA10', 'SP1', 'SP2', 'SP3', 'WK1', 'WK2', 'WK3', 'WK4', 'UAL1', 'UAL2', 'UAL3', 'UAL4', 'UAL5', 'UAL6', 'UAL7', 'UAL8', 'UAL9', 'UAL10', 'UAL11', 'UAL12', 'UAL13', 'UAL14', 'UAL15', 'UBA1', 'UBA2', 'UBA3', 'UBA4', 'UBA5', 'UBA6', 'UBA7', 'UBA8', 'UBA9', 'UFA1', 'UFA2', 'UFA3', 'UFA4', 'UFA5', 'UFA6', 'UFA7', 'UFA8', 'UFA9', 'UFA10', 'USP1', 'USP2', 'USP3', 'USP4', 'USP5', 'UWK1', 'UWK2', 'UWK3', 'UWK4', 'UWK5', 'UWK6'], None]
    RemainingPlayersInSet: Union[List[Player], None]
    AuctionStatus: bool = False
    CurrentPlayer: Union[Player, None] = None
    CurrentBid: Union[CurrentBidInfo, None] = None
    OtherTeamBidding: Optional[CompetitiveBidInfo] = None
    Round :int = 0
    CSK: List[Player] = []
    DC: List[Player] = []
    GT: List[Player] = []
    KKR: List[Player] = []
    LSG: List[Player] = []
    MI: List[Player] = []
    PBKS: List[Player] = []
    RR: List[Player] = []
    RCB: List[Player] = []
    SRH: List[Player] = []
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
            # Handles lists like UnsoldPlayers or initial empty team lists
            if not value:
                print("  (empty)")
            else:
                is_player_list = all(isinstance(item, Player) for item in value)
                for i, item in enumerate(value, 1):
                    if is_player_list:
                        print(f"  {i}. {item.name} ({item.specialism}) - INR {item.sold_price:.2f}Cr")
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
    if current_price < 1.0:
        return 0.05  # Raise by 5 lakh
    elif current_price < 2.0:
        return 0.10  # Raise by 10 lakh
    elif current_price < 5.0:
        return 0.20  # Raise by 20 lakh
    else:
        return 0.25  # Raise by 25 lakh

def competitiveBidMaker(team: Literal['CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', 'PBKS', 'RR', 'RCB', 'SRH'], player: Player, bid_decision: BidderInput) -> CompetitiveBidInfo:
    """Create a CompetitiveBidInfo object for a team's bid.
    
    Args:
        team: The team making the bid.
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

SET_ABBREVIATION_MAPPING = {
    # Marquee Sets
    'M1': "Marquee Set 1",
    'M2': "Marquee Set 2",
    
    # Capped Allrounders
    'AL1': "Allrounders Set 1",
    'AL2': "Allrounders Set 2",
    'AL3': "Allrounders Set 3",
    'AL4': "Allrounders Set 4",
    'AL5': "Allrounders Set 5",
    'AL6': "Allrounders Set 6",
    'AL7': "Allrounders Set 7",
    'AL8': "Allrounders Set 8",
    'AL9': "Allrounders Set 9",
    'AL10': "Allrounders Set 10",
    
    # Capped Batters
    'BA1': "Batters Set 1",
    'BA2': "Batters Set 2",
    'BA3': "Batters Set 3",
    'BA4': "Batters Set 4",
    'BA5': "Batters Set 5",
    
    # Capped Fast Bowlers
    'FA1': "Fast Bowlers Set 1",
    'FA2': "Fast Bowlers Set 2",
    'FA3': "Fast Bowlers Set 3",
    'FA4': "Fast Bowlers Set 4",
    'FA5': "Fast Bowlers Set 5",
    'FA6': "Fast Bowlers Set 6",
    'FA7': "Fast Bowlers Set 7",
    'FA8': "Fast Bowlers Set 8",
    'FA9': "Fast Bowlers Set 9",
    'FA10': "Fast Bowlers Set 10",
    
    # Capped Spinners
    'SP1': "Spinners Set 1",
    'SP2': "Spinners Set 2",
    'SP3': "Spinners Set 3",
    
    # Capped Wicketkeepers
    'WK1': "Wicketkeepers Set 1",
    'WK2': "Wicketkeepers Set 2",
    'WK3': "Wicketkeepers Set 3",
    'WK4': "Wicketkeepers Set 4",
    
    # Uncapped Allrounders
    'UAL1': "Uncapped Allrounders Set 1",
    'UAL2': "Uncapped Allrounders Set 2",
    'UAL3': "Uncapped Allrounders Set 3",
    'UAL4': "Uncapped Allrounders Set 4",
    'UAL5': "Uncapped Allrounders Set 5",
    'UAL6': "Uncapped Allrounders Set 6",
    'UAL7': "Uncapped Allrounders Set 7",
    'UAL8': "Uncapped Allrounders Set 8",
    'UAL9': "Uncapped Allrounders Set 9",
    'UAL10': "Uncapped Allrounders Set 10",
    'UAL11': "Uncapped Allrounders Set 11",
    'UAL12': "Uncapped Allrounders Set 12",
    'UAL13': "Uncapped Allrounders Set 13",
    'UAL14': "Uncapped Allrounders Set 14",
    'UAL15': "Uncapped Allrounders Set 15",
    
    # Uncapped Batters
    'UBA1': "Uncapped Batters Set 1",
    'UBA2': "Uncapped Batters Set 2",
    'UBA3': "Uncapped Batters Set 3",
    'UBA4': "Uncapped Batters Set 4",
    'UBA5': "Uncapped Batters Set 5",
    'UBA6': "Uncapped Batters Set 6",
    'UBA7': "Uncapped Batters Set 7",
    'UBA8': "Uncapped Batters Set 8",
    'UBA9': "Uncapped Batters Set 9",
    
    # Uncapped Fast Bowlers
    'UFA1': "Uncapped Fast Bowlers Set 1",
    'UFA2': "Uncapped Fast Bowlers Set 2",
    'UFA3': "Uncapped Fast Bowlers Set 3",
    'UFA4': "Uncapped Fast Bowlers Set 4",
    'UFA5': "Uncapped Fast Bowlers Set 5",
    'UFA6': "Uncapped Fast Bowlers Set 6",
    'UFA7': "Uncapped Fast Bowlers Set 7",
    'UFA8': "Uncapped Fast Bowlers Set 8",
    'UFA9': "Uncapped Fast Bowlers Set 9",
    'UFA10': "Uncapped Fast Bowlers Set 10",
    
    # Uncapped Spinners
    'USP1': "Uncapped Spinners Set 1",
    'USP2': "Uncapped Spinners Set 2",
    'USP3': "Uncapped Spinners Set 3",
    'USP4': "Uncapped Spinners Set 4",
    'USP5': "Uncapped Spinners Set 5",
    
    # Uncapped Wicketkeepers
    'UWK1': "Uncapped Wicketkeepers Set 1",
    'UWK2': "Uncapped Wicketkeepers Set 2",
    'UWK3': "Uncapped Wicketkeepers Set 3",
    'UWK4': "Uncapped Wicketkeepers Set 4",
    'UWK5': "Uncapped Wicketkeepers Set 5",
    'UWK6': "Uncapped Wicketkeepers Set 6",
}

def get_set_name(set_abbreviation: Union[str, List[str]]) -> Union[str, List[str]]:
    """Converts a set abbreviation or a list of abbreviations to its full name."""
    if isinstance(set_abbreviation, list):
        return [SET_ABBREVIATION_MAPPING.get(abbr, "Unknown Set") for abbr in set_abbreviation]
    return SET_ABBREVIATION_MAPPING.get(set_abbreviation, "Unknown Set")
