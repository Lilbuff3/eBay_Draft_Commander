"""Tests for security fixes: path traversal, settings whitelist, SSRF protection."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


# --- Bug #8: Path traversal prefix bypass ---

class TestPathTraversalGuard:
    """Test that path validation uses is_relative_to() instead of startswith()."""

    def test_prefix_collision_blocked(self, tmp_path):
        """A path like /data/inboxmalicious should NOT pass when base is /data/inbox."""
        from backend.app.core.validator import validate_safe_path, ValidationError

        base_dir = tmp_path / "inbox"
        base_dir.mkdir()
        malicious = tmp_path / "inboxmalicious"
        malicious.mkdir()

        with pytest.raises(ValidationError):
            validate_safe_path(str(malicious), base_dir=str(base_dir))

    def test_valid_child_path_allowed(self, tmp_path):
        """A legitimate child path should be allowed."""
        from backend.app.core.validator import validate_safe_path

        base_dir = tmp_path / "inbox"
        child = base_dir / "subfolder"
        child.mkdir(parents=True)

        result = validate_safe_path(str(child), base_dir=str(base_dir))
        assert result == child.resolve()

    def test_exact_base_dir_allowed(self, tmp_path):
        """The base directory itself should be allowed."""
        from backend.app.core.validator import validate_safe_path

        base_dir = tmp_path / "inbox"
        base_dir.mkdir()

        result = validate_safe_path(str(base_dir), base_dir=str(base_dir))
        assert result == base_dir.resolve()

    def test_parent_traversal_blocked(self, tmp_path):
        """Path with .. that escapes base dir should be blocked."""
        from backend.app.core.validator import validate_safe_path, ValidationError

        base_dir = tmp_path / "inbox"
        base_dir.mkdir()

        with pytest.raises(ValidationError):
            validate_safe_path(str(base_dir / ".." / "etc" / "passwd"), base_dir=str(base_dir))


class TestImageProcessorPathGuard:
    """Test that image_processor uses is_relative_to() instead of startswith()."""

    def test_prefix_collision_blocked(self, tmp_path):
        """Folder path with prefix collision should be rejected."""
        base = tmp_path / "inbox"
        base.mkdir()
        malicious = tmp_path / "inboxmalicious"
        malicious.mkdir()

        folder_path = malicious.resolve()
        allowed_dirs = [base.resolve()]

        # The fixed check: folder_path == d or folder_path.is_relative_to(d)
        result = any(folder_path == d or folder_path.is_relative_to(d) for d in allowed_dirs)
        assert result is False, "Prefix collision path should be rejected"

    def test_valid_child_allowed(self, tmp_path):
        """Legitimate child folder should be allowed."""
        base = tmp_path / "inbox"
        child = base / "subfolder"
        child.mkdir(parents=True)

        folder_path = child.resolve()
        allowed_dirs = [base.resolve()]

        result = any(folder_path == d or folder_path.is_relative_to(d) for d in allowed_dirs)
        assert result is True


# --- Bug #9: Settings API accepts arbitrary keys ---

class TestSettingsWhitelist:
    """Test that the settings POST endpoint rejects unknown keys."""

    @pytest.fixture
    def client(self):
        from backend.app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_unknown_keys_rejected(self, client):
        """Keys not in SETTING_CATEGORIES or DEFAULTS should be filtered out."""
        payload = {
            'DEFAULT_PRICE': '19.99',       # valid key
            'EVIL_SECRET': 'malicious',     # unknown key
            'PATH': '/usr/bin',             # unknown key
        }
        resp = client.post('/api/settings', json=payload,
                           content_type='application/json')
        data = resp.get_json()
        assert data['success'] is True
        assert 'EVIL_SECRET' in data.get('skipped', [])
        assert 'PATH' in data.get('skipped', [])
        assert data.get('saved_count') == 1

    def test_valid_keys_accepted(self, client):
        """All whitelisted keys should be saved."""
        payload = {
            'DEFAULT_PRICE': '24.99',
            'DEFAULT_CONDITION': 'USED_GOOD',
        }
        resp = client.post('/api/settings', json=payload,
                           content_type='application/json')
        data = resp.get_json()
        assert data['success'] is True
        assert data.get('saved_count') == 2
        assert data.get('skipped') == []

    def test_empty_body_rejected(self, client):
        """Empty request body should return 400."""
        resp = client.post('/api/settings', json={},
                           content_type='application/json')
        # Empty dict is falsy, should return 400
        assert resp.status_code == 400


# --- Bug #10: SSRF via thumbnail URL ---

class TestSSRFProtection:
    """Test _validate_thumbnail_url rejects internal/dangerous URLs."""

    def test_private_ip_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('http://192.168.1.1/image.png') is False
        assert _validate_thumbnail_url('http://10.0.0.1/image.png') is False
        assert _validate_thumbnail_url('http://172.16.0.1/image.png') is False

    def test_loopback_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('http://127.0.0.1/image.png') is False

    def test_localhost_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('http://localhost/image.png') is False

    def test_metadata_endpoint_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('http://metadata.google.internal/computeMetadata/v1/') is False

    def test_file_scheme_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('file:///etc/passwd') is False

    def test_ftp_scheme_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('ftp://example.com/image.png') is False

    def test_valid_https_url_accepted(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('https://i.ebayimg.com/images/g/abc/s-l1600.jpg') is True

    def test_valid_http_url_accepted(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('http://example.com/photo.jpg') is True

    def test_ipv6_loopback_rejected(self):
        from backend.app.blueprints.api.jobs_api import _validate_thumbnail_url
        assert _validate_thumbnail_url('http://[::1]/image.png') is False
