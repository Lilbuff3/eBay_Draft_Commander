"""Mobile uploads must not lose the user's condition choice.

The mobile upload endpoint stores the user's condition under
metadata['user_condition']; the folder scanner uses metadata['condition'].
The processor must honor the explicit user choice so the pipeline doesn't let
the AI's guess override it (which underprices items graded above the AI's
estimate).
"""
from backend.app.services.processor_service import ProcessorService

read = ProcessorService._metadata_condition


def test_reads_mobile_upload_user_condition():
    assert read({"user_condition": "USED_EXCELLENT"}) == "USED_EXCELLENT"


def test_reads_folder_scanner_condition():
    assert read({"condition": "USED_GOOD"}) == "USED_GOOD"


def test_user_condition_wins_over_folder_condition():
    assert read({"user_condition": "USED_EXCELLENT", "condition": "USED_GOOD"}) == "USED_EXCELLENT"


def test_none_when_no_condition():
    assert read({}) is None
    assert read(None) is None
