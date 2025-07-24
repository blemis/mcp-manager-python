"""
Task Classifier Module for AI Curation Intelligence.

Classifies task descriptions into appropriate categories for MCP suite recommendations.
Supports both AI-powered and heuristic classification methods.
"""

from typing import Dict, List, Optional
import re

from mcp_manager.ai.curation.models import TaskCategory
from mcp_manager.core.ai_config import ai_config_manager
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class TaskClassifier:
    """Classifies task descriptions into TaskCategory enums."""
    
    # Keyword patterns for heuristic classification
    CATEGORY_KEYWORDS = {
        TaskCategory.WEB_DEVELOPMENT: [
            "web", "website", "html", "css", "javascript", "js", "frontend", "backend",
            "react", "vue", "angular", "node", "express", "django", "flask", "api",
            "http", "rest", "graphql", "server", "client", "browser", "responsive"
        ],
        TaskCategory.DATA_ANALYSIS: [
            "data", "analysis", "analytics", "chart", "graph", "visualization", "viz",
            "pandas", "numpy", "matplotlib", "dataset", "csv", "json", "statistics",
            "ml", "machine learning", "ai", "model", "prediction", "insights", "report"
        ],
        TaskCategory.SYSTEM_ADMIN: [
            "server", "admin", "administration", "infrastructure", "deploy", "deployment",
            "monitor", "monitoring", "devops", "ops", "system", "network", "security",
            "backup", "maintenance", "configuration", "install", "setup", "provision"
        ],
        TaskCategory.CONTENT_CREATION: [
            "content", "write", "writing", "edit", "editing", "document", "documentation",
            "blog", "article", "text", "markdown", "pdf", "word", "create", "generate",
            "publish", "cms", "copy", "copywriting", "author", "draft"
        ],
        TaskCategory.API_DEVELOPMENT: [
            "api", "rest", "restful", "graphql", "endpoint", "service", "microservice",
            "webhook", "integration", "sdk", "client", "server", "json", "xml", "soap",
            "oauth", "authentication", "authorization", "token", "swagger", "openapi"
        ],
        TaskCategory.DATABASE_WORK: [
            "database", "db", "sql", "query", "schema", "table", "mysql", "postgres",
            "postgresql", "sqlite", "mongodb", "redis", "elasticsearch", "data",
            "orm", "migration", "backup", "restore", "index", "optimize", "crud"
        ],
        TaskCategory.FILE_MANAGEMENT: [
            "file", "files", "directory", "folder", "organize", "manage", "sync",
            "backup", "archive", "compress", "extract", "search", "find", "sort",
            "rename", "move", "copy", "delete", "filesystem", "storage", "upload"
        ],
        TaskCategory.AUTOMATION: [
            "automate", "automation", "script", "scripting", "workflow", "schedule",
            "batch", "cron", "task", "job", "pipeline", "ci", "cd", "build", "deploy",
            "test", "continuous", "integration", "process", "robot", "bot", "macro"
        ],
        TaskCategory.RESEARCH: [
            "research", "search", "find", "information", "study", "investigate",
            "explore", "discover", "analyze", "examine", "review", "survey", "google",
            "web search", "academic", "paper", "literature", "source", "reference"
        ],
        TaskCategory.TESTING: [
            "test", "testing", "qa", "quality", "assurance", "verify", "validation",
            "unit test", "integration", "e2e", "selenium", "playwright", "cypress",
            "mock", "stub", "coverage", "assertion", "debug", "troubleshoot"
        ]
    }
    
    # Weighted importance of different keywords
    KEYWORD_WEIGHTS = {
        "primary": 3.0,    # Core functionality keywords
        "secondary": 2.0,  # Supporting functionality keywords
        "tertiary": 1.0    # General related keywords
    }
    
    # Primary keywords for each category (higher weight)
    PRIMARY_KEYWORDS = {
        TaskCategory.WEB_DEVELOPMENT: ["web", "website", "frontend", "backend", "api", "http"],
        TaskCategory.DATA_ANALYSIS: ["data", "analysis", "analytics", "visualization", "ml"],
        TaskCategory.SYSTEM_ADMIN: ["server", "admin", "infrastructure", "deploy", "devops"],
        TaskCategory.CONTENT_CREATION: ["content", "write", "document", "blog", "create"],
        TaskCategory.API_DEVELOPMENT: ["api", "rest", "graphql", "endpoint", "service"],
        TaskCategory.DATABASE_WORK: ["database", "sql", "query", "schema", "table"],
        TaskCategory.FILE_MANAGEMENT: ["file", "directory", "folder", "organize", "manage"],
        TaskCategory.AUTOMATION: ["automate", "script", "workflow", "schedule", "batch"],
        TaskCategory.RESEARCH: ["research", "search", "information", "study", "investigate"],
        TaskCategory.TESTING: ["test", "testing", "qa", "verify", "validation"]
    }
    
    def __init__(self):
        self.ai_config = ai_config_manager
    
    async def classify_task(self, task_description: str) -> TaskCategory:
        """Classify a task description into a category."""
        try:
            # Try AI-powered classification first if available
            if self._is_ai_available():
                return await self._classify_with_ai(task_description)
            else:
                return self._classify_with_heuristics(task_description)
                
        except Exception as e:
            logger.error(f"Failed to classify task: {e}")
            return self._get_fallback_category(task_description)
    
    def classify_multiple_tasks(self, task_descriptions: List[str]) -> Dict[str, TaskCategory]:
        """Classify multiple task descriptions efficiently."""
        try:
            results = {}
            
            for description in task_descriptions:
                # Use heuristic classification for batch processing (faster)
                category = self._classify_with_heuristics(description)
                results[description] = category
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to classify multiple tasks: {e}")
            return {}
    
    def get_classification_confidence(self, task_description: str, category: TaskCategory) -> float:
        """Get confidence score (0-1) for a classification."""
        try:
            scores = self._calculate_category_scores(task_description)
            max_score = max(scores.values()) if scores else 0
            category_score = scores.get(category, 0)
            
            if max_score == 0:
                return 0.5  # Neutral confidence
            
            # Confidence is the ratio of category score to max score
            confidence = category_score / max_score
            
            # Apply confidence adjustments
            if confidence > 0.8:
                return min(1.0, confidence * 1.1)  # High confidence boost
            elif confidence < 0.3:
                return max(0.1, confidence * 0.8)  # Low confidence penalty
            else:
                return confidence
                
        except Exception as e:
            logger.error(f"Failed to calculate classification confidence: {e}")
            return 0.5
    
    def _is_ai_available(self) -> bool:
        """Check if AI services are available for classification."""
        try:
            config = self.ai_config.load_config()
            primary_provider = self.ai_config.get_primary_provider()
            return config.enabled and primary_provider is not None
        except Exception:
            return False
    
    async def _classify_with_ai(self, task_description: str) -> TaskCategory:
        """Classify using AI services (placeholder for future implementation)."""
        try:
            # TODO: Implement actual AI classification when AI client is available
            # This would involve:
            # 1. Prepare classification prompt
            # 2. Call AI service with task description
            # 3. Parse AI response to TaskCategory
            
            logger.debug("AI classification not yet implemented, falling back to heuristics")
            return self._classify_with_heuristics(task_description)
            
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return self._classify_with_heuristics(task_description)
    
    def _classify_with_heuristics(self, task_description: str) -> TaskCategory:
        """Classify using keyword-based heuristics."""
        try:
            # Calculate scores for each category
            scores = self._calculate_category_scores(task_description)
            
            if not scores:
                return TaskCategory.AUTOMATION  # Default fallback
            
            # Return category with highest score
            best_category = max(scores.items(), key=lambda x: x[1])
            return best_category[0]
            
        except Exception as e:
            logger.error(f"Heuristic classification failed: {e}")
            return TaskCategory.AUTOMATION
    
    def _calculate_category_scores(self, task_description: str) -> Dict[TaskCategory, float]:
        """Calculate weighted scores for each category based on keyword matches."""
        try:
            description_lower = task_description.lower()
            # Remove punctuation and split into words
            words = re.findall(r'\b\w+\b', description_lower)
            word_set = set(words)
            
            scores = {}
            
            for category in TaskCategory:
                score = 0.0
                
                # Check primary keywords (higher weight)
                primary_keywords = self.PRIMARY_KEYWORDS.get(category, [])
                for keyword in primary_keywords:
                    if keyword in description_lower:
                        score += self.KEYWORD_WEIGHTS["primary"]
                        # Bonus for exact word matches
                        if keyword in word_set:
                            score += 0.5
                
                # Check all category keywords
                category_keywords = self.CATEGORY_KEYWORDS.get(category, [])
                for keyword in category_keywords:
                    if keyword in description_lower:
                        # Weight based on keyword importance
                        if keyword in primary_keywords:
                            continue  # Already counted above
                        elif len(keyword) > 6:  # Longer keywords are more specific
                            score += self.KEYWORD_WEIGHTS["secondary"]
                        else:
                            score += self.KEYWORD_WEIGHTS["tertiary"]
                        
                        # Bonus for exact word matches
                        if keyword in word_set:
                            score += 0.3
                
                # Apply phrase matching bonus
                score += self._calculate_phrase_bonus(description_lower, category)
                
                scores[category] = score
            
            return scores
            
        except Exception as e:
            logger.error(f"Failed to calculate category scores: {e}")
            return {}
    
    def _calculate_phrase_bonus(self, description: str, category: TaskCategory) -> float:
        """Calculate bonus score for matching common phrases."""
        phrase_patterns = {
            TaskCategory.WEB_DEVELOPMENT: [
                "web app", "web application", "website development", "frontend development",
                "backend development", "full stack", "web service", "web api"
            ],
            TaskCategory.DATA_ANALYSIS: [
                "data analysis", "data science", "machine learning", "data visualization",
                "statistical analysis", "data mining", "business intelligence", "big data"
            ],
            TaskCategory.SYSTEM_ADMIN: [
                "system administration", "server management", "infrastructure management",
                "devops", "system monitoring", "server deployment", "network administration"
            ],
            TaskCategory.CONTENT_CREATION: [
                "content creation", "content management", "technical writing", "blog writing",
                "document creation", "content generation", "copywriting"
            ],
            TaskCategory.API_DEVELOPMENT: [
                "api development", "rest api", "api integration", "web service",
                "microservice", "api design", "service development"
            ],
            TaskCategory.DATABASE_WORK: [
                "database management", "database design", "database administration",
                "data modeling", "sql queries", "database optimization"
            ],
            TaskCategory.FILE_MANAGEMENT: [
                "file management", "file organization", "file system", "document management",
                "file processing", "data organization"
            ],
            TaskCategory.AUTOMATION: [
                "task automation", "workflow automation", "process automation",
                "build automation", "test automation", "deployment automation"
            ],
            TaskCategory.RESEARCH: [
                "research project", "information gathering", "literature review",
                "market research", "academic research", "data collection"
            ],
            TaskCategory.TESTING: [
                "software testing", "quality assurance", "test automation",
                "unit testing", "integration testing", "performance testing"
            ]
        }
        
        bonus = 0.0
        phrases = phrase_patterns.get(category, [])
        
        for phrase in phrases:
            if phrase in description:
                bonus += 1.5  # Significant bonus for phrase matches
        
        return bonus
    
    def _get_fallback_category(self, task_description: str) -> TaskCategory:
        """Get fallback category when all classification methods fail."""
        # Simple fallback based on common words
        description_lower = task_description.lower()
        
        if any(word in description_lower for word in ["web", "site", "app"]):
            return TaskCategory.WEB_DEVELOPMENT
        elif any(word in description_lower for word in ["data", "analysis"]):
            return TaskCategory.DATA_ANALYSIS
        elif any(word in description_lower for word in ["file", "folder"]):
            return TaskCategory.FILE_MANAGEMENT
        else:
            return TaskCategory.AUTOMATION  # Safe default