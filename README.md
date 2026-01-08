# IPL Auction Mock Simulator

## Project Overview

This project is an **AI-powered IPL (Indian Premier League) Cricket Auction Simulator** that uses advanced language models and multi-agent systems to autonomously conduct realistic cricket player auctions. The system simulates bidding behavior of all 10 IPL franchises using intelligent AI agents that make strategic purchasing decisions based on player statistics, team composition, budget constraints, and game-theoretic principles.

## Purpose & Motivation

The primary goals of this project are:

1. **Realistic Auction Simulation**: Model the complex decision-making process in cricket team auctions with intelligent agents rather than simple rule-based bots
2. **AI-Driven Strategy**: Leverage large language models (LLMs) to generate human-like bidding strategies and reasoning
3. **Team Building Optimization**: Explore how teams can build balanced squads considering budget constraints, player specialisms, and market dynamics
4. **Research & Analysis**: Provide insights into auction dynamics, player valuations, and strategic team-building approaches
5. **Interactive Dashboard**: Visualize auction progress in real-time through a Streamlit-based web interface

## Key Features

- **Multi-Agent Architecture**: 10 independent AI agents (one per IPL team) make autonomous bidding decisions
- **LLM-Powered Decision Making**: Uses NVIDIA AI endpoints (Deepseek v3.1) for strategic reasoning
- **Realistic IPL 2025 Auction Structure**: Implements actual IPL 2025 auction sets (Marquee, Capped, Uncapped players across all specialisms)
- **Budget Management**: Each team has a ₹12.5 Crore budget; agents respect budget constraints
- **Dynamic Bidding**: Agents evaluate bids using:
  - Player statistics and international experience
  - Team composition gaps
  - Budget optimization
  - Competitive game-theoretic strategies
- **Real-time Dashboard**: Streamlit interface for monitoring auctions, viewing results, and analyzing team compositions
- **Detailed Logging**: Comprehensive message tracking for debugging and analysis
- **Results Export**: Saves final auction results to CSV for further analysis

### Core Components

#### 1. **data_loader.py**
- Loads player data from CSV database (`DB/players.csv`)
- Organizes players into 68 IPL auction sets (M1, M2, AL1-AL10, BA1-BA5, etc.)
- Associates player statistics from individual stat files
- Initializes auction state with team budgets (₹12.5 Cr each) and empty squad lists

#### 2. **host.py**
- Central orchestrator/router for the auction workflow
- Determines next action based on current state:
  - Routes to `host_assistant` when ready to select new player
  - Routes to `bidder_pool` when auction is active
  - Routes to `END` when auction is complete

#### 3. **host_assistant.py**
- Selects the next set and player for auction
- Manages set transitions when all players in a set are sold/unsold
- Updates auction status and tracks remaining players

#### 4. **agentpool.py**
- Processes bidding from eligible teams sequentially (greedy approach)
- Each team evaluates whether to raise, pass, or make custom bids
- Uses NVIDIA LLM to generate strategic bidding decisions
- Returns first valid bid found for trade_master to process
- Implements minimum bid increments (escalating based on current bid amount)

#### 5. **trade_master.py**
- Processes single bid from agent pool
- Updates CurrentBid with winning team and amount
- Tracks bidding rounds (max 2 rounds per player)
- Finalizes sale when round limit reached
- Triggers AI reasoner to generate purchase justification
- Marks unsold players if no bids received

#### 6. **reasoner.py**
- Generates AI-powered explanation for why a team purchased a player
- Creates contextual narrative using:
  - Player statistics and specialisms
  - Team composition and gaps
  - Budget situation and strategy
  - Remaining sets and available players

#### 7. **utils.py**
- Defines core data structures:
  - `Player`: Comprehensive player object with stats, bids, and sell status
  - `CurrentBidInfo`: Current winning bid information
  - `CompetitiveBidInfo`: New bid from team
  - `AgentState`: Complete auction state (TypedDict with messaging)
- API key management for NVIDIA endpoints
- Bid increment calculation logic
- CSV export utilities
- Prompt loading and utilities

#### 8. **streamlit_dashboard.py**
- Web-based UI for real-time auction monitoring
- Features:
  - Start/stop auction controls
  - Live auction progress display
  - Team compositions and budgets
  - Bid history visualization
  - Final results and unsold players list
  - CSV export of sold players

#### 9. **model_config.py**
- Configuration for LLM parameters:
  - Model: OpenAI GPT-OSS 120B (via NVIDIA)
  - Temperature: 0.7
  - Top-P: 0.9
  - Max tokens: 4096
  - Rate limiting between requests

#### 10. **main_process.py**
- CLI entry point for headless auction execution
- Runs full auction simulation and saves results
- Generates graph visualization

### Data Structures

#### AgentState (TypedDict)
```python
{
    'RemainingPlayers': Dict[str, List[Player]],      # Players by set
    'RemainingSets': List[str],                        # Sets not yet auctioned
    'CurrentSet': Optional[str],                       # Current auction set
    'RemainingPlayersInSet': Optional[List[Player]],   # Players in current set
    'AuctionStatus': bool,                             # Is auction active for current player
    'CurrentPlayer': Optional[Player],                 # Player being auctioned
    'CurrentBid': Optional[CurrentBidInfo],            # Winning bid so far
    'OtherTeamBidding': Optional[CompetitiveBidInfo],  # New bid from agent pool
    'Round': int,                                      # Bidding round counter (max 2)
    'CSK', 'DC', 'GT', 'KKR', 'LSG', 'MI', ...         # Squad lists for each team
    'CSK_Budget', 'DC_Budget', ...                     # Remaining budget for each team
    'UnsoldPlayers': List[Player],                     # Players with no bids
    'Messages': List[AIMessage]                        # Execution log
}
```

### IPL 2025 Auction Structure

The simulator implements actual IPL 2025 auction sets:

- **Marquee (M1, M2)**: Top 2 star players, minimum 2 Cr reserve price
- **Capped Allrounders (AL1-AL10)**: 10 slots for experienced all-rounders
- **Capped Batters (BA1-BA5)**: 5 slots for experienced batters
- **Capped Fast Bowlers (FA1-FA10)**: 10 slots for experienced fast bowlers
- **Capped Spinners (SP1-SP3)**: 3 slots for experienced spinners
- **Capped Wicketkeepers (WK1-WK4)**: 4 slots for experienced keepers
- **Uncapped Allrounders (UAL1-UAL15)**: 15 slots for young all-rounders
- **Uncapped Batters (UBA1-UBA9)**: 9 slots for young batters
- **Uncapped Fast Bowlers (UFA1-UFA10)**: 10 slots for young fast bowlers
- **Uncapped Spinners (USP1-USP5)**: 5 slots for young spinners
- **Uncapped Wicketkeepers (UWK1-UWK6)**: 6 slots for young keepers

## How It's Implemented

### Workflow Flow

1. **Initialization** (`data_loader`)
   - Load all 68 sets of players from database
   - Initialize 10 teams with ₹12.5 Cr budget each
   - Set up empty squads and tracking structures

2. **Player Selection** (`host_assistant`)
   - Pick next available set
   - Select first player from set
   - Mark auction as active

3. **Bidding Round** (`agentpool`)
   - Eligible teams are processed sequentially
   - Each team uses NVIDIA LLM to decide: raise, pass, or custom bid
   - LLM considers:
     - Player stats and role fit
     - Current squad composition
     - Budget remaining
     - Strategic value and scarcity
     - Market conditions
   - First team to raise becomes new highest bidder

4. **Trade Processing** (`trade_master`)
   - Update CurrentBid with new highest bid
   - Increment round counter
   - If round > 2: Finalize sale and update team squad
   - Clear bid and reset for next player

5. **AI Explanation** (`reasoner`)
   - Generate contextual narrative for purchase
   - Explain strategic value using LLM
   - Store reasoning with player record

6. **Dashboard Display** (`streamlit_dashboard`)
   - Show live auction progress
   - Display bids, teams, and budgets
   - Visualize team compositions
   - Export final results

### Bidding Strategy

Teams use structured reasoning to make bids based on:

1. **Player Value Assessment**
   - International experience (Test, ODI, T20 caps)
   - IPL statistics and performance
   - Specialization and role fit
   - Scarcity in market

2. **Team Composition Analysis**
   - Current squad gaps
   - Balance of roles (batters, bowlers, all-rounders)
   - Bench strength

3. **Budget Optimization**
   - Remaining purse
   - Expected costs of remaining sets
   - Opportunity cost of overspending

4. **Game-Theoretic Considerations**
   - Stress rival teams' budgets
   - Exploit mispricings
   - Avoid emotional bidding

### Bid Increment System

- First bid: Can bid at reserve price (₹ amount/100 Lakhs)
- Subsequent bids: Minimum increment scales with bid amount
  - ₹0-50 Cr: ₹10 Lakhs increment
  - ₹50-100 Cr: ₹20 Lakhs increment
  - ₹100+ Cr: ₹50 Lakhs increment

## Technologies Used

- **Python 3.x**: Core programming language
- **LangGraph**: Multi-agent workflow orchestration
- **LangChain**: LLM integration framework
- **NVIDIA AI Endpoints**: GPT-OSS 120B model access
- **Streamlit**: Interactive web dashboard
- **Plotly**: Data visualization
- **Pandas/CSV**: Data handling and export

## File Structure

```
ipl-mock/
├── main_process.py              # CLI entry point
├── streamlit_dashboard.py        # Web UI
├── host.py                      # Main router/orchestrator
├── host_assistant.py            # Player selector
├── agentpool.py                 # Team bidders
├── trade_master.py              # Bid processor
├── reasoner.py                  # AI explainer
├── data_loader.py               # Data initialization
├── utils.py                     # Core data structures & utilities
├── model_config.py              # LLM configuration
├── DB/
│   ├── players.csv              # Player database
│   ├── teams_purse.csv          # Team budgets
│   ├── retained_players.csv     # Pre-retained players
│   ├── orderOfSets.csv          # Auction order
│   └── stats/                   # Individual player stats (1.txt, 2.txt, ...)
├── PROMPTS/
│   ├── Sys.txt                  # Bidding agent system prompt
│   ├── Human.txt                # Bidding agent human prompt template
│   └── ReasonerSysPrompt.txt    # Purchase explanation prompt
└── requirements.txt             # Python dependencies
```

## Running the Project

### Prerequisites
- Python 3.8+
- NVIDIA API keys with access to GPT-OSS 120B model
- `.env` file with API keys configured

### Installation
```bash
pip install -r requirements.txt
```

### Running CLI Auction
```bash
python main_process.py
```

### Running Interactive Dashboard
```bash
streamlit run streamlit_dashboard.py
```

## Results & Outputs

The simulator generates:
- **Console Logs**: Detailed execution trace with agent decisions
- **Graph Visualization**: `graph_visualization.png` showing state flow
- **Agent State Pickle**: `final_agent_state.pkl` with complete auction state
- **CSV Export**: `streamlit_auction_sold_players.csv` with sold players and details
- **Dashboard Display**: Real-time visualization of auction progress and results

## Future Enhancements

- Historical auction data integration for more realistic valuations
- Player injury/retirement handling
- Auction interruptions and rule variations
- Multi-year retention strategy modeling
- Win probability calculations for hypothetical team compositions
- Performance predictions based on drafted squads

## Research Applications

This simulator enables research into:
- Cricket team-building optimization algorithms
- Auction game theory and strategic bidding
- AI decision-making in economic simulations
- LLM reasoning capabilities for complex multi-agent scenarios
- Real-world auction mechanism design

---

**Note**: This is a research project simulating IPL cricket auctions using AI agents. Results are for analytical purposes and do not predict actual IPL auction outcomes.

---

## Complete Project Explanation (For Academic Evaluation)

### What This Project Does

This project creates a complete simulation of how cricket teams buy players in the Indian Premier League (IPL) auction, but instead of having humans make the decisions, I've built artificial intelligence agents that act as the decision-makers for each team. The core idea is to see if we can train computer programs to think strategically about building sports teams the way experienced team managers do.

In a real IPL auction, representatives from 10 cricket teams sit together and bid on players. Each team has a fixed budget (125 Crores of Indian Rupees) and needs to build a squad of around 25 players covering different roles like batsmen, bowlers, all-rounders, and wicketkeepers. The challenge is that every team wants the best players, but they must manage their money carefully because once it's spent, they can't buy more players. This creates a complex decision-making environment where you need to balance immediate needs with long-term strategy.

### The Problem I'm Solving

Traditional simulations of such auctions typically use simple rule-based systems. For example, a rule might say "if the player is a batsman and we need batsmen and we have enough budget, then bid." These systems are predictable and don't capture the nuanced thinking that real decision-makers use. They can't reason about things like:
- "Should we let this player go even though we need him, because saving money now lets us afford a better player later?"
- "Is this player overpriced compared to similar players who might come up for auction later?"
- "Should we deliberately drive up the price to drain a rival team's budget?"

My project tackles this by using large language models - the same type of AI that powers systems like ChatGPT - to make these decisions. These models can process complex information, reason about trade-offs, and generate human-like strategic thinking.

### How The System Works - A Complete Walkthrough

Let me explain how the entire system operates from start to finish:

**Step 1: Data Preparation and Loading**
When the program starts, it reads a database of 370 cricket players. Each player has detailed information including their name, what role they play (batsman, bowler, etc.), their performance statistics from past matches, how many international games they've played, and what their minimum auction price (reserve price) is. This data is organized into 39 different groups or "sets" based on the player's experience level and role. For example, there's a set for top star players (Marquee Set), sets for experienced batsmen, sets for young uncapped bowlers, and so on.

**Step 2: Setting Up The Auction Environment**
Each of the 10 teams (Chennai Super Kings, Mumbai Indians, Royal Challengers Bangalore, etc.) starts with an empty squad and exactly 12.5 Crores in their budget. The system creates what we call an "agent state" - this is essentially a detailed record book that tracks everything: which players have been sold, which teams have bought them, how much money each team has left, whose turn it is to be auctioned, and the complete history of every bid made.

**Step 3: The Auction Coordinator (Host)**
I've created a "host" component that acts like the auctioneer in a real auction. Its job is to manage the flow of the auction. It decides when to bring a new player up for bidding, when to ask teams to place their bids, when to finalize a sale, and when the entire auction is complete. Think of it as the traffic controller that ensures everything happens in the right order.

**Step 4: Selecting Players for Auction (Host Assistant)**
The host assistant's job is to pick which player comes up for auction next. It follows the IPL's actual auction structure - it goes through the sets in order, and within each set, it presents players one by one. When a set is finished, it moves to the next set. This component also handles the bookkeeping of marking when sets are completed and removing sold or unsold players from the remaining pool.

**Step 5: The Bidding Process (Agent Pool)**
This is where the real intelligence happens. When a player is put up for auction, the agent pool component goes through each of the 10 teams and asks them if they want to bid. But here's the crucial part - instead of using simple rules, it sends all the relevant information to a large language model. 

For each team, the system constructs a detailed message that includes:
- The current player's complete profile and statistics
- The team's current squad composition and what roles they're missing
- How much budget the team has left
- What other players are still coming up for auction in future sets
- The current bid amount (if someone has already bid)
- The minimum amount they need to bid if they want this player

This information is sent to the language model along with carefully designed instructions that tell it to think like a strategic team manager. The model then processes all this information and returns a decision: either "pass" (don't bid on this player) or "raise" (place a higher bid). If it decides to raise, it must also provide reasoning for why this is a good decision.

The clever part is that the system processes teams in a specific order to make the auction realistic. It looks at which teams have shown more interest in the player in previous rounds and gives them priority. This mimics how real auctions work where teams that really want a player keep coming back.

**Step 6: Processing The Bids (Trade Master)**
Once the agent pool finds a team that wants to bid higher, the trade master component takes over. Its job is to update the official record of who the current highest bidder is and how much they've bid. It also keeps track of how many rounds of bidding have happened for this player.

The trade master implements a key rule: if two complete rounds go by without any new bids, the auction for that player is over and they're sold to the current highest bidder. If no one bids at all, the player is marked as "unsold." This mirrors real IPL auction rules.

**Step 7: Explaining The Purchase (Reasoner)**
When a player is finally sold to a team, the system does something interesting - it generates a human-readable explanation of why this purchase makes sense. It sends all the context (player details, team composition, budget situation, strategic considerations) to the language model again, but this time with different instructions: write a paragraph explaining the strategic value of this acquisition.

This serves two purposes: it makes the simulation more interpretable (we can understand the AI's reasoning), and it creates a record that can be analyzed later to see if the AI's stated reasoning matches actual good team-building practices.

**Step 8: Recording and Moving Forward**
After each player is processed (whether sold or unsold), the system updates all the records:
- If sold: the player is added to the winning team's squad, their budget is reduced by the sale price, and the player is marked as owned
- If unsold: the player is added to a separate unsold list
- The current player is cleared, and the system signals it's ready for the next player

This entire process (steps 4-8) repeats for every single player in the database until all players have been auctioned.

### The Technical Architecture

From a computer science perspective, I've implemented this using a framework called LangGraph, which is designed for building applications where multiple AI agents work together. The system is structured as a state machine - a computer science concept where the program can be in different states, and specific events cause transitions between states.

The states in my system are:
- Loading data state
- Selecting next player state  
- Actively bidding on a player state
- Finalizing a sale state
- Auction complete state

The state machine ensures that the auction follows a logical flow and that impossible situations can't occur (like trying to bid on a player who's already been sold, or spending more money than a team has).

### The AI Decision-Making Process

The most important aspect of this project is how the AI agents make decisions. When evaluating whether to bid on a player, the language model considers multiple factors simultaneously:

1. **Player Quality Assessment**: It looks at the player's statistics, international experience, and IPL track record to judge their skill level.

2. **Team Fit Analysis**: It examines the current squad composition to determine if this player fills a gap. For example, if the team already has 5 great batsmen but no good bowlers, it should prioritize bowlers.

3. **Financial Planning**: It calculates whether the team can afford this player while still having enough money left for future essential purchases. This requires reasoning about future scarcity - if most players are still to come, you can spend less now, but if this is one of the last good bowlers available, you might need to pay premium.

4. **Competitive Strategy**: It considers what other teams might do. Sometimes it's worth bidding to drain a rival's budget even if you don't desperately need the player.

5. **Value Assessment**: It tries to determine if the player is priced fairly or if they're overpriced/underpriced compared to their actual value.

The language model processes all these considerations together and generates structured output indicating its decision and reasoning. This is fundamentally different from simple rule-based systems because it can handle the complexity of weighing multiple competing factors and doesn't require explicitly programming every possible scenario.

### The Visualization Interface

To make the simulation observable and interactive, I've built a web-based dashboard using Streamlit. This provides a visual interface where you can:
- Start and stop the auction
- Watch in real-time as players are auctioned and teams place bids
- See updated team compositions and budgets after each sale
- View the complete history of bidding for any player
- Examine the final squads and see which players went unsold
- Export all the results to a spreadsheet for further analysis

This dashboard makes the project accessible to non-technical users who want to explore how the AI agents behave without needing to read code or console logs.

### Why This Project Matters

From a research perspective, this project demonstrates several important concepts:

**1. Multi-Agent Decision Making**: Real-world scenarios often involve multiple independent decision-makers whose actions affect each other. This project shows how AI agents can operate in such environments, learning to make decisions while considering what other agents might do.

**2. Complex Reasoning Under Constraints**: The agents must reason about resource allocation (budget), timing (when to spend), uncertainty (future player availability), and competition (other teams' strategies) simultaneously. This is much closer to real-world decision-making than simple optimization problems.

**3. Explainable AI**: By having the system generate reasoning for its decisions, we can understand and evaluate the AI's thinking process. This is crucial for building trustworthy AI systems, especially in domains where decisions have significant consequences.

**4. Economic Simulation**: The auction mechanism itself is an interesting economic system with elements of game theory, resource allocation, and strategic behavior. Simulating it with AI agents lets us study these dynamics in ways that would be expensive or impossible with human participants.

**5. Transfer Learning**: The large language models I'm using were trained on vast amounts of text from the internet, including sports analysis, strategy articles, and auction discussions. The project demonstrates how this general knowledge can be applied to a specific domain (cricket auctions) without requiring specialized training data.

### Challenges Overcome

Building this system involved solving several technical challenges:

- **State Management**: Keeping track of all the information (over 1000 players, 10 teams, budgets, bids, messages) in a way that's both efficient and prevents errors required careful design of data structures.

- **API Rate Limiting**: Language model APIs have limits on how many requests you can make per minute. With 10 teams potentially querying the model for every player, this could mean thousands of API calls. I implemented request pacing and API key rotation to handle this.

- **Prompt Engineering**: Getting the language model to consistently return valid, strategic decisions required carefully crafting the instructions I send it. The prompts needed to be detailed enough to guide good decisions but flexible enough to allow creative thinking.

- **Deterministic Flow Control**: While the AI's decisions are somewhat random, the overall auction process must be deterministic and follow IPL rules exactly. Balancing AI flexibility with rule adherence required careful system design.

- **Performance Optimization**: With over 1100 players and multiple bidding rounds each, the simulation could take hours. I optimized the bidding process to stop as soon as the first valid bid is found rather than querying all teams every time.

### Potential Extensions and Future Work

This project establishes a foundation that could be extended in several directions:

- **Historical Validation**: Compare the AI agents' decisions and team compositions against actual IPL auction results to measure how realistic the simulation is
- **Strategy Optimization**: Run thousands of simulations with different strategies to identify optimal auction approaches
- **Player Performance Modeling**: Integrate predictive models that estimate how well a purchased squad would perform in actual matches
- **Interactive Mode**: Allow a human to control one team while AI agents control the others, creating a training tool for auction strategy
- **Different Auction Formats**: Adapt the system to simulate other sports leagues (NBA, Premier League) or non-sports auctions

### Academic Contribution

This project contributes to the academic understanding of artificial intelligence in several ways:

It demonstrates practical application of large language models beyond simple text generation tasks, showing they can handle structured decision-making in constrained environments. It provides a testbed for studying multi-agent AI systems where agents must compete and cooperate simultaneously. It offers insights into how AI can be used for sports analytics and strategy development. And it creates a reproducible framework that other researchers can build upon or adapt to different domains.

The complete source code, data, and documentation are organized to allow other researchers to replicate the work, modify components, and conduct their own experiments with different auction mechanisms, AI models, or decision strategies.

### Conclusion

In summary, this project builds a complete, end-to-end simulation of IPL cricket auctions where artificial intelligence agents replace human decision-makers. It combines several computer science disciplines - artificial intelligence, multi-agent systems, software engineering, and data analysis - to create a realistic and observable model of a complex real-world process. The system successfully demonstrates that modern language models can reason strategically about resource allocation, competition, and team building in ways that go far beyond simple rule-based automation. The resulting tool serves both as a research platform for studying AI decision-making and as a practical simulator that could be used by sports analysts to explore auction strategies and team-building approaches.
