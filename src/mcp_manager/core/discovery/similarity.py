"""
Server similarity detection for MCP servers.

Detects servers that provide similar functionality to avoid duplication.
"""

from typing import Any, Dict, List

from mcp_manager.core.models import DiscoveryResult
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SimilarityDetector:
    """Detects similar servers based on functionality."""
    
    def detect_similar_servers(self, target_server: DiscoveryResult, existing_servers: List[Any]) -> List[Dict[str, Any]]:
        """
        Detect servers that provide similar functionality to the target server.
        
        Args:
            target_server: The server to check for similarities
            existing_servers: List of currently installed servers
            
        Returns:
            List of similar servers with similarity details
        """
        similar_servers = []
        
        # Extract target server's core functionality
        target_core_name = self._extract_core_server_name(target_server.name)
        target_functionality = self._extract_server_functionality(target_server)
        
        for existing_server in existing_servers:
            similarity_score = 0
            similarity_reasons = []
            
            # Check name similarity
            existing_core_name = self._extract_core_server_name(existing_server.name)
            if target_core_name == existing_core_name:
                similarity_score += 50
                similarity_reasons.append(f"Same core functionality: {target_core_name}")
            
            # Check functionality overlap
            existing_functionality = self._extract_server_functionality_from_server(existing_server)
            functionality_overlap = target_functionality & existing_functionality
            if functionality_overlap:
                similarity_score += len(functionality_overlap) * 10
                similarity_reasons.append(f"Shared functionality: {', '.join(functionality_overlap)}")
            
            # Check description similarity (if available)
            if (hasattr(target_server, 'description') and target_server.description and
                hasattr(existing_server, 'description') and existing_server.description):
                desc_similarity = self._calculate_description_similarity(
                    target_server.description, existing_server.description
                )
                if desc_similarity > 0.3:  # 30% similarity threshold
                    similarity_score += int(desc_similarity * 20)
                    similarity_reasons.append(f"Similar description ({desc_similarity:.1%} match)")
            
            # Check package name patterns (npm scoped packages, docker prefixes)
            if self._check_package_name_similarity(target_server, existing_server):
                similarity_score += 30
                similarity_reasons.append("Similar package naming pattern")
            
            # If similarity score is significant, include it
            if similarity_score >= 40:  # Minimum threshold for considering servers similar
                similar_servers.append({
                    "server": existing_server,
                    "similarity_score": similarity_score,
                    "reasons": similarity_reasons,
                    "recommendation": self._generate_similarity_recommendation(similarity_score, similarity_reasons)
                })
        
        # Sort by similarity score (highest first)
        similar_servers.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similar_servers
    
    def _extract_core_server_name(self, server_name: str) -> str:
        """Extract the core functionality name from a server name."""
        # Remove common prefixes and suffixes
        name = server_name.lower()
        
        # Remove common suffixes first (more specific patterns)
        suffixes_to_remove = ['-mcp', '_mcp', '-server', '_server', '-client', '_client']
        for suffix in suffixes_to_remove:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        
        # Remove common prefixes
        prefixes_to_remove = [
            'mcp-', 'mcp_', '@modelcontextprotocol/', '@', 'dd-', 'docker-',
            'official-', 'npm-', 'node-'
        ]
        
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        # Handle complex names like 'playwright-mcp-ta', 'sqlite-database-server'
        # Extract the first meaningful component that likely represents the core functionality
        if '-' in name:
            parts = name.split('-')
            # Look for known functionality keywords in the first few parts
            functionality_keywords = [
                'playwright', 'sqlite', 'database', 'filesystem', 'file', 'github', 'git',
                'web', 'browser', 'search', 'notification', 'docker', 'aws', 'cloud',
                'terraform', 'kubernetes', 'k8s', 'http', 'api', 'oauth', 'auth',
                'slack', 'discord', 'email', 'calendar', 'pdf', 'image', 'video'
            ]
            
            # Check if the first part is a known functionality
            if parts[0] in functionality_keywords:
                name = parts[0]
            else:
                # Check if any of the first 2-3 parts match known functionalities
                for i in range(min(3, len(parts))):
                    if parts[i] in functionality_keywords:
                        name = parts[i]
                        break
                else:
                    # If no known functionality found, check for common patterns
                    # like "mcp-X-Y" where X is likely the core functionality
                    if len(parts) >= 2 and parts[0] != 'mcp':
                        name = parts[0]
        
        # Handle underscore-separated names similarly
        if '_' in name and '-' not in name:
            parts = name.split('_')
            functionality_keywords = [
                'playwright', 'sqlite', 'database', 'filesystem', 'file', 'github', 'git',
                'web', 'browser', 'search', 'notification', 'docker', 'aws', 'cloud',
                'terraform', 'kubernetes', 'k8s', 'http', 'api', 'oauth', 'auth',
                'slack', 'discord', 'email', 'calendar', 'pdf', 'image', 'video'
            ]
            
            # Check if the first part is a known functionality
            if parts[0] in functionality_keywords:
                name = parts[0]
            else:
                # Check if any of the first 2-3 parts match known functionalities
                for i in range(min(3, len(parts))):
                    if parts[i] in functionality_keywords:
                        name = parts[i]
                        break
                else:
                    # If no known functionality found, use the first meaningful part
                    if len(parts) >= 2 and parts[0] != 'mcp':
                        name = parts[0]
        
        return name
    
    def _extract_server_functionality(self, server: DiscoveryResult) -> set:
        """Extract functionality keywords from a server's metadata."""
        functionality = set()
        
        # Extract from server name
        core_name = self._extract_core_server_name(server.name)
        functionality.add(core_name)
        
        # Extract from description
        if server.description:
            desc_lower = server.description.lower()
            
            # Common MCP server functionalities
            function_keywords = [
                'filesystem', 'file', 'directory', 'storage',
                'database', 'sqlite', 'sql', 'query',
                'github', 'git', 'repository', 'source',
                'web', 'browser', 'automation', 'playwright',
                'search', 'index', 'retrieval',
                'notification', 'message', 'alert',
                'docker', 'container', 'deployment',
                'aws', 'cloud', 'infrastructure'
            ]
            
            for keyword in function_keywords:
                if keyword in desc_lower:
                    functionality.add(keyword)
        
        # Extract from package name patterns
        if server.package:
            package_lower = server.package.lower()
            if 'playwright' in package_lower:
                functionality.add('playwright')
            if 'sqlite' in package_lower or 'database' in package_lower:
                functionality.add('database')
            if 'filesystem' in package_lower or 'file' in package_lower:
                functionality.add('filesystem')
            if 'github' in package_lower:
                functionality.add('github')
        
        return functionality
    
    def _extract_server_functionality_from_server(self, server: Any) -> set:
        """Extract functionality from an installed server object."""
        functionality = set()
        
        # Extract from server name
        core_name = self._extract_core_server_name(server.name)
        functionality.add(core_name)
        
        # Extract from description if available
        if hasattr(server, 'description') and server.description:
            desc_lower = server.description.lower()
            
            function_keywords = [
                'filesystem', 'file', 'directory', 'storage',
                'database', 'sqlite', 'sql', 'query',
                'github', 'git', 'repository', 'source',
                'web', 'browser', 'automation', 'playwright',
                'search', 'index', 'retrieval',
                'notification', 'message', 'alert',
                'docker', 'container', 'deployment',
                'aws', 'cloud', 'infrastructure'
            ]
            
            for keyword in function_keywords:
                if keyword in desc_lower:
                    functionality.add(keyword)
        
        return functionality
    
    def _calculate_description_similarity(self, desc1: str, desc2: str) -> float:
        """Calculate similarity between two descriptions."""
        if not desc1 or not desc2:
            return 0.0
        
        # Simple word-based similarity calculation
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        
        # Remove common words that don't indicate functionality
        common_words = {'a', 'an', 'the', 'and', 'or', 'but', 'for', 'with', 'to', 'from', 'of', 'in', 'on', 'at', 'by'}
        words1 -= common_words
        words2 -= common_words
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _check_package_name_similarity(self, server1: DiscoveryResult, server2: Any) -> bool:
        """Check if two servers have similar package naming patterns."""
        # Check for common scoped package patterns
        if (server1.package and hasattr(server2, 'package') and server2.package):
            pkg1 = server1.package.lower()
            pkg2 = server2.package.lower()
            
            # Check for scoped packages (@org/name pattern)
            if pkg1.startswith('@') and pkg2.startswith('@'):
                # Extract the package name part after the scope
                name1 = pkg1.split('/')[-1] if '/' in pkg1 else pkg1
                name2 = pkg2.split('/')[-1] if '/' in pkg2 else pkg2
                
                if self._extract_core_server_name(name1) == self._extract_core_server_name(name2):
                    return True
        
        return False
    
    def _generate_similarity_recommendation(self, score: int, reasons: List[str]) -> str:
        """Generate a recommendation based on similarity analysis."""
        if score >= 80:
            return "High similarity - consider if both servers are needed"
        elif score >= 60:
            return "Moderate similarity - review functionality overlap"
        elif score >= 40:
            return "Some similarity - check for potential conflicts"
        else:
            return "Low similarity - likely safe to install both"