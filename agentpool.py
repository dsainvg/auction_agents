import string
from utils import (
    AgentState, 
    AIMessage,
    competitiveBidMaker, 
    get_next_api_key,
    load_prompts,
    get_raise_amount,
    BidderInput,
    get_set_name
)
import json
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import HumanMessage, SystemMessage
from model_config import MODEL_NAME, TEMPERATURE, TOP_P, MAX_TOKENS, EXTRA_BODY, WAIT_BETWEEN_REQUESTS
import time
import random


def agent_pool(state: AgentState) -> AgentState:
    """
    Agent pool node that processes teams sequentially and returns the FIRST bid found.
    Optimized for speed - stops immediately when any team raises a bid.
    For first bid, minimum raise is zero (can bid at base price).
    """
    prompts = load_prompts()
    message_lines = []
    current_player = state.get("CurrentPlayer")
    if not current_player:
        print("[AGENT_POOL] No current player, skipping", flush=True)
        state["Messages"] = [AIMessage(content="AGENT POOL: No current player, skipping")]
        return state
    
    current_bid = state.get("CurrentBid")
    current_bid_team = current_bid.team if current_bid else None
    
    message_lines.append("="*60)
    message_lines.append("AGENT POOL - Bidding Round")
    message_lines.append(f"Player: {current_player.name} ({current_player.specialism})")
    message_lines.append(f"Reserve Price: {current_player.reserve_price_lakh / 100:.2f} Cr")
    message_lines.append(f"Current bid: {f'INR {current_bid.current_bid_amount:.2f} by {current_bid.team}' if current_bid else 'No bids yet'}")
    message_lines.append(f"Round: {state.get('Round')}")
    
    # Initialize or clear OtherTeamBidding
    state["OtherTeamBidding"] = {}
    
    teams = ["CSK", "DC", "GT", "KKR", "LSG", "MI", "PBKS", "RR", "RCB", "SRH"]
    
    message_lines.append(f"Current bid holder: {current_bid_team if current_bid_team else 'None'}")
    message_lines.append("Teams evaluating bids (Greedy Sequential Approach):")

    # --- Start of greedy sequential execution ---
    # Stagger requests to avoid rate limits
    base_sleep_duration = WAIT_BETWEEN_REQUESTS  # seconds
    
    # Build list of eligible teams
    if current_bid:
        current_price = current_bid.current_bid_amount
        min_bid_raise = get_raise_amount(current_price)
        next_bid_price = current_price + min_bid_raise
    else:
        # First bid: minimum raise is zero, can bid at reserve price
        current_price = current_player.reserve_price_lakh / 100  # Convert lakhs to crores
        min_bid_raise = 0.0
        next_bid_price = current_price
    
    eligible_teams = []
    for team_id in teams:
        budget = state.get(f"{team_id}_Budget", 0.0)
        if current_bid_team == team_id:
            message_lines.append(f"  {team_id}: Skipped (current bid holder)")
        elif budget < next_bid_price:
            message_lines.append(f"  {team_id}: Skipped (insufficient budget: {budget} < required INR {next_bid_price:.2f})")
        else:
            eligible_teams.append(team_id)
    
    # Process teams one by one in random order
    # Shuffle eligible teams to randomize order
    random.shuffle(eligible_teams)
    
    for team_id in eligible_teams:
        message_lines.append(f"\n  Checking {team_id}...")
        
        try:
            time.sleep(base_sleep_duration)  # Rate limiting
            
            api_key, api_key_id = get_next_api_key()
            if not api_key:
                message_lines.append(f"  {team_id}: Error - No API key available.")
                continue

            message_lines.append(f"  {team_id}: Using NVIDIA API key #{api_key_id}")

            llm = ChatNVIDIA(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                max_tokens=MAX_TOKENS,
                api_key=api_key,
                extra_body=EXTRA_BODY,
            ).with_structured_output(BidderInput)
            
            # Prepare context for this team
            budget = state.get(f"{team_id}_Budget", 0.0)
            squad = state.get(team_id, [])
            # Build a minimal squad summary containing only player name and reason_for_purchase
            squad_short = []
            for p in squad:
                try:
                    name = p.name
                except Exception:
                    name = str(p)
                reason = getattr(p, 'reason_for_purchase', None)
                squad_short.append({"name": name, "reason": reason})
            player_stats = current_player.stats
            
            # Update pricing for this team's evaluation
            if current_bid:
                current_price = current_bid.current_bid_amount
                min_bid_raise = get_raise_amount(current_price)
                next_bid_price = current_price + min_bid_raise
            else:
                # First bid opportunity - zero minimum raise
                current_price = current_player.reserve_price_lakh / 100  # Convert lakhs to crores
                min_bid_raise = 0.0
                next_bid_price = current_price
            
            other_team_compositions = ""
            other_team_budgets = ""
            for t in teams:
                if t != team_id:
                    # For other teams, expose only name and reason per player
                    other_team_squad = state.get(t, [])
                    other_short = []
                    for p in other_team_squad:
                        try:
                            name = p.name
                        except Exception:
                            name = str(p)
                        # For other teams provide minimal player info: specialism, sold_price, player_status
                        specialism = getattr(p, 'specialism', None)
                        sold_price = getattr(p, 'sold_price', None)
                        player_status = getattr(p, 'player_status', None)
                        ipl_matches = getattr(p, 'ipl_matches', None)
                        other_short.append({
                            "name": name,
                            "specialism": specialism,
                            "sold_price": sold_price,
                            "player_status": player_status,
                            "ipl_matches": ipl_matches,
                        })
                    other_team_compositions += f"{t}: {json.dumps(other_short, ensure_ascii=False)}\n"
                    other_team_budgets += f"{t}: {state.get(f'{t}_Budget', 0.0)}\n"

            current_set_abbr = state.get('CurrentSet')
            current_set_name = get_set_name(current_set_abbr) if current_set_abbr else "N/A"
            remaining_sets_list = state.get('RemainingSets', [])
            remaining_sets_full_names = get_set_name(remaining_sets_list)
            remaining_sets_str = ", ".join(remaining_sets_full_names) if remaining_sets_full_names else "None"

            remaining_in_set_players = str(state.get('RemainingPlayersInSet', []))

            # Format other teams' bid history for this player
            other_teams_intentions = ""
            for t in teams:
                if t != team_id and t in current_player.team_bid_history:
                    history = current_player.team_bid_history[t]
                    if history:
                        other_teams_intentions += f"\n{t}'s bidding history:\n"
                        for entry in history:
                            decision_type = entry.get('decision', 'unknown')
                            reason = entry.get('reason', 'No reason provided')
                            round_num = entry.get('round', 0)
                            price = entry.get('current_price', 0)
                            if decision_type == "raise":
                                is_normal = entry.get('is_normal', True)
                                raised_amt = entry.get('raised_amount', 0)
                                raise_info = "Normal raise" if is_normal else f"Custom raise (+{raised_amt} Cr)"
                                other_teams_intentions += f"  Round {round_num} (at {price} Cr): {raise_info} - {reason}\n"
                            else:
                                other_teams_intentions += f"  Round {round_num} (at {price} Cr): PASSED - {reason}\n"
            
            if not other_teams_intentions:
                other_teams_intentions = "First bidding opportunity - No other teams have bid yet. You have a strategic advantage to set the value for this player."

            # Format this team's own bid history for this player
            own_bid_history = ""
            if team_id in current_player.team_bid_history:
                history = current_player.team_bid_history[team_id]
                if history:
                    own_bid_history = f"Your team's bidding history for this player:\n"
                    for entry in history:
                        decision_type = entry.get('decision', 'unknown')
                        reason = entry.get('reason', 'No reason provided')
                        round_num = entry.get('round', 0)
                        price = entry.get('current_price', 0)
                        if decision_type == "raise":
                            is_normal = entry.get('is_normal', True)
                            raised_amt = entry.get('raised_amount', 0)
                            raise_info = "Normal raise" if is_normal else f"Custom raise (+{raised_amt} Cr)"
                            own_bid_history += f"  Round {round_num} (at {price} Cr): {raise_info} - {reason}\n"
                        else:
                            own_bid_history += f"  Round {round_num} (at {price} Cr): PASSED - {reason}\n"
                else:
                    own_bid_history = "This is your first opportunity to bid on this player. You can set your bidding strategy from the start."
            else:
                own_bid_history = "This is your first opportunity to bid on this player. You can set your bidding strategy from the start."

            # Use static system prompt (no player-specific substitutions) per best practices
            sys_prompt = prompts[f'{team_id}_sys']

            # Prepare human prompt with player-specific substitutions only
            human_template_raw = prompts[f'{team_id}_human']
            human_prompt_template = string.Template(human_template_raw)
            reserve_price_cr = current_player.reserve_price_lakh / 100
            human_subs = {
                'player_name': current_player.name,
                'specialism': current_player.specialism,
                'batting_style': current_player.batting_style,
                'bowling_style': current_player.bowling_style,
                'test_caps': current_player.test_caps,
                'odi_caps': current_player.odi_caps,
                't20_caps': current_player.t20_caps,
                'ipl_matches': current_player.ipl_matches,
                'player_status': current_player.player_status,
                'reserve_price_lakh': current_player.reserve_price_lakh,
                'reserve_price_cr': reserve_price_cr,
                'current_price': current_price,
                'min_bid_raise': min_bid_raise,
                'next_bid_price': next_bid_price,
                'team_composition': json.dumps(squad_short, ensure_ascii=False),
                'budget': budget,
                'other_team_compositions': other_team_compositions,
                'other_team_budgets': other_team_budgets,
                'current_set': current_set_name,
                'remaining_sets': remaining_sets_str,
                'remaining_in_set_players': remaining_in_set_players,
                'other_teams_intentions': other_teams_intentions,
                'own_bid_history': own_bid_history
            }
            if '${player_stats}' in human_template_raw:
                human_subs['player_stats'] = player_stats
            human_msg = human_prompt_template.substitute(human_subs)
            messages = [SystemMessage(content=sys_prompt), HumanMessage(content=human_msg)]
            
            bid_decision = llm.invoke(messages)
            message_lines.append(f"  {team_id}: Received response from model. Response: {bid_decision}")
            
            if bid_decision:
                message = AIMessage(content=str(bid_decision))
                state["Messages"] = [message]

                # Validate bid decision
                is_raise = bool(getattr(bid_decision, 'is_raise', False))
                is_normal = bool(getattr(bid_decision, 'is_normal', True))
                raised_amount = float(getattr(bid_decision, 'raised_amount', 0.0) or 0.0)

                # For custom raises, validate against minimum (except first bid where min is 0)
                if is_raise and (not is_normal) and min_bid_raise > 0:
                    if raised_amount < min_bid_raise:
                        if team_id not in current_player.team_bid_history:
                            current_player.team_bid_history[team_id] = []
                        bid_history_entry = {
                            "round": state.get('Round', 0),
                            "reason": f"Custom raise {raised_amount} below minimum required {min_bid_raise}",
                            "decision": "pass",
                            "is_normal": None,
                            "raised_amount": None,
                            "current_price": current_price
                        }
                        current_player.team_bid_history[team_id].append(bid_history_entry)
                        message_lines.append(f"  {team_id}: PASS - Custom raise {raised_amount} < required INR {min_bid_raise:.2f}")
                        continue

                # Store this team's bid decision in the player's history
                if team_id not in current_player.team_bid_history:
                    current_player.team_bid_history[team_id] = []

                bid_history_entry = {
                    "round": state.get('Round', 0),
                    "reason": bid_decision.reason,
                    "decision": "raise" if is_raise else "pass",
                    "is_normal": bid_decision.is_normal if is_raise else None,
                    "raised_amount": bid_decision.raised_amount if is_raise else None,
                    "current_price": current_price
                }
                current_player.team_bid_history[team_id].append(bid_history_entry)

                if is_raise:
                    bid_info = competitiveBidMaker(team_id, current_player, bid_decision)
                    state["OtherTeamBidding"] = bid_info  # Single bid, not dict
                    raise_type = "Normal" if bid_decision.is_normal else f"Custom (+{bid_decision.raised_amount})"
                    message_lines.append(f"  {team_id}: BID ({raise_type}) - Reason: {bid_decision.reason}")
                    message_lines.append(f"\n  FIRST BID FOUND! Passing to trade master...")
                    message_lines.append("="*60)
                    print("[AGENT_POOL] Message:\n" + "\n".join(message_lines), flush=True)
                    state["Messages"] = [AIMessage(content="\n".join(message_lines))]
                    return state  # Return immediately with first bid
                else:
                    message_lines.append(f"  {team_id}: PASS - Reason: {bid_decision.reason}")
            else:
                message_lines.append(f"  {team_id}: PASS (Could not parse bid decision) - Reason: {str(bid_decision)}")
                
        except Exception as e:
            try:
                key_info = f" (API key #{api_key_id})"
            except Exception:
                key_info = ""
            message_lines.append(f"  {team_id}: Error{key_info} - {str(e)}")

    # --- End of greedy sequential execution ---
    # All teams passed
    message_lines.append(f"\n  All eligible teams passed. No bids found.")
    message_lines.append("="*60)
    print("[AGENT_POOL] Message:\n" + "\n".join(message_lines), flush=True)
    state["OtherTeamBidding"] = None  # Clear any previous bids
    state["Messages"] = [AIMessage(content="\n".join(message_lines))]
    return state
