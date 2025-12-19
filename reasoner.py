from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage
import re
import os
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
    "You are an expert IPL auction analyst.\n"
    f"Explain why {winning_team} should purchase {player.name} ({player.role}) NOW at INR {final_price:.2f} Cr, "
    "using a single dense paragraph that follows your system instructions.\n\n"
    "Context:\n"
    f"Player base price: {player.base_price}\n"
    f"Player previous sold price: {player.previous_sold_price}\n"
    f"Player category/experience: {player.category} / {player.experience}\n"
    f"Player stats: {player_stats}\n\n"
    "Teams summary:\n" + "\n".join(team_info_lines) + "\n\n"
    f"Available sets left: {remaining_sets_full}\n"
    f"Available players in current set: {remaining_players_in_set}\n"
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

    # Use a light system instruction (read as UTF-8, tolerant on Windows)
    prompt_path = os.path.join(os.path.dirname(__file__), 'PROMPTS', 'ReasonerSysPrompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8', errors='ignore') as f:
            system_prompt_text = f.read()
    except FileNotFoundError:
        # Fallback to old/case-variant path if needed
        alt_path = os.path.join(os.path.dirname(__file__), 'Prompts', 'reasonerSysprompt.txt')
        with open(alt_path, 'r', encoding='utf-8', errors='ignore') as f:
            system_prompt_text = f.read()
    system = SystemMessage(content=system_prompt_text)
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

    # Clean text and return all sentences as a single paragraph (no metadata)
    # Normalize whitespace and remove surrounding quotes
    text = text.strip().strip('"').strip("'")
    # Split into sentences
    sentences = re.split(r'(?<=[\.\!\?])\s+', text)
    # Filter out empty sentences and join all as a single paragraph
    non_empty_sentences = [s.strip() for s in sentences if s.strip()]
    essay_text = ' '.join(non_empty_sentences) if non_empty_sentences else text
    # Ensure it ends with a period
    if not re.search(r'[\.\!\?]$', essay_text):
        essay_text = essay_text.rstrip() + '.'
    return essay_text
