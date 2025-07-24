"""
Quality-aware discovery integration.

This module enhances the discovery system with quality metrics,
warnings, and recommendations based on community tracking data.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from mcp_manager.core.models import DiscoveryResult
from mcp_manager.core.quality.tracker import QualityTracker
from mcp_manager.core.quality.models import QualityMetrics, InstallOutcome
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QualityEnhancedResult:
    """Discovery result enhanced with quality information."""
    
    # Original discovery result
    original: DiscoveryResult
    
    # Quality metrics
    quality_metrics: Optional[QualityMetrics] = None
    
    # Display enhancements
    quality_badge: str = ""
    warning_message: str = ""
    recommendation_text: str = ""
    alternative_suggestions: List[str] = None
    
    def __post_init__(self):
        """Initialize alternative suggestions if None."""
        if self.alternative_suggestions is None:
            self.alternative_suggestions = []
    
    @property
    def display_name(self) -> str:
        """Get display name with quality badge."""
        base_name = self.original.name
        if self.quality_badge:
            return f"{self.quality_badge} {base_name}"
        return base_name
    
    @property
    def enhanced_description(self) -> str:
        """Get description with quality information."""
        desc = self.original.description
        
        if self.quality_metrics:
            m = self.quality_metrics
            if m.total_install_attempts > 0:
                success_info = f" | Success: {m.success_rate:.0%} ({m.successful_installs}/{m.total_install_attempts})"
                desc += success_info
            
            if m.average_rating > 0:
                rating_info = f" | Rating: {m.average_rating:.1f}/5"  
                desc += rating_info
        
        return desc


class QualityAwareDiscovery:
    """
    Discovery system enhanced with quality tracking.
    
    Provides quality-aware search results with warnings, recommendations,
    and alternative suggestions based on community data.
    """
    
    def __init__(self, quality_tracker: Optional[QualityTracker] = None):
        """
        Initialize quality-aware discovery.
        
        Args:
            quality_tracker: Quality tracker instance. If None, creates new one.
        """
        self.quality_tracker = quality_tracker or QualityTracker()
        
        # Quality thresholds for warnings
        self.warning_thresholds = {
            "min_attempts": 5,  # Minimum attempts before showing quality data
            "poor_success_rate": 0.6,  # Below 60% success rate
            "critical_success_rate": 0.3,  # Below 30% success rate  
            "low_rating": 2.5,  # Below 2.5/5 rating
            "stale_days": 90  # No successful installs in 90 days
        }
        
        logger.debug("QualityAwareDiscovery initialized")
    
    def enhance_discovery_results(
        self, 
        results: List[DiscoveryResult],
        show_quality_details: bool = True
    ) -> List[QualityEnhancedResult]:
        """
        Enhance discovery results with quality information.
        
        Args:
            results: Original discovery results
            show_quality_details: Whether to include detailed quality info
            
        Returns:
            List of quality-enhanced discovery results
        """
        enhanced_results = []
        
        for result in results:
            enhanced = self._enhance_single_result(result, show_quality_details)
            enhanced_results.append(enhanced)
        
        # Sort by quality score (descending), then by original relevance
        enhanced_results.sort(key=lambda x: (
            x.quality_metrics.reliability_score if x.quality_metrics else 0,
            x.original.relevance_score
        ), reverse=True)
        
        logger.debug(f"Enhanced {len(results)} discovery results with quality data")
        return enhanced_results
    
    def _enhance_single_result(
        self, 
        result: DiscoveryResult, 
        show_details: bool
    ) -> QualityEnhancedResult:
        """Enhance a single discovery result with quality data."""
        enhanced = QualityEnhancedResult(original=result)
        
        try:
            # Get quality metrics
            metrics = self.quality_tracker.get_quality_metrics(
                server_id=result.name,
                install_id=result.install_id
            )
            
            # Only show quality info if we have meaningful data
            if metrics.total_install_attempts >= self.warning_thresholds["min_attempts"]:
                enhanced.quality_metrics = metrics
                enhanced.quality_badge = self._get_quality_badge(metrics)
                enhanced.warning_message = self._get_warning_message(metrics)
                enhanced.recommendation_text = self._get_recommendation_text(metrics)
                enhanced.alternative_suggestions = self._get_alternatives(result, metrics)
            elif metrics.total_install_attempts > 0:
                # Limited data - show basic info
                enhanced.quality_metrics = metrics
                enhanced.quality_badge = "📊"  # Data available but limited
                enhanced.recommendation_text = f"Limited data ({metrics.total_install_attempts} attempts)"
        
        except Exception as e:
            logger.warning(f"Failed to enhance result {result.name} with quality data: {e}")
        
        return enhanced
    
    def _get_quality_badge(self, metrics: QualityMetrics) -> str:
        """Get quality badge based on metrics."""
        tier = metrics.get_quality_tier()
        
        badge_map = {
            "excellent": "🏆",  # Trophy for excellent
            "good": "✅",       # Check mark for good
            "fair": "⚠️",       # Warning for fair
            "poor": "❗",       # Exclamation for poor
            "critical": "❌"    # X for critical
        }
        
        return badge_map.get(tier, "")
    
    def _get_warning_message(self, metrics: QualityMetrics) -> str:
        """Generate warning message based on quality issues."""
        warnings = []
        
        # Success rate warnings
        if metrics.success_rate < self.warning_thresholds["critical_success_rate"]:
            warnings.append(f"Very low success rate ({metrics.success_rate:.0%})")
        elif metrics.success_rate < self.warning_thresholds["poor_success_rate"]:
            warnings.append(f"Low success rate ({metrics.success_rate:.0%})")
        
        # Rating warnings
        if metrics.average_rating > 0 and metrics.average_rating < self.warning_thresholds["low_rating"]:
            warnings.append(f"Low user rating ({metrics.average_rating:.1f}/5)")
        
        # Maintenance warnings
        if metrics.maintenance_status == "abandoned":
            warnings.append("Server appears abandoned")
        elif metrics.maintenance_status == "stale":
            warnings.append("Server may be stale")
        
        # Common issues
        if metrics.common_issues:
            top_issue = max(metrics.common_issues.items(), key=lambda x: x[1])
            issue_name = top_issue[0].value.replace("_", " ").title()
            warnings.append(f"Common issue: {issue_name}")
        
        return " | ".join(warnings) if warnings else ""
    
    def _get_recommendation_text(self, metrics: QualityMetrics) -> str:
        """Generate recommendation text."""
        tier = metrics.get_quality_tier()
        
        if tier == "excellent":
            return f"Highly recommended (Score: {metrics.reliability_score:.0f}/100)"
        elif tier == "good":
            return f"Recommended (Score: {metrics.reliability_score:.0f}/100)"
        elif tier == "fair":
            return f"Use with caution (Score: {metrics.reliability_score:.0f}/100)"
        elif tier == "poor":
            return f"Known issues (Score: {metrics.reliability_score:.0f}/100)"
        else:  # critical
            return f"Not recommended (Score: {metrics.reliability_score:.0f}/100)"
    
    def _get_alternatives(self, result: DiscoveryResult, metrics: QualityMetrics) -> List[str]:
        """Get alternative server suggestions."""
        alternatives = []
        
        # If this server has quality issues, suggest better alternatives
        if metrics.reliability_score < 60:  # Below "good" threshold
            # Look for similar servers with better scores
            similar_servers = self._find_similar_servers(result)
            
            for server_id, alt_metrics in similar_servers:
                if alt_metrics.reliability_score > metrics.reliability_score + 20:  # Significantly better
                    alternatives.append(server_id)
        
        return alternatives[:3]  # Limit to top 3 alternatives
    
    def _find_similar_servers(self, result: DiscoveryResult) -> List[Tuple[str, QualityMetrics]]:
        """Find servers similar to the given result."""
        # Simple similarity based on name/description keywords
        keywords = self._extract_keywords(result)
        
        # Get all server rankings
        all_servers = self.quality_tracker.get_server_rankings(limit=100)
        
        similar_servers = []
        for server_id, metrics in all_servers:
            if server_id != result.name:  # Don't include the same server
                server_keywords = self._extract_keywords_from_name(server_id)
                if self._has_keyword_overlap(keywords, server_keywords):
                    similar_servers.append((server_id, metrics))
        
        # Sort by reliability score
        similar_servers.sort(key=lambda x: x[1].reliability_score, reverse=True)
        return similar_servers[:5]  # Top 5 similar servers
    
    def _extract_keywords(self, result: DiscoveryResult) -> set:
        """Extract keywords from discovery result."""
        text = f"{result.name} {result.description}".lower()
        
        # Common MCP server keywords
        keywords = set()
        common_terms = [
            "filesystem", "file", "database", "db", "sqlite", "postgres", "mysql",
            "web", "http", "api", "rest", "git", "github", "docker", "aws", "cloud",
            "search", "index", "browser", "selenium", "playwright", "test", "testing"
        ]
        
        for term in common_terms:
            if term in text:
                keywords.add(term)
        
        return keywords
    
    def _extract_keywords_from_name(self, server_name: str) -> set:
        """Extract keywords from server name."""
        name_lower = server_name.lower()
        keywords = set()
        
        common_terms = [
            "filesystem", "file", "database", "db", "sqlite", "postgres", "mysql",
            "web", "http", "api", "rest", "git", "github", "docker", "aws", "cloud",
            "search", "index", "browser", "selenium", "playwright", "test", "testing"
        ]
        
        for term in common_terms:
            if term in name_lower:
                keywords.add(term)
        
        return keywords
    
    def _has_keyword_overlap(self, keywords1: set, keywords2: set) -> bool:
        """Check if two keyword sets have meaningful overlap."""
        return len(keywords1.intersection(keywords2)) > 0
    
    def get_quality_summary_for_install(self, install_id: str) -> Dict:
        """
        Get quality summary for installation prompt.
        
        Args:
            install_id: Server install ID
            
        Returns:
            Dictionary with quality summary for display
        """
        try:
            metrics = self.quality_tracker.get_quality_metrics(
                server_id=install_id,  # Using install_id as server_id for now
                install_id=install_id
            )
            
            if metrics.total_install_attempts < self.warning_thresholds["min_attempts"]:
                return {
                    "has_data": False,
                    "message": "No quality data available yet"
                }
            
            summary = {
                "has_data": True,
                "reliability_score": metrics.reliability_score,
                "success_rate": metrics.success_rate,
                "total_attempts": metrics.total_install_attempts,
                "quality_tier": metrics.get_quality_tier(),
                "recommendation": metrics.get_recommendation_status(),
                "warning_message": self._get_warning_message(metrics),
                "alternatives": metrics.recommended_alternatives
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get quality summary for {install_id}: {e}")
            return {"has_data": False, "error": str(e)}
    
    def record_install_outcome(
        self,
        install_id: str,
        success: bool,
        duration_seconds: float,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record the outcome of an installation attempt.
        
        Args:
            install_id: Server install ID
            success: Whether installation succeeded
            duration_seconds: Time taken for installation
            error_message: Error message if failed
        """
        outcome = InstallOutcome.SUCCESS if success else InstallOutcome.FAILURE
        
        # Try to categorize the error
        error_category = None
        if error_message and not success:
            error_lower = error_message.lower()
            if "timeout" in error_lower:
                outcome = InstallOutcome.TIMEOUT
            elif "connection" in error_lower or "connect" in error_lower:
                from mcp_manager.core.quality.models import IssueCategory
                error_category = IssueCategory.CONNECTION
            elif "config" in error_lower or "argument" in error_lower:
                from mcp_manager.core.quality.models import IssueCategory
                error_category = IssueCategory.CONFIGURATION
            elif "dependency" in error_lower or "module" in error_lower:
                from mcp_manager.core.quality.models import IssueCategory
                error_category = IssueCategory.DEPENDENCIES
        
        self.quality_tracker.record_install_attempt(
            server_id=install_id,  # Using install_id as server_id for now
            install_id=install_id,
            outcome=outcome,
            duration_seconds=duration_seconds,
            error_message=error_message,
            error_category=error_category
        )
        
        logger.info(f"Recorded install outcome for {install_id}: {outcome.value}")


def create_quality_aware_discovery() -> QualityAwareDiscovery:
    """Factory function to create quality-aware discovery instance."""
    return QualityAwareDiscovery()