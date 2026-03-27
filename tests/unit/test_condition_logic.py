"""
Tests for condition determination logic in ProcessorService.

Tests the newly refactored _determine_condition() helper method to ensure
proper priority handling: User Override > Queue Metadata > Folder Name > Default
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path
from backend.app.services.processor_service import ProcessorService
from backend.app.core.constants import CONDITION_MAP, DEFAULT_CONDITION


@pytest.fixture
def processor():
    """Create ProcessorService instance with mocked dependencies"""
    service = ProcessorService()
    return service


@pytest.fixture
def mock_callback():
    """Mock logging callback"""
    return MagicMock()


def test_condition_user_override_highest_priority(processor, mock_callback, tmp_path):
    """User override in job.json should win over all other sources"""
    # Arrange
    folder = tmp_path / "Used" / "test_item"  # Parent folder suggests "USED_GOOD"
    folder.mkdir(parents=True)

    user_condition = "NEW"  # User explicitly wants NEW
    metadata_condition = "USED_EXCELLENT"  # Queue says USED_EXCELLENT

    # Act
    result = processor._determine_condition(
        folder,
        metadata_condition,
        user_condition,
        mock_callback
    )

    # Assert
    assert result == "NEW"
    mock_callback.assert_called()  # Should log the decision


def test_condition_queue_metadata_second_priority(processor, mock_callback, tmp_path):
    """Queue metadata should be used if no user override present"""
    # Arrange
    folder = tmp_path / "Used" / "test_item"  # Parent folder suggests USED_GOOD
    folder.mkdir(parents=True)
    
    user_overrides = {}  # No user override
    metadata_condition = "LIKE_NEW"  # Queue says LIKE_NEW
    
    # Act
    result = processor._determine_condition(
        folder,
        metadata_condition,
        user_overrides,
        mock_callback
    )
    
    # Assert
    assert result == "LIKE_NEW"


def test_condition_folder_name_third_priority(processor, mock_callback, tmp_path):
    """Parent folder name should be detected if no override or metadata"""
    # Arrange
    folder = tmp_path / "New Old Stock" / "test_item"
    folder.mkdir(parents=True)
    
    user_overrides = {}
    metadata_condition = None
    
    # Act
    result = processor._determine_condition(
        folder,
        metadata_condition,
        user_overrides,
        mock_callback
    )
    
    # Assert
    assert result == "NEW_OTHER"  # "New Old Stock" maps to NEW_OTHER in CONDITION_MAP


def test_condition_default_fallback(processor, mock_callback, tmp_path):
    """Should use DEFAULT_CONDITION when no other source is available"""
    # Arrange
    folder = tmp_path / "RandomFolder" / "test_item"  # Not in CONDITION_MAP
    folder.mkdir(parents=True)
    
    user_overrides = {}
    metadata_condition = None
    
    # Act
    result = processor._determine_condition(
        folder,
        metadata_condition,
        user_overrides,
        mock_callback
    )
    
    # Assert
    assert result is None  # No source -> None triggers awaiting_condition flow


def test_condition_priority_cascade(processor, mock_callback, tmp_path):
    """When multiple sources present, highest priority should win"""
    # Arrange
    folder = tmp_path / "For Parts" / "test_item"  # Folder suggests FOR_PARTS_OR_NOT_WORKING
    folder.mkdir(parents=True)

    # All three sources present
    user_condition = "CERTIFIED_REFURBISHED"
    metadata_condition = "USED_GOOD"
    # Folder name would give FOR_PARTS_OR_NOT_WORKING

    # Act
    result = processor._determine_condition(
        folder,
        metadata_condition,
        user_condition,
        mock_callback
    )

    # Assert
    assert result == "CERTIFIED_REFURBISHED"  # User override wins


def test_condition_all_folder_mappings(processor, mock_callback, tmp_path):
    """Verify all folder name mappings from CONDITION_MAP work correctly"""
    # Test a few key mappings from CONDITION_MAP
    test_cases = [
        ("New", "NEW"),
        ("New Open Box", "NEW_OTHER"),
        ("Used Excellent", "USED_EXCELLENT"),
        ("For Parts", "FOR_PARTS_OR_NOT_WORKING"),
    ]
    
    for folder_name, expected_condition in test_cases:
        folder = tmp_path / folder_name / "test_item"
        folder.mkdir(parents=True, exist_ok=True)
        
        result = processor._determine_condition(
            folder,
            None,  # No metadata
            {},    # No override
            mock_callback
        )
        
        assert result == expected_condition, f"Folder '{folder_name}' should map to '{expected_condition}'"
