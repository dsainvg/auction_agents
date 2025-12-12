"""Gemini API client for LangGraph integration with tool support.

This module provides a `GeminiClient` class that integrates with LangGraph
and supports tool/function calling. Uses the official `google.genai` library
with REST fallback if unavailable.

Environment variables checked for API key (in order):
- `AISTUDIO_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`

Example:
	from gemini import GeminiClient
	
	client = GeminiClient()
	response = client.gemini("Explain reinforcement learning in a paragraph.")
	print(response)
	
	# With tools
	tools = [{"name": "search", "description": "Search the web", "parameters": {...}}]
	response = client.gemini("Find recent AI news", tools=tools)
"""

from typing import Optional, List, Dict, Any, Union, Callable
import os
import json
import inspect

# Load environment variables from .env file if available
try:
	from dotenv import load_dotenv
	load_dotenv()
except ImportError:
	pass  # dotenv not installed, skip

__all__ = ["GeminiClient"]


class GeminiClient:
	"""Gemini API client with LangGraph and tool support."""
	
	def __init__(
		self,
		api_key: Optional[str] = None,
		model: str = "gemini-2.5-flash",
		temperature: float = 0.0,
		max_tokens: int = 512,
		timeout: int = 30,
	):
		"""Initialize Gemini client.
		
		Args:
			api_key: Optional API key. If omitted, reads from environment.
			model: Model name (default: "gemini-2.5-flash").
			temperature: Sampling temperature.
			max_tokens: Maximum output tokens.
			timeout: HTTP request timeout in seconds.
		"""
		if api_key is None:
			api_key = (
				os.environ.get("AISTUDIO_API_KEY")
				or os.environ.get("GEMINI_API_KEY")
				or os.environ.get("GOOGLE_API_KEY")
			)
		
		if not api_key:
			raise ValueError(
				"No API key provided. Set AISTUDIO_API_KEY or pass `api_key` argument."
			)
		
		self.api_key = api_key
		self.model = model
		self.temperature = temperature
		self.max_tokens = max_tokens
		self.timeout = timeout
		self._client = None
		self._bound_tools = []  # Store bound tools
		self._tool_functions = {}  # Map tool names to functions
		
		# Try to initialize official client
		try:
			from google import genai
			self._client = genai.Client(api_key=self.api_key)
		except Exception:
			pass  # Will use REST fallback
	
	def bind_tools(self, tools: List[Callable]) -> 'GeminiClient':
		"""Bind Python functions as tools for the model to use.
		
		Automatically extracts function signatures and docstrings to create
		tool definitions. The model can then call these functions.
		
		Args:
			tools: List of Python functions to bind as tools.
		
		Returns:
			Self for method chaining.
		
		Example:
			def search_web(query: str) -> str:
				'''Search the web for information.
				
				Args:
					query: The search query string.
				'''
				return f"Results for: {query}"
			
			client = GeminiClient().bind_tools([search_web])
			response = client.gemini("Find info about quantum computing")
		"""
		for func in tools:
			tool_def = self._function_to_tool(func)
			self._bound_tools.append(tool_def)
			self._tool_functions[func.__name__] = func
		
		return self
	
	def _function_to_tool(self, func: Callable) -> Dict[str, Any]:
		"""Convert a Python function to a tool definition."""
		sig = inspect.signature(func)
		doc = inspect.getdoc(func) or f"Call the {func.__name__} function."
		
		# Extract parameters
		parameters = {
			"type": "object",
			"properties": {},
			"required": []
		}
		
		for param_name, param in sig.parameters.items():
			if param_name == "self":
				continue
			
			param_type = "string"  # default
			if param.annotation != inspect.Parameter.empty:
				annotation = param.annotation
				if annotation == int:
					param_type = "integer"
				elif annotation == float:
					param_type = "number"
				elif annotation == bool:
					param_type = "boolean"
				elif annotation == list or annotation == List:
					param_type = "array"
				elif annotation == dict or annotation == Dict:
					param_type = "object"
			
			parameters["properties"][param_name] = {
				"type": param_type,
				"description": f"Parameter {param_name}"
			}
			
			if param.default == inspect.Parameter.empty:
				parameters["required"].append(param_name)
		
		return {
			"name": func.__name__,
			"description": doc.split('\n')[0] if doc else f"{func.__name__} function",
			"parameters": parameters
		}
	
	def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
		"""Execute a bound tool function.
		
		Args:
			tool_name: Name of the tool to execute.
			arguments: Arguments to pass to the tool.
		
		Returns:
			Result from the tool function.
		
		Raises:
			ValueError: If tool is not bound.
		"""
		if tool_name not in self._tool_functions:
			raise ValueError(f"Tool '{tool_name}' not found. Available: {list(self._tool_functions.keys())}")
		
		func = self._tool_functions[tool_name]
		return func(**arguments)
	
	def gemini(
		self,
		prompt: str,
		tools: Optional[List[Dict[str, Any]]] = None,
		model: Optional[str] = None,
		temperature: Optional[float] = None,
		max_tokens: Optional[int] = None,
	) -> Union[str, Dict[str, Any]]:
		"""Generate text using Gemini API with optional tool support.
		
		Args:
			prompt: Text prompt to send to the model.
			tools: Optional list of tool definitions. Format:
				[{
					"name": "function_name",
					"description": "What the function does",
					"parameters": {
						"type": "object",
						"properties": {
							"param1": {"type": "string", "description": "..."},
						},
						"required": ["param1"]
					}
				}]
				If None, uses bound tools from bind_tools().
			model: Override default model.
			temperature: Override default temperature.
			max_tokens: Override default max tokens.
		
		Returns:
			Generated text string, or dict with tool_calls if tools were invoked:
			{
				"text": "Response text",
				"tool_calls": [
					{"name": "function_name", "arguments": {"param1": "value"}}
				]
			}
		
		Raises:
			ValueError: If no API key is provided.
			Exception: For unexpected errors from the client or HTTP call.
		"""
		model = model or self.model
		temperature = temperature if temperature is not None else self.temperature
		max_tokens = max_tokens or self.max_tokens
		
		# Use bound tools if no tools provided
		if tools is None and self._bound_tools:
			tools = self._bound_tools
		
		# Try official client first
		if self._client:
			try:
				config = {
					"temperature": temperature,
					"max_output_tokens": max_tokens,
				}
				
				if tools:
					# Convert tools to Gemini format
					config["tools"] = self._format_tools(tools)
				
				resp = self._client.models.generate_content(
					model=model,
					contents=prompt,
					config=config,
				)
				
				# Check for tool calls
				if hasattr(resp, "candidates") and resp.candidates:
					candidate = resp.candidates[0]
					if hasattr(candidate, "function_calls") and candidate.function_calls:
						return {
							"text": getattr(resp, "text", ""),
							"tool_calls": self._extract_tool_calls(candidate.function_calls),
						}
				
				return getattr(resp, "text", str(resp))
			except Exception as e:
				# Fall through to REST if client fails
				pass
		
		# REST fallback
		return self._rest_call(prompt, tools, model, temperature, max_tokens)
	
	def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""Convert tool definitions to Gemini function calling format."""
		formatted = []
		for tool in tools:
			formatted.append({
				"function_declarations": [{
					"name": tool.get("name", ""),
					"description": tool.get("description", ""),
					"parameters": tool.get("parameters", {}),
				}]
			})
		return formatted
	
	def _extract_tool_calls(self, function_calls) -> List[Dict[str, Any]]:
		"""Extract tool calls from response."""
		calls = []
		for fc in function_calls:
			calls.append({
				"name": fc.name,
				"arguments": dict(fc.args) if hasattr(fc, "args") else {},
			})
		return calls
	
	def _rest_call(
		self,
		prompt: str,
		tools: Optional[List[Dict[str, Any]]],
		model: str,
		temperature: float,
		max_tokens: int,
	) -> Union[str, Dict[str, Any]]:
		"""REST API fallback."""
		try:
			import requests
			
			url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
			headers = {"Content-Type": "application/json"}
			
			payload = {
				"contents": [{"parts": [{"text": prompt}]}],
				"generationConfig": {
					"temperature": temperature,
					"maxOutputTokens": max_tokens,
				}
			}
			
			if tools:
				payload["tools"] = self._format_tools(tools)
			
			resp = requests.post(
				f"{url}?key={self.api_key}",
				headers=headers,
				json=payload,
				timeout=self.timeout,
			)
			resp.raise_for_status()
			data = resp.json()
			
			# Extract text and tool calls
			text = None
			tool_calls = []
			
			if "candidates" in data and data["candidates"]:
				candidate = data["candidates"][0]
				
				# Extract text
				if "content" in candidate and "parts" in candidate["content"]:
					for part in candidate["content"]["parts"]:
						if "text" in part:
							text = part["text"]
							break
						elif "functionCall" in part:
							tool_calls.append({
								"name": part["functionCall"].get("name", ""),
								"arguments": part["functionCall"].get("args", {}),
							})
			
			if tool_calls:
				return {"text": text or "", "tool_calls": tool_calls}
			
			return text or json.dumps(data, ensure_ascii=False)
		
		except Exception as exc:
			raise

