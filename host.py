from utils import AgentState, Player
from typing import Literal

def host(state: AgentState) -> Literal["host_assistant", "bidder_pool", "end"]:
    """Host function to route to host_assistant, bidder_pool, or END."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    remaining_sets = state.get('RemainingSets') or []
    remaining_in_set = state.get('RemainingPlayersInSet') or []
    current_player = state.get('CurrentPlayer')
    auction_status = state.get('AuctionStatus')
    
    print(f"[HOST] RemainingSets={len(remaining_sets)}, RemainingInSet={len(remaining_in_set)}, CurrentPlayer={getattr(current_player, 'name', None)}, AuctionStatus={auction_status}", flush=True)

    # Route to end if all sets and players are done
    if not remaining_sets and not remaining_in_set and not current_player:
        print(f"[HOST] Routing to end - auction complete", flush=True)
        return "end"
    
    # Route to host_assistant if auction not started
    if not auction_status:
        print(f"[HOST] Routing to host_assistant - starting new set/player", flush=True)
        return "host_assistant"
    
    # Route to bidder_pool if auction is active
    print(f"[HOST] Routing to bidder_pool - auction active", flush=True)
    return "bidder_pool"

