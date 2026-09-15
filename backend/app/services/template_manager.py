"""
Listing Template Manager for eBay Draft Commander Pro.

Renders the final eBay HTML description from templates/ebay_master.html.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.app.core.logger import get_logger

logger = get_logger('template_manager')


class TemplateManager:
    """Renders listing descriptions from the master HTML template."""

    def render_description(self, title: str, description: str,
                           images: Optional[List[str]] = None,
                           aspects: Optional[Dict[str, Any]] = None,
                           condition: str = "") -> str:
        """
        Render a clean, mobile-native description using semantic HTML.

        No tables, no inline-styled container divs, no embedded image stack:
        eBay already renders the photo gallery and the Item Specifics panel
        itself, so repeating them here only produced a description the seller
        could not edit in the native eBay mobile app.

        images/aspects are accepted and ignored — kept in the signature so
        callers (processor_service._render_listing_template) stay unchanged.
        """
        try:
            desc_clean = (description or "").strip()
            cond_clean = (condition or "").strip()
            cond_html = f"<p><strong>Condition:</strong> {cond_clean}</p>" if cond_clean else ""

            template_path = Path(__file__).parent.parent.parent.parent / "templates" / "ebay_master.html"
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                # The template carries a bare {{CONDITION}}; cond_html supplies
                # the whole <p> so an empty condition leaves no dangling label.
                html = html.replace('{{TITLE}}', title or '')
                html = html.replace('{{DESCRIPTION}}', desc_clean)
                html = html.replace('{{IMAGES}}', '')
                html = html.replace('{{ASPECTS}}', '')
                html = html.replace('{{CONDITION}}', cond_html)
                return html.strip()

            # Fallback when the template file is missing.
            parts = []
            if title:
                parts.append(f"<p><strong>{title}</strong></p>")
            if desc_clean:
                parts.append(desc_clean)
            if cond_html:
                parts.append(cond_html)
            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"Template Render Error: {e}")
            return f"<p><strong>{title}</strong></p>\n<p>{description}</p>"


_instance = None


def get_template_manager() -> TemplateManager:
    global _instance
    if _instance is None:
        _instance = TemplateManager()
    return _instance
