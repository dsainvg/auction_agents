import warnings
from langgraph.graph import StateGraph, END

from utils import AgentState, load_api_keys, load_player_data, prettyprint
from model_config import MODEL_NAME
from host import host
from host_assistant import host_assistant
from agentpool import agent_pool
from trade_master import trademaster
import pickle
# Suppress NVIDIA API endpoint warnings
warnings.filterwarnings('ignore', category=UserWarning, module='langchain_nvidia_ai_endpoints')


load_api_keys()
# Initialize agent state with proper values
agent: AgentState = {
    'RemainingPlayers': load_player_data(),
    'RemainingSets': ['M1', 'M2', 'AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10', 'BA1', 'BA2', 'BA3', 'BA4', 'BA5', 'FA1', 'FA2', 'FA3', 'FA4', 'FA5', 'FA6', 'FA7', 'FA8', 'FA9', 'FA10', 'SP1', 'SP2', 'SP3', 'WK1', 'WK2', 'WK3', 'WK4', 'UAL1', 'UAL2', 'UAL3', 'UAL4', 'UAL5', 'UAL6', 'UAL7', 'UAL8', 'UAL9', 'UAL10', 'UAL11', 'UAL12', 'UAL13', 'UAL14', 'UAL15', 'UBA1', 'UBA2', 'UBA3', 'UBA4', 'UBA5', 'UBA6', 'UBA7', 'UBA8', 'UBA9', 'UFA1', 'UFA2', 'UFA3', 'UFA4', 'UFA5', 'UFA6', 'UFA7', 'UFA8', 'UFA9', 'UFA10', 'USP1', 'USP2', 'USP3', 'USP4', 'USP5', 'UWK1', 'UWK2', 'UWK3', 'UWK4', 'UWK5', 'UWK6'],
    'CurrentSet': None,
    'RemainingPlayersInSet': None,
    'AuctionStatus': False,
    'CurrentPlayer': None,
    'CurrentBid': None,
    'OtherTeamBidding': {},
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
    'CSK_Budget': 100.0,
    'DC_Budget': 100.0,
    'GT_Budget': 100.0,
    'KKR_Budget': 100.0,
    'LSG_Budget': 100.0,
    'MI_Budget': 100.0,
    'PBKS_Budget': 100.0,
    'RR_Budget': 100.0,
    'RCB_Budget': 100.0,
    'SRH_Budget': 100.0,
    'Messages': []
}



# Build the graph
graph_builder = StateGraph(AgentState)

# Add nodes
graph_builder.add_node("host", lambda state: state)  # Host just passes state through
graph_builder.add_node("host_assistant", host_assistant)
graph_builder.add_node("bidder_pool", agent_pool)
graph_builder.add_node("trademaster", trademaster)
# Set entry point
graph_builder.set_entry_point("host")

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
