from utils import AgentState
from typing import Literal

def host(state: AgentState) -> Literal["host_assistant", "bidder_pool", "__end__"]:
    """Host function to route to host_assistant, bidder_pool, or END."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    # Check if auction is complete (no more players or sets)
    if not state.get('RemainingSets') and not state.get('RemainingPlayersInSet') and not state.get('CurrentPlayer'):
        return "__end__"
    
    # Route to host_assistant if auction is inactive (need new player)
    if state.get('AuctionStatus', False) is False:
        return "host_assistant"
    
    # Route to bidder_pool for active auction
    return "bidder_pool"

