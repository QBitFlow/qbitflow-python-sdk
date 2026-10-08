"""
Base model for all DTOs in QBitFlow SDK.

This module provides a base Pydantic model with common configuration
for automatic camelCase/snake_case conversion.
"""

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict

from qbitflow.utils.helpers import snake_to_camel_case


class BaseModel(PydanticBaseModel):
    """
    Base model with common configuration for all DTOs.

    This model automatically handles conversion between Python's snake_case
    convention and the API's camelCase convention.

    Features:
        - Automatic camelCase to snake_case conversion for incoming data
        - Automatic snake_case to camelCase conversion for outgoing data
        - Support for both naming conventions when loading data
    """

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both camelCase and snake_case
        alias_generator=snake_to_camel_case,  # Generate camelCase aliases
        # use_enum_values=True,  # Use enum values instead of enum objects
    )

    def model_dump(self, *args, **kwargs):
        """
        Serialize the model to a dictionary with camelCase keys.

        Args:
            *args: Positional arguments to pass to parent method.
            **kwargs: Keyword arguments to pass to parent method.

        Returns:
            Dictionary representation of the model with camelCase keys.
        """
        kwargs["by_alias"] = True
        return super().model_dump(*args, **kwargs)
