from utils import AgentState
from typing import Literal

def host(state: AgentState) -> Literal["host_assistant", "bidder_pool", "__end__"]:
    """Host function to route to host_assistant, bidder_pool, or END."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    print("\n" + "="*60)
    print("HOST ROUTING DECISION")
    print(f"AuctionStatus: {state.get('AuctionStatus')}")
    print(f"CurrentPlayer: {state.get('CurrentPlayer').name if state.get('CurrentPlayer') else None}")
    print(f"CurrentBid: {state.get('CurrentBid')}")
    print(f"Round: {state.get('Round')}")
    print(f"RemainingSets: {len(state.get('RemainingSets', []))} sets")
    print(f"RemainingPlayersInSet: {len(state.get('RemainingPlayersInSet', [])) if state.get('RemainingPlayersInSet') else 0} players")
    
    # Check if auction is complete (no more players or sets)
    if not state.get('RemainingSets') and not state.get('RemainingPlayersInSet') and not state.get('CurrentPlayer'):
        print("ROUTING TO: __end__ (auction complete)")
        print("="*60)
        return "__end__"
    
    # Route to host_assistant if auction is inactive (need new player)
    if state.get('AuctionStatus', False) is False:
        print("ROUTING TO: host_assistant (need new player)")
        print("="*60)
        return "host_assistant"
    
    # Route to bidder_pool for active auction
    print("ROUTING TO: bidder_pool (active auction)")
    print("="*60)
    return "bidder_pool"

