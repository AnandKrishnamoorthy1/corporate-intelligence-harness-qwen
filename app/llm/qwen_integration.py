"""
Qwen LLM Integration Module

Provides wrapper functions for interacting with Alibaba's Qwen models
through the DashScope API. Handles structured output for the routing
and analysis tasks.
"""

import json
from typing import Dict, Any, Optional

from loguru import logger
import dashscope
from dashscope import Generation
from config.settings import settings


def initialize_qwen():
    """Initialize Qwen API with credentials from settings."""
    if not settings.qwen_api_key:
        raise ValueError(
            "QWEN_API_KEY environment variable not set. "
            "Please set your Alibaba Qwen API key."
        )
    dashscope.api_key = settings.qwen_api_key
    logger.info(f"Qwen initialized with model: {settings.qwen_model}")


def call_qwen_with_structured_output(
    system_prompt: str,
    user_message: str,
    response_schema: Dict[str, Any],
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Call Qwen with a structured output request.
    
    Args:
        system_prompt: System message defining the assistant's role
        user_message: User query/prompt
        response_schema: Expected JSON schema for response
        temperature: Sampling temperature (0.0-2.0), defaults to settings
        top_p: Nucleus sampling parameter, defaults to settings
        
    Returns:
        Parsed JSON response matching the schema
        
    Raises:
        ValueError: If API key not set
        RuntimeError: If API call fails or response cannot be parsed
    """
    if not settings.qwen_api_key:
        initialize_qwen()
    
    temperature = temperature or settings.qwen_temperature
    top_p = top_p or settings.qwen_top_p
    
    # Prepare the prompt with schema instructions
    schema_instruction = f"""
You must respond with ONLY valid JSON matching this schema:
{json.dumps(response_schema, indent=2)}

Do not include any text outside the JSON response.
"""
    
    full_user_message = f"{user_message}\n\n{schema_instruction}"
    
    try:
        logger.info(f"Calling Qwen ({settings.qwen_model}) with structured output request")
        logger.debug(f"User message: {user_message[:200]}...")
        
        response = Generation.call(
            model=settings.qwen_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": full_user_message,
                }
            ],
            temperature=temperature,
            top_p=top_p,
            result_format="text",  # DashScope returns text, we'll parse JSON
        )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"Qwen API error: {response.code} - {response.message}"
            )
        
        # Extract the response text
        response_text = response.output.text.strip()
        logger.debug(f"Raw Qwen response: {response_text[:300]}...")
        
        # Parse JSON response
        try:
            # Try to extract JSON if there's surrounding text
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
            else:
                json_str = response_text
            
            parsed_response = json.loads(json_str)
            logger.debug(f"Parsed response: {parsed_response}")
            return parsed_response
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Qwen JSON response: {response_text}")
            raise RuntimeError(
                f"Failed to parse Qwen response as JSON: {str(e)}"
            )
        
    except Exception as e:
        logger.error(f"Qwen API call failed: {str(e)}")
        raise RuntimeError(f"Qwen API error: {str(e)}")


def call_qwen_for_triage(user_input: str) -> Dict[str, Any]:
    """
    Use Qwen to perform triage/routing of user query.
    
    Args:
        user_input: User query to route
        
    Returns:
        Dict with keys: ticker, routing_path, confidence, reasoning
    """
    from app.prompts.system_prompts import TRIAGE_PROMPT, SYSTEM_MESSAGE_RESEARCH
    
    schema = {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol or empty string"
            },
            "routing_path": {
                "type": "string",
                "enum": ["research", "general_q"],
                "description": "Routing path for the query"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence score of routing"
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation of routing decision"
            }
        },
        "required": ["ticker", "routing_path", "confidence", "reasoning"]
    }
    
    formatted_prompt = TRIAGE_PROMPT.format(user_input=user_input)
    
    response = call_qwen_with_structured_output(
        system_prompt=SYSTEM_MESSAGE_RESEARCH,
        user_message=formatted_prompt,
        response_schema=schema,
    )
    
    return response


def call_qwen_for_research(
    ticker: str,
    price: float,
    market_cap: float,
    pe_ratio: float,
    change_pct: float,
) -> str:
    """
    Use Qwen to generate research report.
    
    Args:
        ticker: Stock ticker
        price: Current stock price
        market_cap: Market cap in billions
        pe_ratio: P/E ratio
        change_pct: 52-week change percentage
        
    Returns:
        Research report in markdown format
    """
    from app.prompts.system_prompts import (
        RESEARCH_PROMPT,
        SYSTEM_MESSAGE_RESEARCH
    )
    
    formatted_prompt = RESEARCH_PROMPT.format(
        ticker=ticker,
        price=price,
        market_cap=market_cap,
        pe_ratio=pe_ratio,
        change_pct=change_pct,
    )
    
    try:
        logger.info(f"Calling Qwen for research report on {ticker}")
        
        response = Generation.call(
            model=settings.qwen_model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_MESSAGE_RESEARCH,
                },
                {
                    "role": "user",
                    "content": formatted_prompt,
                }
            ],
            temperature=settings.qwen_temperature,
            top_p=settings.qwen_top_p,
            result_format="text",
        )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"Qwen API error: {response.code} - {response.message}"
            )
        
        report = response.output.text.strip()
        logger.info(f"Research report generated for {ticker}")
        return report
        
    except Exception as e:
        logger.error(f"Qwen research call failed: {str(e)}")
        raise RuntimeError(f"Qwen research error: {str(e)}")


def call_qwen_for_general_qa(user_input: str) -> str:
    """
    Use Qwen to answer general financial questions.
    
    Args:
        user_input: User question
        
    Returns:
        Answer in markdown format
    """
    from app.prompts.system_prompts import (
        GENERAL_QA_PROMPT,
        SYSTEM_MESSAGE_QA
    )
    
    formatted_prompt = GENERAL_QA_PROMPT.format(user_input=user_input)
    
    try:
        logger.info("Calling Qwen for general Q&A")
        
        response = Generation.call(
            model=settings.qwen_model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_MESSAGE_QA,
                },
                {
                    "role": "user",
                    "content": formatted_prompt,
                }
            ],
            temperature=settings.qwen_temperature,
            top_p=settings.qwen_top_p,
            result_format="text",
        )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"Qwen API error: {response.code} - {response.message}"
            )
        
        answer = response.output.text.strip()
        logger.info("General Q&A response generated")
        return answer
        
    except Exception as e:
        logger.error(f"Qwen QA call failed: {str(e)}")
        raise RuntimeError(f"Qwen QA error: {str(e)}")
