import warnings
from langgraph.graph import StateGraph, END

from utils import AgentState, load_api_keys, prettyprint, export_sold_players_to_csv
from model_config import MODEL_NAME
from data_loader import initialize_auction
from host import host
from host_assistant import host_assistant
from agentpool import agent_pool
from trade_master import trademaster
import pickle
# Suppress NVIDIA API endpoint warnings
warnings.filterwarnings('ignore', category=UserWarning, module='langchain_nvidia_ai_endpoints')


load_api_keys()
# Initialize empty agent state - data_loader node will populate everything
agent: AgentState = {
    'RemainingPlayers': {},
    'RemainingSets': [],
    'CurrentSet': None,
    'RemainingPlayersInSet': None,
    'AuctionStatus': False,
    'CurrentPlayer': None,
    'CurrentBid': None,
    'OtherTeamBidding': None,
    'Round': 0,
    'CSK': [],
    'DC': [],
    'GT': [],
    'KKR': [],
    'LSG': [],
    'MI': [],
    'PBKS': [],
    'RR': [],
    'RCB': [],
    'SRH': [],
    'UnsoldPlayers': [],
    'CSK_Budget': 0.0,
    'DC_Budget': 0.0,
    'GT_Budget': 0.0,
    'KKR_Budget': 0.0,
    'LSG_Budget': 0.0,
    'MI_Budget': 0.0,
    'PBKS_Budget': 0.0,
    'RR_Budget': 0.0,
    'RCB_Budget': 0.0,
    'SRH_Budget': 0.0,
    'Messages': []
}



# Build the graph
graph_builder = StateGraph(AgentState)

# Add nodes
graph_builder.add_node("data_loader", initialize_auction)
graph_builder.add_node("host", lambda state: state)  # Host just passes state through
graph_builder.add_node("host_assistant", host_assistant)
graph_builder.add_node("bidder_pool", agent_pool)
graph_builder.add_node("trademaster", trademaster)
# Set entry point to data_loader
graph_builder.set_entry_point("data_loader")

# data_loader goes to host
graph_builder.add_edge("data_loader", "host")

# Add edges - all routing controlled by host
# host routes to host_assistant, bidder_pool, or END
graph_builder.add_conditional_edges(
    "host",
    host,
    {
        "host_assistant": "host_assistant",
        "bidder_pool": "bidder_pool",
        "end": END
    }
)

# host_assistant reports back to host
graph_builder.add_edge("host_assistant", "host")

# bidder_pool -> trademaster
graph_builder.add_edge("bidder_pool", "trademaster")

# trademaster reports back to host
graph_builder.add_edge("trademaster", "host")

# Compile the graph
graph = graph_builder.compile()

# Run the auction
prettyprint(agent)
print("Starting auction...\n")
# Save the graph visualization
with open('graph_visualization.png', 'wb') as f:
    f.write(graph.get_graph().draw_mermaid_png())
print(f"[MAIN] Invoking graph with recursion_limit=10000, CurrentPlayer={getattr(agent.get('CurrentPlayer'), 'name', None)}", flush=True)
# Run the graph with increased recursion limit and protect with logging
print("[MAIN] About to invoke graph.invoke(...)", flush=True)
try:
    result = graph.invoke(agent, {"recursion_limit": 10000})
    print("[MAIN] graph.invoke returned normally", flush=True)
except Exception as e:
    print(f"[MAIN] Exception during graph.invoke: {type(e).__name__}: {e}", flush=True)
    raise

print("\nAuction completed!")
pickle.dump(result, open("final_agent_state.pkl", "wb"))
print("Final agent state:")
prettyprint(result)

# Export all sold players (excluding retained) to CSV
export_sold_players_to_csv(result)
