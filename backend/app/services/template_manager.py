"""
Listing Template Manager for eBay Draft Commander Pro.

Renders the final eBay HTML description from templates/ebay_master.html.
"""
from pathlib import Path
from typing import List, Dict
from backend.app.core.logger import get_logger

logger = get_logger('template_manager')


class TemplateManager:
    """Renders listing descriptions from the master HTML template."""

    def render_description(self, title: str, description: str, images: List[str], aspects: Dict[str, List[str]], condition: str) -> str:
        """
        Render the final HTML description using templates/ebay_master.html.
        """
        try:
            # Locate the master template
            template_path = Path(__file__).parent.parent.parent.parent / "templates" / "ebay_master.html"
            if not template_path.exists():
                return f"<h1>{title}</h1><p>{description}</p>" # Fallback
                
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
                
            # 1. Render Images (inline-styled, stacked for mobile)
            img_html = ""
            for img in images[:12]:  # Max 12
                img_html += (
                    f'<div style="text-align: center; margin-bottom: 12px;">'
                    f'<img src="{img}" alt="{title}" style="max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 6px;">'
                    f'</div>'
                )

            # 2. Render Aspects (inline-styled table — works on eBay mobile)
            aspects_html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">'
            for k, v in aspects.items():
                val_str = ", ".join(v) if isinstance(v, list) else str(v)
                aspects_html += (
                    f'<tr style="border-bottom: 1px solid #f0f0f0;">'
                    f'<th style="text-align: left; padding: 10px 8px; width: 40%; color: #666; font-weight: 500; background: #fdfdfd;">{k}</th>'
                    f'<td style="padding: 10px 8px; font-weight: 600;">{val_str}</td>'
                    f'</tr>'
                )
            aspects_html += '</table>'
            
            # 3. Replace Token
            html = html.replace('{{TITLE}}', title)
            html = html.replace('{{DESCRIPTION}}', description)
            html = html.replace('{{IMAGES}}', img_html)
            html = html.replace('{{ASPECTS}}', aspects_html)
            html = html.replace('{{CONDITION}}', condition)
            
            return html
            
        except Exception as e:
            logger.error(f"Template Render Error: {e}")
            return f"<h1>{title}</h1><p>{description}</p>"


_instance = None


def get_template_manager() -> TemplateManager:
    global _instance
    if _instance is None:
        _instance = TemplateManager()
    return _instance
