import warnings
from langgraph.graph import StateGraph, END

from utils import AgentState, load_api_keys, load_player_data, prettyprint
from model_config import MODEL_NAME
from host import host
from host_assistant import host_assistant
from agentpool import agent_pool
from trade_master import trademaster
import pickle
from team_manager import team_manager

# Suppress NVIDIA API endpoint warnings
warnings.filterwarnings('ignore', category=UserWarning, module='langchain_nvidia_ai_endpoints')


load_api_keys()
# Initialize agent state with proper values
agent: AgentState = {
    'RemainingPlayers': load_player_data(),
    'RemainingSets': ['SBC', 'SAC', 'SBwC', 'EBC', 'EAC', 'EBwC', 'MBC', 'MAC', 'MBwC', 'EmBwU', 'EmAU', 'EmBC'],
    'CurrentSet': None,
    'RemainingPlayersInSet': None,
    'AuctionStatus': False,
    'CurrentPlayer': None,
    'CurrentBid': None,
    'OtherTeamBidding': {},
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



# Build the graph
graph_builder = StateGraph(AgentState)

# Add nodes
graph_builder.add_node("host", lambda state: state)  # Host just passes state through
graph_builder.add_node("host_assistant", host_assistant)
graph_builder.add_node("bidder_pool", agent_pool)
graph_builder.add_node("trademaster", trademaster)
graph_builder.add_node("team_manager", team_manager)
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
        "team_manager": "team_manager"
    }
)

# host_assistant reports back to host
graph_builder.add_edge("host_assistant", "host")

# bidder_pool -> trademaster
graph_builder.add_edge("bidder_pool", "trademaster")

# trademaster reports back to host
graph_builder.add_edge("trademaster", "host")

# team_manager -> END
graph_builder.add_edge("team_manager", END)
# Compile the graph
graph = graph_builder.compile()

# Run the auction
prettyprint(agent)
print("Starting auction...\n")
# Save the graph visualization
with open('graph_visualization.png', 'wb') as f:
    f.write(graph.get_graph().draw_mermaid_png())
print(f"[MAIN] Invoking graph with recursion_limit=10000, CurrentPlayer={getattr(agent.get('CurrentPlayer'), 'name', None)}", flush=True)
# Run the graph with increased recursion limit
result = graph.invoke(agent, {"recursion_limit": 10000})

print("\nAuction completed!")
pickle.dump(result, open("final_agent_state.pkl", "wb"))
print("Final agent state:")
prettyprint(result)
