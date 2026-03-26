import os
import time
import tempfile
import pytest
from PIL import Image
from albumgrids import (
    calculate_grid_size,
    remove_duplicates,
    get_album_art_from_tracks,
    create_normal_grid,
    create_diagonal_grid,
    create_checkered_grid,
    create_spiral_grid,
)
from app import extract_playlist_id, cleanup_old_temp_file, prune_stale_tasks, tasks, app


# --- calculate_grid_size ---

class TestCalculateGridSize:
    def test_zero(self):
        assert calculate_grid_size(0) == 0

    def test_one(self):
        assert calculate_grid_size(1) == 1

    def test_perfect_square(self):
        assert calculate_grid_size(4) == 2
        assert calculate_grid_size(9) == 3
        assert calculate_grid_size(100) == 10

    def test_non_square(self):
        assert calculate_grid_size(10) == 3
        assert calculate_grid_size(15) == 3
        assert calculate_grid_size(17) == 4

    def test_large(self):
        assert calculate_grid_size(300) == 17


# --- extract_playlist_id ---

class TestExtractPlaylistId:
    def test_raw_id(self):
        assert extract_playlist_id("1l4roHQ43lYI3J9zbxExFf") == "1l4roHQ43lYI3J9zbxExFf"

    def test_full_url(self):
        url = "https://open.spotify.com/playlist/1l4roHQ43lYI3J9zbxExFf"
        assert extract_playlist_id(url) == "1l4roHQ43lYI3J9zbxExFf"

    def test_url_with_query_params(self):
        url = "https://open.spotify.com/playlist/1l4roHQ43lYI3J9zbxExFf?si=abc123"
        assert extract_playlist_id(url) == "1l4roHQ43lYI3J9zbxExFf"

    def test_whitespace(self):
        assert extract_playlist_id("  1l4roHQ43lYI3J9zbxExFf  ") == "1l4roHQ43lYI3J9zbxExFf"

    def test_url_with_whitespace(self):
        url = "  https://open.spotify.com/playlist/1l4roHQ43lYI3J9zbxExFf?si=abc  "
        assert extract_playlist_id(url) == "1l4roHQ43lYI3J9zbxExFf"


# --- remove_duplicates ---

class TestRemoveDuplicates:
    def test_no_duplicates(self):
        entries = [("a1", "url1"), ("a2", "url2"), ("a3", "url3")]
        assert remove_duplicates(entries) == entries

    def test_duplicate_album_id(self):
        entries = [("a1", "url1"), ("a1", "url1"), ("a2", "url2")]
        assert remove_duplicates(entries) == [("a1", "url1"), ("a2", "url2")]

    def test_same_url_different_id(self):
        entries = [("a1", "url1"), ("a2", "url1")]
        result = remove_duplicates(entries)
        assert result == [("a1", "url1")]

    def test_different_url_same_id(self):
        entries = [("a1", "url1"), ("a1", "url2")]
        result = remove_duplicates(entries)
        assert result == [("a1", "url1")]

    def test_empty(self):
        assert remove_duplicates([]) == []

    def test_preserves_order(self):
        entries = [("c", "u3"), ("a", "u1"), ("b", "u2"), ("a", "u1")]
        assert remove_duplicates(entries) == [("c", "u3"), ("a", "u1"), ("b", "u2")]


# --- get_album_art_from_tracks ---

class TestGetAlbumArtFromTracks:
    def test_playlist_format(self):
        tracks = [
            {"track": {"album": {"id": "alb1", "images": [{"url": "http://img1"}]}}},
            {"track": {"album": {"id": "alb2", "images": [{"url": "http://img2"}]}}},
        ]
        result = get_album_art_from_tracks(tracks)
        assert result == [("alb1", "http://img1"), ("alb2", "http://img2")]

    def test_top_tracks_format(self):
        tracks = [
            {"album": {"id": "alb1", "images": [{"url": "http://img1"}]}},
        ]
        result = get_album_art_from_tracks(tracks)
        assert result == [("alb1", "http://img1")]

    def test_missing_images_skipped(self):
        tracks = [
            {"track": {"album": {"id": "alb1", "images": []}}},
            {"track": {"album": {"id": "alb2", "images": [{"url": "http://img2"}]}}},
        ]
        result = get_album_art_from_tracks(tracks)
        assert result == [("alb2", "http://img2")]

    def test_none_track_skipped(self):
        tracks = [{"track": None}]
        result = get_album_art_from_tracks(tracks)
        assert result == []

    def test_empty(self):
        assert get_album_art_from_tracks([]) == []

    def test_missing_album_key(self):
        tracks = [{"track": {"name": "no album here"}}]
        result = get_album_art_from_tracks(tracks)
        assert result == []


# --- Grid creation functions ---

def _make_test_images(n, color=(255, 0, 0)):
    return [Image.new("RGB", (10, 10), color) for _ in range(n)]


class TestCreateNormalGrid:
    def test_dimensions_default(self):
        images = _make_test_images(4)
        grid = create_normal_grid(images, 2)
        assert grid.size == (200, 200)

    def test_dimensions_custom_cell_size(self):
        images = _make_test_images(4)
        grid = create_normal_grid(images, 2, cell_size=50)
        assert grid.size == (100, 100)

    def test_dimensions_high_res(self):
        images = _make_test_images(4)
        grid = create_normal_grid(images, 2, cell_size=200)
        assert grid.size == (400, 400)

    def test_dimensions_ultra_res(self):
        images = _make_test_images(4)
        grid = create_normal_grid(images, 2, cell_size=300)
        assert grid.size == (600, 600)

    def test_pixels_filled(self):
        images = _make_test_images(4, color=(255, 0, 0))
        grid = create_normal_grid(images, 2, cell_size=50)
        assert grid.getpixel((0, 0)) == (255, 0, 0)
        assert grid.getpixel((50, 0)) == (255, 0, 0)
        assert grid.getpixel((0, 50)) == (255, 0, 0)
        assert grid.getpixel((50, 50)) == (255, 0, 0)

    def test_single_image(self):
        images = _make_test_images(1, color=(128, 128, 128))
        grid = create_normal_grid(images, 1, cell_size=100)
        assert grid.size == (100, 100)
        assert grid.getpixel((50, 50)) == (128, 128, 128)

    def test_round_image_clips_corners(self):
        from albumgrids import round_image
        images = _make_test_images(4, color=(255, 0, 0))
        grid = create_normal_grid(images, 2, cell_size=100)
        rounded = round_image(grid, radius=20)
        assert rounded.mode == "RGBA"
        assert rounded.size == (200, 200)
        assert rounded.getpixel((100, 100)) == (255, 0, 0, 255)
        assert rounded.getpixel((0, 0)) == (0, 0, 0, 0)  # corner is transparent


class TestCreateDiagonalGrid:
    def test_dimensions(self):
        images = _make_test_images(9)
        grid = create_diagonal_grid(images, 3, cell_size=50)
        assert grid.size == (150, 150)

    def test_dimensions_high_res(self):
        images = _make_test_images(9)
        grid = create_diagonal_grid(images, 3, cell_size=200)
        assert grid.size == (600, 600)

    def test_all_cells_filled(self):
        images = _make_test_images(4, color=(0, 128, 255))
        grid = create_diagonal_grid(images, 2, cell_size=50)
        assert grid.getpixel((0, 0)) == (0, 128, 255)


class TestCreateCheckeredGrid:
    def test_dimensions(self):
        images = _make_test_images(5)
        grid = create_checkered_grid(images, 3, cell_size=50)
        assert grid.size == (150, 150)

    def test_dimensions_high_res(self):
        images = _make_test_images(5)
        grid = create_checkered_grid(images, 3, cell_size=200)
        assert grid.size == (600, 600)

    def test_only_even_cells_filled(self):
        images = _make_test_images(5, color=(0, 255, 0))
        grid = create_checkered_grid(images, 3, cell_size=50)
        assert grid.getpixel((0, 0)) == (0, 255, 0)
        assert grid.getpixel((50, 0)) == (0, 0, 0)
        assert grid.getpixel((100, 0)) == (0, 255, 0)

    def test_uses_all_images_sequentially(self):
        red = [Image.new("RGB", (10, 10), (255, 0, 0))]
        blue = [Image.new("RGB", (10, 10), (0, 0, 255))]
        images = red + blue
        grid = create_checkered_grid(images, 2, cell_size=50)
        assert grid.getpixel((0, 0)) == (255, 0, 0)
        assert grid.getpixel((50, 50)) == (0, 0, 255)


class TestCreateSpiralGrid:
    def test_dimensions(self):
        images = _make_test_images(9)
        grid = create_spiral_grid(images, 3, cell_size=50)
        assert grid.size == (150, 150)

    def test_dimensions_high_res(self):
        images = _make_test_images(9)
        grid = create_spiral_grid(images, 3, cell_size=200)
        assert grid.size == (600, 600)

    def test_first_cell_filled(self):
        images = _make_test_images(4, color=(0, 0, 255))
        grid = create_spiral_grid(images, 2, cell_size=50)
        assert grid.getpixel((0, 0)) == (0, 0, 255)


# --- Progress callback ---

class TestProgressCallback:
    def test_callback_receives_messages(self):
        from albumgrids import generate_album_grid
        from unittest.mock import MagicMock

        calls = []
        def track_progress(current, total, message):
            calls.append((current, total, message))

        sp = MagicMock()
        sp.playlist_items.return_value = {
            "items": [
                {"track": {"album": {"id": f"a{i}", "images": [{"url": f"http://fake/{i}.jpg"}]}}}
                for i in range(4)
            ]
        }

        try:
            generate_album_grid(sp, mode="playlist", playlist_id="test", progress_callback=track_progress)
        except Exception:
            pass

        assert len(calls) > 0
        assert any("Fetching" in msg for _, _, msg in calls)


# --- Temp file cleanup ---

class TestCleanupOldTempFile:
    def test_deletes_existing_file(self):
        with app.test_request_context():
            app.config["SECRET_KEY"] = "test"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(b"fake")
            tmp.close()

            from flask import session as flask_session
            flask_session["generated_image_path"] = tmp.name
            flask_session["generated_image_name"] = "test.png"

            assert os.path.exists(tmp.name)
            cleanup_old_temp_file()
            assert not os.path.exists(tmp.name)
            assert "generated_image_path" not in flask_session

    def test_handles_missing_file(self):
        with app.test_request_context():
            app.config["SECRET_KEY"] = "test"
            from flask import session as flask_session
            flask_session["generated_image_path"] = "/nonexistent/file.png"
            cleanup_old_temp_file()
            assert "generated_image_path" not in flask_session

    def test_noop_when_no_path(self):
        with app.test_request_context():
            app.config["SECRET_KEY"] = "test"
            cleanup_old_temp_file()


class TestPruneStaleTasks:
    def test_removes_old_tasks(self):
        old_id = "old-task"
        tasks[old_id] = {
            "status": "done",
            "created_at": time.time() - 9999,
            "current": 0, "total": 1, "message": "old",
        }
        prune_stale_tasks()
        assert old_id not in tasks

    def test_keeps_fresh_tasks(self):
        fresh_id = "fresh-task"
        tasks[fresh_id] = {
            "status": "running",
            "created_at": time.time(),
            "current": 0, "total": 1, "message": "fresh",
        }
        prune_stale_tasks()
        assert fresh_id in tasks
        del tasks[fresh_id]

    def test_deletes_stale_temp_file(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(b"fake")
        tmp.close()

        stale_id = "stale-with-file"
        tasks[stale_id] = {
            "status": "done",
            "created_at": time.time() - 9999,
            "image_path": tmp.name,
            "current": 0, "total": 1, "message": "stale",
        }
        prune_stale_tasks()
        assert not os.path.exists(tmp.name)
        assert stale_id not in tasks
