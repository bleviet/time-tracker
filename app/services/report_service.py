"""
Report Generation Service using Jinja2 templates.

Architecture Decision: Template Pattern
Allows users to customize reports without changing code.
"""

import datetime
from pathlib import Path
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader

from app.infra.repository import TaskRepository, TimeEntryRepository, UserRepository, AccountingRepository
from app.utils import get_resource_path


class ReportService:
    """
    Generates reports from time tracking data using Jinja2 templates.
    """
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the report service.
        
        Args:
            template_dir: Directory containing Jinja2 templates
        """
        if template_dir is None:
            template_dir = get_resource_path("app/resources/templates")
        
        self.template_dir = template_dir
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['format_duration'] = self._format_duration
        self.env.filters['format_date'] = self._format_date
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format seconds as HH:MM:SS"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def _format_date(dt: datetime.datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format datetime object"""
        return dt.strftime(fmt)
    
    async def generate_report(self, template_name: str, 
                             start_date: datetime.datetime,
                             end_date: datetime.datetime,
                             output_file: Optional[Path] = None) -> str:
        """
        Generate a report for a date range.
        
        Args:
            template_name: Name of the template file (e.g., 'monthly_report.txt')
            start_date: Start of reporting period
            end_date: End of reporting period
            output_file: Optional file path to save the report
            
        Returns:
            The generated report as a string
        """
        # Fetch data
        task_repo = TaskRepository()
        entry_repo = TimeEntryRepository()
        user_repo = UserRepository()
        acc_repo = AccountingRepository()
        
        tasks = await task_repo.get_all_active()
        prefs = await user_repo.get_preferences()
        accounting_profiles = await acc_repo.get_all_active()
        acc_map = {acc.id: acc for acc in accounting_profiles}
        
        # Aggregate data by task
        report_data = []
        total_seconds = 0
        
        for task in tasks:
            entries = await entry_repo.get_by_task(
                task.id, 
                start_date=start_date, 
                end_date=end_date
            )
            
            task_seconds = sum(e.duration_seconds for e in entries)
            total_seconds += task_seconds
            
            # Get Accounting Info
            acc_name = ""
            acc_attrs = {}
            if task.accounting_id in acc_map:
                acc = acc_map[task.accounting_id]
                acc_name = acc.name
                acc_attrs = acc.attributes
            
            if task_seconds > 0:  # Only include tasks with time
                report_data.append({
                    'task': task,
                    'entries': entries,
                    'total_seconds': task_seconds,
                    'total_hours': task_seconds / 3600,
                    'accounting_name': acc_name,
                    'accounting_attributes': acc_attrs
                })
        
        # Prepare template context
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'tasks': report_data,
            'total_seconds': total_seconds,
            'total_hours': total_seconds / 3600,
            'generated_at': datetime.datetime.now(),
            'accounting_columns': prefs.accounting_columns
        }
        
        # Render template
        template = self.env.get_template(template_name)
        report_content = template.render(**context)
        
        # Save to file if specified
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
        
        return report_content
    
    def render_template_string(self, template_string: str, **context) -> str:
        """
        Render a template from a string instead of a file.
        
        Args:
            template_string: The template content as a string
            **context: Variables to pass to the template
            
        Returns:
            The rendered content
        """
        template = self.env.from_string(template_string)
        return template.render(**context)
    
    def list_templates(self) -> List[str]:
        """List all available template files"""
        return [f.name for f in self.template_dir.glob("*.txt")] + \
               [f.name for f in self.template_dir.glob("*.md")] + \
               [f.name for f in self.template_dir.glob("*.html")]
