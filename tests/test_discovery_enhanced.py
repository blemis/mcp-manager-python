"""Enhanced tests for server discovery functionality across all sources."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.models import DiscoveryResult, ServerType


@pytest.mark.asyncio
class TestDiscoveryAllSources:
    """Test discovery across NPM, Docker Hub, and Docker Desktop."""

    async def test_discover_all_sources(self):
        """Test discovery returns results from all three sources."""
        discovery = ServerDiscovery()
        
        # Mock NPM response
        npm_response = {
            "objects": [
                {
                    "package": {
                        "name": "@modelcontextprotocol/server-filesystem",
                        "version": "1.0.0",
                        "description": "Filesystem MCP server",
                        "keywords": ["mcp", "filesystem"],
                        "author": {"name": "Test Author"},
                        "links": {"repository": "https://github.com/test/repo"},
                    },
                    "score": {"detail": {"popularity": 0.8}},
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Mock NPM request
            mock_npm_response = AsyncMock()
            mock_npm_response.json.return_value = npm_response
            mock_npm_response.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_npm_response
            
            results = await discovery.discover_servers(limit=30)
            
            # Should have results from all sources
            assert len(results) > 0
            
            # Check for different types
            npm_results = [r for r in results if "@modelcontextprotocol" in r.package]
            docker_hub_results = [r for r in results if "mcp-docker-desktop" in r.package]
            docker_desktop_results = [r for r in results if "docker.io/phidata" in r.package]
            
            assert len(npm_results) > 0
            assert len(docker_hub_results) > 0
            assert len(docker_desktop_results) > 0

    async def test_discover_npm_only(self):
        """Test discovery with NPM filter."""
        discovery = ServerDiscovery()
        
        npm_response = {
            "objects": [
                {
                    "package": {
                        "name": "@modelcontextprotocol/server-sqlite",
                        "version": "2.0.0",
                        "description": "SQLite MCP server",
                        "keywords": ["mcp", "sqlite", "database"],
                    },
                    "score": {"detail": {"popularity": 0.9}},
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            mock_response = AsyncMock()
            mock_response.json.return_value = npm_response
            mock_response.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_response
            
            results = await discovery.discover_servers(server_type=ServerType.NPM)
            
            # Should only have NPM results
            assert all(r.server_type == ServerType.NPM for r in results)
            assert any("sqlite" in r.name for r in results)

    async def test_discover_docker_only(self):
        """Test discovery with Docker filter."""
        discovery = ServerDiscovery()
        
        results = await discovery.discover_servers(server_type=ServerType.DOCKER)
        
        # Should only have Docker results
        assert all(r.server_type == ServerType.DOCKER for r in results)
        
        # Should include both Docker Hub and Docker Desktop servers
        docker_hub_names = ["puppeteer", "search", "http", "k8s", "terraform", "aws"]
        docker_desktop_names = ["aws-design", "curl", "hashicorp-terraform", "git", "python"]
        
        result_names = [r.name for r in results]
        
        # Check for some Docker Hub servers
        assert any(name in str(result_names) for name in docker_hub_names)
        
        # Check for some Docker Desktop servers
        assert any(f"docker-desktop-{name}" in result_names for name in docker_desktop_names)

    async def test_search_query_filtering(self):
        """Test search query filters results correctly."""
        discovery = ServerDiscovery()
        
        # Search for terraform
        results = await discovery.discover_servers(query="terraform")
        
        # Should find both Docker Hub and Docker Desktop terraform servers
        terraform_results = [r for r in results if "terraform" in r.name.lower()]
        assert len(terraform_results) >= 2  # At least Docker Hub and Docker Desktop versions
        
        # Search for AWS
        aws_results = await discovery.discover_servers(query="aws")
        aws_names = [r.name for r in aws_results]
        
        # Should find both aws and aws-design
        assert any("aws" in name and "design" not in name for name in aws_names)
        assert any("aws-design" in name for name in aws_names)

    async def test_docker_desktop_specific_servers(self):
        """Test Docker Desktop specific servers are discoverable."""
        discovery = ServerDiscovery()
        
        # Test specific Docker Desktop servers mentioned by user
        important_servers = ["aws-design", "curl", "hashicorp-terraform"]
        
        for server_name in important_servers:
            results = await discovery.discover_servers(query=server_name)
            
            # Should find the Docker Desktop version
            docker_desktop_match = next(
                (r for r in results if f"docker-desktop-{server_name}" == r.name),
                None
            )
            
            assert docker_desktop_match is not None
            assert docker_desktop_match.server_type == ServerType.DOCKER
            assert "docker.io/phidata" in docker_desktop_match.package
            assert "--network bridge" in docker_desktop_match.install_command

    async def test_concurrent_discovery(self):
        """Test concurrent discovery doesn't cause issues."""
        discovery = ServerDiscovery()
        
        # Run multiple discoveries concurrently
        tasks = [
            discovery.discover_servers(query="python"),
            discovery.discover_servers(query="node"),
            discovery.discover_servers(server_type=ServerType.DOCKER),
            discovery.discover_servers(server_type=ServerType.NPM),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert all(isinstance(r, list) for r in results)
        assert all(len(r) > 0 for r in results)

    async def test_discovery_error_handling(self):
        """Test discovery handles errors gracefully."""
        discovery = ServerDiscovery()
        
        # Test with NPM failure
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Make NPM fail
            mock_instance.get.side_effect = httpx.RequestError("Network error")
            
            # Should still get Docker results
            results = await discovery.discover_servers()
            
            # Should have Docker results even if NPM failed
            docker_results = [r for r in results if r.server_type == ServerType.DOCKER]
            assert len(docker_results) > 0

    async def test_cache_functionality(self):
        """Test discovery caching works correctly."""
        discovery = ServerDiscovery()
        
        # Clear cache first
        discovery.clear_cache()
        
        # First call - should hit sources
        with patch.object(discovery, '_discover_npm_servers') as mock_npm:
            mock_npm.return_value = []
            
            results1 = await discovery.discover_servers(query="test", use_cache=True)
            assert mock_npm.called
            
            # Second call - should use cache
            mock_npm.reset_mock()
            results2 = await discovery.discover_servers(query="test", use_cache=True)
            assert not mock_npm.called
            
            # With cache disabled - should hit sources again
            results3 = await discovery.discover_servers(query="test", use_cache=False)
            assert mock_npm.called

    async def test_relevance_sorting(self):
        """Test results are sorted by relevance."""
        discovery = ServerDiscovery()
        
        # Get results without query (all results)
        all_results = await discovery.discover_servers(limit=50)
        
        # Check that results are sorted (can't verify exact order but check structure)
        assert len(all_results) > 0
        
        # Popular/well-known servers should appear near the top
        top_10_names = [r.name for r in all_results[:10]]
        
        # Some well-known servers should be in top results
        well_known = ["filesystem", "puppeteer", "aws", "terraform", "git", "python"]
        assert any(any(known in name for known in well_known) for name in top_10_names)