"""Example usage of GeminiClient with tool binding."""

from gemini import GeminiClient


# Define some example tools as Python functions
def get_player_stats(player_name: str) -> str:
	"""Get cricket player statistics.
	
	Args:
		player_name: Name of the cricket player.
	"""
	# In real implementation, fetch from database
	return f"Stats for {player_name}: 45 avg, 150 SR"


def calculate_team_value(players: list, budget: int) -> str:
	"""Calculate total team value and remaining budget.
	
	Args:
		players: List of player names.
		budget: Total budget in crores.
	"""
	return f"Team of {len(players)} players, {budget - 50} crores remaining"


def search_player_history(player_name: str, years: int = 5) -> str:
	"""Search player auction history.
	
	Args:
		player_name: Name of the player.
		years: Number of years to look back (default: 5).
	"""
	return f"Auction history for {player_name} over last {years} years"


# Example 1: Basic usage without tools
def basic_example():
	print("=== Basic Usage ===")
	client = GeminiClient()
	response = client.gemini("Explain IPL auction strategy in one sentence.")
	print(f"Response: {response}\n")


# Example 2: Bind tools and use them
def tool_binding_example():
	print("=== Tool Binding Example ===")
	client = GeminiClient()
	
	# Bind Python functions as tools
	client.bind_tools([
		get_player_stats,
		calculate_team_value,
		search_player_history
	])
	
	# Model can now call these functions
	response = client.gemini(
		"What are Virat Kohli's stats and his last 3 years auction history?"
	)
	
	print(f"Response: {response}")
	
	# If tools were called
	if isinstance(response, dict) and "tool_calls" in response:
		print(f"\nText: {response['text']}")
		print(f"Tool calls: {response['tool_calls']}")
		
		# Execute the tools
		for tool_call in response["tool_calls"]:
			result = client.execute_tool(
				tool_call["name"],
				tool_call["arguments"]
			)
			print(f"Tool result: {result}")
	print()


# Example 3: Manual tool definitions
def manual_tools_example():
	print("=== Manual Tool Definition ===")
	client = GeminiClient()
	
	# Define tools manually (alternative to bind_tools)
	tools = [{
		"name": "get_weather",
		"description": "Get current weather for a city",
		"parameters": {
			"type": "object",
			"properties": {
				"city": {"type": "string", "description": "City name"},
				"units": {"type": "string", "description": "celsius or fahrenheit"}
			},
			"required": ["city"]
		}
	}]
	
	response = client.gemini(
		"What's the weather in Mumbai?",
		tools=tools
	)
	print(f"Response: {response}\n")


if __name__ == "__main__":
	# Uncomment to run examples (requires AISTUDIO_API_KEY in .env)
	basic_example()
	tool_binding_example()
	manual_tools_example()
	
	print("Examples ready. Set AISTUDIO_API_KEY in .env and uncomment examples to run.")
