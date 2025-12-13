from typing import Optional, Literal
from time import sleep
from typing_extensions import Annotated

from utils import AgentState, CompetitiveBidInfo
from gemini import GeminiClient, decide_bid
from langgraph.prebuilt import InjectedState

import logging
import random

logger = logging.getLogger(__name__)

def bidder(team_id: Literal["TeamA", "TeamB", "TeamC"], is_raise: bool, is_normal: Optional[bool], raised_amount: Optional[float], state: AgentState) -> CompetitiveBidInfo:
    """Generate a competitive bid info based on the provided arguments and current agent state.

    Args:
        team_id: The team making the bid ('TeamA', 'TeamB', 'TeamC').
        is_raise: Whether this bid is a raise.
        is_normal: Whether this is a normal raise (fixed increment). Only applicable if is_raise is True.
        raised_amount: The custom raise amount. Only applicable if is_raise is True and is_normal is False.
        state: Current AgentState containing `CurrentPlayer`.

    Returns:
        CompetitiveBidInfo instance with `player` populated from the state.

    Raises:
        ValueError: If validation checks fail for is_raise, is_normal, and raised_amount combinations.
    """
    current_player = state.get("CurrentPlayer")
    if not current_player:
        raise ValueError("No CurrentPlayer in state to create a bid for.")

    # Validation checks
    if not is_raise:
        # If not a raise, is_normal and raised_amount should not be set (or at least raised_amount shouldn't be)
        if raised_amount is not None:
             raise ValueError("raised_amount must be None when is_raise is False.")
        # We can enforce is_normal is None, or just ignore it. Let's enforce consistency.
        if is_normal is not None:
             # Depending on strictness, we might allow it but it's cleaner to say it should be None
             pass 
    else:
        # is_raise is True
        if is_normal is None:
             raise ValueError("is_normal must be specified (True/False) when is_raise is True.")
        
        if is_normal:
            if raised_amount is not None:
                raise ValueError("raised_amount must be None when is_normal is True.")
        else:
            if raised_amount is None:
                raise ValueError("raised_amount must be provided when is_normal is False.")
            if raised_amount <= 0:
                raise ValueError("raised_amount must be positive.")

    return CompetitiveBidInfo(
        player=current_player,
        team=team_id,
        is_raise=is_raise,
        is_normal=is_normal,
        raised_amount=raised_amount
    )


def agent_pool(state: AgentState) -> AgentState:
    """Agent pool node with three team agents that can bid on current player.
    
    Only teams who are NOT the current bid holder will be called.
    If there's no current bid, all teams can bid.
    Adds bids to state["OtherTeamBidding"].
    """
    current_player = state.get("CurrentPlayer")
    if not current_player:
        logger.info("AGENT POOL: No current player, skipping")
        return state
    
    current_bid = state.get("CurrentBid")
    current_bid_team = current_bid.team if current_bid else None
    
    logger.info("="*60)
    logger.info("AGENT POOL - Bidding Round")
    logger.info(f"Player: {current_player.name}")
    logger.info(f"Current bid: {f'INR {current_bid.current_bid_amount:.2f} by {current_bid.team}' if current_bid else 'No bids yet'}")
    logger.info(f"Round: {state.get('Round')}")
    
    # Initialize OtherTeamBidding if needed
    if state.get("OtherTeamBidding") is None:
        state["OtherTeamBidding"] = {}
    else:
        # Clear previous bids for this round
        state["OtherTeamBidding"] = {}
    
    # Simplified: Each team makes a basic bidding decision
    # For now, teams will bid with 50% probability and use normal raise
    teams = ["TeamA", "TeamB", "TeamC"]
    
    logger.info(f"Current bid holder: {current_bid_team if current_bid_team else 'None'}")
    logger.info("Teams evaluating bids:")
    
    current_price = current_bid.current_bid_amount if current_bid else current_player.base_price

    for team_id in teams:
        # Skip if this team is the current bid holder
        if current_bid_team == team_id:
            logger.info(f"  {team_id}: Skipped (current bid holder)")
            continue
        
        team_budget = state.get(f'{team_id}_Budget', 0)
        
        # Intelligent bidding logic using gemini.decide_bid
        will_bid = decide_bid(team_budget, current_price, current_player.base_price)
        
        logger.info(f"  {team_id}: Budget=INR {team_budget:.2f} Cr, Price=INR {current_price:.2f} Cr, Will bid={will_bid}")
        
        if will_bid:
            try:
                # Place a normal raise bid
                bid_info = bidder(
                    team_id=team_id,
                    is_raise=True,
                    is_normal=True,
                    raised_amount=None,
                    state=state
                )
                state["OtherTeamBidding"][team_id] = bid_info
                logger.info(f"    [+] {team_id} placed a bid!")
            except Exception as e:
                logger.error(f"    [x] Error creating bid for {team_id}: {e}")
    
    logger.info(f"Total bids received: {len(state['OtherTeamBidding'])}")
    logger.info("="*60)
    return state

