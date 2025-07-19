"""
Test discovery functionality of MCP Manager.

Test server discovery from NPM and Docker registries.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from mcp_manager.core.discovery import ServerDiscovery, DiscoveryResult
from mcp_manager.core.models import ServerType


class TestServerDiscovery:
    """Test ServerDiscovery class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.discovery = ServerDiscovery()
        
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_discover_npm_servers(self, mock_get):
        """Test discovering NPM servers."""
        # Mock NPM registry response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "objects": [
                {
                    "package": {
                        "name": "@test/mcp-server",
                        "version": "1.0.0",
                        "description": "Test MCP server",
                        "keywords": ["mcp", "server"],
                        "links": {
                            "npm": "https://www.npmjs.com/package/@test/mcp-server"
                        }
                    }
                }
            ]
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        results = await self.discovery._discover_npm_servers("test", limit=10)
        
        assert len(results) == 1
        assert results[0].name == "@test/mcp-server"
        assert results[0].server_type == ServerType.NPM
        assert results[0].description == "Test MCP server"
        assert results[0].package == "@test/mcp-server"
        
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_discover_npm_servers_error(self, mock_get):
        """Test NPM discovery with API error."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_get.return_value.__aenter__.return_value = mock_response
        
        results = await self.discovery._discover_npm_servers("test")
        
        assert results == []
        
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_discover_docker_servers(self, mock_get):
        """Test discovering Docker servers."""
        # Mock Docker Hub API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "test/mcp-server",
                    "description": "Test Docker MCP server",
                    "star_count": 10,
                    "is_official": False
                }
            ]
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        results = await self.discovery._discover_docker_servers("test", limit=10)
        
        assert len(results) == 1
        assert results[0].name == "test/mcp-server"
        assert results[0].server_type == ServerType.DOCKER
        assert results[0].description == "Test Docker MCP server"
        assert results[0].package == "test/mcp-server"
        
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_discover_docker_servers_error(self, mock_get):
        """Test Docker discovery with API error."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response
        
        results = await self.discovery._discover_docker_servers("test")
        
        assert results == []
        
    @pytest.mark.asyncio
    @patch.object(ServerDiscovery, '_discover_npm_servers')
    @patch.object(ServerDiscovery, '_discover_docker_servers')
    async def test_discover_servers(self, mock_docker, mock_npm):
        """Test combined server discovery."""
        # Mock results from both sources
        npm_result = DiscoveryResult(
            name="@test/npm-server",
            server_type=ServerType.NPM,
            package="@test/npm-server",
            version="1.0.0",
                install_command="npx @test/npm-server",
                description="NPM server"
        )
        docker_result = DiscoveryResult(
            name="test/docker-server",
            server_type=ServerType.DOCKER,
            package="test/docker-server",
            version="latest",
                install_command="docker run test/docker-server",
                description="Docker server"
        )
        
        mock_npm.return_value = [npm_result]
        mock_docker.return_value = [docker_result]
        
        results = await self.discovery.discover_servers("test", limit=20)
        
        assert len(results) == 2
        assert any(r.server_type == ServerType.NPM for r in results)
        assert any(r.server_type == ServerType.DOCKER for r in results)
        
    @pytest.mark.asyncio
    async def test_discover_servers_with_filter(self):
        """Test server discovery with type filter."""
        with patch.object(self.discovery, '_discover_npm_servers') as mock_npm:
            mock_npm.return_value = [
                DiscoveryResult(
                    name="@test/server",
                    server_type=ServerType.NPM,
                    package="@test/server",
                    version="1.0.0",
                    install_command="npx @test/server",
                    description="Test server"
                )
            ]
            
            results = await self.discovery.discover_servers(
                "test", 
                server_type=ServerType.NPM, 
                limit=10
            )
            
            assert len(results) == 1
            assert results[0].server_type == ServerType.NPM
            mock_npm.assert_called_once()
            
    def test_filter_by_keywords(self):
        """Test filtering results by keywords."""
        results = [
            DiscoveryResult(
                name="filesystem-server",
                server_type=ServerType.NPM,
                package="@test/filesystem",
                version="1.0.0",
                install_command="npx @test/filesystem",
                description="File system operations",
                keywords=["filesystem", "files"]
            ),
            DiscoveryResult(
                name="database-server",
                server_type=ServerType.NPM,
                package="@test/database",
                version="1.0.0",
                install_command="npx @test/database",
                description="Database operations",
                keywords=["database", "sql"]
            )
        ]
        
        filtered = self.discovery._filter_by_keywords(results, ["filesystem"])
        
        assert len(filtered) == 1
        assert filtered[0].name == "filesystem-server"
        
    def test_sort_by_relevance(self):
        """Test sorting results by relevance."""
        results = [
            DiscoveryResult(
                name="database-server",
                server_type=ServerType.NPM,
                package="@test/database",
                version="1.0.0",
                install_command="npx @test/database",
                description="Database operations"
            ),
            DiscoveryResult(
                name="filesystem-server",
                server_type=ServerType.NPM,
                package="@test/filesystem",
                version="1.0.0",
                install_command="npx @test/filesystem",
                description="File system operations for test query"
            )
        ]
        
        sorted_results = self.discovery._sort_by_relevance(results, "test")
        
        # Result with "test" in description should be first
        assert sorted_results[0].name == "filesystem-server"
        assert sorted_results[1].name == "database-server"


class TestDiscoveryResult:
    """Test DiscoveryResult model."""
    
    def test_discovery_result_creation(self):
        """Test creating a discovery result."""
        result = DiscoveryResult(
            name="test-server",
            server_type=ServerType.NPM,
            package="@test/server",
            version="1.0.0",
            install_command="npx @test/server",
            description="Test server",
            keywords=["test", "server"],
            homepage="https://example.com"
        )
        
        assert result.name == "test-server"
        assert result.server_type == ServerType.NPM
        assert result.package == "@test/server"
        assert result.description == "Test server"
        assert result.keywords == ["test", "server"]
        assert result.homepage == "https://example.com"
        assert result.version == "1.0.0"
        
    def test_discovery_result_defaults(self):
        """Test discovery result with default values."""
        result = DiscoveryResult(
            name="test-server",
            server_type=ServerType.NPM,
            package="@test/server",
            version="1.0.0",
            install_command="npx @test/server"
        )
        
        assert result.description is None
        assert result.keywords == []
        assert result.homepage is None