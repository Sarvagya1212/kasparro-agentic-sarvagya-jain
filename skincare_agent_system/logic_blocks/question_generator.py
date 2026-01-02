"""
Question Generator Block - Uses Intelligence Provider for FAQ generation.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("QuestionGenerator")


def generate_questions_by_category(
    product_data: Dict[str, Any], min_questions: int = 15
) -> List[Tuple[str, str, str]]:
    """
    Generate categorized questions and answers using provider abstraction.
    Uses MistralProvider if available, falls back to OfflineRuleProvider.
    """
    from ..infrastructure.providers import get_provider
    
    provider = get_provider()
    logger.info(f"Using provider: {provider.name}")
    
    questions = provider.generate_faq(product_data)
    
    if len(questions) >= min_questions:
        logger.info(f"Generated {len(questions)} questions via {provider.name}")
        return questions
    
    # If still short, this should not happen with proper providers
    logger.warning(f"Only got {len(questions)} questions, expected {min_questions}")
    return questions
