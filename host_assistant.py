from utils import AgentState
import random

def host_assistant(state: AgentState) -> AgentState:
    """Host assistant function to update the agent state with current player selection."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    print("\n" + "="*60)
    print("HOST ASSISTANT - Selecting Player")
    
    # Select a new set if current set is None or empty
    if state["CurrentSet"] is None or not state.get("RemainingPlayersInSet"):
        # Find a set with players
        available_sets = [s for s in state["RemainingSets"] if state["RemainingPlayers"].get(s)]
        print(f"Available sets with players: {available_sets}")
        
        if not available_sets:
            # No more players to auction
            print("No more players available!")
            print("="*60)
            return state
        
        # Update RemainingSets to only include available sets
        state["RemainingSets"] = available_sets.copy()
        print(f"Updated RemainingSets to: {state['RemainingSets']}")
        
        state["CurrentSet"] = random.choice(available_sets)
        state["RemainingPlayersInSet"] = state["RemainingPlayers"][state["CurrentSet"]].copy()
        state['RemainingSets'].remove(state["CurrentSet"])
        print(f"Selected set: {state['CurrentSet']}")
        print(f"Players in set: {len(state['RemainingPlayersInSet'])}")
    
    # Select a player from the current set
    if state['RemainingPlayersInSet']:
        state['CurrentPlayer'] = random.choice(state['RemainingPlayersInSet'])
        state['RemainingPlayersInSet'].remove(state['CurrentPlayer'])
        state['AuctionStatus'] = True
        print(f"Selected player: {state['CurrentPlayer'].name} ({state['CurrentPlayer'].role})")
        print(f"Base price: ₹{state['CurrentPlayer'].base_price:.2f} Cr")
        print(f"Remaining players in set: {len(state['RemainingPlayersInSet'])}")
    
    print("="*60)
    return state