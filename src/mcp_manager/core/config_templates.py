"""
Predefined configuration templates for common development workflows.

Provides ready-to-use workflow templates that integrate with AI curation recommendations
and can be customized for specific development contexts.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from mcp_manager.core.models import TaskCategory
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WorkflowTemplate:
    """Template for creating workflows."""
    name: str
    description: str
    category: TaskCategory
    required_servers: List[str]
    optional_servers: List[str]
    priority: int
    auto_activate: bool = True
    notes: Optional[str] = None


class ConfigTemplates:
    """Predefined workflow templates for common development tasks."""
    
    # Core development templates
    WEB_DEVELOPMENT = WorkflowTemplate(
        name="Web Development",
        description="Full-stack web development with database, API, and frontend tools",
        category=TaskCategory.WEB_DEVELOPMENT,
        required_servers=["official-filesystem", "docker-gateway"],
        optional_servers=["brave-search", "playwright"],
        priority=90,
        notes="Optimized for React/Node.js web applications with database integration"
    )
    
    DATA_ANALYSIS = WorkflowTemplate(
        name="Data Analysis",
        description="Data science and analytics workflow with database and visualization tools",
        category=TaskCategory.DATA_ANALYSIS,
        required_servers=["docker-gateway"],  # Includes SQLite tools
        optional_servers=["official-filesystem", "brave-search"],
        priority=85,
        notes="Includes SQLite for data storage, filesystem for data files"
    )
    
    SYSTEM_ADMINISTRATION = WorkflowTemplate(
        name="System Administration", 
        description="System administration and DevOps workflow",
        category=TaskCategory.SYSTEM_ADMINISTRATION,
        required_servers=["official-filesystem", "docker-gateway"],
        optional_servers=["brave-search"],
        priority=80,
        notes="Filesystem access and container management tools"
    )
    
    RESEARCH = WorkflowTemplate(
        name="Research & Documentation",
        description="Research workflow with web search and document management",
        category=TaskCategory.RESEARCH,
        required_servers=["brave-search", "official-filesystem"],
        optional_servers=["docker-gateway"],
        priority=75,
        notes="Web search for research, filesystem for document organization"
    )
    
    AUTOMATION = WorkflowTemplate(
        name="Automation & Scripting",
        description="Automation and scripting workflow",
        category=TaskCategory.AUTOMATION,
        required_servers=["official-filesystem"],
        optional_servers=["docker-gateway", "brave-search"],
        priority=70,
        notes="File system access for script management and execution"
    )
    
    TESTING = WorkflowTemplate(
        name="Testing & QA",
        description="Quality assurance and testing workflow",
        category=TaskCategory.TESTING,
        required_servers=["playwright", "official-filesystem"],
        optional_servers=["docker-gateway", "brave-search"],
        priority=75,
        notes="Browser automation for testing, filesystem for test assets"
    )
    
    # Specialized templates
    DATABASE_DEVELOPMENT = WorkflowTemplate(
        name="Database Development",
        description="Database design and development workflow",
        category=TaskCategory.DATA_ANALYSIS,
        required_servers=["docker-gateway"],  # SQLite tools
        optional_servers=["official-filesystem"],
        priority=85,
        notes="Focused on SQLite database operations and schema management"
    )
    
    API_DEVELOPMENT = WorkflowTemplate(
        name="API Development",
        description="API development and integration workflow", 
        category=TaskCategory.WEB_DEVELOPMENT,
        required_servers=["docker-gateway", "official-filesystem"],
        optional_servers=["brave-search", "playwright"],
        priority=88,
        notes="API development with testing and documentation tools"
    )
    
    CLOUD_DEVELOPMENT = WorkflowTemplate(
        name="Cloud Development",
        description="Cloud architecture and AWS development",
        category=TaskCategory.SYSTEM_ADMINISTRATION,
        required_servers=["docker-gateway"],  # AWS diagram tools
        optional_servers=["official-filesystem", "brave-search"],
        priority=85,
        notes="AWS diagram generation and cloud architecture tools"
    )
    
    FRONTEND_DEVELOPMENT = WorkflowTemplate(
        name="Frontend Development",
        description="Frontend development with browser testing",
        category=TaskCategory.WEB_DEVELOPMENT,
        required_servers=["playwright", "official-filesystem"],
        optional_servers=["docker-gateway", "brave-search"],
        priority=82,
        notes="Browser automation for frontend testing and development"
    )
    
    # Minimal templates
    MINIMAL_FILESYSTEM = WorkflowTemplate(
        name="File Management",
        description="Basic file system operations",
        category=TaskCategory.GENERAL,
        required_servers=["official-filesystem"],
        optional_servers=[],
        priority=60,
        notes="Minimal setup for basic file operations"
    )
    
    MINIMAL_WEB_SEARCH = WorkflowTemplate(
        name="Web Research",
        description="Web search and research only",
        category=TaskCategory.RESEARCH,
        required_servers=["brave-search"],
        optional_servers=["official-filesystem"],
        priority=65,
        notes="Minimal setup for web research tasks"
    )

    @classmethod
    def get_all_templates(cls) -> List[WorkflowTemplate]:
        """Get all available workflow templates."""
        templates = []
        
        # Get all class attributes that are WorkflowTemplate instances
        for attr_name in dir(cls):
            if not attr_name.startswith('_') and attr_name.isupper():
                attr_value = getattr(cls, attr_name)
                if isinstance(attr_value, WorkflowTemplate):
                    templates.append(attr_value)
        
        # Sort by priority (highest first)
        return sorted(templates, key=lambda t: t.priority, reverse=True)
    
    @classmethod
    def get_templates_by_category(cls, category: TaskCategory) -> List[WorkflowTemplate]:
        """Get templates for a specific category."""
        return [t for t in cls.get_all_templates() if t.category == category]
    
    @classmethod
    def get_template_by_name(cls, name: str) -> Optional[WorkflowTemplate]:
        """Get template by name."""
        for template in cls.get_all_templates():
            if template.name == name:
                return template
        return None
    
    @classmethod
    def get_recommended_template(cls, category: TaskCategory, 
                                available_servers: List[str]) -> Optional[WorkflowTemplate]:
        """
        Get the best template for a category based on available servers.
        
        Args:
            category: Task category
            available_servers: List of available server names
            
        Returns:
            Best matching template or None
        """
        category_templates = cls.get_templates_by_category(category)
        if not category_templates:
            return None
        
        # Score templates based on server availability
        scored_templates = []
        
        for template in category_templates:
            score = 0
            total_required = len(template.required_servers)
            total_optional = len(template.optional_servers)
            
            # Required servers (high weight)
            required_available = len([s for s in template.required_servers if s in available_servers])
            if total_required > 0:
                score += (required_available / total_required) * 100
            else:
                score += 100  # No requirements = always available
            
            # Optional servers (low weight)
            optional_available = len([s for s in template.optional_servers if s in available_servers])
            if total_optional > 0:
                score += (optional_available / total_optional) * 20
            
            # Priority bonus
            score += template.priority * 0.1
            
            # Penalty if required servers are missing
            if required_available < total_required:
                score *= 0.5  # Heavy penalty
            
            scored_templates.append((template, score))
        
        # Return highest scoring template
        if scored_templates:
            best_template, _ = max(scored_templates, key=lambda x: x[1])
            return best_template
        
        return None
    
    @classmethod
    def create_custom_template(cls, name: str, description: str, category: TaskCategory,
                              required_servers: List[str], optional_servers: List[str],
                              priority: int = 50, auto_activate: bool = True,
                              notes: Optional[str] = None) -> WorkflowTemplate:
        """
        Create a custom workflow template.
        
        Args:
            name: Template name
            description: Template description
            category: Task category
            required_servers: Required server names
            optional_servers: Optional server names
            priority: Template priority (1-100)
            auto_activate: Whether to auto-activate
            notes: Additional notes
            
        Returns:
            Custom workflow template
        """
        return WorkflowTemplate(
            name=name,
            description=description,
            category=category,
            required_servers=required_servers,
            optional_servers=optional_servers,
            priority=priority,
            auto_activate=auto_activate,
            notes=notes
        )


class TemplateInstaller:
    """Installs workflow templates as actual workflows."""
    
    @staticmethod
    async def install_template(template: WorkflowTemplate, 
                              workflow_manager, suite_manager,
                              override_existing: bool = False) -> bool:
        """
        Install a template as a workflow.
        
        Args:
            template: Template to install
            workflow_manager: WorkflowManager instance
            suite_manager: SuiteManager instance  
            override_existing: Whether to override existing workflow
            
        Returns:
            True if installed successfully
        """
        try:
            logger.info(f"Installing workflow template '{template.name}'")
            
            # Check if workflow already exists
            if workflow_manager.get_workflow(template.name) and not override_existing:
                logger.warning(f"Workflow '{template.name}' already exists")
                return False
            
            # Create suite for the template
            suite_id = f"template-{template.name.lower().replace(' ', '-').replace('&', 'and')}"
            
            success = await suite_manager.create_or_update_suite(
                suite_id=suite_id,
                name=f"Suite: {template.name}",
                description=template.description,
                category=template.category.value
            )
            
            if not success:
                logger.error(f"Failed to create suite for template '{template.name}'")
                return False
            
            # Add required servers to suite (high priority)
            for server_name in template.required_servers:
                await suite_manager.add_server_to_suite(
                    suite_id, server_name, role="primary", priority=90
                )
            
            # Add optional servers to suite (lower priority)
            for server_name in template.optional_servers:
                await suite_manager.add_server_to_suite(
                    suite_id, server_name, role="optional", priority=70
                )
            
            # Create workflow
            success = await workflow_manager.create_workflow(
                name=template.name,
                description=template.description,
                suite_ids=[suite_id],
                category=template.category,
                auto_activate=template.auto_activate,
                priority=template.priority
            )
            
            if success:
                logger.info(f"Successfully installed workflow template '{template.name}'")
                return True
            else:
                logger.error(f"Failed to create workflow for template '{template.name}'")
                return False
                
        except Exception as e:
            logger.error(f"Failed to install template '{template.name}': {e}")
            return False
    
    @staticmethod
    async def install_all_templates(workflow_manager, suite_manager,
                                   available_servers: List[str],
                                   override_existing: bool = False) -> Dict[str, bool]:
        """
        Install all viable templates based on available servers.
        
        Args:
            workflow_manager: WorkflowManager instance
            suite_manager: SuiteManager instance
            available_servers: List of available server names
            override_existing: Whether to override existing workflows
            
        Returns:
            Dictionary mapping template names to installation success
        """
        results = {}
        available_set = set(available_servers)
        
        for template in ConfigTemplates.get_all_templates():
            # Check if required servers are available
            required_set = set(template.required_servers)
            if not required_set.issubset(available_set):
                missing = required_set - available_set
                logger.info(f"Skipping template '{template.name}' - missing required servers: {missing}")
                results[template.name] = False
                continue
            
            # Install template
            results[template.name] = await TemplateInstaller.install_template(
                template, workflow_manager, suite_manager, override_existing
            )
        
        successful = sum(1 for success in results.values() if success)
        logger.info(f"Template installation complete: {successful}/{len(results)} successful")
        
        return results