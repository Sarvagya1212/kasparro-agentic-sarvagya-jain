"""
Schema Validators - Validation guards for all tool boundaries.
"""

import functools
import logging
from typing import Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("Validators")


def validate_schema(
    input_model: Type[BaseModel] = None, output_model: Type[BaseModel] = None
):
    """
    Decorator that validates input/output at tool boundaries.
    Throws structured error immediately if schema validation fails.

    Usage:
        @validate_schema(input_model=ProductData, output_model=ContentSchema)
        def my_tool(data: ProductData) -> ContentSchema:
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validate first positional argument if input_model specified
            if input_model and args:
                first_arg = args[0]
                if not isinstance(first_arg, input_model):
                    try:
                        # Try to coerce to expected type
                        if isinstance(first_arg, dict):
                            validated = input_model(**first_arg)
                            args = (validated,) + args[1:]
                        else:
                            raise TypeError(
                                f"Expected {input_model.__name__}, "
                                f"got {type(first_arg).__name__}"
                            )
                    except ValidationError as e:
                        logger.error(f"Input validation failed: {e}")
                        raise ValueError(f"Schema validation failed: {e}") from e

            # Execute function
            result = func(*args, **kwargs)

            # Validate output if output_model specified
            if output_model and result is not None:
                if not isinstance(result, output_model):
                    try:
                        if isinstance(result, dict):
                            result = output_model(**result)
                        else:
                            raise TypeError(
                                f"Expected {output_model.__name__}, "
                                f"got {type(result).__name__}"
                            )
                    except ValidationError as e:
                        logger.error(f"Output validation failed: {e}")
                        raise ValueError(f"Output schema validation failed: {e}") from e

            return result

        return wrapper

    return decorator


def validate_context(func):
    """
    Simpler decorator - just validates that GlobalContext is passed.
    """

    @functools.wraps(func)
    def wrapper(self, context, *args, **kwargs):
        from skincare_agent_system.core.models import GlobalContext

        if not isinstance(context, GlobalContext):
            raise TypeError(
                f"Expected GlobalContext, got {type(context).__name__}. "
                f"All agents must receive GlobalContext."
            )
        return func(self, context, *args, **kwargs)

    return wrapper
