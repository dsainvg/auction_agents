from langgraph.graph import StateGraph, END
from utils import *
from host import host
from host_assistant import host_assistant
from agentpool import agent_pool
from trade_master import trademaster

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
    'TeamC_Budget': 100.0
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
        "__end__": END
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
print("\nStarting auction...\n")
# Save the graph visualization
with open('graph_visualization.png', 'wb') as f:
    f.write(graph.get_graph().draw_mermaid_png())
# Run the graph with increased recursion limit
result = graph.invoke(agent, {"recursion_limit": 10000})

print("\nFinal state:")
prettyprint(result)

