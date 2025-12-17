
import pickle
from team_manager import team_manager
from utils import AgentState, prettyprint

def test_team_manager_output():
    # Load the final agent state from the pickle file
    try:
        with open('final_agent_state.pkl', 'rb') as f:
            # It's important to load the state correctly. 
            # Assuming AgentState is a dict or a class that can be pickled.
            final_state = pickle.load(f)
    except FileNotFoundError:
        print("Error: 'final_agent_state.pkl' not found. Please ensure the file exists.")
        return
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        return

    final_state["Messages"] = []  # Clear messages to avoid LLM context issues
    # Call the team_manager function with the loaded state
    # updated_state = final_state
    updated_state = team_manager(final_state)

    # Pretty print the output
    print("Output from team_manager:")
    prettyprint(updated_state)

if __name__ == "__main__":
    test_team_manager_output()
