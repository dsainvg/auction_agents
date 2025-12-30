from utils import AgentState, CurrentBidInfo, get_raise_amount, AIMessage
from reasoner import generate_purchase_reason

def trademaster(state: AgentState) -> AgentState:
    """Trade master function optimized to process single bid from agent pool.
    
    Process:
    1. Processes single bid from OtherTeamBidding (no longer a dict)
    2. For first bid, minimum raise is zero (can bid at base price)
    3. Updates CurrentBid or finalizes auction based on round limits
    """
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    message_lines = []
    message_lines.append("\n" + "="*60)
    message_lines.append("TRADEMASTER - Processing Bids")
    
    # Get current bidding information - now single bid instead of dict
    other_bid = state.get("OtherTeamBidding")  # Single CompetitiveBidInfo or None
    current_bid_obj = state.get("CurrentBid")  # CurrentBidInfo object or None
    current_round = state.get("Round", 0)
    current_player = state.get("CurrentPlayer")
    
    message_lines.append(f"Player: {current_player.name if current_player else 'None'}")
    message_lines.append(f"Current Round: {current_round}")
    message_lines.append(f"Current Bid: {f'INR {current_bid_obj.current_bid_amount:.2f} by {current_bid_obj.team}' if current_bid_obj else 'None'}")
    message_lines.append(f"New Bid: {f'{other_bid.team} - raise={other_bid.is_raise}' if other_bid else 'None'}")
    
    if not current_player:
        message_lines.append("No current player, returning")
        message_lines.append("="*60)
        print("[TRADEMASTER] Message:\n" + "\n".join(message_lines), flush=True)
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state
    
    # Case 1: No current bid AND no other bid → player goes directly to unsold
    if (current_bid_obj is None) and (other_bid is None):
        message_lines.append("\nCASE 1: No bids at all - Player UNSOLD")
        state["UnsoldPlayers"].append(current_player)
        message_lines.append(f"Added {current_player.name} to UnsoldPlayers")
        
        # Reset for next player
        state["CurrentPlayer"] = None
        state['AuctionStatus'] = False
        state["CurrentBid"] = None
        state["Round"] = 1
        state["OtherTeamBidding"] = None
        message_lines.append("Reset state for next player")
        message_lines.append("="*60)
        
        print("[TRADEMASTER] Message:\n" + "\n".join(message_lines), flush=True)
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state
    
    # Case 2: No new bid this round
    if other_bid is None:
        message_lines.append("\nCASE 2: No new bid this round")
        state["Round"] = current_round + 1
        message_lines.append(f"Incrementing round to {state['Round']}")
        state["OtherTeamBidding"] = None
        
        # Check if round limit reached
        if state["Round"] > 2:
            message_lines.append("Round limit exceeded (>2)")
            current_bid_final = state.get("CurrentBid")
            
            if current_player and current_bid_final and current_bid_final.team:
                # Finalize the sale
                player = current_player
                winning_team = current_bid_final.team
                
                # Get final price from CurrentBidInfo
                final_price = current_bid_final.current_bid_amount
                
                # Update player status
                player.status = True
                player.sold_price = final_price
                player.sold_team = winning_team
                # If round > 2, generate AI reason and suggestions for the purchase
                try:
                    reason_text = generate_purchase_reason(state, player, winning_team, final_price)
                    player.reason_for_purchase = reason_text
                    message_lines.append(f"AI Reason+Suggestions: {reason_text}")
                except Exception as e:
                    message_lines.append(f"AI reasoner error: {e}")
                
                # Add player to winning team
                if winning_team in state:
                    state[winning_team].append(player)
                
                # Deduct from team budget
                budget_key = f"{winning_team}_Budget"
                if budget_key in state:
                    state[budget_key] -= final_price
                
                # Move to next player
                state["CurrentPlayer"] = None
                state["CurrentBid"] = None
                state["Round"] = 1
                state["OtherTeamBidding"] = None
                state['AuctionStatus'] = False
            else:
                # No CurrentBid and Round > 2, player goes unsold
                state["UnsoldPlayers"].append(current_player)
                state["CurrentPlayer"] = None
                state["CurrentBid"] = None
                state["Round"] = 1
                state["OtherTeamBidding"] = None
                state['AuctionStatus'] = False
        
        print("[TRADEMASTER] Message:\n" + "\n".join(message_lines), flush=True)
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state
    
    # Case 3: Process the new bid
    else:
        message_lines.append("\nCASE 3: Processing new bid")
        team_name = other_bid.team
        budget_key = f"{team_name}_Budget"
        team_budget = state.get(budget_key, 0.0)
        
        # Calculate bid amount
        if current_bid_obj is None:
            # First bid - minimum raise is zero
            current_price = current_player.reserve_price_lakh / 100  # Convert lakhs to crores
            if other_bid.is_raise:
                if other_bid.is_normal:
                    bid_amount = current_price  # First bid at base price
                else:
                    bid_amount = current_price + other_bid.raised_amount
            else:
                message_lines.append("Invalid bid - not a raise")
                state["OtherTeamBidding"] = None
                return state
        else:
            # Subsequent bid - normal raise rules apply
            current_price = current_bid_obj.current_bid_amount
            if other_bid.is_raise:
                if other_bid.is_normal:
                    raise_amt = get_raise_amount(current_price)
                    bid_amount = current_price + raise_amt
                else:
                    min_required = get_raise_amount(current_price)
                    if other_bid.raised_amount >= min_required:
                        bid_amount = current_price + other_bid.raised_amount
                    else:
                        message_lines.append(f"Invalid custom raise: {other_bid.raised_amount} < {min_required}")
                        state["Round"] = current_round + 1
                        state["OtherTeamBidding"] = None
                        return state
            else:
                message_lines.append("Invalid bid - not a raise")
                state["OtherTeamBidding"] = None
                return state
        
        # Validate budget
        if bid_amount <= team_budget:
            # Valid bid - update CurrentBid
            next_raise_amt = get_raise_amount(bid_amount)
            new_current_bid = CurrentBidInfo(
                player=current_player,
                team=team_name,
                current_bid_amount=bid_amount,
                current_raise_amount=next_raise_amt
            )
            state["CurrentBid"] = new_current_bid
            state["Round"] = 0
            message_lines.append(f"Bid accepted: {team_name} bids {bid_amount:.2f} Cr")
        else:
            message_lines.append(f"Bid rejected: {bid_amount:.2f} > budget {team_budget:.2f}")
            state["Round"] = current_round + 1
        
        state["OtherTeamBidding"] = None
        message_lines.append("="*60)
        print("[TRADEMASTER] Message:\n" + "\n".join(message_lines), flush=True)
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state