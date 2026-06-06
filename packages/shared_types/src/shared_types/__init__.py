"""Public contract barrel for the novel-to-screenplay MVP shared types.

Re-exports the version constants, both contract layers (model-output DTOs and
the backend document model), the validated-screenplay wrapper, the validation
report, and the pipeline error.

Note: ``mark_validated`` is intentionally NOT exported here. It lives in
``shared_types.internal`` so that only the validators layer mints a
``ValidatedScreenplay``.
"""

from __future__ import annotations

from .errors import PipelineError, PipelineErrorType, PipelineStage
from .model_output import (
    ChapterSummaryOutput,
    ContentBlockType,
    KeyEventImportance,
    KeyEventOutput,
    ModelActionBlock,
    ModelContentBlock,
    ModelDialogueBlock,
    ModelNoteBlock,
    ModelVoiceOverBlock,
    RepairOutput,
    SceneContentOutput,
    ScenePlanItem,
    ScenePlanOutput,
)
from .screenplay_document import (
    ActionBlock,
    AdaptationChange,
    AdaptationChangeType,
    AdaptationConfig,
    Chapter,
    Character,
    ContentBlock,
    DialogueBlock,
    EmbeddedValidation,
    KeyEvent,
    KeyEventStatus,
    Location,
    Metadata,
    NoteBlock,
    RevisionNote,
    Scene,
    Screenplay,
    ScreenplayDraftDocument,
    TimelineEntry,
    VoiceOverBlock,
)
from .validated import ValidatedScreenplay
from .validation import (
    ValidationErrorIssue,
    ValidationIssueSeverity,
    ValidationReport,
    ValidationWarningIssue,
)
from .versions import (
    SCREENPLAY_GENERATOR_VERSION,
    SCREENPLAY_PROMPT_VERSION,
    SCREENPLAY_SCHEMA_DOC_VERSION,
    SCREENPLAY_SCHEMA_VERSION,
    __version__,
)

__all__ = [
    # versions
    "SCREENPLAY_SCHEMA_VERSION",
    "SCREENPLAY_SCHEMA_DOC_VERSION",
    "SCREENPLAY_GENERATOR_VERSION",
    "SCREENPLAY_PROMPT_VERSION",
    "__version__",
    # model-output DTOs
    "KeyEventImportance",
    "ContentBlockType",
    "KeyEventOutput",
    "ChapterSummaryOutput",
    "ScenePlanItem",
    "ScenePlanOutput",
    "ModelActionBlock",
    "ModelDialogueBlock",
    "ModelVoiceOverBlock",
    "ModelNoteBlock",
    "ModelContentBlock",
    "SceneContentOutput",
    "RepairOutput",
    # document layer: enums
    "KeyEventStatus",
    "AdaptationChangeType",
    # document layer: content blocks
    "ActionBlock",
    "DialogueBlock",
    "VoiceOverBlock",
    "NoteBlock",
    "ContentBlock",
    # document layer: sub-models
    "KeyEvent",
    "Chapter",
    "Character",
    "Location",
    "Scene",
    "Screenplay",
    "TimelineEntry",
    "AdaptationChange",
    "Metadata",
    "AdaptationConfig",
    "EmbeddedValidation",
    "RevisionNote",
    # document layer: top-level
    "ScreenplayDraftDocument",
    # validated wrapper
    "ValidatedScreenplay",
    # validation report
    "ValidationIssueSeverity",
    "ValidationErrorIssue",
    "ValidationWarningIssue",
    "ValidationReport",
    # pipeline error
    "PipelineErrorType",
    "PipelineStage",
    "PipelineError",
]
