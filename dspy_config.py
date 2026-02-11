#!/usr/bin/env python3
"""
DSPy configuration module for mailtagger.
Handles LLM provider configuration for OpenAI and Ollama.
"""

import os
import logging
import dspy
from typing import Optional

logger = logging.getLogger(__name__)


def configure_dspy_lm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 500,
    temperature: float = 0.0
) -> dspy.LM:
    """Configure DSPy to use the specified LLM provider.
    
    Args:
        provider: LLM provider ('openai' or 'ollama'). If None, reads from LLM_PROVIDER env var.
        model: Model name. If None, reads from provider-specific env var.
        api_key: API key for OpenAI. If None, reads from OPENAI_API_KEY env var.
        base_url: Base URL for Ollama. If None, reads from OLLAMA_URL env var.
        max_tokens: Maximum tokens for completion (default: 500)
        temperature: Sampling temperature (default: 0.0 for deterministic)
    
    Returns:
        Configured DSPy language model instance
        
    Raises:
        ValueError: If provider configuration is invalid or missing
    """
    # Get provider from parameter or environment
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    else:
        provider = provider.lower()
    
    logger.info(f"Configuring DSPy with provider: {provider}")
    
    if provider == "ollama":
        # Configure Ollama local LLM
        if model is None:
            model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
        if base_url is None:
            base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        
        # Remove the /v1/chat/completions suffix if present (DSPy adds it)
        base_url = base_url.replace("/v1/chat/completions", "")
        
        logger.info(f"  Model: {model}")
        logger.info(f"  Base URL: {base_url}")
        
        try:
            lm = dspy.OllamaLocal(
                model=model,
                base_url=base_url,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"Failed to configure Ollama: {e}")
            raise ValueError(f"Ollama configuration failed: {e}")
    
    elif provider == "openai":
        # Configure OpenAI
        if model is None:
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        logger.info(f"  Model: {model}")
        logger.info(f"  API Key: {'*' * 8}{api_key[-4:] if len(api_key) > 4 else '****'}")
        
        try:
            lm = dspy.OpenAI(
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"Failed to configure OpenAI: {e}")
            raise ValueError(f"OpenAI configuration failed: {e}")
    
    else:
        raise ValueError(
            f"Unknown provider: {provider}. Supported providers: 'openai', 'ollama'"
        )
    
    # Configure DSPy settings globally
    dspy.settings.configure(lm=lm)
    
    logger.info(f"DSPy configured successfully with {provider}")
    return lm


def get_current_lm() -> Optional[dspy.LM]:
    """Get the currently configured DSPy language model.
    
    Returns:
        Current LM instance or None if not configured
    """
    try:
        return dspy.settings.lm
    except AttributeError:
        return None


def is_configured() -> bool:
    """Check if DSPy is currently configured with an LM.
    
    Returns:
        True if DSPy has an active LM configuration
    """
    return get_current_lm() is not None


def reset_configuration():
    """Reset DSPy configuration (useful for testing or switching providers)."""
    if hasattr(dspy.settings, 'lm'):
        dspy.settings.lm = None
        logger.info("DSPy configuration reset")


def configure_with_fallback(
    preferred_provider: Optional[str] = None,
    fallback_provider: Optional[str] = None
) -> dspy.LM:
    """Configure DSPy with fallback to another provider if primary fails.
    
    Args:
        preferred_provider: First choice provider ('openai' or 'ollama')
        fallback_provider: Fallback provider if preferred fails
    
    Returns:
        Configured DSPy language model instance
        
    Raises:
        ValueError: If both providers fail to configure
    """
    if preferred_provider is None:
        preferred_provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if fallback_provider is None:
        fallback_provider = "ollama" if preferred_provider == "openai" else "openai"
    
    try:
        return configure_dspy_lm(provider=preferred_provider)
    except Exception as e:
        logger.warning(f"Failed to configure {preferred_provider}: {e}")
        logger.info(f"Attempting fallback to {fallback_provider}")
        
        try:
            return configure_dspy_lm(provider=fallback_provider)
        except Exception as e2:
            logger.error(f"Fallback to {fallback_provider} also failed: {e2}")
            raise ValueError(f"Both {preferred_provider} and {fallback_provider} failed")


# Convenience function for common use case
def setup_dspy(verbose: bool = False) -> dspy.LM:
    """Quick setup of DSPy using environment variables.
    
    This is a convenience wrapper around configure_dspy_lm that uses
    all settings from environment variables.
    
    Args:
        verbose: If True, log detailed configuration info
        
    Returns:
        Configured DSPy language model instance
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    return configure_dspy_lm()


if __name__ == "__main__":
    # Test configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing DSPy configuration...")
    
    try:
        lm = setup_dspy(verbose=True)
        print(f"✓ Successfully configured: {lm}")
        print(f"✓ Is configured: {is_configured()}")
        print(f"✓ Current LM: {get_current_lm()}")
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
