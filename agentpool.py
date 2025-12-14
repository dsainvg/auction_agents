import string
from utils import (
    AgentState, 
    AIMessage, 
    ToolMessage, 
    competitiveBidMaker, 
    get_next_api_key,
    api_keys,
    load_prompts,
    get_player_stats,
    get_raise_amount
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from agent_tools import bidder_tool
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
    num_keys = len(api_keys)
    base_sleep_duration = 120  # seconds
    sleep_per_request = base_sleep_duration / num_keys if num_keys > 0 else base_sleep_duration
    time.sleep(sleep_per_request) # Stagger requests slightly
    def run_agent_decision(team_id: str):
        """Worker function for each thread to get a team's bid decision."""
        try:
                        
            api_key = get_next_api_key()
            if not api_key:
                with lock:
                    message_lines.append(f"  {team_id}: Error - No API key available.")
                return

            llm = ChatGoogleGenerativeAI(
                model="gemini-flash-lite-latest",
                temperature=0.1,
                max_retries=2,
                google_api_key=api_key,
            ).bind_tools([bidder_tool])

            # Prepare context for this team
            budget = state.get(f"{team_id}_Budget", 0.0)
            squad = state.get(team_id, [])
            player_stats = get_player_stats(current_player.name)
            
            # Add current bid info to prompt
            if current_bid:
                current_price = current_bid.current_bid_amount
            else:
                current_price = current_player.base_price

            min_bid_raise = get_raise_amount(current_price)
            next_bid_price = current_price + min_bid_raise
            
            sys_prompt_template = string.Template(prompts[f'{team_id}_sys'])
            sys_prompt = sys_prompt_template.substitute(
                budget=budget, 
                player_name=current_player.name, 
                base_price=current_player.base_price,
                player_stats=player_stats,
                current_price=current_price,
                min_bid_raise=min_bid_raise,
                next_bid_price=next_bid_price
            )

            human_prompt_template = string.Template(prompts[f'{team_id}_human'])
            human_msg = human_prompt_template.substitute(
                player_name=current_player.name,
                team_composition=str(squad),
                player_stats=player_stats
            )
            # sys_prompt = prompts[f'{team_id}_sys']
            # human_msg = prompts[f'{team_id}_human']
            # print(f"[AGENT_POOL] {team_id} sending request to LLM... with prompt: {human_msg} and system prompt: {sys_prompt}", flush=True)
            messages = [SystemMessage(content=sys_prompt), HumanMessage(content=human_msg)]
            
            response = llm.invoke(messages)
            # message_lines.append(f"  {team_id}: Received response from model. and responce is {str(response)}")
            with lock:
                if response.tool_calls:
                    tool_call = response.tool_calls[0]
                    args = tool_call['args']
                    message = ToolMessage(content=f"Tool Called with status 'success' and it returned bid decision : {args}", name=tool_call['name'], tool_call_id=tool_call['id'])
                    state["Messages"] = [message]
                    message = AIMessage(content=str(response.content))
                    state["Messages"] = [message]
                    
                    if args.get("is_raise"):
                        bid_decision = {
                            "is_raise": True,
                            "is_normal": args.get("is_normal"),
                            "raised_amount": args.get("raised_amount")
                        }
                        bid_info = competitiveBidMaker(team_id, current_player, bid_decision)
                        state["OtherTeamBidding"][team_id] = bid_info
                        raise_type = "Normal" if bid_decision["is_normal"] else f"Custom (+{bid_decision['raised_amount']})"
                        message_lines.append(f"  {team_id}: BID ({raise_type})")
                    else:
                        message_lines.append(f"  {team_id}: PASS")
                else:
                    message_lines.append(f"  {team_id}: PASS (No tool call)")
        except Exception as e:
            with lock:
                message_lines.append(f"  {team_id}: Error - {str(e.with_traceback(e.__traceback__))}")

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


