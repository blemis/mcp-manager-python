"""
Query analysis and categorization for usage analytics.

Handles query pattern analysis, keyword extraction, and categorization
for user queries in the MCP Manager analytics system.
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class QueryProcessor:
    """Handles query analysis and pattern tracking for analytics."""
    
    def __init__(self, db_connection: sqlite3.Connection):
        """
        Initialize query processor.
        
        Args:
            db_connection: SQLite database connection
        """
        self.db_connection = db_connection
        
        # Query categorization patterns
        self.category_patterns = {
            "filesystem": ["file", "directory", "folder", "path", "read", "write"],
            "search": ["search", "find", "lookup", "locate", "discover"],
            "database": ["database", "sql", "query", "table", "select", "insert"],
            "web": ["web", "http", "api", "request", "url", "fetch"],
            "development": ["git", "github", "repo", "commit", "branch", "code"],
            "automation": ["automate", "script", "run", "execute", "batch", "schedule"],
            "data": ["data", "json", "csv", "parse", "transform", "analyze"],
            "system": ["system", "process", "service", "monitor", "status"],
        }
        
        # Common stop words to exclude from keywords
        self.stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
            "of", "with", "by", "from", "up", "about", "into", "through", "during",
            "before", "after", "above", "below", "between", "among", "through",
            "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
            "your", "yours", "yourself", "yourselves", "he", "him", "his", 
            "himself", "she", "her", "hers", "herself", "it", "its", "itself",
            "they", "them", "their", "theirs", "themselves", "what", "which",
            "who", "whom", "this", "that", "these", "those", "am", "is", "are",
            "was", "were", "be", "been", "being", "have", "has", "had", "having",
            "do", "does", "did", "doing", "will", "would", "should", "could",
            "can", "may", "might", "must", "shall"
        }
    
    def categorize_query(self, query: str) -> str:
        """
        Categorize a user query based on content analysis.
        
        Args:
            query: User query string
            
        Returns:
            Category string
        """
        if not query or not query.strip():
            return "general"
        
        query_lower = query.lower()
        category_scores = {}
        
        # Score each category based on keyword matches
        for category, keywords in self.category_patterns.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            return "general"
        
        # Return category with highest score
        return max(category_scores.items(), key=lambda x: x[1])[0]
    
    def extract_keywords(self, query: str, max_keywords: int = 10) -> List[str]:
        """
        Extract meaningful keywords from a query.
        
        Args:
            query: User query string
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List of extracted keywords
        """
        if not query or not query.strip():
            return []
        
        # Extract words using regex
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter out stop words and short words
        keywords = [
            word for word in words 
            if word not in self.stop_words and len(word) > 2
        ]
        
        # Remove duplicates while preserving order
        unique_keywords = []
        seen = set()
        for keyword in keywords:
            if keyword not in seen:
                unique_keywords.append(keyword)
                seen.add(keyword)
        
        return unique_keywords[:max_keywords]
    
    def hash_query(self, query: str) -> str:
        """
        Generate a privacy-preserving hash of the query.
        
        Args:
            query: User query string
            
        Returns:
            SHA256 hash of the query
        """
        if not query:
            return ""
        
        return hashlib.sha256(query.encode('utf-8')).hexdigest()
    
    def update_query_patterns(self, query: str, selected_tool: Optional[str], 
                            success: bool) -> bool:
        """
        Update query pattern analytics in the database.
        
        Args:
            query: User query string
            selected_tool: Tool selected by user (if any)
            success: Whether the query execution was successful
            
        Returns:
            True if update was successful
        """
        if not query or not query.strip():
            return False
        
        try:
            query_hash = self.hash_query(query)
            category = self.categorize_query(query)
            keywords = self.extract_keywords(query)
            
            cursor = self.db_connection.cursor()
            
            # Get existing pattern
            cursor.execute("""
                SELECT frequency, success_rate, most_selected_tools, 
                       average_recommendation_count
                FROM query_patterns WHERE query_hash = ?
            """, (query_hash,))
            
            existing = cursor.fetchone()
            
            if existing:
                self._update_existing_pattern(
                    cursor, query_hash, existing, selected_tool, success
                )
            else:
                self._create_new_pattern(
                    cursor, query_hash, category, keywords, selected_tool, success
                )
            
            self.db_connection.commit()
            
            logger.debug("Query pattern updated", extra={
                "category": category,
                "keywords_count": len(keywords),
                "selected_tool": selected_tool,
                "success": success
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update query patterns: {e}")
            return False
    
    def _update_existing_pattern(self, cursor: sqlite3.Cursor, query_hash: str,
                               existing: tuple, selected_tool: Optional[str], 
                               success: bool) -> None:
        """Update an existing query pattern record."""
        freq, succ_rate, tools_json, avg_rec = existing
        most_tools = json.loads(tools_json) if tools_json else []
        
        # Update frequency and success rate
        new_freq = freq + 1
        new_succ_rate = ((succ_rate * freq) + (1 if success else 0)) / new_freq
        
        # Update most selected tools list
        if selected_tool and selected_tool not in most_tools:
            most_tools.append(selected_tool)
            # Keep only top 5 most recent tools
            if len(most_tools) > 5:
                most_tools = most_tools[-5:]
        
        # Calculate trending score (frequency weighted by recency and success)
        trending_score = new_freq * 0.7 + new_succ_rate * 0.3
        
        cursor.execute("""
            UPDATE query_patterns SET
                frequency = ?, success_rate = ?, most_selected_tools = ?,
                last_seen = ?, trending_score = ?
            WHERE query_hash = ?
        """, (
            new_freq, new_succ_rate, json.dumps(most_tools),
            datetime.utcnow().isoformat(), trending_score, query_hash
        ))
    
    def _create_new_pattern(self, cursor: sqlite3.Cursor, query_hash: str,
                          category: str, keywords: List[str], 
                          selected_tool: Optional[str], success: bool) -> None:
        """Create a new query pattern record."""
        tools_list = [selected_tool] if selected_tool else []
        
        cursor.execute("""
            INSERT INTO query_patterns (
                query_hash, query_category, query_keywords, frequency,
                success_rate, most_selected_tools, trending_score,
                last_seen, first_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            query_hash, category, json.dumps(keywords), 1,
            1.0 if success else 0.0, json.dumps(tools_list), 1.0,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
        ))
    
    def get_trending_queries(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get trending query patterns.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of trending query information
        """
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                SELECT query_category, frequency, success_rate, 
                       average_recommendation_count, most_selected_tools,
                       trending_score, last_seen, first_seen
                FROM query_patterns 
                ORDER BY trending_score DESC, frequency DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "category": row[0],
                    "frequency": row[1],
                    "success_rate": row[2],
                    "avg_recommendations": row[3],
                    "popular_tools": json.loads(row[4]) if row[4] else [],
                    "trending_score": row[5],
                    "last_seen": row[6],
                    "first_seen": row[7]
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get trending queries: {e}")
            return []
    
    def get_query_categories(self) -> Dict[str, int]:
        """
        Get query category distribution.
        
        Returns:
            Dictionary mapping categories to frequency counts
        """
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                SELECT query_category, SUM(frequency) as total_frequency
                FROM query_patterns 
                GROUP BY query_category
                ORDER BY total_frequency DESC
            """)
            
            return {row[0]: row[1] for row in cursor.fetchall()}
            
        except Exception as e:
            logger.error(f"Failed to get query categories: {e}")
            return {}