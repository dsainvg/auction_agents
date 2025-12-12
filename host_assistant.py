import logging
from utils import AgentState
import random

logger = logging.getLogger(__name__)

def host_assistant(state: AgentState) -> AgentState:
    """Host assistant function to update the agent state with current player selection."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    logger.info("="*60)
    logger.info("HOST ASSISTANT - Selecting Player")
    
    # Select a new set if current set is None or empty
    if state["CurrentSet"] is None or not state.get("RemainingPlayersInSet"):
        # Find a set with players
        available_sets = [s for s in state["RemainingSets"] if state["RemainingPlayers"].get(s)]
        logger.info(f"Available sets with players: {available_sets}")
        
        if not available_sets:
            # No more players to auction
            logger.info("No more players available!")
            logger.info("="*60)
            return state
        
        # Update RemainingSets to only include available sets
        state["RemainingSets"] = available_sets.copy()
        logger.info(f"Updated RemainingSets to: {state['RemainingSets']}")
        
        state["CurrentSet"] = random.choice(available_sets)
        state["RemainingPlayersInSet"] = state["RemainingPlayers"][state["CurrentSet"]].copy()
        state['RemainingSets'].remove(state["CurrentSet"])
        logger.info(f"Selected set: {state['CurrentSet']}")
        logger.info(f"Players in set: {len(state['RemainingPlayersInSet'])}")
    
    # Select a player from the current set
    if state['RemainingPlayersInSet']:
        state['CurrentPlayer'] = random.choice(state['RemainingPlayersInSet'])
        state['RemainingPlayersInSet'].remove(state['CurrentPlayer'])
        state['AuctionStatus'] = True
        logger.info(f"Selected player: {state['CurrentPlayer'].name} ({state['CurrentPlayer'].role})")
        logger.info(f"Base price: ₹{state['CurrentPlayer'].base_price:.2f} Cr")
        logger.info(f"Remaining players in set: {len(state['RemainingPlayersInSet'])}")
    
    logger.info("="*60)
    return state