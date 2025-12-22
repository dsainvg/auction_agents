from utils import AgentState
from typing import Literal

def host(state: AgentState) -> Literal["host_assistant", "bidder_pool", "team_manager"]:
    """Host function to route to host_assistant, bidder_pool, or END."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    remaining_sets_len = len(state.get('RemainingSets') or [])
    current_player_name = getattr(state.get('CurrentPlayer'), 'name', None)
    auction_status = state.get('AuctionStatus')
    print(f"[HOST] Entered host(state) - RemainingSets={remaining_sets_len}, CurrentPlayer={current_player_name}, AuctionStatus={auction_status}", flush=True)

    # Decide route
    if not state.get('RemainingSets') and not state.get('RemainingPlayersInSet') and not state.get('CurrentPlayer'):
        next_node = "team_manager"
    elif state.get('AuctionStatus', False) is False:
        next_node = "host_assistant"
    else:
        next_node = "bidder_pool"

    # Log routing decision for easier debugging
    print(f"[HOST] Routing decision: {next_node}", flush=True)
    return next_node

