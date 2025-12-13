from utils import AgentState, CompetitiveBidInfo, AIMessage, ToolMessage, competitiveBidMaker
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from agent_tools import bidder_tool

def agent_pool(state: AgentState) -> AgentState:
    """Agent pool node with three team agents that can bid on current player.
    
    Only teams who are NOT the current bid holder will be called.
    If there's no current bid, all teams can bid.
    Adds bids to state["OtherTeamBidding"].
    """
    message_lines = []
    current_player = state.get("CurrentPlayer")
    if not current_player:
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
    
    # Initialize OtherTeamBidding if needed
    if state.get("OtherTeamBidding") is None:
        state["OtherTeamBidding"] = {}
    else:
        # Clear previous bids for this round
        state["OtherTeamBidding"] = {}
    
    teams = ["TeamA", "TeamB", "TeamC"]
    
    message_lines.append(f"Current bid holder: {current_bid_team if current_bid_team else 'None'}")
    message_lines.append("Teams evaluating bids:")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        message_lines.append("Error: GEMINI_API_KEY not found.")
        state["Messages"] = [AIMessage(content="\n".join(message_lines))]
        return state

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        temperature=0.1,
        max_retries=2,
        google_api_key=api_key,
    ).bind_tools([bidder_tool])
    
    # System prompts for each team
    system_prompts = {
                            "TeamA": """You are the manager of TeamA in an IPL auction. 
                    Strategy: Aggressive. You want to build a strong team and are willing to pay a premium for good players, especially All-Rounders and Batsmen.
                    Budget: {budget} Cr.
                    Current Squad: {squad_count} players.
                    Make Sure You call the bidder_tool to place your bid.
                    Decide whether to bid for the current player. If you bid, you can raise by a standard increment or a custom amount.""",
                            
                            "TeamB": """You are the manager of TeamB in an IPL auction.
                    Strategy: Conservative/Moneyball. You look for value buys. You avoid bidding wars unless the player is a key Bowler.
                    Budget: {budget} Cr.
                    Current Squad: {squad_count} players.
                    Make Sure You call the bidder_tool to place your bid.
                    Decide whether to bid for the current player.""",
                            
                            "TeamC": """You are the manager of TeamC in an IPL auction.
                    Strategy: Balanced. You need a mix of roles. You are cautious in early rounds but aggressive if you need specific roles.
                    Budget: {budget} Cr.
                    Current Squad: {squad_count} players.
                    Make Sure You call the bidder_tool to place your bid.
                    Decide whether to bid for the current player."""
            }

    for team_id in teams:
        # Skip if this team is the current bid holder
        if current_bid_team == team_id:
            message_lines.append(f"  {team_id}: Skipped (current bid holder)")
            continue
            
        # Prepare context
        budget = state.get(f"{team_id}_Budget", 0.0)
        squad = state.get(team_id, [])
        
        sys_prompt = system_prompts[team_id].format(budget=budget, squad_count=len(squad))
        
        human_msg = f"""Current Player: {current_player.name}
                        Role: {current_player.role}
                        Base Price: {current_player.base_price} Cr
                        Current Bid: {current_bid.current_bid_amount if current_bid else 'None'}
                        Current Bid Holder: {current_bid_team if current_bid_team else 'None'}

                        Do you want to bid? Use the bidder_tool to place a bid or pass."""

        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=human_msg)
        ]
        
        try:
            response = llm.invoke(messages)
            
            if response.tool_calls:
                tool_call = response.tool_calls[0]
                args = tool_call['args']
                message = ToolMessage(content=f"Tool Called with status 'success' and it returned bid decision : {args}", name=tool_call['name'], tool_call_id=tool_call['id'])
                state["Messages"] = [message]
                # Parse info using tool message structure (as requested)
                is_raise = args.get("is_raise")
                
                if is_raise:
                    bid_decision = {
                        "is_raise": True,
                        "is_normal": args.get("is_normal"),
                        "raised_amount": args.get("raised_amount")
                    }
                    
                    # Create competitive bid info
                    bid_info = competitiveBidMaker(team_id, current_player, bid_decision)
                    state["OtherTeamBidding"][team_id] = bid_info
                    
                    raise_type = "Normal" if bid_decision["is_normal"] else f"Custom (+{bid_decision['raised_amount']})"
                    message_lines.append(f"  {team_id}: BID ({raise_type})")
                else:
                    message_lines.append(f"  {team_id}: PASS")
            else:
                message_lines.append(f"  {team_id}: PASS (No tool call)")
                
        except Exception as e:
            message_lines.append(f"  {team_id}: Error - {str(e)}")
        
    message_lines.append(f"Total bids received: {len(state['OtherTeamBidding'])}")
    message_lines.append("="*60)
    state["Messages"] = [AIMessage(content="\n".join(message_lines))]
    return state

