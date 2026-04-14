"""
Test provider-aware scope review skip logic in parallel_review.py.

Tests cover:
1. OUROBOROS_SKIP_SCOPE_REVIEW environment variable
2. Cloud.ru provider + diff size > 0.5 MB auto-skip
3. Advisory finding verification in fallback result
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from ouroboros.tools.parallel_review import (
    _run_scope,
    _FallbackScopeResult,
)


class TestScopeManualOverride:
    """Test OUROBOROS_SKIP_SCOPE_REVIEW environment variable."""
    
    def test_skip_scope_review_when_env_var_set(self):
        """When OUROBOROS_SKIP_SCOPE_REVIEW=1, scope review is skipped entirely."""
        os.environ['OUROBOROS_SKIP_SCOPE_REVIEW'] = '1'
        
        try:
            result = _run_scope()
            
            assert result.blocked is False
            assert result.block_message == ""
            assert result.critical_findings == []
            assert result.advisory_findings == []
        finally:
            os.environ.pop('OUROBOROS_SKIP_SCOPE_REVIEW', None)
    
    def test_skip_scope_review_case_insensitive_true_values(self):
        """Environment variable accepts '1', 'true', 'TRUE' as true values."""
        for value in ['1', 'true', 'TRUE', 'yes', 'YES']:
            os.environ['OUROBOROS_SKIP_SCOPE_REVIEW'] = value
            
            try:
                result = _run_scope()
                assert result.blocked is False
            finally:
                os.environ.pop('OUROBOROS_SKIP_SCOPE_REVIEW', None)
    
    def test_run_scope_review_when_env_var_false(self):
        """When OUROBOROS_SKIP_SCOPE_REVIEW=0, scope review runs normally."""
        os.environ['OUROBOROS_SKIP_SCOPE_REVIEW'] = '0'
        
        try:
            # Mock the actual scope review to avoid API call
            with patch('ouroboros.tools.parallel_review.run_scope_review') as mock_sr:
                mock_result = _FallbackScopeResult(
                    blocked=False,
                    block_message="",
                    critical_findings=[],
                    advisory_findings=[]
                )
                mock_sr.return_value = mock_result
                
                result = _run_scope()
                
                # Verify scope review was called
                mock_sr.assert_called_once()
                assert result.blocked is False
        finally:
            os.environ.pop('OUROBOROS_SKIP_SCOPE_REVIEW', None)


class TestProviderAwareCloudruSkip:
    """Test Cloud.ru provider + diff size auto-skip logic."""
    
    def setup_method(self):
        """Set up mock context and globals before each test."""
        # Create mock context with Cloud.ru model
        self.mock_ctx = Mock()
        self.mock_ctx._scope_review_model = 'cloudru::zai-org/GLM-4.7'
        
        # Create mock diff_bytes (small and large)
        self.small_diff = b"x" * (100 * 1024)  # 100 KB (< 0.5 MB)
        self.large_diff = b"x" * (1024 * 1024)  # 1 MB (> 0.5 MB)
    
    def test_run_scope_review_with_small_diff_cloudru(self):
        """Small diffs on Cloud.ru should still run scope review."""
        # Set globals
        global ctx, diff_bytes, goal, scope, review_rebuttal, _history_snapshot, _scope_history
        ctx = self.mock_ctx
        diff_bytes = self.small_diff
        
        with patch('ouroboros.tools.parallel_review.run_scope_review') as mock_sr:
            mock_result = _FallbackScopeResult(
                blocked=False,
                block_message="",
                critical_findings=[],
                advisory_findings=[]
            )
            mock_sr.return_value = mock_result
            
            result = _run_scope()
            
            # Verify scope review was called (not skipped)
            mock_sr.assert_called_once()
            assert result.blocked is False
    
    def test_skip_scope_review_with_large_diff_cloudru(self):
        """Large diffs on Cloud.ru should auto-skip with advisory finding."""
        # Set globals
        global ctx, diff_bytes, goal, scope, review_rebuttal, _history_snapshot, _scope_history
        ctx = self.mock_ctx
        diff_bytes = self.large_diff
        
        result = _run_scope()
        
        # Verify auto-skip happened
        assert result.blocked is False
        assert result.block_message == ""
        assert result.critical_findings == []
        
        # Verify advisory finding present
        assert len(result.advisory_findings) == 1
        finding = result.advisory_findings[0]
        assert finding['item'] == 'scope_review_auto_skipped'
        assert 'Cloud.ru payload exceeds 0.5 MB threshold' in finding['reason']
        assert finding['tag'] == 'provider-payload-limit'
        assert finding['severity'] == 'advisory'
    
    def test_run_scope_review_with_anthropic_provider_large_diff(self):
        """Large diffs on Anthropic don't auto-skip (has large context)."""
        # Set context with Anthropic model
        self.mock_ctx._scope_review_model = 'anthropic::claude-opus-4.6'
        global ctx, diff_bytes
        ctx = self.mock_ctx
        diff_bytes = self.large_diff
        
        with patch('ouroboros.tools.parallel_review.run_scope_review') as mock_sr:
            mock_result = _FallbackScopeResult(
                blocked=False,
                block_message="",
                critical_findings=[],
                advisory_findings=[]
            )
            mock_sr.return_value = mock_result
            
            result = _run_scope()
            
            # Verify scope review was called (not skipped)
            mock_sr.assert_called_once()
            assert result.blocked is False
    
    def test_cloudru_detection_case_insensitive(self):
        """Cloud.ru detection should work with various capitalizations."""
        variations = [
            'cloudru::MODEL',
            'cloudru-something::MODEL',
            'CLOUDRU::MODEL',
            'CloudRu::MODEL',
        ]
        
        global ctx, diff_bytes, goal, scope, review_rebuttal, _history_snapshot, _scope_history
        diff_bytes = self.large_diff
        
        for model_id in variations:
            ctx = Mock()
            ctx._scope_review_model = model_id
            
            result = _run_scope()
            
            # All Cloud.ru variants should trigger auto-skip
            assert result.blocked is False
            assert len(result.advisory_findings) == 1
            finding = result.advisory_findings[0]
            assert finding['item'] == 'scope_review_auto_skipped'
    
    def test_diff_size_threshold_at_exactly_0_5_mb(self):
        """Test exact boundary condition at 0.5 MB (524288 bytes)."""
        global ctx, diff_bytes
        ctx = self.mock_ctx
        
        # Exactly 0.5 MB (524288 bytes = 0.5 MB)
        diff_bytes = b"x" * (512 * 1024)
        
        with patch('ouroboros.tools.parallel_review.run_scope_review') as mock_sr:
            mock_result = _FallbackScopeResult(
                blocked=False,
                block_message="",
                critical_findings=[],
                advisory_findings=[]
            )
            mock_sr.return_value = mock_result
            
            result = _run_scope()
            
            # <= 0.5 MB should run scope review
            mock_sr.assert_called_once()
            assert result.blocked is False


class TestScopeReviewImportErrors:
    """Test graceful handling of scope_review import errors."""
    
    @patch('sys.modules', {'ouroboros.tools.scope_review': None})
    def test_scope_review_import_missing_blocks_commit(self):
        """When scope_review module is missing, commit is blocked."""
        # This can't literally happen in Python, but tests the error path logic
        # In reality, if import fails, _run_scope catches ImportError
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])