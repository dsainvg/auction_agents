from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from utils import AgentState, Player, Team, get_player_stats
from model_config import MODEL_NAME, TEMPERATURE, TOP_P, MAX_TOKENS, EXTRA_BODY
from utils import get_next_api_key
import difflib

class TeamManagerInput(BaseModel):
    Captain: str = Field(..., description="Name of the captain of the team.")
    WicketKeeper: str = Field(..., description="Name of the wicket keeper of the team.")
    StrikingOpener : str = Field(..., description="Name of the striking opener of the team.")
    NonStrikingOpener : str = Field(..., description="Name of the non-striking opener of the team.")
    OneDownBatsman : str = Field(..., description="Name of the one down batsman of the team.")
    TwoDownBatsman : str = Field(..., description="Name of the two down batsman of the team.")
    ThreeDownBatsman : str = Field(..., description="Name of the three down batsman of the team.")
    FourDownBatsman : str = Field(..., description="Name of the four down batsman of the team.")
    FiveDownBatsman : str = Field(..., description="Name of the five down batsman of the team.")
    SixDownBatsman : str = Field(..., description="Name of the six down batsman of the team.")
    SevenDownBatsman : str = Field(..., description="Name of the seven down batsman of the team.")
    EightDownBatsman : str = Field(..., description="Name of the eight down batsman of the team.")
    NineDownBatsman : str = Field(..., description="Name of the nine down batsman of the team.")
    PowerplayBowlers : list[str] = Field(..., description="List of names of the bowlers to be used in powerplay overs.")
    MiddleOversBowlers : list[str] = Field(..., description="List of names of the bowlers to be used in middle overs.")
    DeathOversBowlers : list[str] = Field(..., description="List of names of the bowlers to be used in death overs.")
    PlayersNotInPlayingXI : list[str] = Field(..., description="List of names of players not in the playing XI.")

def _build_team_manager_human_prompt(team_name: str, team_players: list[Player]) -> str:
    """Builds the data-focused human prompt for the team manager AI."""
    player_details = []
    for player in team_players:
        player_details.append(
            f"Name: {player.name}, Role: {player.role}, Price: {player.sold_price} Cr, "
            f"Base Price: {player.base_price} Cr, Previous Sold Price: {player.previous_sold_price} Cr, "
            f"Category/Experience: {player.category} / {player.experience}, "
            f"Reason for Purchase: {player.reason_for_purchase}"
        )

    player_details_str = "\n\n".join(player_details)
    squad_size = len(team_players)
    num_out_of_xi = max(0, squad_size - 11)

    prompt = (
        f"Team: {team_name}\n\n"
        f"Total players in squad: {squad_size}. You MUST select exactly 11 unique players for the Playing XI. "
        f"Exactly {num_out_of_xi} players must be in PlayersNotInPlayingXI.\n\n"
        "Squad Details (no stats, only roles, prices and reasons):\n"
        f"{player_details_str}\n\n"
        "Note: Do not change player name spellings; adhere to the names listed above.\n"
    )
    return prompt


def team_manager(state: AgentState) -> AgentState:
    """
    This function analyzes the teams and assigns roles to the players using an AI model.
    """
    import pickle
    pickle.dump(state, open("PreTeamAllocation.pkl", "wb"))
    print("Team Manager invoked. Current state:")
    for team_name in ['TeamA', 'TeamB', 'TeamC']:
        team_players = state.get(team_name)

        if not team_players or isinstance(team_players, Team):
            continue

        human_prompt = _build_team_manager_human_prompt(team_name, team_players)
        
        api_key, api_key_id = get_next_api_key()
        print(f"Team Manager ({team_name}): Using NVIDIA API key #{api_key_id}")

        llm = ChatNVIDIA(
            model="deepseek-ai/deepseek-v3.2",
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_tokens=4*MAX_TOKENS,
            api_key=api_key,
            extra_body={"chat_template_kwargs": {"thinking":True}}
        )

        with open('PROMPTS/CoachSysPrompt.txt', 'r', encoding='utf-8',errors='ignore') as f:
            sys_prompt = f.read()
        
        system_message = SystemMessage(content=sys_prompt)
        human_message = HumanMessage(content=human_prompt)

        print(f"Invoking Team Manager LLM for {team_name}...")
        response = llm.invoke([system_message, human_message])
        print(f"Team Manager LLM response for {team_name}: {response}")
        team_manager_input = None
        try:
            # The response content should be a JSON string that can be parsed
            team_manager_input = TeamManagerInput.model_validate_json(response.content)
        except Exception:
            # If direct parsing fails, try to extract JSON from the response content
            print(f"Direct JSON parsing failed for team {team_name}, attempting fallback.")
            try:
                # Find the JSON part of the response
                json_start = response.content.find('{')
                json_end = response.content.rfind('}') + 1
                if json_start != -1 and json_end != 0:
                    json_str = response.content[json_start:json_end]
                    team_manager_input = TeamManagerInput.model_validate_json(json_str)
                else:
                    raise ValueError("No JSON object found in the response.")
            except Exception as e:
                print(f"Fallback JSON parsing also failed for team {team_name}: {e}")

        if team_manager_input:
            all_player_names = set()
            for field_name, field_value in team_manager_input:
                if field_name == "PlayersNotInPlayingXI":
                    continue
                elif isinstance(field_value, str):
                    all_player_names.add(field_value)
                elif isinstance(field_value, list):
                    all_player_names.update(field_value)

            if len(all_player_names) > 11:
                print(f"Warning: Team {team_name} has {len(all_player_names)} unique players specified, which is more than 11.")
            try:
                player_map = {p.name: p for p in team_players}

                # Helper to get player from map
                def get_player(name):
                    # 1. Exact match
                    player = player_map.get(name)
                    if player:
                        return player
                    
                    # 2. Fuzzy match
                    # The LLM might hallucinate and add extra details to the name.
                    # Let's try to be more robust by stripping special characters and extra spaces.
                    normalized_name = " ".join(str(name).strip().split())

                    player = player_map.get(normalized_name)
                    if player:
                        print(f"Found player with normalized name '{normalized_name}' for original '{name}'")
                        return player

                    # Find close matches
                    close_matches = difflib.get_close_matches(normalized_name, player_map.keys(), n=1, cutoff=0.8)
                    if close_matches:
                        matched_name = close_matches[0]
                        print(f"Warning: Player '{name}' not found. Using closest match '{matched_name}'.")
                        return player_map[matched_name]

                    # 3. Fallback to dummy player
                    print(f"Warning: Player '{name}' not found in team '{team_name}' and no close match found. Using a dummy player.")
                    return Player(name=name, role="Unknown", base_price=0, previous_sold_price=0, category="Unknown", experience="Unknown", set="Unknown")

                # Create the Team object
                team = Team(
                    Name=team_name,
                    Captain=get_player(team_manager_input.Captain),
                    WicketKeeper=get_player(team_manager_input.WicketKeeper),
                    StrikingOpener=get_player(team_manager_input.StrikingOpener),
                    NonStrikingOpener=get_player(team_manager_input.NonStrikingOpener),
                    OneDownBatsman=get_player(team_manager_input.OneDownBatsman),
                    TwoDownBatsman=get_player(team_manager_input.TwoDownBatsman),
                    ThreeDownBatsman=get_player(team_manager_input.ThreeDownBatsman),
                    FourDownBatsman=get_player(team_manager_input.FourDownBatsman),
                    FiveDownBatsman=get_player(team_manager_input.FiveDownBatsman),
                    SixDownBatsman=get_player(team_manager_input.SixDownBatsman),
                    SevenDownBatsman=get_player(team_manager_input.SevenDownBatsman),
                    EightDownBatsman=get_player(team_manager_input.EightDownBatsman),
                    NineDownBatsman=get_player(team_manager_input.NineDownBatsman),
                    PowerplayBowlers=[get_player(name) for name in team_manager_input.PowerplayBowlers],
                    MiddleOversBowlers=[get_player(name) for name in team_manager_input.MiddleOversBowlers],
                    DeathOversBowlers=[get_player(name) for name in team_manager_input.DeathOversBowlers],
                    PlayersNotInPlayingXI=[get_player(name) for name in team_manager_input.PlayersNotInPlayingXI]
                )

                state[team_name] = team
                print(f"Successfully updated team '{team_name}' with structured data.")

            except Exception as e:
                print(f"Error processing team {team_name} after successful parsing: {e}")
                # Optionally, you might want to leave the team as a list of players
                # if the AI call or parsing fails.
        else:
            print(f"Could not parse team manager input for {team_name}. Leaving as list of players.")

    return state
