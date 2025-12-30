from utils import AgentState, AIMessage
import random

def host_assistant(state: AgentState) -> AgentState:
    """Host assistant function to update the agent state with current player selection."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    print(f"[HOST_ASSISTANT] Entered host_assistant(state) - RemainingSets={len(state.get('RemainingSets') or [])}, CurrentSet={state.get('CurrentSet')}, AuctionStatus={state.get('AuctionStatus')}", flush=True)
    
    message_lines = []
    message_lines.append("="*60)
    message_lines.append("HOST ASSISTANT - Selecting Player")
    
    # Select a new set if current set is None or empty
    if state["CurrentSet"] is None or not state.get("RemainingPlayersInSet"):
        # Find a set with players
        available_sets = [s for s in state["RemainingSets"] if state["RemainingPlayers"].get(s)]
        message_lines.append(f"Available sets with players: {available_sets}")
        
        
        
        # Update RemainingSets to only include available sets
        state["RemainingSets"] = available_sets.copy()
        message_lines.append(f"Updated RemainingSets to: {state['RemainingSets']}")
        if not available_sets:
            # No more players to auction - clear all state
            message_lines.append("No more players available!")
            state["CurrentSet"] = None
            state["RemainingPlayersInSet"] = None
            state["CurrentPlayer"] = None
            state["AuctionStatus"] = False
            message_lines.append("="*60)
            joined = "\n".join(message_lines).replace('\u20b9', 'INR ')
            print("[HOST_ASSISTANT] Message:\n" + joined, flush=True)
            state["Messages"] = [AIMessage(content=joined)]
            return state
        state["CurrentSet"] = random.choice(available_sets)
        state["RemainingPlayersInSet"] = state["RemainingPlayers"][state["CurrentSet"]].copy()
        state['RemainingSets'].remove(state["CurrentSet"])
        state["RemainingPlayers"][state["CurrentSet"]] = []
        message_lines.append(f"Selected set: {state['CurrentSet']}")
        message_lines.append(f"Players in set: {len(state['RemainingPlayersInSet'])}")
    
    # Select a player from the current set
    if state['RemainingPlayersInSet']:
        state['CurrentPlayer'] = random.choice(state['RemainingPlayersInSet'])
        state['RemainingPlayersInSet'].remove(state['CurrentPlayer'])
        state['AuctionStatus'] = True
        message_lines.append(f"Selected player: {state['CurrentPlayer'].name} ({state['CurrentPlayer'].specialism})")
        reserve_cr = state['CurrentPlayer'].reserve_price_lakh / 100
        message_lines.append(f"Reserve price: INR {reserve_cr:.2f} Cr")
        message_lines.append(f"Remaining players in set: {len(state['RemainingPlayersInSet'])}")
        
        # Clear RemainingPlayersInSet if empty
        if not state['RemainingPlayersInSet']:
            state['RemainingPlayersInSet'] = None
            message_lines.append("Set completed - cleared RemainingPlayersInSet")
    
    message_lines.append("="*60)
    joined = "\n".join(message_lines).replace('\u20b9', 'INR ')
    print("[HOST_ASSISTANT] Message:\n" + joined, flush=True)
    state["Messages"] = [AIMessage(content=joined)]
    return state