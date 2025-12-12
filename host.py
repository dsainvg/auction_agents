import logging
from utils import AgentState
from typing import Literal

logger = logging.getLogger(__name__)

def host(state: AgentState) -> Literal["host_assistant", "bidder_pool", "__end__"]:
    """Host function to route to host_assistant, bidder_pool, or END."""
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    logger.info("="*60)
    logger.info("HOST ROUTING DECISION")
    logger.info(f"AuctionStatus: {state.get('AuctionStatus')}")
    logger.info(f"CurrentPlayer: {state.get('CurrentPlayer').name if state.get('CurrentPlayer') else None}")
    logger.info(f"CurrentBid: {state.get('CurrentBid')}")
    logger.info(f"Round: {state.get('Round')}")
    logger.info(f"RemainingSets: {len(state.get('RemainingSets', []))} sets")
    logger.info(f"RemainingPlayersInSet: {len(state.get('RemainingPlayersInSet', [])) if state.get('RemainingPlayersInSet') else 0} players")
    
    # Check if auction is complete (no more players or sets)
    if not state.get('RemainingSets') and not state.get('RemainingPlayersInSet') and not state.get('CurrentPlayer'):
        logger.info("ROUTING TO: __end__ (auction complete)")
        logger.info("="*60)
        return "__end__"
    
    # Route to host_assistant if auction is inactive (need new player)
    if state.get('AuctionStatus', False) is False:
        logger.info("ROUTING TO: host_assistant (need new player)")
        logger.info("="*60)
        return "host_assistant"
    
    # Route to bidder_pool for active auction
    logger.info("ROUTING TO: bidder_pool (active auction)")
    logger.info("="*60)
    return "bidder_pool"

