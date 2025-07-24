"""
Helper utilities for discovery functionality.

Provides pattern matching and other utility functions.
"""

import fnmatch
import re
from typing import List, Optional

from mcp_manager.core.models import DiscoveryResult
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class PatternMatcher:
    """Handles pattern matching for discovery queries."""
    
    def is_pattern_query(self, query: Optional[str]) -> bool:
        """Check if query contains pattern matching syntax."""
        if not query:
            return False
        return any(char in query for char in ['*', '?', '[']) or query.startswith('regex:')
    
    def extract_base_query(self, query: Optional[str]) -> Optional[str]:
        """Extract base search term from pattern for API queries."""
        if not query:
            return None
            
        if query.startswith('regex:'):
            return None  # Use broad search for regex
        else:
            base_term = query.split('*')[0].split('?')[0].split('[')[0]
            return base_term if len(base_term) >= 2 else None
    
    def matches_pattern(self, text: str, pattern: str) -> bool:
        """
        Check if text matches pattern using wildcards and regex.
        
        Supports:
        - Wildcards: aws* matches aws-s3, aws-dynamodb, etc.
        - Regex: if pattern starts with 'regex:' it's treated as regex
        - Case-insensitive matching
        
        Args:
            text: Text to match against
            pattern: Pattern to match (supports wildcards and regex)
            
        Returns:
            True if text matches pattern
        """
        if not pattern:
            return True
            
        text = text.lower()
        pattern = pattern.lower()
        
        # Handle regex patterns (prefix with 'regex:')
        if pattern.startswith('regex:'):
            try:
                regex_pattern = pattern[6:]  # Remove 'regex:' prefix
                return bool(re.search(regex_pattern, text))
            except re.error:
                # If regex is invalid, fall back to literal matching
                return pattern[6:] in text
        
        # Handle wildcard patterns (*, ?, [])
        if any(char in pattern for char in ['*', '?', '[']):
            return fnmatch.fnmatch(text, pattern)
        
        # Default: substring matching
        return pattern in text
    
    def filter_results_by_pattern(self, results: List[DiscoveryResult], query: str) -> List[DiscoveryResult]:
        """
        Filter discovery results by pattern matching on name, package, and description.
        
        Args:
            results: List of discovery results
            query: Pattern to match
            
        Returns:
            Filtered list of results
        """
        if not query:
            return results
            
        filtered = []
        for result in results:
            # Check name, package, and description
            if (self.matches_pattern(result.name, query) or 
                self.matches_pattern(result.package or "", query) or
                self.matches_pattern(result.description or "", query)):
                filtered.append(result)
                
        return filtered