import streamlit as st
import warnings
from langgraph.graph import StateGraph, END
from utils import AgentState, load_player_data
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
    
    # Update remaining players in set
    remaining_in_set = state.get("RemainingPlayersInSet", [])
    
    # Extract trade master message
    messages = state.get("Messages", [])
    trade_message = messages[-1].content if messages else ""
    
    # Update team info and budgets
    for team in ['TeamA', 'TeamB', 'TeamC']:
        team_players = state.get(team, [])
        if team_players:
            st.session_state.teams[team] = team_players
            print(f"[DEBUG] Updated {team} with {len(team_players)} players")
        budget = state.get(f"{team}_Budget", 100.0)
        st.session_state.budgets[team] = budget
        print(f"[DEBUG] {team} budget: {budget}")
    
    # Add to bid history if there's a current bid
    if current_bid and current_player:
        bid_entry = {
            'player': current_player.name,
            'team': current_bid.team,
            'amount': current_bid.current_bid_amount,
            'status': 'Active'
        }
        # Avoid duplicates by checking if this exact bid exists
        if not any(b['player'] == bid_entry['player'] and b['amount'] == bid_entry['amount'] and b['status'] == 'Active' for b in st.session_state.bid_history):
            st.session_state.bid_history.append(bid_entry)
            print(f"[DEBUG] Added bid: {bid_entry}")
    
    # Check for finalized sales in team rosters
    for team in ['TeamA', 'TeamB', 'TeamC']:
        team_players = state.get(team, [])
        for player in team_players:
            if hasattr(player, 'sold_price') and player.sold_price > 0:
                # Mark previous active bids as sold
                for bid in st.session_state.bid_history:
                    if bid['player'] == player.name and bid['status'] == 'Active':
                        bid['status'] = 'SOLD'
                        print(f"[DEBUG] Marked {player.name} as SOLD to {team}")
    
    return {
        'current_bid': current_bid.current_bid_amount if current_bid else 0,
        'current_player': current_player.name if current_player else "None",
        'bidder': current_bid.team if current_bid else "None",
        'remaining_count': len(remaining_in_set) if remaining_in_set else 0,
        'remaining_players': [p.name for p in remaining_in_set[:5]] if remaining_in_set else [],
        'trade_message': trade_message[:100] + "..." if len(trade_message) > 100 else trade_message
    }

def render_ui():
    """Render the main UI"""
    st.title("🏏 IPL Mock Auction Dashboard")
    
    # Host status indicator
    if st.session_state.host_active:
        st.success("🟢 HOST ACTIVE")
    else:
        st.info("⚪ IDLE")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Current Auction Status")
        
        if st.session_state.current_state:
            info = process_state_update(st.session_state.current_state)
            
            st.metric("Current Bid", f"₹{info['current_bid']:.2f} Cr")
            st.metric("Bidder", info['bidder'])
            st.metric("Player", info['current_player'])
            st.metric("Remaining in Set", info['remaining_count'])
            
            if info['remaining_players']:
                st.write("**Next Players:**", ", ".join(info['remaining_players']))
            
            if info['trade_message']:
                st.text_area("Trade Master Message", info['trade_message'], height=100)
        
        # Team Status
        st.subheader("Team Status")
        for team in ['TeamA', 'TeamB', 'TeamC']:
            with st.expander(f"{team} - Budget: ₹{st.session_state.budgets[team]:.2f} Cr"):
                players = st.session_state.teams[team]
                if players:
                    total_spent = sum(p.sold_price for p in players if hasattr(p, 'sold_price'))
                    st.write(f"**Total Spent:** ₹{total_spent:.2f} Cr")
                    for player in players:
                        price = getattr(player, 'sold_price', 0)
                        st.write(f"• {player.name} - ₹{price:.2f} Cr")
                else:
                    st.write("No players yet")
    
    with col2:
        st.subheader("Bid History")
        if st.session_state.bid_history:
            for i, bid in enumerate(reversed(st.session_state.bid_history[-10:])):
                status_color = "🟢" if bid['status'] == 'SOLD' else "🔵"
                st.write(f"{status_color} {bid['player']} - {bid['team']} - ₹{bid['amount']:.2f} Cr")
        else:
            st.write("No bids yet")

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
    
    # Control buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🚀 Start Mock Auction", disabled=st.session_state.auction_running):
            st.session_state.bid_history = []
            st.session_state.teams = {'TeamA': [], 'TeamB': [], 'TeamC': []}
            st.session_state.budgets = {'TeamA': 100.0, 'TeamB': 100.0, 'TeamC': 100.0}
            start_auction()
    
    with col2:
        if st.button("🔄 Reset Dashboard"):
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
    
    # Always render UI
    render_ui()
    
    # Process next auction state if running
    if st.session_state.auction_running and st.session_state.stream_iterator:
        print("[DEBUG] Processing next state...")
        if process_next_state():
            print("[DEBUG] Rerunning for next state...")
            import time
            time.sleep(0.1)  # Small delay for UI visibility
            st.rerun()  # Continue processing
        else:
            print("[DEBUG] No more states to process")

if __name__ == "__main__":
    main()