"""
Code that is shared by the packages for multiple scripts.
"""

# pyright: reportUnusedImport=false

from .assets import (
    AssetManager,
    Attachment,
    Download,
    DownloadDeduplicated,
    DownloadFailed,
    DownloadPlan,
    DownloadResult,
    DownloadSkipped,
    DownloadSucceeded,
)
from .dependency_provider import ReccDependencyProvider, SimplifiedMessengerSettings
from .diff import Deletion, Edit, Insertion, NoOp, diff_has_changes, find_diff
from .slides import Slide, SlideBlueprint, SlideBlueprintReader, SlideGenerator
from .summarize_plan import (
    AnnotatedItem,
    AnnotatedSong,
    PlanSummary,
    PlanSummaryDiff,
    diff_plan_summaries,
    get_plan_summary,
    load_plan_summary,
    plan_summary_diff_to_html,
    plan_summary_to_json,
)
