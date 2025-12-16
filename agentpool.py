import string
from utils import (
    AgentState, 
    AIMessage,
    competitiveBidMaker, 
    get_next_api_key,
    load_prompts,
    get_player_stats,
    get_raise_amount,
    BidderInput,
    get_set_name
)
import json
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import HumanMessage, SystemMessage
from model_config import MODEL_NAME, TEMPERATURE, TOP_P, MAX_TOKENS, EXTRA_BODY, WAIT_BETWEEN_REQUESTS
import concurrent.futures
import threading
import time

def agent_pool(state: AgentState) -> AgentState:
    """
    Agent pool node with three team agents that can bid on the current player in parallel.
    Only teams who are NOT the current bid holder will be called.
    If there's no current bid, all teams can bid.
    Adds bids to state["OtherTeamBidding"].
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
    message_lines.append(f"Player: {current_player.name} ({current_player.role})")
    message_lines.append(f"Base Price: {current_player.base_price} Cr")
    message_lines.append(f"Current bid: {f'INR {current_bid.current_bid_amount:.2f} by {current_bid.team}' if current_bid else 'No bids yet'}")
    message_lines.append(f"Round: {state.get('Round')}")
    
    # Initialize or clear OtherTeamBidding
    state["OtherTeamBidding"] = {}
    
    teams = ["TeamA", "TeamB", "TeamC"]
    
    message_lines.append(f"Current bid holder: {current_bid_team if current_bid_team else 'None'}")
    message_lines.append("Teams evaluating bids:")

    # --- Start of parallel execution ---
    lock = threading.Lock()
    
    # Define sleep duration based on number of keys to avoid rate limits
    # num_keys = len(api_keys)
    base_sleep_duration = WAIT_BETWEEN_REQUESTS  # seconds
    # sleep_per_request = base_sleep_duration / num_keys if num_keys > 0 else base_sleep_duration
    time.sleep(base_sleep_duration) # Stagger requests slightly
    def run_agent_decision(team_id: str):
        """Worker function for each thread to get a team's bid decision."""
        try:
                        
            api_key, api_key_id = get_next_api_key()
            if not api_key:
                with lock:
                    message_lines.append(f"  {team_id}: Error - No API key available.")
                return

            # Log which API key index is being used (masking actual key)
            with lock:
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
            player_stats = get_player_stats(current_player.name)
            
            # Add current bid info to prompt
            if current_bid:
                current_price = current_bid.current_bid_amount
            else:
                current_price = current_player.base_price

            min_bid_raise = get_raise_amount(current_price)
            next_bid_price = current_price + min_bid_raise
            
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
                        # For other teams provide minimal player info: role, sold_price, category, experience
                        role = getattr(p, 'role', None)
                        sold_price = getattr(p, 'sold_price', None)
                        category = getattr(p, 'category', None)
                        experience = getattr(p, 'experience', None)
                        other_short.append({
                            "name": name,
                            "role": role,
                            "sold_price": sold_price,
                            "category": category,
                            "experience": experience,
                        })
                    other_team_compositions += f"{t}: {json.dumps(other_short, ensure_ascii=False)}\n"
                    other_team_budgets += f"{t}: {state.get(f'{t}_Budget', 0.0)}\n"

            current_set_abbr = state.get('CurrentSet')
            current_set_name = get_set_name(current_set_abbr) if current_set_abbr else "N/A"
            remaining_sets_list = state.get('RemainingSets', [])
            remaining_sets_full_names = get_set_name(remaining_sets_list)
            remaining_sets_str = ", ".join(remaining_sets_full_names) if remaining_sets_full_names else "None"

            remaining_in_set_players = str(state.get('RemainingPlayersInSet', []))

            # Use static system prompt (no player-specific substitutions) per best practices
            sys_prompt = prompts[f'{team_id}_sys']

            # Prepare human prompt with player-specific substitutions only
            human_template_raw = prompts[f'{team_id}_human']
            human_prompt_template = string.Template(human_template_raw)
            human_subs = {
                'player_name': current_player.name,
                'base_price': current_player.base_price,
                'current_price': current_price,
                'min_bid_raise': min_bid_raise,
                'next_bid_price': next_bid_price,
                'team_composition': json.dumps(squad_short, ensure_ascii=False),
                'budget': budget,
                'other_team_compositions': other_team_compositions,
                'other_team_budgets': other_team_budgets,
                'current_set': current_set_name,
                'remaining_sets': remaining_sets_str,
                'remaining_in_set_players': remaining_in_set_players
            }
            if '${player_stats}' in human_template_raw:
                human_subs['player_stats'] = player_stats
            human_msg = human_prompt_template.substitute(human_subs)
            # sys_prompt = prompts[f'{team_id}_sys']
            # human_msg = prompts[f'{team_id}_human']
            messages = [SystemMessage(content=sys_prompt), HumanMessage(content=human_msg)]
            
            bid_decision = llm.invoke(messages)
            # message_lines.append(f"  {team_id}: Received response from model. and responce is {str(response)}")
            with lock:
                message_lines.append(f"  {team_id}: Received response from model. and responce is {bid_decision}")
                if bid_decision:
                    message = AIMessage(content=str(bid_decision))
                    state["Messages"] = [message]
                    
                    if bid_decision.is_raise:
                        bid_info = competitiveBidMaker(team_id, current_player, bid_decision)
                        state["OtherTeamBidding"][team_id] = bid_info
                        raise_type = "Normal" if bid_decision.is_normal else f"Custom (+{bid_decision.raised_amount})"
                        message_lines.append(f"  {team_id}: BID ({raise_type}) - Reason: {bid_decision.reason}")
                    else:
                        message_lines.append(f"  {team_id}: PASS - Reason: {bid_decision.reason}")
                else:
                    message_lines.append(f"  {team_id}: PASS (Could not parse bid decision) - Reason: {str(bid_decision)}")
        except Exception as e:
            # Try to include api_key_id in the error message if available
            try:
                key_info = f" (API key #{api_key_id})"
            except Exception:
                key_info = ""
            with lock:
                message_lines.append(f"  {team_id}: Error{key_info} - {str(e.with_traceback(e.__traceback__))}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(teams)) as executor:
        futures = []
        for team_id in teams:
            if current_bid_team != team_id:
                futures.append(executor.submit(run_agent_decision, team_id))
            else:
                 message_lines.append(f"  {team_id}: Skipped (current bid holder)")
        
        # Wait for all futures to complete
        concurrent.futures.wait(futures)

    # --- End of parallel execution ---

    message_lines.append(f"Total bids received: {len(state['OtherTeamBidding'])}")
    message_lines.append("="*60)
    # Print messages to terminal for debugging
    print("[AGENT_POOL] Message:\n" + "\n".join(message_lines), flush=True)
    state["Messages"] = [AIMessage(content="\n".join(message_lines))]
    return state
