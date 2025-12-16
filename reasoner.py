from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage
import re
from model_config import MODEL_NAME, TEMPERATURE, TOP_P, MAX_TOKENS, EXTRA_BODY
from utils import AgentState, Player, get_player_stats, get_next_api_key, get_set_name

def _build_reasoner_prompt(state: AgentState, player: Player, winning_team: str, final_price: float) -> str:
    # Collect team compositions and budgets
    teams = ['TeamA', 'TeamB', 'TeamC']
    team_info_lines = []
    for t in teams:
        comp = state.get(t, [])
        budget = state.get(f"{t}_Budget", 0.0)
        team_info_lines.append(f"{t}: budget={budget}, squad_size={len(comp)}")

    remaining_sets = state.get('RemainingSets', [])
    # Convert set abbreviations to full names like agentpool does
    try:
        remaining_sets_full = get_set_name(remaining_sets)
    except Exception:
        remaining_sets_full = remaining_sets
    remaining_players_in_set = state.get('RemainingPlayersInSet', [])

    player_stats = get_player_stats(player.name)

    human = (
        f"You are an expert IPL auction analyst.\n"
        f"Provide a concise single-paragraph (3-4 sentences) explanation why {winning_team} should purchase {player.name} ({player.role}) NOW at INR {final_price:.2f} Cr given the context below.\n\n"
        f"Context:\n"
        f"Player base price: {player.base_price}\n"
        f"Player previous sold price: {player.previous_sold_price}\n"
        f"Player category/experience: {player.category} / {player.experience}\n"
        f"Player stats: {player_stats}\n\n"
        f"Teams summary:\n" + "\n".join(team_info_lines) + "\n\n"
        f"Available sets left: {remaining_sets_full}\n"
        f"Available players in current set: {remaining_players_in_set}\n\n"
        f"Instruction: In the single paragraph include these elements: (1) the player's specialty/specific role (e.g., power-hitter, finisher, strike bowler, death overs specialist, all-rounder), (2) how this specialty fits into {winning_team}'s current squad and strategy, (3) a clear justification of the price being paid and an explicit mention of the price and whether it is fair/value-for-money compared to expectations, and (4) one short actionable suggestion for how to use or develop the player. Keep the whole answer to one paragraph of 3-4 sentences and DO NOT output additional paragraphs or metadata."
    )
    return human

def generate_purchase_reason(state: AgentState, player: Player, winning_team: str, final_price: float) -> str:
    """Call LLM to generate a single-paragraph reason+suggestion string.

    Returns: single string (one paragraph) containing the reason and short suggestions.
    """
    human_prompt = _build_reasoner_prompt(state, player, winning_team, final_price)

    api_key = None
    api_key_id = None
    try:
        api_key, api_key_id = get_next_api_key()
    except Exception:
        api_key = None
        api_key_id = None

    # Log which API key index is used for the reasoner call
    if api_key_id is not None:
        print(f"Reasoner: Using NVIDIA API key #{api_key_id}")

    llm = ChatNVIDIA(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_TOKENS,
        api_key=api_key,
        extra_body=EXTRA_BODY,
    )

    # Use a light system instruction
    system = SystemMessage(content="You are a concise cricket auction analyst.")
    human = HumanMessage(content=human_prompt)
    print("Invoking reasoner LLM...")
    # print("Prompt:", flush=True)
    # print(system, flush=True)
    # print(human, flush=True)
    try:
        response = llm.invoke([system, human])
        # Try to extract assistant content safely
        if hasattr(response, 'content') and isinstance(response.content, str):
            text = response.content
        elif isinstance(response, dict):
            # common key names
            text = response.get('content') or response.get('text') or str(response)
        else:
            s = str(response)
            # look for patterns like content='...' or "content": '...'
            m = re.search(r"content\s*[:=]\s*['\"](.*?)['\"]", s)
            if m:
                text = m.group(1)
            else:
                text = s
    except Exception:
        # Fallback text if model call fails
        text = f"{winning_team} acquiring {player.name} at INR {final_price:.2f} is a strategic move due to squad balance and available budget."

    # Clean text and return only the first sentence (no metadata)
    # Normalize whitespace and remove surrounding quotes
    text = text.strip().strip('"').strip("'")
    # Split into sentences; pick the first non-empty sentence
    sentences = re.split(r'(?<=[\.\!\?])\s+', text)
    first_sentence = sentences[0].strip() if sentences and sentences[0].strip() else text
    # Ensure it ends with a period
    if not re.search(r'[\.\!\?]$', first_sentence):
        first_sentence = first_sentence.rstrip() + '.'
    return first_sentence
