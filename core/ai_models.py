"""
OpenAI Models Registry
Defines available models and their capabilities/parameters
"""

from typing import Dict, List, Any, Optional

# Model parameter definitions with ranges and defaults
PARAMETER_DEFINITIONS = {
    "temperature": {
        "type": "float",
        "min": 0.0,
        "max": 2.0,
        "default": 0.7,
        "step": 0.1,
        "description": "Controls randomness. Lower = more focused, higher = more creative"
    },
    "top_p": {
        "type": "float", 
        "min": 0.0,
        "max": 1.0,
        "default": 0.9,
        "step": 0.05,
        "description": "Alternative to temperature. Controls diversity via nucleus sampling"
    },
    "frequency_penalty": {
        "type": "float",
        "min": -2.0,
        "max": 2.0,
        "default": 0.0,
        "step": 0.1,
        "description": "Reduces repetition. Higher values decrease likelihood of repeated tokens"
    },
    "presence_penalty": {
        "type": "float",
        "min": -2.0,
        "max": 2.0,
        "default": 0.0,
        "step": 0.1,
        "description": "Encourages new topics. Higher values increase likelihood of new topics"
    },
    "max_tokens": {
        "type": "int",
        "min": 1,
        "max": 4096,  # Will be overridden by model-specific limits
        "default": 1000,
        "step": 50,
        "description": "Maximum number of tokens to generate"
    },
    "response_format": {
        "type": "select",
        "options": ["text", "json_object"],
        "default": "text",
        "description": "Response format. 'json_object' ensures valid JSON output"
    }
}

# OpenAI Models Registry with their capabilities
OPENAI_MODELS = {
    # GPT-4o Series (Omni)
    "gpt-4o": {
        "name": "GPT-4o",
        "description": "Most capable model, best for complex tasks",
        "supports_system_message": True,
        "supports_functions": True,
        "max_tokens": 4096,
        "max_total_tokens": 128000,
        "parameters": ["temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens", "response_format"],
        "defaults": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000
        }
    },
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "description": "Smaller, faster, cheaper version of GPT-4o",
        "supports_system_message": True,
        "supports_functions": True,
        "max_tokens": 16384,
        "max_total_tokens": 128000,
        "parameters": ["temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens", "response_format"],
        "defaults": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000
        }
    },
    
    # O1 Series (Reasoning models)
    "o1-preview": {
        "name": "O1 Preview",
        "description": "Advanced reasoning model for complex problems",
        "supports_system_message": False,
        "supports_functions": False,
        "max_tokens": 32768,
        "max_total_tokens": 128000,
        "parameters": ["max_tokens"],  # O1 models don't support temperature/top_p
        "defaults": {
            "max_tokens": 4096
        },
        "notes": "Uses 'max_completion_tokens' instead of 'max_tokens' in API"
    },
    "o1-mini": {
        "name": "O1 Mini",
        "description": "Faster reasoning model, good for coding and analysis",
        "supports_system_message": False,
        "supports_functions": False,
        "max_tokens": 65536,
        "max_total_tokens": 128000,
        "parameters": ["max_tokens"],  # O1 models don't support temperature/top_p
        "defaults": {
            "max_tokens": 4096
        },
        "notes": "Uses 'max_completion_tokens' instead of 'max_tokens' in API"
    },
    
    # GPT-4 Turbo
    "gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "description": "Previous generation, good balance of capability and cost",
        "supports_system_message": True,
        "supports_functions": True,
        "max_tokens": 4096,
        "max_total_tokens": 128000,
        "parameters": ["temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens", "response_format"],
        "defaults": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000
        }
    },
    "gpt-4-turbo-preview": {
        "name": "GPT-4 Turbo Preview",
        "description": "Preview version of GPT-4 Turbo",
        "supports_system_message": True,
        "supports_functions": True,
        "max_tokens": 4096,
        "max_total_tokens": 128000,
        "parameters": ["temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens", "response_format"],
        "defaults": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000
        }
    },
    
    # GPT-4 Original
    "gpt-4": {
        "name": "GPT-4",
        "description": "Original GPT-4 model",
        "supports_system_message": True,
        "supports_functions": True,
        "max_tokens": 8192,
        "max_total_tokens": 8192,
        "parameters": ["temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens"],
        "defaults": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000
        }
    },
    
    # GPT-3.5 Series
    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "description": "Fast and cost-effective for simple tasks",
        "supports_system_message": True,
        "supports_functions": True,
        "max_tokens": 4096,
        "max_total_tokens": 16385,
        "parameters": ["temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens", "response_format"],
        "defaults": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000
        }
    }
}

# Model presets for common use cases
MODEL_PRESETS = {
    "persian_translation": {
        "name": "Persian Translation",
        "description": "Optimized for translating English news to Persian",
        "model": "o1-mini",
        "parameters": {
            "max_tokens": 1000
        },
        "system_prompt": "You are a professional Persian translator specializing in news content.",
        "user_prompt_template": "Translate the following English news to Persian:\n\n{content}"
    },
    "news_analysis": {
        "name": "News Analysis",
        "description": "Analyze news content for key points and sentiment",
        "model": "gpt-4o-mini",
        "parameters": {
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 500
        },
        "system_prompt": "You are a news analyst. Extract key points and analyze sentiment.",
        "user_prompt_template": "Analyze this news article:\n\n{content}"
    },
    "creative_summary": {
        "name": "Creative Summary",
        "description": "Generate engaging summaries with more creativity",
        "model": "gpt-4o",
        "parameters": {
            "temperature": 0.8,
            "top_p": 0.95,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.3,
            "max_tokens": 300
        },
        "system_prompt": "You are a creative writer who summarizes news in an engaging way.",
        "user_prompt_template": "Create an engaging summary of this news:\n\n{content}"
    },
    "factual_extraction": {
        "name": "Factual Extraction", 
        "description": "Extract facts and data points with high accuracy",
        "model": "gpt-4o",
        "parameters": {
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 800,
            "response_format": "json_object"
        },
        "system_prompt": "Extract factual information and return as JSON.",
        "user_prompt_template": "Extract all facts from this text as JSON:\n\n{content}"
    }
}

def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Get information about a specific model"""
    return OPENAI_MODELS.get(model_id)

def get_available_models() -> List[Dict[str, Any]]:
    """Get list of all available models with their info"""
    models = []
    for model_id, info in OPENAI_MODELS.items():
        model_data = info.copy()
        model_data["id"] = model_id
        models.append(model_data)
    return models

def get_model_parameters(model_id: str) -> Dict[str, Any]:
    """Get parameter definitions for a specific model"""
    model_info = get_model_info(model_id)
    if not model_info:
        return {}
    
    parameters = {}
    for param_name in model_info.get("parameters", []):
        if param_name in PARAMETER_DEFINITIONS:
            param_def = PARAMETER_DEFINITIONS[param_name].copy()
            
            # Override max_tokens limit for specific model
            if param_name == "max_tokens":
                param_def["max"] = model_info.get("max_tokens", 4096)
            
            # Use model-specific default if available
            if param_name in model_info.get("defaults", {}):
                param_def["default"] = model_info["defaults"][param_name]
                
            parameters[param_name] = param_def
    
    return parameters

def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific preset configuration"""
    return MODEL_PRESETS.get(preset_id)

def get_all_presets() -> Dict[str, Dict[str, Any]]:
    """Get all available presets"""
    return MODEL_PRESETS.copy()

def validate_parameters(model_id: str, parameters: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate parameters for a specific model
    Returns: (is_valid, list_of_errors)
    """
    errors = []
    model_info = get_model_info(model_id)
    
    if not model_info:
        return False, ["Invalid model ID"]
    
    allowed_params = model_info.get("parameters", [])
    param_defs = get_model_parameters(model_id)
    
    for param_name, value in parameters.items():
        # Check if parameter is allowed for this model
        if param_name not in allowed_params:
            errors.append(f"Parameter '{param_name}' not supported by {model_id}")
            continue
            
        # Validate parameter value
        if param_name in param_defs:
            param_def = param_defs[param_name]
            
            # Type validation
            if param_def["type"] == "float":
                try:
                    float_val = float(value)
                    if float_val < param_def["min"] or float_val > param_def["max"]:
                        errors.append(f"{param_name} must be between {param_def['min']} and {param_def['max']}")
                except (TypeError, ValueError):
                    errors.append(f"{param_name} must be a number")
                    
            elif param_def["type"] == "int":
                try:
                    int_val = int(value)
                    if int_val < param_def["min"] or int_val > param_def["max"]:
                        errors.append(f"{param_name} must be between {param_def['min']} and {param_def['max']}")
                except (TypeError, ValueError):
                    errors.append(f"{param_name} must be an integer")
                    
            elif param_def["type"] == "select":
                if value not in param_def["options"]:
                    errors.append(f"{param_name} must be one of: {', '.join(param_def['options'])}")
    
    return len(errors) == 0, errors