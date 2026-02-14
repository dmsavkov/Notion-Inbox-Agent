import json
import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def supports_response_format(model_name: str) -> bool:
    """
    Determine if a model supports the response_format parameter.
    
    Gemma models (non-Flash) do not support response_format.
    Gemini Flash models do support it.
    
    Args:
        model_name: Name of the LLM model
        
    Returns:
        True if model supports response_format, False otherwise
    """
    # Gemma models don't support response_format
    if "gemma" in model_name.lower() and "flash" not in model_name.lower():
        return False
    
    # Gemini Flash models support response_format
    if "gemini" in model_name.lower() and "flash" in model_name.lower():
        return True
    
    # Default to True for other models (can be adjusted)
    return True


def is_gemma_model(model_name: str) -> bool:
    """Check if model is a Gemma variant (doesn't support system role)"""
    return "gemma" in model_name.lower() and "flash" not in model_name.lower()


def transform_messages_for_gemma(messages: list) -> list:
    """
    Transform messages for Gemma models, which don't support system role.
    
    Converts system role messages to user messages with "Instructions:" prefix.
    
    Args:
        messages: List of message dictionaries with role and content
        
    Returns:
        Transformed messages list compatible with Gemma
    """
    if not messages:
        return messages
    
    transformed = []
    system_instructions = []
    
    # Collect system messages
    for msg in messages:
        if msg.get("role") == "system":
            system_instructions.append(msg.get("content", ""))
        else:
            transformed.append(msg)
    
    # If we have system instructions, prepend them to the first user message
    if system_instructions:
        instructions_text = "\n".join(system_instructions)
        
        # Find first user message and prepend instructions
        for i, msg in enumerate(transformed):
            if msg.get("role") == "user":
                msg["content"] = f"Instructions:\n{instructions_text}\n\n{msg['content']}"
                break
        else:
            # No user message found, create one
            transformed.insert(0, {
                "role": "user",
                "content": f"Instructions:\n{instructions_text}"
            })
    
    return transformed


def extract_json_from_response(response_content: Optional[str]) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response content.
    
    Handles multiple formats:
    1. Direct JSON string
    2. JSON wrapped in markdown code blocks (```json ... ```)
    3. JSON with extra whitespace/newlines
    
    Args:
        response_content: Raw response content from LLM
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        ValueError: If JSON cannot be extracted or parsed
    """
    if response_content is None:
        raise ValueError("Response content is None")
    
    # Try direct parsing first
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, attempting markdown extraction")
    
    # Try extracting from markdown code blocks
    # Pattern matches: ```json\n{...}\n``` or ```\n{...}\n```
    patterns = [
        r'```json\s*\n(.*?)\n```',  # ```json ... ```
        r'```\s*\n(.*?)\n```',       # ``` ... ```
        r'```json\s*(.*?)```',       # ```json...``` (no newlines)
        r'```\s*(.*?)```',           # ```...``` (no newlines)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response_content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse JSON from pattern: {pattern}")
                continue
    
    # Fallback: Try the split method from notebook
    # result.split('```')[1][5:] - splits by ``` and takes second part, skipping "json\n"
    try:
        parts = response_content.split('```')
        if len(parts) >= 3:  # Should have at least [before, content, after]
            json_str = parts[1]
            # Remove "json" prefix if present
            if json_str.startswith('json'):
                json_str = json_str[4:].strip()
            return json.loads(json_str)
    except (json.JSONDecodeError, IndexError) as e:
        logger.debug(f"Fallback split method failed: {e}")
    
    # If all methods fail, raise error with helpful message
    raise ValueError(
        f"Failed to extract JSON from response. "
        f"Content preview: {response_content[:200]}..."
    )


def call_llm_with_json_response(
    client,
    model_config,
    messages: list
) -> Dict[str, Any]:
    """
    Call LLM and extract JSON response with automatic handling of response_format.
    
    This function automatically determines whether to use response_format parameter
    based on the model type, and handles JSON extraction from the response.
    
    For Gemma models (which don't support system role), system messages are
    converted to user messages with an "Instructions:" prefix.
    
    Args:
        client: OpenAI client instance
        model_config: ModelConfig object with model_name, temperature, top_p
        messages: List of message dictionaries for the chat
        
    Returns:
        Parsed JSON response as dictionary
        
    Raises:
        ValueError: If JSON cannot be extracted
        Exception: Re-raises any API errors
    """
    # Determine if we should use response_format
    use_response_format = supports_response_format(model_config.model_name)
    
    # Transform messages for Gemma models (no system role support)
    processed_messages = messages
    if is_gemma_model(model_config.model_name):
        processed_messages = transform_messages_for_gemma(messages)
    
    # Request params dict is more convenient to put in client chat later
    request_params = {
        "model": model_config.model_name,
        "messages": processed_messages,
        "temperature": model_config.temperature,
        "top_p": model_config.top_p
    }
    
    # Add response_format only if supported
    if use_response_format:
        request_params["response_format"] = {"type": "json_object"}
    
    logger.debug(
        f"Calling LLM: model={model_config.model_name}, "
        f"response_format={'enabled' if use_response_format else 'disabled'}, "
        f"messages_transformed={is_gemma_model(model_config.model_name)}"
    )
    
    try:
        # Make the API call
        response = client.chat.completions.parse(**request_params)
        
        # Extract content
        content = response.choices[0].message.content
        
        # Parse JSON
        return extract_json_from_response(content)
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        raise

def generate_default_title(note: str, max_length: int = 80) -> str:
    """Generate task title from note (first line or truncated)"""
    first_line = note.split('\n')[0].strip()
    
    # Remove markdown markers
    title = first_line.replace('**', '').replace('*', '').replace('[', '').replace(']', '')
    
    if len(title) > max_length:
        title = title[:max_length-3] + "..."
    
    return title or "Untitled Task"

