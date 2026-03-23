import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.app.services.image_processor import ImageProcessor


def create_test_images(folder, names):
    """Create empty files with image extensions for testing."""
    paths = []
    for name in names:
        p = folder / name
        p.write_bytes(b'\x00' * 100)  # dummy content
        paths.append(p)
    return paths


@pytest.fixture
def processor():
    mock_ebay = MagicMock()
    return ImageProcessor(mock_ebay)


@pytest.fixture
def image_folder(tmp_path):
    folder = tmp_path / "test_item"
    folder.mkdir()
    return folder


class TestUploadImages:
    """Tests for ImageProcessor.upload_images()"""

    @pytest.fixture(autouse=True)
    def allow_tmp_path(self, tmp_path):
        """Set INBOX_DIR to tmp_path so path traversal guard allows test folders."""
        with patch.dict('os.environ', {'INBOX_DIR': str(tmp_path)}):
            yield

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_basic_upload_3_images(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg', 'b.jpg', 'c.jpg'])
        mock_upload.return_value = 'https://i.ebayimg.com/images/test.jpg'

        result = processor.upload_images(image_folder)

        assert 'urls' in result
        assert len(result['urls']) == 3
        assert mock_upload.call_count == 3
        assert 'timing' in result

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_reordering_with_ordered_filenames(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg', 'b.jpg', 'c.jpg'])
        mock_upload.return_value = 'https://i.ebayimg.com/images/test.jpg'

        result = processor.upload_images(image_folder, ordered_filenames=['c.jpg', 'a.jpg', 'b.jpg'])

        assert 'urls' in result
        call_args = [call[0][0].name for call in mock_upload.call_args_list]
        assert call_args == ['c.jpg', 'a.jpg', 'b.jpg']

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_max_12_images_limit(self, mock_upload, mock_reachable, processor, image_folder):
        names = [f'img_{i:02d}.jpg' for i in range(15)]
        create_test_images(image_folder, names)
        mock_upload.return_value = 'https://i.ebayimg.com/images/test.jpg'

        result = processor.upload_images(image_folder)

        assert 'urls' in result
        assert len(result['urls']) == 12
        assert mock_upload.call_count == 12

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_missing_folder_returns_error(self, mock_upload, mock_reachable, processor, tmp_path):
        nonexistent = tmp_path / "does_not_exist"

        result = processor.upload_images(nonexistent)

        assert 'error' in result
        assert 'not found' in result['error'].lower() or 'Image folder not found' in result['error']
        mock_upload.assert_not_called()

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_empty_folder_returns_error(self, mock_upload, mock_reachable, processor, image_folder):
        # Folder exists but contains no image files
        result = processor.upload_images(image_folder)

        assert 'error' in result
        assert 'No image files found' in result['error']
        mock_upload.assert_not_called()

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_partial_failure_returns_urls(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg', 'b.jpg', 'c.jpg'])
        mock_upload.side_effect = [
            'https://i.ebayimg.com/images/1.jpg',
            None,
            'https://i.ebayimg.com/images/3.jpg',
        ]

        result = processor.upload_images(image_folder)

        assert 'urls' in result
        assert len(result['urls']) == 2
        assert 'error' not in result

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_total_failure_returns_error(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg', 'b.jpg', 'c.jpg'])
        mock_upload.return_value = None

        result = processor.upload_images(image_folder)

        assert 'error' in result
        assert 'All' in result['error'] and 'failed' in result['error']

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_orig_files_skipped(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['img.jpg', 'img.jpg.orig'])
        mock_upload.return_value = 'https://i.ebayimg.com/images/test.jpg'

        result = processor.upload_images(image_folder)

        assert 'urls' in result
        assert len(result['urls']) == 1
        assert mock_upload.call_count == 1
        call_args = [call[0][0].name for call in mock_upload.call_args_list]
        assert call_args == ['img.jpg']

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_non_image_files_skipped(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['img.jpg', 'notes.txt', 'data.csv'])
        mock_upload.return_value = 'https://i.ebayimg.com/images/test.jpg'

        result = processor.upload_images(image_folder)

        assert 'urls' in result
        assert len(result['urls']) == 1
        assert mock_upload.call_count == 1

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_extras_appended_sorted(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg', 'b.jpg', 'c.jpg'])
        mock_upload.side_effect = lambda p: f'https://i.ebayimg.com/images/{p.name}'

        result = processor.upload_images(image_folder, ordered_filenames=['c.jpg', 'a.jpg'])

        assert 'urls' in result
        # Result order must respect ordered_filenames: c.jpg first, a.jpg second, b.jpg last
        assert result['urls'] == [
            'https://i.ebayimg.com/images/c.jpg',
            'https://i.ebayimg.com/images/a.jpg',
            'https://i.ebayimg.com/images/b.jpg',
        ]

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=False)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_endpoint_unreachable_returns_error(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg'])

        result = processor.upload_images(image_folder)

        assert 'error' in result
        assert 'unreachable' in result['error'].lower()
        mock_upload.assert_not_called()

    @patch('backend.app.core.rate_limiter.limiter')
    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_parallel_upload_faster_than_serial(self, mock_upload, mock_reachable, mock_limiter, processor, image_folder):
        """Multiple uploads should complete faster than serial execution."""
        create_test_images(image_folder, [f'img_{i}.jpg' for i in range(6)])

        def slow_upload(path):
            time.sleep(0.3)
            return f'https://i.ebayimg.com/images/{path.name}'

        mock_upload.side_effect = slow_upload

        start = time.time()
        result = processor.upload_images(image_folder)
        elapsed = time.time() - start

        assert 'urls' in result
        assert len(result['urls']) == 6
        # Serial would be ~1.8s (6 x 0.3s). Parallel with 4 workers should be < 1.0s.
        assert elapsed < 1.0, f"Expected parallel uploads < 1.0s, got {elapsed:.2f}s"

    @patch('backend.app.core.rate_limiter.limiter')
    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_parallel_upload_preserves_order(self, mock_upload, mock_reachable, mock_limiter, processor, image_folder):
        """Parallel uploads must preserve original image order."""
        create_test_images(image_folder, ['a.jpg', 'b.jpg', 'c.jpg', 'd.jpg'])

        def slow_upload(path):
            # Make later files finish faster to test order preservation
            delays = {'a.jpg': 0.3, 'b.jpg': 0.1, 'c.jpg': 0.2, 'd.jpg': 0.05}
            time.sleep(delays.get(path.name, 0.1))
            return f'https://i.ebayimg.com/images/{path.name}'

        mock_upload.side_effect = slow_upload

        result = processor.upload_images(image_folder)

        assert 'urls' in result
        assert len(result['urls']) == 4
        # URLs must be in alphabetical order (default sort) regardless of completion order
        assert result['urls'] == [
            'https://i.ebayimg.com/images/a.jpg',
            'https://i.ebayimg.com/images/b.jpg',
            'https://i.ebayimg.com/images/c.jpg',
            'https://i.ebayimg.com/images/d.jpg',
        ]

    @patch('backend.app.services.image_processor.check_endpoint_reachability', return_value=True)
    @patch('backend.app.services.image_processor.upload_image_to_eps')
    def test_log_callback_called(self, mock_upload, mock_reachable, processor, image_folder):
        create_test_images(image_folder, ['a.jpg'])
        mock_upload.return_value = 'https://i.ebayimg.com/images/test.jpg'
        mock_callback = MagicMock()

        result = processor.upload_images(image_folder, log_callback=mock_callback)

        assert 'urls' in result
        assert mock_callback.call_count >= 1
        # Verify callback received string message and level
        first_call_args = mock_callback.call_args_list[0][0]
        assert isinstance(first_call_args[0], str)


class TestRemoveBackgroundAndSquare:
    """Tests for ImageProcessor.remove_background_and_square()"""

    def _make_pil_rembg_mocks(self):
        """Create coordinated PIL and rembg module mocks for lazy-import patching.

        Returns (mock_pil_module, mock_rembg_module) where mock_pil_module.Image
        is the Image class mock used by `from PIL import Image`.
        """
        mock_image_class = MagicMock()
        mock_pil_module = MagicMock()
        mock_pil_module.Image = mock_image_class
        mock_rembg_module = MagicMock()
        return mock_pil_module, mock_image_class, mock_rembg_module

    @patch('backend.app.services.image_processor.logger')
    def test_successful_removal(self, mock_logger, processor, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        input_path.write_bytes(b'\x00' * 100)

        mock_pil, mock_Image, mock_rembg = self._make_pil_rembg_mocks()

        mock_img = MagicMock()
        mock_output_png = MagicMock()
        mock_output_png.getbbox.return_value = (10, 10, 500, 500)

        mock_cropped = MagicMock()
        mock_cropped.width = 490
        mock_cropped.height = 490
        mock_output_png.crop.return_value = mock_cropped

        mock_resized = MagicMock()
        mock_resized.mode = 'RGBA'
        mock_cropped.resize.return_value = mock_resized

        mock_canvas = MagicMock()

        mock_Image.open.return_value = mock_img
        mock_Image.new.return_value = mock_canvas
        mock_rembg.remove.return_value = mock_output_png

        with patch.dict('sys.modules', {'PIL': mock_pil, 'PIL.Image': mock_Image, 'rembg': mock_rembg}):
            result = processor.remove_background_and_square(input_path, output_path)

        assert result is True
        mock_Image.open.assert_called_once_with(input_path)
        mock_rembg.remove.assert_called_once_with(mock_img)
        mock_canvas.save.assert_called_once_with(output_path, 'JPEG', quality=90)

    @patch('backend.app.services.image_processor.logger')
    def test_empty_bbox_returns_false(self, mock_logger, processor, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        input_path.write_bytes(b'\x00' * 100)

        mock_pil, mock_Image, mock_rembg = self._make_pil_rembg_mocks()

        mock_img = MagicMock()
        mock_output_png = MagicMock()
        mock_output_png.getbbox.return_value = None

        mock_Image.open.return_value = mock_img
        mock_rembg.remove.return_value = mock_output_png

        with patch.dict('sys.modules', {'PIL': mock_pil, 'PIL.Image': mock_Image, 'rembg': mock_rembg}):
            result = processor.remove_background_and_square(input_path, output_path)

        assert result is False

    @patch('backend.app.services.image_processor.logger')
    def test_exception_returns_false(self, mock_logger, processor, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        input_path.write_bytes(b'\x00' * 100)

        mock_pil, mock_Image, mock_rembg = self._make_pil_rembg_mocks()
        mock_Image.open.side_effect = OSError("Corrupt image file")

        with patch.dict('sys.modules', {'PIL': mock_pil, 'PIL.Image': mock_Image, 'rembg': mock_rembg}):
            result = processor.remove_background_and_square(input_path, output_path)

        assert result is False
        mock_logger.error.assert_called_once()
