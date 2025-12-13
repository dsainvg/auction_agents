from utils import AgentState, CurrentBidInfo, get_raise_amount, AIMessage

def trademaster(state: AgentState) -> AgentState:
    """Trade master function to manage trades and update the agent state accordingly.
    
    Process:
    0. Checks if bid is valid.
    1. Checks OtherTeamsBidding for the best bid and updates CurrentBid accordingly.
    2. If no best bid is found, leaves CurrentBid unchanged and increments Round by 1.
    3. If Round exceeds the limit (3), finalizes the auction for the current player by:
       - Assigning the player to the winning team
       - Deducting the bid amount from the team's budget
       - Marking the player as sold
       - Adding unsold players to the UnsoldPlayers list
    """
    if not state:
        raise ValueError("State cannot be None or empty.")
    
    message_lines = []
    message_lines.append("\n" + "="*60)
    message_lines.append("TRADEMASTER - Processing Bids")
    
    # Get current bidding information
    other_bids = state.get("OtherTeamBidding", {})  # Dict[team, CompetitiveBidInfo]
    current_bid_obj = state.get("CurrentBid")  # CurrentBidInfo object or None
    current_round = state.get("Round", 0)
    current_player = state.get("CurrentPlayer")
    
    message_lines.append(f"Player: {current_player.name if current_player else 'None'}")
    message_lines.append(f"Current Round: {current_round}")
    message_lines.append(f"Current Bid: {f'₹{current_bid_obj.current_bid_amount:.2f} by {current_bid_obj.team}' if current_bid_obj else 'None'}")
    message_lines.append(f"Other Bids Received: {len(other_bids)}")
    for team, bid in other_bids.items():
        message_lines.append(f"  - {team}: is_raise={bid.is_raise}, is_normal={bid.is_normal}, raised_amount={bid.raised_amount}")
    
    if not current_player:
        message_lines.append("No current player, returning")
        message_lines.append("="*60)
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state
    
    # Case 1: No current bid AND no other bids → player goes directly to unsold
    if (current_bid_obj is None) and (not other_bids or len(other_bids) == 0):
        message_lines.append("\nCASE 1: No bids at all - Player UNSOLD")
        # Player unsold - add to UnsoldPlayers
        state["UnsoldPlayers"].append(current_player)
        message_lines.append(f"Added {current_player.name} to UnsoldPlayers")
        
        # Move to next player
        state["CurrentPlayer"] = None
        state['AuctionStatus'] = False
        state["CurrentBid"] = None
        state["Round"] = 0
        state["OtherTeamBidding"] = {}
        message_lines.append("Reset state for next player")
        message_lines.append("="*60)
        
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state
    
    # Case 2: Check if there are any new bids
    if not other_bids or len(other_bids) == 0:
        message_lines.append("\nCASE 2: No new bids this round")
        # No bids received, increment round
        state["Round"] = current_round + 1
        message_lines.append(f"Incrementing round to {state['Round']}")
        # Clear the bidding dict for next round
        state["OtherTeamBidding"] = {}
        
        # Check if round limit reached
        if state["Round"] > 3:
            message_lines.append("Round limit exceeded (>3)")
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
                state["OtherTeamBidding"] = {}
                state['AuctionStatus'] = False
            else:
                # No CurrentBid and Round > 3, player goes unsold
                state["UnsoldPlayers"].append(current_player)
                state["CurrentPlayer"] = None
                state["CurrentBid"] = None
                state["Round"] = 1
                state["OtherTeamBidding"] = {}
                state['AuctionStatus'] = False
        
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state
    
    # Case 3: There are other bids to process
    else:
        message_lines.append("\nCASE 3: Processing new bids")
        # Check if CurrentBid exists
        if current_bid_obj is None:
            message_lines.append("No current bid - selecting first bid")
            # No current bid, process bids starting from base price with priorities
            current_bid_amount = current_player.base_price
            
            # Find valid bids and prioritize custom raises (is_normal=False)
            valid_bids = {}
            
            for team_name, competitive_bid in other_bids.items():
                budget_key = f"{team_name}_Budget"
                team_budget = state.get(budget_key, 0.0)
                
                # Calculate bid amount from CompetitiveBidInfo object
                if competitive_bid.is_raise:
                    if competitive_bid.is_normal:
                        # Normal increment using get_raise_amount function
                        raise_amt = get_raise_amount(current_bid_amount)
                        bid_amount = current_bid_amount + raise_amt
                    else:
                        # Custom raise amount
                        if competitive_bid.raised_amount:
                            bid_amount = current_bid_amount + competitive_bid.raised_amount
                        else:
                            continue  # Invalid bid, skip
                else:
                    # Not a raise, invalid
                    continue
                
                # Validate bid: must be higher than or equal to base price and within team budget
                if bid_amount >= current_bid_amount and bid_amount <= team_budget:
                    valid_bids[team_name] = (competitive_bid, bid_amount)
            
            # Find the best valid bid - prioritize custom raises
            best_competitive_bid = None
            best_bid_amount = None
            best_team = None
            
            # First, check if there's a custom raise (is_normal=False)
            for team_name, (competitive_bid, bid_amount) in valid_bids.items():
                if not competitive_bid.is_normal:
                    if best_bid_amount is None or bid_amount > best_bid_amount:
                        best_bid_amount = bid_amount
                        best_competitive_bid = competitive_bid
                        best_team = team_name
            
            # If no custom raise, take any valid bid
            if best_competitive_bid is None:
                for team_name, (competitive_bid, bid_amount) in valid_bids.items():
                    if best_bid_amount is None or bid_amount > best_bid_amount:
                        best_bid_amount = bid_amount
                        best_competitive_bid = competitive_bid
                        best_team = team_name
            
            # Create CurrentBid from best valid bid
            if best_competitive_bid is not None:
                next_raise_amt = get_raise_amount(best_bid_amount)
                
                new_current_bid = CurrentBidInfo(
                    player=current_player,
                    team=best_team,
                    current_bid_amount=best_bid_amount,
                    current_raise_amount=next_raise_amt
                )
                state["CurrentBid"] = new_current_bid
                state["Round"] = 0
                message_lines.append(f"First bid accepted: {best_team} bids ₹{best_bid_amount:.2f} Cr")
            else:
                message_lines.append("No valid bids found")
            
            state["OtherTeamBidding"] = {}
            message_lines.append("="*60)
            state["Messages"] = [AIMessage(content="\n".join(message_lines))]
            return state
        
        else:
            message_lines.append(f"Current bid exists: ₹{current_bid_obj.current_bid_amount:.2f} by {current_bid_obj.team}")
            # Current bid exists, process the other bids (max 2)
            current_bid_amount = current_bid_obj.current_bid_amount
            
            # Find valid bids and prioritize custom raises (is_normal=False)
            valid_bids = {}
            
            for team_name, competitive_bid in other_bids.items():
                budget_key = f"{team_name}_Budget"
                team_budget = state.get(budget_key, 0.0)
                
                # Calculate bid amount from CompetitiveBidInfo object
                if competitive_bid.is_raise:
                    if competitive_bid.is_normal:
                        # Normal increment using get_raise_amount function
                        raise_amt = get_raise_amount(current_bid_amount)
                        bid_amount = current_bid_amount + raise_amt
                    else:
                        # Custom raise amount
                        if competitive_bid.raised_amount:
                            bid_amount = current_bid_amount + competitive_bid.raised_amount
                        else:
                            continue  # Invalid bid, skip
                else:
                    # Not a raise, invalid
                    continue
                
                # Validate bid: must be higher than current bid and within team budget
                if bid_amount > current_bid_amount and bid_amount <= team_budget:
                    valid_bids[team_name] = (competitive_bid, bid_amount)
            
            # Find the best valid bid - prioritize custom raises
            best_competitive_bid = None
            best_bid_amount = None
            best_team = None
            
            # First, check if there's a custom raise (is_normal=False)
            for team_name, (competitive_bid, bid_amount) in valid_bids.items():
                if not competitive_bid.is_normal:
                    if best_bid_amount is None or bid_amount > best_bid_amount:
                        best_bid_amount = bid_amount
                        best_competitive_bid = competitive_bid
                        best_team = team_name
            
            # If no custom raise, take any valid bid
            if best_competitive_bid is None:
                for team_name, (competitive_bid, bid_amount) in valid_bids.items():
                    if best_bid_amount is None or bid_amount > best_bid_amount:
                        best_bid_amount = bid_amount
                        best_competitive_bid = competitive_bid
                        best_team = team_name
            
            # Update state based on best bid
            if best_competitive_bid is not None:
                # Calculate raise amount for next bid
                next_raise_amt = get_raise_amount(best_bid_amount)
                
                # Create new CurrentBidInfo from the best competitive bid
                new_current_bid = CurrentBidInfo(
                    player=current_player,
                    team=best_team,
                    current_bid_amount=best_bid_amount,
                    current_raise_amount=next_raise_amt
                )
                state["CurrentBid"] = new_current_bid
                state["Round"] = 0
                message_lines.append(f"Bid updated: {best_team} raises to ₹{best_bid_amount:.2f} Cr")
            else:
                # Bids received but none were valid, increment round
                state["Round"] = current_round + 1
                message_lines.append(f"No valid counter-bids, incrementing round to {state['Round']}")
            
            # Clear the bidding dict for next round
            state["OtherTeamBidding"] = {}
            message_lines.append("="*60)
            
            state["Messages"] = [AIMessage(content="\n".join(message_lines))]
            return state
    
    message_lines.append("="*60)
    state["Messages"] = [AIMessage(content="\n".join(message_lines))]
    return state

