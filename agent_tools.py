from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class BidderInput(BaseModel):
    is_raise: bool = Field(description="Whether this bid is a raise or just a call")
    is_normal: Optional[bool] = Field(
        default=None, 
        description="Whether this is a normal raise (fixed increment). Only applicable if is_raise is True"
    )
    raised_amount: Optional[float] = Field(
        default=None,
        description="The custom raise amount. Only applicable if is_raise is True and is_normal is False"
    )

# --- Tool Definitions ---
@tool("bidder_tool", args_schema=BidderInput, return_direct=True)
def bidder_tool(is_raise: bool, is_normal: Optional[bool], raised_amount: Optional[float]) -> dict:
    """Generate a competitive bid info based on the provided arguments and current agent state.

    Args:
        is_raise: Whether this bid is a raise.
        is_normal: Whether this is a normal raise (fixed increment). Only applicable if is_raise is True.
        raised_amount: The custom raise amount. Only applicable if is_raise is True and is_normal is False.

    Returns:
        A dict containing Tool Message.

    Raises:
        ValueError: If validation checks fail for is_raise, is_normal, and raised_amount combinations.
    """

    # Validation checks
    if not is_raise:
        # If not a raise, is_normal and raised_amount should not be set (or at least raised_amount shouldn't be)
        if raised_amount is not None:
             raise ValueError("raised_amount must be None when is_raise is False.")
        # We can enforce is_normal is None, or just ignore it. Let's enforce consistency.
        if is_normal is not None:
             # Depending on strictness, we might allow it but it's cleaner to say it should be None
             pass 
    else:
        # is_raise is True
        if is_normal is None:
             raise ValueError("is_normal must be specified (True/False) when is_raise is True.")
        
        if is_normal:
            if raised_amount is not None:
                raise ValueError("raised_amount must be None when is_normal is True.")
        else:
            if raised_amount is None:
                raise ValueError("raised_amount must be provided when is_normal is False.")
            if raised_amount <= 0:
                raise ValueError("raised_amount must be positive.")
    
    return {
        "status": "success",
        "bid_decision": {
            "is_raise": is_raise,
            "is_normal": is_normal,
            "raised_amount": raised_amount
        }
    }
    

