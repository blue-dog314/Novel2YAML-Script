"""One-shot repair helpers for invalid model outputs."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from shared_types import PipelineErrorType, PipelineStage, RepairOutput

from .llm import LLMClient
from .prompts import build_repair_prompt

TModel = TypeVar("TModel", bound=BaseModel)


class ModelOutputInvalid(Exception):
    """Raised when a generation stage cannot produce a valid DTO."""

    def __init__(
        self,
        *,
        stage: PipelineStage,
        message: str,
        raw_output: str,
    ) -> None:
        self.stage = stage
        self.error_type: PipelineErrorType = "model_output_invalid"
        self.error_message = message
        self.raw_output = raw_output
        super().__init__(f"{stage}: {message}")


def complete_json_with_repair(
    *,
    model_type: type[TModel],
    llm: LLMClient,
    stage: PipelineStage,
    system: str,
    user: str,
) -> TModel:
    """Complete and parse a DTO JSON object, repairing once on parse failure."""
    raw_output = llm.complete(system=system, user=user)
    try:
        return model_type.model_validate_json(raw_output)
    except ValidationError as first_error:
        repair_system, repair_user = build_repair_prompt(
            stage=stage,
            target_model_name=model_type.__name__,
            raw_output=raw_output,
            error_message=str(first_error),
        )
        repair_raw_output = llm.complete(system=repair_system, user=repair_user)
        repair_output = _parse_repair_output(
            stage=stage,
            raw_output=repair_raw_output,
        )
        if not repair_output.fixed or repair_output.result is None:
            raise ModelOutputInvalid(
                stage=stage,
                message=f"repair did not fix output: {repair_output.reason}",
                raw_output=repair_raw_output,
            ) from first_error
        try:
            return model_type.model_validate(repair_output.result)
        except ValidationError as second_error:
            raise ModelOutputInvalid(
                stage=stage,
                message=f"repaired output is still invalid: {second_error}",
                raw_output=json.dumps(
                    repair_output.result,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ) from second_error


def _parse_repair_output(
    *,
    stage: PipelineStage,
    raw_output: str,
) -> RepairOutput:
    try:
        return RepairOutput.model_validate_json(raw_output)
    except ValidationError as exc:
        raise ModelOutputInvalid(
            stage=stage,
            message=f"repair output is invalid: {exc}",
            raw_output=raw_output,
        ) from exc


__all__ = [
    "ModelOutputInvalid",
    "complete_json_with_repair",
]
