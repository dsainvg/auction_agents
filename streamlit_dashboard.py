import streamlit as st
import warnings
from langgraph.graph import StateGraph, END
from utils import AgentState, load_player_data, get_raise_amount
from host import host
from host_assistant import host_assistant
from agentpool import agent_pool
from trade_master import trademaster
from team_manager import team_manager

# Suppress warnings
warnings.filterwarnings('ignore')

def init_session_state():
    """Initialize session state variables"""
    if 'auction_running' not in st.session_state:
        st.session_state.auction_running = False
    if 'bid_history' not in st.session_state:
        st.session_state.bid_history = []
    if 'teams' not in st.session_state:
        st.session_state.teams = {'TeamA': [], 'TeamB': [], 'TeamC': []}
    if 'budgets' not in st.session_state:
        st.session_state.budgets = {'TeamA': 100.0, 'TeamB': 100.0, 'TeamC': 100.0}
    if 'host_active' not in st.session_state:
        st.session_state.host_active = False
    if 'current_state' not in st.session_state:
        st.session_state.current_state = None
    if 'stream_iterator' not in st.session_state:
        st.session_state.stream_iterator = None
    if 'current_set' not in st.session_state:
        st.session_state.current_set = None
    if 'remaining_sets' not in st.session_state:
        st.session_state.remaining_sets = []

def create_graph():
    """Create and return the LangGraph"""
    graph_builder = StateGraph(AgentState)
    
    graph_builder.add_node("host", lambda state: state)
    graph_builder.add_node("host_assistant", host_assistant)
    graph_builder.add_node("bidder_pool", agent_pool)
    graph_builder.add_node("trademaster", trademaster)
    graph_builder.add_node("team_manager", team_manager)
    
    graph_builder.set_entry_point("host")
    
    graph_builder.add_conditional_edges(
        "host", host,
        {"host_assistant": "host_assistant", "bidder_pool": "bidder_pool", "team_manager": "team_manager"}
    )
    
    graph_builder.add_edge("host_assistant", "host")
    graph_builder.add_edge("bidder_pool", "trademaster")
    graph_builder.add_edge("trademaster", "host")
    graph_builder.add_edge("team_manager", END)
    
    return graph_builder.compile()

def process_state_update(state, node_name=None):
    """Process a state update and extract relevant information"""
    print(f"[DEBUG] Processing state update - CurrentPlayer: {state.get('CurrentPlayer', {}).name if state.get('CurrentPlayer') else 'None'}")
    st.session_state.current_state = state
    
    # Update host status
    st.session_state.host_active = (node_name == "host")
    
    # Extract current bid info
    current_bid = state.get("CurrentBid")
    current_player = state.get("CurrentPlayer")
    current_round = state.get("Round", 0)
    
    # Update set information
    st.session_state.current_set = state.get("CurrentSet")
    st.session_state.remaining_sets = state.get("RemainingSets", [])
    
    # Update remaining players in set
    remaining_in_set = state.get("RemainingPlayersInSet", [])
    
    # Extract messages - PASS actions are logged here
    messages = state.get("Messages", [])
    trade_message = messages[-1].content if messages else ""
    
    # Try to extract PASS actions from the message
    if trade_message and "PASS" in trade_message:
        # Parse PASS actions from agent pool message
        import re
        pass_matches = re.findall(r'(Team[ABC]):\s*PASS\s*-\s*Reason:\s*(.+?)(?=\n\n|\n  |$)', trade_message, re.DOTALL)
        if pass_matches and current_player:
            for team, reason in pass_matches:
                bid_entry = {
                    'player': current_player.name,
                    'team': team,
                    'amount': current_bid.current_bid_amount if current_bid else 0,
                    'round': current_round,
                    'reason': reason.strip(),
                    'action': 'PASS',
                    'status': 'Pass'
                }
                st.session_state.bid_history.append(bid_entry)
                print(f"[DEBUG] Added PASS from message: {bid_entry}")
    
    # Extract bid from OtherTeamBidding - this has the reason!
    other_bid = state.get("OtherTeamBidding")
    bid_reason = ""
    bid_action = "BID"
    
    print(f"[DEBUG] OtherTeamBidding: {other_bid}")
    print(f"[DEBUG] Has reason attr: {hasattr(other_bid, 'reason') if other_bid else False}")
    
    if other_bid and hasattr(other_bid, 'reason'):
        bid_reason = other_bid.reason
        bid_action = "BID" if other_bid.is_raise else "PASS"
        print(f"[DEBUG] Bid action: {bid_action}, is_raise: {other_bid.is_raise}")
    
    # Update team info and budgets
    for team in ['TeamA', 'TeamB', 'TeamC']:
        team_players = state.get(team, [])
        if team_players:
            st.session_state.teams[team] = team_players
        budget = state.get(f"{team}_Budget", 100.0)
        st.session_state.budgets[team] = budget
    
    # Add ALL bid actions (including PASS) to history
    if other_bid and current_player:
        # Calculate the actual bid amount for this action
        if other_bid.is_raise:
            if current_bid:
                # Subsequent bid
                if other_bid.is_normal:
                    actual_bid_amount = current_bid.current_bid_amount + get_raise_amount(current_bid.current_bid_amount)
                else:
                    actual_bid_amount = current_bid.current_bid_amount + other_bid.raised_amount
            else:
                # First bid
                if other_bid.is_normal:
                    actual_bid_amount = current_player.base_price
                else:
                    actual_bid_amount = current_player.base_price + other_bid.raised_amount
        else:
            # PASS - use current bid amount or 0
            actual_bid_amount = current_bid.current_bid_amount if current_bid else 0
        
        bid_entry = {
            'player': current_player.name,
            'team': other_bid.team,
            'amount': actual_bid_amount,
            'round': current_round,
            'reason': bid_reason,
            'action': bid_action,
            'status': 'Active' if other_bid.is_raise else 'Pass'
        }
        st.session_state.bid_history.append(bid_entry)
        print(f"[DEBUG] Added {bid_action}: {bid_entry}")
    
    # Check for finalized sales
    for team in ['TeamA', 'TeamB', 'TeamC']:
        team_players = state.get(team, [])
        for player in team_players:
            if hasattr(player, 'sold_price') and player.sold_price > 0:
                for bid in st.session_state.bid_history:
                    if bid['player'] == player.name and bid.get('status') == 'Active':
                        bid['status'] = 'SOLD'
                        bid['final_team'] = team
                        bid['final_price'] = player.sold_price
                        if hasattr(player, 'reason_for_purchase'):
                            bid['purchase_reason'] = player.reason_for_purchase
    
    return {
        'current_bid': current_bid.current_bid_amount if current_bid else 0,
        'current_player': current_player.name if current_player else "None",
        'bidder': current_bid.team if current_bid else "None",
        'round': current_round,
        'remaining_count': len(remaining_in_set) if remaining_in_set else 0,
        'remaining_players': [p.name for p in remaining_in_set[:5]] if remaining_in_set else [],
        'trade_message': trade_message,
        'bid_reason': bid_reason
    }

def render_ui():
    """Render the main UI"""
    st.markdown("<style>.block-container{max-width: 95%; padding: 1rem;}</style>", unsafe_allow_html=True)
    
    # Host status and auction info
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.session_state.host_active:
            st.success("🟢 HOST ACTIVE")
        else:
            st.info("⚪ IDLE")
    with col2:
        if st.session_state.current_set:
            st.metric("Current Set", st.session_state.current_set)
    with col3:
        st.metric("Remaining Sets", len(st.session_state.remaining_sets))
    
    # Main content - wider layout
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("🎯 Current Auction")
        
        if st.session_state.current_state:
            current_bid = st.session_state.current_state.get("CurrentBid")
            current_player = st.session_state.current_state.get("CurrentPlayer")
            current_round = st.session_state.current_state.get("Round", 0)
            remaining_in_set = st.session_state.current_state.get("RemainingPlayersInSet", [])
            
            # Current player and bid
            if current_player:
                st.markdown(f"### 🏏 {current_player.name}")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Current Bid", f"₹{current_bid.current_bid_amount if current_bid else 0:.2f} Cr")
                with col_b:
                    st.metric("Bidder", current_bid.team if current_bid else "None")
                with col_c:
                    st.metric("Round", current_round)
                
                if remaining_in_set:
                    st.write(f"**Remaining in Set:** {len(remaining_in_set)} players")
                    if len(remaining_in_set) > 0:
                        st.write("**Next:** " + ", ".join([p.name for p in remaining_in_set[:5]]))
            else:
                st.info("Waiting for next player...")
        
        # Bid History with reasons
        st.subheader("📜 Bid & Pass History")
        
        # Debug info
        st.caption(f"Total bids in history: {len(st.session_state.bid_history)}")
        pass_count = sum(1 for b in st.session_state.bid_history if b.get('action') == 'PASS' or b.get('status') == 'Pass')
        st.caption(f"PASS actions: {pass_count}")
        
        if st.session_state.bid_history:
            # Show all bids including PASS
            for bid in reversed(st.session_state.bid_history[-30:]):
                # Team color circles
                team_colors = {'TeamA': '🔴', 'TeamB': '🔵', 'TeamC': '🟢'}
                team_circle = team_colors.get(bid['team'], '⚪')
                
                # Status icon - check both action and status
                if bid.get('status') == 'SOLD':
                    status_icon = "✅"
                elif bid.get('action') == 'PASS' or bid.get('status') == 'Pass':
                    status_icon = "❌"
                else:
                    status_icon = "💰"
                
                action_text = bid.get('action', 'BID')
                title = f"{team_circle} {status_icon} {bid['player']} - {bid['team']} {action_text}"
                if action_text != 'PASS':
                    title += f" - ₹{bid['amount']:.2f} Cr"
                else:
                    title += f" (at ₹{bid['amount']:.2f} Cr)"
                
                # Expand PASS and Active bids by default
                # is_expanded = (bid.get('status')=='Active' or bid.get('action')=='PASS')
                with st.expander(title, expanded=False):
                    if bid.get('reason'):
                        st.markdown(f"**Reason:** {bid['reason']}")
                    else:
                        st.write("_No reason provided_")
                    
                    if bid.get('status') == 'SOLD':
                        st.success(f"**SOLD to {bid.get('final_team', bid['team'])} for ₹{bid.get('final_price', bid['amount']):.2f} Cr**")
                        if bid.get('purchase_reason'):
                            st.markdown(f"**Purchase Analysis:** {bid['purchase_reason'][:300]}...")
        else:
            st.write("No bids yet")
    
    with col_right:
        st.subheader("👥 Teams")
        
        for team in ['TeamA', 'TeamB', 'TeamC']:
            players = st.session_state.teams[team]
            budget = st.session_state.budgets[team]
            spent = 100.0 - budget
            
            team_colors = {'TeamA': '🔴', 'TeamB': '🔵', 'TeamC': '🟢'}
            team_circle = team_colors.get(team, '⚪')
            
            with st.expander(f"{team_circle} **{team}** ({len(players)} players)", expanded=False):
                st.metric("Budget", f"₹{budget:.2f} Cr")
                st.metric("Spent", f"₹{spent:.2f} Cr")
                
                if players:
                    st.write("**Squad:**")
                    for player in players:
                        price = getattr(player, 'sold_price', 0)
                        role = getattr(player, 'role', 'N/A')
                        reason = getattr(player, 'reason_for_purchase', None)
                        
                        with st.expander(f"• {player.name} ({role}) - ₹{price:.2f} Cr", expanded=False):
                            if reason:
                                st.markdown(f"**Purchase Reason:** {reason}")
                            else:
                                st.write("_No purchase reason available_")
                else:
                    st.write("_No players yet_")

def start_auction():
    """Initialize auction stream"""
    print("[DEBUG] Starting auction...")
    initial_state = {
        'RemainingPlayers': load_player_data(),
        'RemainingSets': ['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'],
        'CurrentSet': None,
        'RemainingPlayersInSet': None,
        'AuctionStatus': False,
        'CurrentPlayer': None,
        'CurrentBid': None,
        'OtherTeamBidding': None,
        'Round': 0,
        'TeamA': [],
        'TeamB': [],
        'TeamC': [],
        'UnsoldPlayers': [],
        'TeamA_Budget': 100.0,
        'TeamB_Budget': 100.0,
        'TeamC_Budget': 100.0,
        'Messages': []
    }
    
    print("[DEBUG] Creating graph...")
    graph = create_graph()
    print("[DEBUG] Starting stream...")
    config = {"recursion_limit": 10000}
    st.session_state.stream_iterator = graph.stream(initial_state, config, stream_mode="values")
    st.session_state.auction_running = True
    print("[DEBUG] Auction started!")

def process_next_state():
    """Process next state from stream"""
    try:
        if st.session_state.stream_iterator:
            print("[DEBUG] Getting next state...")
            state = next(st.session_state.stream_iterator)
            print(f"[DEBUG] Got state with keys: {list(state.keys())}")
            process_state_update(state)
            return True
    except StopIteration:
        print("[DEBUG] Stream completed")
        st.session_state.auction_running = False
        st.session_state.stream_iterator = None
        return False
    except Exception as e:
        print(f"[DEBUG] Stream error: {e}")
        st.session_state.auction_running = False
        st.session_state.auction_error = str(e)
        return False
    return False

def main():
    init_session_state()
    
    st.title("🏏 IPL Mock Auction Dashboard")
    
    # Control buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🚀 Start Mock Auction", key="start_btn", disabled=st.session_state.auction_running):
            st.session_state.bid_history = []
            st.session_state.teams = {'TeamA': [], 'TeamB': [], 'TeamC': []}
            st.session_state.budgets = {'TeamA': 100.0, 'TeamB': 100.0, 'TeamC': 100.0}
            start_auction()
    
    with col2:
        if st.button("⏸️ Stop Auction", key="stop_btn", disabled=not st.session_state.auction_running):
            st.session_state.auction_running = False
            st.session_state.stream_iterator = None
            st.warning("Auction stopped!")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Dashboard", key="reset_btn"):
            st.session_state.auction_running = False
            st.session_state.stream_iterator = None
            for key in ['bid_history', 'teams', 'budgets', 'current_state', 'auction_error']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Show status
    if st.session_state.auction_running:
        st.info("🔄 Auction running...")
    elif hasattr(st.session_state, 'auction_error') and st.session_state.auction_error:
        st.error(f"Auction error: {st.session_state.auction_error}")
    elif st.session_state.current_state:
        st.success("🏁 Auction Completed!")
    
    st.divider()
    
    # Render UI
    render_ui()
    
    # Process next auction state if running
    if st.session_state.auction_running and st.session_state.stream_iterator:
        print("[DEBUG] Processing next state...")
        if process_next_state():
            print("[DEBUG] Rerunning for next state...")
            import time
            time.sleep(0.1)
            st.rerun()
        else:
            print("[DEBUG] No more states to process")

if __name__ == "__main__":
    main()