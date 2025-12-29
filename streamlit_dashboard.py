import streamlit as st
import warnings
import pickle
import os
from datetime import datetime
from langgraph.graph import StateGraph, END
from utils import AgentState, load_player_data, get_raise_amount, Player, Team
from host import host
from host_assistant import host_assistant
from agentpool import agent_pool
from trade_master import trademaster
import plotly.graph_objects as go

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
    if 'auction_completed' not in st.session_state:
        st.session_state.auction_completed = False
    if 'unsold_players' not in st.session_state:
        st.session_state.unsold_players = []
    if 'save_preallocation' not in st.session_state:
        st.session_state.save_preallocation = True

def create_graph():
    """Create and return the LangGraph"""
    graph_builder = StateGraph(AgentState)
    
    graph_builder.add_node("host", lambda state: state)
    graph_builder.add_node("host_assistant", host_assistant)
    graph_builder.add_node("bidder_pool", agent_pool)
    graph_builder.add_node("trademaster", trademaster)
    
    graph_builder.set_entry_point("host")
    
    graph_builder.add_conditional_edges(
        "host", host,
        {"host_assistant": "host_assistant", "bidder_pool": "bidder_pool", "end": END}
    )
    
    graph_builder.add_edge("host_assistant", "host")
    graph_builder.add_edge("bidder_pool", "trademaster")
    graph_builder.add_edge("trademaster", "host")
    
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
    
    # Extract bid from OtherTeamBidding
    other_bid = state.get("OtherTeamBidding")
    
    print(f"[DEBUG] OtherTeamBidding: {other_bid}")
    print(f"[DEBUG] Has reason attr: {hasattr(other_bid, 'reason') if other_bid else False}")
    
    # Update team info and budgets - handle both list and Team class
    for team in ['TeamA', 'TeamB', 'TeamC']:
        team_data = state.get(team, [])
        if team_data:
            st.session_state.teams[team] = team_data
        budget = state.get(f"{team}_Budget", 100.0)
        st.session_state.budgets[team] = budget
    
    # Update unsold players
    unsold = state.get('UnsoldPlayers', [])
    if unsold:
        st.session_state.unsold_players = unsold
    
    # Add bid action to history ONLY from OtherTeamBidding (single source of truth)
    if other_bid and current_player and hasattr(other_bid, 'reason'):
        bid_reason = other_bid.reason
        bid_action = "BID" if other_bid.is_raise else "PASS"
        
        # Calculate the actual bid amount
        if other_bid.is_raise:
            if current_bid:
                if other_bid.is_normal:
                    actual_bid_amount = current_bid.current_bid_amount + get_raise_amount(current_bid.current_bid_amount)
                else:
                    actual_bid_amount = current_bid.current_bid_amount + other_bid.raised_amount
            else:
                if other_bid.is_normal:
                    actual_bid_amount = current_player.base_price
                else:
                    actual_bid_amount = current_player.base_price + other_bid.raised_amount
        else:
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
    
    # Check for finalized sales - handle both list and Team class
    for team in ['TeamA', 'TeamB', 'TeamC']:
        team_data = state.get(team, [])
        team_players = []
        
        # Extract players from Team class or list
        if isinstance(team_data, Team):
            for attr in ['Captain', 'WicketKeeper', 'StrikingOpener', 'NonStrikingOpener',
                       'OneDownBatsman', 'TwoDownBatsman', 'ThreeDownBatsman', 'FourDownBatsman',
                       'FiveDownBatsman', 'SixDownBatsman', 'SevenDownBatsman', 'EightDownBatsman', 'NineDownBatsman']:
                p = getattr(team_data, attr, None)
                if p and isinstance(p, Player):
                    team_players.append(p)
            for attr in ['PowerplayBowlers', 'MiddleOversBowlers', 'DeathOversBowlers', 'PlayersNotInPlayingXI']:
                plist = getattr(team_data, attr, [])
                if plist:
                    team_players.extend(plist)
        elif isinstance(team_data, list):
            team_players = team_data
        
        for player in team_players:
            if hasattr(player, 'sold_price') and player.sold_price > 0:
                for bid in st.session_state.bid_history:
                    if bid['player'] == player.name and bid.get('status') == 'Active':
                        bid['status'] = 'SOLD'
                        bid['final_team'] = team
                        bid['final_price'] = player.sold_price
                        if hasattr(player, 'reason_for_purchase'):
                            bid['purchase_reason'] = player.reason_for_purchase
    
    # Extract trade message for display
    messages = state.get("Messages", [])
    trade_message = messages[-1].content if messages else ""
    
    return {
        'current_bid': current_bid.current_bid_amount if current_bid else 0,
        'current_player': current_player.name if current_player else "None",
        'bidder': current_bid.team if current_bid else "None",
        'round': current_round,
        'remaining_count': len(remaining_in_set) if remaining_in_set else 0,
        'remaining_players': [p.name for p in remaining_in_set[:5]] if remaining_in_set else [],
        'trade_message': trade_message,
        'bid_reason': ''
    }

def render_ui():
    """Render the main UI"""
    st.markdown("""
        <style>
        .block-container{max-width: 95%; padding-top: 2rem; padding-left:1rem; padding-right:1rem; padding-bottom:1rem;}
        .stMetric{text-align: center;}
        div[data-testid="stHorizontalBlock"] > div{justify-content: center;}
        </style>
    """, unsafe_allow_html=True)
    
    # Auction completion banner at top
    if st.session_state.auction_completed:
        st.success("🏁 Auction Completed! Teams have been finalized.")
    
    # Host status and auction info - centered
    col1, col2, col3, col4 = st.columns(4)
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
    with col4:
        st.metric("Unsold Players", len(st.session_state.unsold_players))
    
    st.divider()
    
    # Budget bars with plotly
    if any(b < 100.0 for b in st.session_state.budgets.values()):
        st.subheader("💰 Team Budgets")
        
        fig = go.Figure()
        team_colors_map = {'TeamA': '#FF4B4B', 'TeamB': '#4B4BFF', 'TeamC': '#4BFF4B'}
        player_colors = ['#FF6B6B', '#FFB84D', '#4ECDC4', '#95E1D3', '#F38181', '#AA96DA', '#FCBAD3', '#FFFFD2']
        
        for idx, team in enumerate(['TeamA', 'TeamB', 'TeamC']):
            budget = st.session_state.budgets[team]
            spent = 100.0 - budget
            team_data = st.session_state.teams[team]
            
            # Extract players
            players = []
            if isinstance(team_data, Team):
                for attr in ['Captain', 'WicketKeeper', 'StrikingOpener', 'NonStrikingOpener',
                           'OneDownBatsman', 'TwoDownBatsman', 'ThreeDownBatsman', 'FourDownBatsman',
                           'FiveDownBatsman', 'SixDownBatsman', 'SevenDownBatsman', 'EightDownBatsman', 'NineDownBatsman']:
                    p = getattr(team_data, attr, None)
                    if p and isinstance(p, Player):
                        players.append(p)
                for attr in ['PowerplayBowlers', 'MiddleOversBowlers', 'DeathOversBowlers', 'PlayersNotInPlayingXI']:
                    plist = getattr(team_data, attr, [])
                    if plist:
                        players.extend(plist)
                players = list({p.name: p for p in players}.values())
            elif isinstance(team_data, list):
                players = team_data
            else:
                players = []
            
            # Add individual player bars with different colors
            for pidx, player in enumerate(players):
                price = getattr(player, 'sold_price', 0)
                color = player_colors[pidx % len(player_colors)]
                fig.add_trace(go.Bar(
                    y=[team],
                    x=[price],
                    orientation='h',
                    name=player.name,
                    marker=dict(color=color),
                    hovertemplate=f'<b>{player.name}</b><br>₹{price:.2f}Cr<extra></extra>',
                    showlegend=False
                ))
            
            # Remaining bar
            fig.add_trace(go.Bar(
                y=[team],
                x=[budget],
                orientation='h',
                name='Remaining' if idx == 0 else '',
                marker=dict(color='lightgray'),
                text=f'₹{budget:.1f}Cr',
                textposition='inside',
                hovertemplate=f'<b>{team} - Remaining</b><br>₹{budget:.2f}Cr<extra></extra>',
                showlegend=(idx == 0)
            ))
        
        fig.update_layout(
            barmode='stack',
            xaxis=dict(range=[0, 100], title='Budget (Crores)', fixedrange=True),
            yaxis=dict(title='', fixedrange=True),
            height=200,
            margin=dict(l=80, r=20, t=20, b=40),
            hovermode='closest'
        )
        
        st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    
    st.divider()
    
    # Teams side by side in middle
    st.subheader("👥 Teams Overview")
    team_col1, team_col2, team_col3 = st.columns(3)
    
    for idx, (col, team) in enumerate(zip([team_col1, team_col2, team_col3], ['TeamA', 'TeamB', 'TeamC'])):
        with col:
            team_data = st.session_state.teams[team]
            budget = st.session_state.budgets[team]
            spent = 100.0 - budget
            
            team_colors = {'TeamA': '🔴', 'TeamB': '🔵', 'TeamC': '🟢'}
            team_circle = team_colors.get(team, '⚪')
            
            # Extract players - handle both list and Team class
            players = []
            if isinstance(team_data, Team):
                for attr in ['Captain', 'WicketKeeper', 'StrikingOpener', 'NonStrikingOpener',
                           'OneDownBatsman', 'TwoDownBatsman', 'ThreeDownBatsman', 'FourDownBatsman',
                           'FiveDownBatsman', 'SixDownBatsman', 'SevenDownBatsman', 'EightDownBatsman', 'NineDownBatsman']:
                    p = getattr(team_data, attr, None)
                    if p and isinstance(p, Player):
                        players.append(p)
                for attr in ['PowerplayBowlers', 'MiddleOversBowlers', 'DeathOversBowlers', 'PlayersNotInPlayingXI']:
                    plist = getattr(team_data, attr, [])
                    if plist:
                        players.extend(plist)
                players = list({p.name: p for p in players}.values())
            elif isinstance(team_data, list):
                players = team_data
            else:
                players = []
            
            st.markdown(f"### {team_circle} {team}")
            st.metric("Players", len(players))
            st.metric("Budget Left", f"₹{budget:.2f} Cr")
            st.metric("Spent", f"₹{spent:.2f} Cr")
            
            if players:
                with st.expander("View Squad", expanded=False):
                    for player in players:
                        price = getattr(player, 'sold_price', 0)
                        role = getattr(player, 'role', 'N/A')
                        reason = getattr(player, 'reason_for_purchase', None)
                        
                        if reason:
                            # Display player with expandable reason
                            with st.expander(f"• {player.name} ({role}) - ₹{price:.2f}Cr", expanded=False):
                                st.caption(f"**Purchase Reason:** {reason}")
                        else:
                            st.write(f"• {player.name} ({role}) - ₹{price:.2f}Cr")
    
    st.divider()
    
    # Current auction and bid history - moved down
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("🎯 Current Auction")
        # Show completed banner near the auction area for better placement
        if st.session_state.auction_completed:
            col_save1, col_save2 = st.columns(2)
            with col_save1:
                if st.button("💾 Save Final State", key="save_final"):
                    filename = save_state_to_file()
                    if filename:
                        st.success(f"Saved to {filename}")
            with col_save2:
                st.info("All teams finalized!")
        
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
        # Unsold players section
        if st.session_state.unsold_players:
            st.subheader("❌ Unsold Players")
            with st.expander(f"View {len(st.session_state.unsold_players)} unsold players", expanded=False):
                for player in st.session_state.unsold_players:
                    st.write(f"• {player.name} ({player.role}) - Base: ₹{player.base_price:.2f} Cr")

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
    st.session_state.auction_completed = False
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
        st.session_state.auction_completed = True
        # Force rerun to show completion UI
        st.rerun()
        return False
    except Exception as e:
        print(f"[DEBUG] Stream error: {e}")
        st.session_state.auction_running = False
        st.session_state.auction_error = str(e)
        st.rerun()
        return False
    return False

def save_state_to_file():
    """Save current state to pickle file"""
    if st.session_state.current_state:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"saved_state_{timestamp}.pkl"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'wb') as f:
            pickle.dump(st.session_state.current_state, f)
        return filename
    return None

def main():
    init_session_state()
    
    st.title("🏏 IPL Mock Auction Dashboard")
    
    # Pre-auction settings
    if not st.session_state.auction_running and not st.session_state.auction_completed:
        with st.expander("⚙️ Auction Settings", expanded=False):
            st.session_state.save_preallocation = st.checkbox(
                "Save pre-allocation state (before team manager)",
                value=st.session_state.save_preallocation,
                help="Auto-save auction state before team allocation process"
            )
    
    # Control buttons
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("🚀 Start Mock Auction", key="start_btn", disabled=st.session_state.auction_running):
            st.session_state.bid_history = []
            st.session_state.teams = {'TeamA': [], 'TeamB': [], 'TeamC': []}
            st.session_state.budgets = {'TeamA': 100.0, 'TeamB': 100.0, 'TeamC': 100.0}
            st.session_state.unsold_players = []
            start_auction()
    
    with col2:
        if st.button("💾 Save & Stop", key="save_btn", disabled=not st.session_state.auction_running):
            filename = save_state_to_file()
            st.session_state.auction_running = False
            st.session_state.stream_iterator = None
            if filename:
                st.success(f"State saved to {filename}")
            st.rerun()
    
    with col3:
        if st.button("⏸️ Stop Auction", key="stop_btn", disabled=not st.session_state.auction_running):
            st.session_state.auction_running = False
            st.session_state.stream_iterator = None
            st.session_state.auction_completed = False
            st.warning("Auction stopped!")
            st.rerun()
    
    with col4:
        if st.button("🔄 Reset Dashboard", key="reset_btn"):
            st.session_state.auction_running = False
            st.session_state.stream_iterator = None
            for key in ['bid_history', 'teams', 'budgets', 'current_state', 'auction_error', 'auction_completed', 'unsold_players']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Show status (running / error)
    if st.session_state.auction_running:
        st.info("🔄 Auction running...")
    elif hasattr(st.session_state, 'auction_error') and st.session_state.auction_error:
        st.error(f"Auction error: {st.session_state.auction_error}")
    
    st.divider()
    
    # Render UI
    render_ui()
    
    # Process next auction state if running
    if st.session_state.auction_running and st.session_state.stream_iterator:
        if process_next_state():
            import time
            time.sleep(0.1)
            st.rerun()

if __name__ == "__main__":
    main()