"""
Scenario Parser for JSON test scenarios.

Handles loading, preprocessing, and organizing test scenarios from various sources.
Supports filtering, sorting, and batching scenarios for efficient execution.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ScenarioMetadata:
    """Metadata extracted from a scenario for organization and filtering."""
    id: str
    name: str
    category: str
    priority: str
    tags: List[str]
    created_by: str
    confidence_score: float
    required_servers: List[str]
    scope: str
    file_path: Path
    deduplication_key: Optional[str] = None
    estimated_duration: float = 30.0

class ScenarioParser:
    """Parses and organizes JSON test scenarios."""
    
    def __init__(self, scenarios_root: Optional[Path] = None):
        """Initialize scenario parser."""
        if scenarios_root is None:
            scenarios_root = Path(__file__).parent.parent / "scenarios"
        
        self.scenarios_root = scenarios_root
        self.scenario_cache = {}
        self.metadata_cache = {}
    
    def discover_scenarios(self, 
                          category_filter: Optional[str] = None,
                          priority_filter: Optional[str] = None,
                          tag_filter: Optional[List[str]] = None,
                          created_by_filter: Optional[str] = None) -> List[ScenarioMetadata]:
        """
        Discover all scenarios matching the given filters.
        
        Args:
            category_filter: Filter by category (core, workflow, integration, etc.)
            priority_filter: Filter by priority (critical, high, medium, low)
            tag_filter: Filter by tags (must contain all specified tags)
            created_by_filter: Filter by creator (ai, admin, system, migration)
            
        Returns:
            List of scenario metadata matching filters
        """
        logger.info(f"🔍 Discovering scenarios in {self.scenarios_root}")
        
        if not self.scenarios_root.exists():
            logger.warning(f"Scenarios directory does not exist: {self.scenarios_root}")
            return []
        
        all_scenarios = []
        json_files = list(self.scenarios_root.glob("**/*.json"))
        
        logger.debug(f"Found {len(json_files)} potential scenario files")
        
        for json_file in json_files:
            try:
                metadata = self._extract_scenario_metadata(json_file)
                if metadata and self._matches_filters(
                    metadata, category_filter, priority_filter, tag_filter, created_by_filter
                ):
                    all_scenarios.append(metadata)
                    
            except Exception as e:
                logger.warning(f"Failed to parse scenario {json_file}: {e}")
        
        logger.info(f"📋 Discovered {len(all_scenarios)} matching scenarios")
        return all_scenarios
    
    def _extract_scenario_metadata(self, file_path: Path) -> Optional[ScenarioMetadata]:
        """Extract metadata from a scenario file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            scenario_info = data.get('scenario', {})
            mcp_reqs = data.get('mcp_requirements', {})
            test_steps = data.get('test_steps', [])
            
            # Calculate estimated duration from steps
            estimated_duration = sum(
                step.get('timeout', 30) for step in test_steps
            )
            
            metadata = ScenarioMetadata(
                id=scenario_info.get('id', ''),
                name=scenario_info.get('name', ''),
                category=scenario_info.get('category', 'unknown'),
                priority=scenario_info.get('priority', 'medium'),
                tags=scenario_info.get('tags', []),
                created_by=scenario_info.get('created_by', 'unknown'),
                confidence_score=scenario_info.get('confidence_score', 0.0),
                required_servers=[
                    server.get('name', '') for server in mcp_reqs.get('required_servers', [])
                ],
                scope=mcp_reqs.get('scope', 'user'),
                file_path=file_path,
                deduplication_key=mcp_reqs.get('deduplication_key'),
                estimated_duration=estimated_duration
            )
            
            # Cache metadata for faster subsequent access
            self.metadata_cache[str(file_path)] = metadata
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata from {file_path}: {e}")
            return None
    
    def _matches_filters(self, 
                        metadata: ScenarioMetadata,
                        category_filter: Optional[str],
                        priority_filter: Optional[str],
                        tag_filter: Optional[List[str]],
                        created_by_filter: Optional[str]) -> bool:
        """Check if metadata matches all specified filters."""
        
        if category_filter and metadata.category != category_filter:
            return False
        
        if priority_filter and metadata.priority != priority_filter:
            return False
        
        if created_by_filter and metadata.created_by != created_by_filter:
            return False
        
        if tag_filter:
            metadata_tags_set = set(metadata.tags)
            required_tags_set = set(tag_filter)
            if not required_tags_set.issubset(metadata_tags_set):
                return False
        
        return True
    
    def load_scenario(self, scenario_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load a complete scenario from file.
        
        Args:
            scenario_path: Path to scenario JSON file
            
        Returns:
            Complete scenario data or None if loading fails
        """
        cache_key = str(scenario_path)
        
        # Check cache first
        if cache_key in self.scenario_cache:
            logger.debug(f"📋 Loading scenario from cache: {scenario_path.name}")
            return self.scenario_cache[cache_key]
        
        try:
            with open(scenario_path, 'r') as f:
                scenario_data = json.load(f)
            
            # Validate basic structure
            required_keys = ['scenario', 'mcp_requirements', 'test_steps', 'validation']
            if not all(key in scenario_data for key in required_keys):
                logger.error(f"Scenario missing required keys: {scenario_path}")
                return None
            
            # Cache for future use
            self.scenario_cache[cache_key] = scenario_data
            
            logger.debug(f"📋 Loaded scenario: {scenario_data['scenario'].get('name', 'Unknown')}")
            return scenario_data
            
        except Exception as e:
            logger.error(f"Failed to load scenario from {scenario_path}: {e}")
            return None
    
    def organize_scenarios_by_category(self, scenarios: List[ScenarioMetadata]) -> Dict[str, List[ScenarioMetadata]]:
        """Organize scenarios by category."""
        categories = {}
        
        for scenario in scenarios:
            category = scenario.category
            if category not in categories:
                categories[category] = []
            categories[category].append(scenario)
        
        # Sort scenarios within each category by priority
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        
        for category in categories:
            categories[category].sort(
                key=lambda s: (priority_order.get(s.priority, 4), s.name)
            )
        
        return categories
    
    def create_execution_batches(self, 
                               scenarios: List[ScenarioMetadata],
                               max_batch_duration: float = 300.0,
                               max_batch_size: int = 10) -> List[List[ScenarioMetadata]]:
        """
        Create optimal batches for scenario execution.
        
        Args:
            scenarios: List of scenarios to batch
            max_batch_duration: Maximum total duration per batch (seconds)
            max_batch_size: Maximum number of scenarios per batch
            
        Returns:
            List of scenario batches optimized for execution
        """
        logger.info(f"📦 Creating execution batches from {len(scenarios)} scenarios")
        
        # Sort scenarios by priority and estimated duration
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sorted_scenarios = sorted(
            scenarios,
            key=lambda s: (priority_order.get(s.priority, 4), s.estimated_duration)
        )
        
        batches = []
        current_batch = []
        current_duration = 0.0
        
        for scenario in sorted_scenarios:
            # Check if adding this scenario would exceed batch limits
            would_exceed_duration = (current_duration + scenario.estimated_duration) > max_batch_duration
            would_exceed_size = len(current_batch) >= max_batch_size
            
            if current_batch and (would_exceed_duration or would_exceed_size):
                # Start a new batch
                batches.append(current_batch)
                current_batch = []
                current_duration = 0.0
            
            current_batch.append(scenario)
            current_duration += scenario.estimated_duration
        
        # Add the final batch if it has scenarios
        if current_batch:
            batches.append(current_batch)
        
        logger.info(f"📦 Created {len(batches)} execution batches")
        for i, batch in enumerate(batches):
            total_duration = sum(s.estimated_duration for s in batch)
            logger.debug(f"   Batch {i+1}: {len(batch)} scenarios, ~{total_duration:.1f}s")
        
        return batches
    
    def detect_duplicate_scenarios(self, scenarios: List[ScenarioMetadata]) -> List[Tuple[ScenarioMetadata, ScenarioMetadata]]:
        """
        Detect potentially duplicate scenarios based on deduplication keys and similarity.
        
        Args:
            scenarios: List of scenarios to check for duplicates
            
        Returns:
            List of tuples containing potential duplicate pairs
        """
        duplicates = []
        
        # Group by deduplication key
        dedup_groups = {}
        for scenario in scenarios:
            if scenario.deduplication_key:
                key = scenario.deduplication_key
                if key not in dedup_groups:
                    dedup_groups[key] = []
                dedup_groups[key].append(scenario)
        
        # Find groups with multiple scenarios
        for key, group in dedup_groups.items():
            if len(group) > 1:
                logger.warning(f"Found {len(group)} scenarios with same deduplication key: {key}")
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        duplicates.append((group[i], group[j]))
        
        # Also check for similar names/functionality
        for i, scenario1 in enumerate(scenarios):
            for j, scenario2 in enumerate(scenarios[i + 1:], i + 1):
                if self._are_scenarios_similar(scenario1, scenario2):
                    duplicates.append((scenario1, scenario2))
        
        if duplicates:
            logger.warning(f"⚠️  Found {len(duplicates)} potential duplicate scenario pairs")
        
        return duplicates
    
    def _are_scenarios_similar(self, scenario1: ScenarioMetadata, scenario2: ScenarioMetadata) -> bool:
        """Check if two scenarios are potentially duplicates based on similarity."""
        # Same category and very similar names
        if scenario1.category == scenario2.category:
            name1_words = set(re.findall(r'\\w+', scenario1.name.lower()))
            name2_words = set(re.findall(r'\\w+', scenario2.name.lower()))
            
            # High word overlap might indicate similarity
            common_words = name1_words.intersection(name2_words)
            total_words = name1_words.union(name2_words)
            
            if len(total_words) > 0:
                similarity = len(common_words) / len(total_words)
                if similarity > 0.7:  # 70% word overlap
                    return True
        
        # Same required servers and scope
        if (set(scenario1.required_servers) == set(scenario2.required_servers) and
            scenario1.scope == scenario2.scope and
            scenario1.category == scenario2.category):
            return True
        
        return False
    
    def generate_scenario_summary(self, scenarios: List[ScenarioMetadata]) -> Dict[str, Any]:
        """Generate a comprehensive summary of scenarios."""
        if not scenarios:
            return {"total_scenarios": 0}
        
        # Basic counts
        total = len(scenarios)
        categories = {}
        priorities = {}
        creators = {}
        server_usage = {}
        
        for scenario in scenarios:
            # Count by category
            categories[scenario.category] = categories.get(scenario.category, 0) + 1
            
            # Count by priority
            priorities[scenario.priority] = priorities.get(scenario.priority, 0) + 1
            
            # Count by creator
            creators[scenario.created_by] = creators.get(scenario.created_by, 0) + 1
            
            # Count server usage
            for server in scenario.required_servers:
                server_usage[server] = server_usage.get(server, 0) + 1
        
        # Calculate totals
        total_duration = sum(s.estimated_duration for s in scenarios)
        avg_confidence = sum(s.confidence_score for s in scenarios) / total
        
        summary = {
            "total_scenarios": total,
            "categories": dict(sorted(categories.items())),
            "priorities": dict(sorted(priorities.items())),
            "creators": dict(sorted(creators.items())),
            "server_usage": dict(sorted(server_usage.items(), key=lambda x: x[1], reverse=True)),
            "estimated_total_duration": total_duration,
            "average_confidence_score": avg_confidence,
            "most_used_servers": list(dict(sorted(server_usage.items(), key=lambda x: x[1], reverse=True)).keys())[:5]
        }
        
        return summary
    
    def print_scenario_summary(self, scenarios: List[ScenarioMetadata]):
        """Print a human-readable scenario summary."""
        summary = self.generate_scenario_summary(scenarios)
        
        if summary["total_scenarios"] == 0:
            print("📋 No scenarios found")
            return
        
        print(f"\\n📋 Scenario Discovery Summary")
        print(f"{'='*50}")
        print(f"📊 Total Scenarios: {summary['total_scenarios']}")
        print(f"⏱️  Estimated Duration: {summary['estimated_total_duration']:.1f}s")
        print(f"🎯 Average Confidence: {summary['average_confidence_score']:.2f}")
        
        print(f"\\n📁 Categories:")
        for category, count in summary['categories'].items():
            print(f"   • {category}: {count}")
        
        print(f"\\n🔥 Priorities:")
        for priority, count in summary['priorities'].items():
            print(f"   • {priority}: {count}")
        
        print(f"\\n🛠️  Most Used Servers:")
        for server in summary['most_used_servers'][:3]:
            count = summary['server_usage'][server]
            print(f"   • {server}: {count} scenarios")

if __name__ == "__main__":
    # Example usage
    parser = ScenarioParser()
    scenarios = parser.discover_scenarios()
    parser.print_scenario_summary(scenarios)