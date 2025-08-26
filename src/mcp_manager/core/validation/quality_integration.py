"""
Quality Integration for Test Scenarios

Integrates quality system data with test scenario execution via API.
Single responsibility: Bridge quality data to testing framework.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..quality.tracker import QualityTracker
from ..quality.models import QualityReport, QualityMetrics
from .ide_connectivity import IDEConnectivityManager, ConnectivityResult, IDEType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ServerQualityProfile:
    """Combined quality and connectivity profile for an MCP server."""
    server_name: str
    quality_score: int
    success_rate: float
    install_attempts: int
    last_health_check: Optional[datetime]
    connectivity_status: bool
    connectivity_error: Optional[str]
    recommended_for_testing: bool
    quality_tier: str  # "excellent", "good", "fair", "poor"


class QualityIntegratedValidator:
    """Validator that combines quality data with IDE connectivity testing."""
    
    def __init__(self, ide_type: IDEType = IDEType.CLAUDE_CODE, min_quality_score: int = 40):
        self.quality_tracker = QualityTracker()
        self.ide_manager = IDEConnectivityManager(ide_type)
        self.min_quality_score = min_quality_score
        
    async def get_quality_filtered_servers(self, 
                                         min_quality: int = None,
                                         min_success_rate: float = 0.5,
                                         max_servers: int = 10) -> List[ServerQualityProfile]:
        """Get servers filtered by quality metrics and validate connectivity."""
        min_quality = min_quality or self.min_quality_score
        
        try:
            # Get quality rankings from quality system
            quality_rankings = self.quality_tracker.get_server_rankings(limit=max_servers * 2)  # Get more to filter
            
            logger.info(f"🔍 Evaluating {len(quality_rankings)} servers for quality testing")
            
            quality_profiles = []
            for server_id, metrics in quality_rankings:
                # Filter by minimum quality criteria  
                reliability_score = getattr(metrics, 'reliability_score', 0)
                if (reliability_score >= min_quality and 
                    metrics.success_rate >= min_success_rate and
                    metrics.total_install_attempts >= 3):  # Need sufficient data
                    
                    # Test connectivity for qualified servers
                    logger.debug(f"Testing connectivity for qualified server: {server_id}")
                    
                    # Get server command from quality data or construct it
                    server_command = self._get_server_command(server_id)
                    connectivity = await self.ide_manager.validate_server_connectivity(
                        server_id, server_command
                    )
                    
                    # Determine quality tier
                    quality_tier = self._determine_quality_tier(reliability_score)
                    
                    # Recommend for testing based on quality + connectivity
                    recommended = (
                        connectivity.connected and 
                        reliability_score >= min_quality and
                        metrics.success_rate >= min_success_rate
                    )
                    
                    profile = ServerQualityProfile(
                        server_name=server_id,
                        quality_score=reliability_score,
                        success_rate=metrics.success_rate,
                        install_attempts=metrics.total_install_attempts,
                        last_health_check=getattr(metrics, 'last_health_check', None),
                        connectivity_status=connectivity.connected,
                        connectivity_error=connectivity.error_message,
                        recommended_for_testing=recommended,
                        quality_tier=quality_tier
                    )
                    
                    quality_profiles.append(profile)
                    
                    # Stop when we have enough recommended servers
                    recommended_count = sum(1 for p in quality_profiles if p.recommended_for_testing)
                    if recommended_count >= max_servers:
                        break
            
            # Sort by quality score descending
            quality_profiles.sort(key=lambda p: p.quality_score, reverse=True)
            
            recommended_count = sum(1 for p in quality_profiles if p.recommended_for_testing)
            logger.info(f"✅ Found {recommended_count} servers recommended for testing out of {len(quality_profiles)} evaluated")
            
            return quality_profiles[:max_servers]
            
        except Exception as e:
            logger.error(f"Failed to get quality filtered servers: {e}")
            return []
    
    def _get_server_command(self, server_name: str) -> str:
        """Get or construct server command for connectivity testing."""
        # This would ideally come from the server registry
        # For now, construct based on naming patterns
        if server_name.startswith('dd-') or 'docker-desktop' in server_name:
            return f"docker-desktop://{server_name.replace('dd-', '').replace('docker-desktop-', '')}"
        elif '@' in server_name or server_name.startswith('mcp-'):
            return f"npx -y {server_name}"
        else:
            return f"npx -y {server_name}"  # Default to npm
    
    def _determine_quality_tier(self, quality_score: int) -> str:
        """Determine quality tier based on score."""
        if quality_score >= 80:
            return "excellent"
        elif quality_score >= 60:
            return "good"
        elif quality_score >= 40:
            return "fair"
        else:
            return "poor"
    
    async def validate_and_update_quality(self, server_name: str, server_command: str) -> ServerQualityProfile:
        """Validate server connectivity and update quality metrics."""
        try:
            # Test connectivity
            connectivity = await self.ide_manager.validate_server_connectivity(server_name, server_command)
            
            # Record the result in quality system
            if connectivity.connected:
                # Record successful health check
                self.quality_tracker.record_health_check(
                    server_name=server_name,
                    status=True,
                    response_time_ms=connectivity.response_time_ms or 0,
                    details={"ide_type": connectivity.ide_type, "command": connectivity.command_used}
                )
                logger.info(f"✅ {server_name}: Connectivity validated and quality updated")
            else:
                # Record failed health check
                self.quality_tracker.record_health_check(
                    server_name=server_name,
                    status=False,
                    response_time_ms=0,
                    error_message=connectivity.error_message,
                    details={"ide_type": connectivity.ide_type, "command": connectivity.command_used}
                )
                logger.warning(f"❌ {server_name}: Connectivity failed, quality updated")
            
            # Get updated quality report
            quality_report = self.quality_tracker.get_server_quality_report(server_name)
            if quality_report:
                metrics = quality_report.quality_metrics
                return ServerQualityProfile(
                    server_name=server_name,
                    quality_score=metrics.quality_score,
                    success_rate=metrics.success_rate,
                    install_attempts=metrics.install_attempts,
                    last_health_check=datetime.now(),
                    connectivity_status=connectivity.connected,
                    connectivity_error=connectivity.error_message,
                    recommended_for_testing=connectivity.connected and metrics.quality_score >= self.min_quality_score,
                    quality_tier=self._determine_quality_tier(metrics.quality_score)
                )
            else:
                # No quality data yet, create basic profile
                return ServerQualityProfile(
                    server_name=server_name,
                    quality_score=0,
                    success_rate=0.0,
                    install_attempts=0,
                    last_health_check=datetime.now(),
                    connectivity_status=connectivity.connected,
                    connectivity_error=connectivity.error_message,
                    recommended_for_testing=False,
                    quality_tier="poor"
                )
                
        except Exception as e:
            logger.error(f"Failed to validate and update quality for {server_name}: {e}")
            return ServerQualityProfile(
                server_name=server_name,
                quality_score=0,
                success_rate=0.0,
                install_attempts=0,
                last_health_check=None,
                connectivity_status=False,
                connectivity_error=str(e),
                recommended_for_testing=False,
                quality_tier="poor"
            )


class TestScenarioQualityFilter:
    """Filters and validates servers for test scenario execution."""
    
    def __init__(self, ide_type: IDEType = IDEType.CLAUDE_CODE):
        self.validator = QualityIntegratedValidator(ide_type)
        
    async def get_servers_for_testing(self, 
                                    category: str = "core",
                                    max_servers: int = 5,
                                    min_quality: int = 50) -> List[ServerQualityProfile]:
        """Get high-quality servers suitable for test scenarios."""
        logger.info(f"🎯 Getting servers for {category} testing (min quality: {min_quality})")
        
        # Get quality-filtered servers
        servers = await self.validator.get_quality_filtered_servers(
            min_quality=min_quality,
            min_success_rate=0.6,  # At least 60% success rate
            max_servers=max_servers
        )
        
        # Filter recommended servers only
        recommended_servers = [s for s in servers if s.recommended_for_testing]
        
        if not recommended_servers:
            logger.warning(f"⚠️ No servers meet quality requirements for {category} testing")
            return []
        
        logger.info(f"✅ Selected {len(recommended_servers)} high-quality servers for {category} testing:")
        for server in recommended_servers:
            logger.info(f"   • {server.server_name}: {server.quality_score}/100 quality, {server.success_rate:.1%} success rate")
        
        return recommended_servers
    
    async def validate_test_suite_quality(self, server_names: List[str]) -> Dict[str, ServerQualityProfile]:
        """Validate quality and connectivity for a list of servers in a test suite."""
        logger.info(f"🔍 Validating quality for {len(server_names)} servers in test suite")
        
        results = {}
        for server_name in server_names:
            server_command = self.validator._get_server_command(server_name)
            profile = await self.validator.validate_and_update_quality(server_name, server_command)
            results[server_name] = profile
        
        # Log summary
        recommended_count = sum(1 for p in results.values() if p.recommended_for_testing)
        logger.info(f"📊 Suite validation: {recommended_count}/{len(server_names)} servers recommended for testing")
        
        return results
    
    async def should_skip_test_scenario(self, required_servers: List[str], min_quality_threshold: int = 40) -> Tuple[bool, str]:
        """Determine if a test scenario should be skipped based on server quality."""
        if not required_servers:
            return False, "No server requirements"
        
        # Validate required servers
        validation_results = await self.validate_test_suite_quality(required_servers)
        
        # Check if any required servers fail quality threshold
        failed_servers = []
        for server_name, profile in validation_results.items():
            if not profile.connectivity_status:
                failed_servers.append(f"{server_name} (connectivity failed)")
            elif profile.quality_score < min_quality_threshold:
                failed_servers.append(f"{server_name} (quality {profile.quality_score} < {min_quality_threshold})")
        
        if failed_servers:
            reason = f"Required servers failed quality check: {', '.join(failed_servers)}"
            return True, reason
        
        return False, "All required servers meet quality requirements"


# Convenience functions for common use cases
async def get_high_quality_servers_for_testing(max_servers: int = 5, min_quality: int = 60) -> List[ServerQualityProfile]:
    """Get high-quality servers suitable for testing."""
    filter_service = TestScenarioQualityFilter()
    return await filter_service.get_servers_for_testing(max_servers=max_servers, min_quality=min_quality)


async def validate_server_for_testing(server_name: str) -> ServerQualityProfile:
    """Validate a single server for testing suitability."""
    validator = QualityIntegratedValidator()
    server_command = validator._get_server_command(server_name)
    return await validator.validate_and_update_quality(server_name, server_command)