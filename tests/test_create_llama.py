"""Tests for _create_llama() — safe LLM model loading with stderr redirect."""

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.llm import _create_llama


class TestCreateLlama:
    """Test the _create_llama wrapper that protects Textual's WriterThread."""

    @patch("src.llm.Llama")
    def test_forces_verbose_true_even_when_false(self, mock_llama_cls):
        mock_llama_cls.return_value = MagicMock()
        _create_llama(model_path="/fake/model.gguf", verbose=False)
        _, kwargs = mock_llama_cls.call_args
        assert kwargs["verbose"] is True

    @patch("src.llm.Llama")
    def test_forces_verbose_true_when_omitted(self, mock_llama_cls):
        mock_llama_cls.return_value = MagicMock()
        _create_llama(model_path="/fake/model.gguf")
        _, kwargs = mock_llama_cls.call_args
        assert kwargs["verbose"] is True

    @patch("src.llm.Llama")
    def test_stderr_restored_after_successful_load(self, mock_llama_cls):
        mock_llama_cls.return_value = MagicMock()
        saved_fd = os.dup(2)
        try:
            _create_llama(model_path="/fake/model.gguf")
            after = os.fstat(2)
            expected = os.fstat(saved_fd)
            assert after.st_dev == expected.st_dev
            assert after.st_ino == expected.st_ino
        finally:
            os.close(saved_fd)

    @patch("src.llm.Llama")
    def test_stderr_restored_after_failed_load(self, mock_llama_cls):
        mock_llama_cls.side_effect = RuntimeError("model load failed")
        saved_fd = os.dup(2)
        try:
            with pytest.raises(RuntimeError, match="model load failed"):
                _create_llama(model_path="/fake/model.gguf")
            after = os.fstat(2)
            expected = os.fstat(saved_fd)
            assert after.st_dev == expected.st_dev
            assert after.st_ino == expected.st_ino
        finally:
            os.close(saved_fd)

    @patch("src.llm.Llama")
    def test_stdout_untouched_during_load(self, mock_llama_cls):
        stdout_before = os.fstat(1)
        stdout_during_load = None

        def capture_stdout(**kwargs):
            nonlocal stdout_during_load
            stdout_during_load = os.fstat(1)
            return MagicMock()

        mock_llama_cls.side_effect = capture_stdout
        _create_llama(model_path="/fake/model.gguf")
        stdout_after = os.fstat(1)

        assert stdout_before.st_dev == stdout_during_load.st_dev
        assert stdout_before.st_ino == stdout_during_load.st_ino
        assert stdout_before.st_dev == stdout_after.st_dev

    @patch("src.llm.Llama")
    def test_lock_prevents_concurrent_loads(self, mock_llama_cls):
        peak_concurrency = 0
        active_count = 0
        count_lock = threading.Lock()

        def slow_load(**kwargs):
            nonlocal peak_concurrency, active_count
            with count_lock:
                active_count += 1
                peak_concurrency = max(peak_concurrency, active_count)
            time.sleep(0.05)
            with count_lock:
                active_count -= 1
            return MagicMock()

        mock_llama_cls.side_effect = slow_load

        threads = [threading.Thread(target=_create_llama, kwargs={"model_path": "/fake/model.gguf"}) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert peak_concurrency == 1

    @patch("src.llm.os.dup", side_effect=OSError("dup failed"))
    @patch("src.llm.Llama")
    def test_loads_model_even_when_redirect_fails(self, mock_llama_cls, mock_dup):
        mock_llama_cls.return_value = MagicMock()
        result = _create_llama(model_path="/fake/model.gguf")
        assert result is not None
        mock_llama_cls.assert_called_once()
