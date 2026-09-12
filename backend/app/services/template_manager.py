"""
Listing Template Manager for eBay Draft Commander Pro
Now powered by SQLite database.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.core.database import init_db, TemplateModel
from backend.app.core.logger import get_logger

logger = get_logger('template_manager')

class ListingTemplate:
    """Represents a saved listing template (Data Wrapper)"""
    def __init__(self, name: str, data: dict, created_at=None, updated_at=None, use_count=0):
        self.name = name
        self.data = data
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()
        self.use_count = use_count
    
    def to_dict(self) -> dict:
        result = self.data.copy()
        result['_name'] = self.name
        result['_created_at'] = self.created_at
        result['_updated_at'] = self.updated_at
        result['_use_count'] = self.use_count
        return result

class TemplateManager:
    """Manages listing templates using SQLAlchemy"""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Assume standard data location
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "commander.db"
            
        self.SessionFactory = init_db(db_path)
        self.TemplateModel = TemplateModel
        self._templates: Dict[str, ListingTemplate] = {}
        self.load_all()
    
    def load_all(self) -> Dict[str, ListingTemplate]:
        """Load all templates from database"""
        session = self.SessionFactory()
        try:
            db_templates = session.query(self.TemplateModel).all()
            self._templates = {}
            for db_t in db_templates:
                template = ListingTemplate(
                    name=db_t.name,
                    data=db_t.data,
                    created_at=db_t.created_at.isoformat(),
                    updated_at=db_t.updated_at.isoformat(),
                    use_count=db_t.use_count
                )
                self._templates[template.name] = template
            return self._templates
        finally:
            session.close()
    
    def get_all(self) -> List[ListingTemplate]:
        """Get all templates sorted by use count"""
        return sorted(self._templates.values(), key=lambda t: t.use_count, reverse=True)
    
    def get(self, name: str) -> Optional[ListingTemplate]:
        return self._templates.get(name)
    
    def save(self, name: str, data: dict) -> ListingTemplate:
        """Save a new template or update existing in DB"""
        session = self.SessionFactory()
        try:
            db_t = session.query(self.TemplateModel).filter_by(name=name).first()
            if db_t:
                db_t.data = data
                db_t.updated_at = datetime.now(timezone.utc)
            else:
                db_t = self.TemplateModel(name=name)
                db_t.data = data
            
            session.add(db_t)
            session.commit()
            
            # Update cache
            template = ListingTemplate(
                name=db_t.name,
                data=db_t.data,
                created_at=db_t.created_at.isoformat(),
                updated_at=db_t.updated_at.isoformat(),
                use_count=db_t.use_count
            )
            self._templates[name] = template
            return template
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def delete(self, name: str) -> bool:
        session = self.SessionFactory()
        try:
            db_t = session.query(self.TemplateModel).filter_by(name=name).first()
            if db_t:
                session.delete(db_t)
                session.commit()
                if name in self._templates:
                    del self._templates[name]
                return True
            return False
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()
    
    def use(self, name: str) -> Optional[dict]:
        """Increment use count in DB and return data"""
        session = self.SessionFactory()
        try:
            db_t = session.query(self.TemplateModel).filter_by(name=name).first()
            if not db_t:
                return None
            
            db_t.use_count += 1
            session.commit()
            
            # Update cache
            if name in self._templates:
                self._templates[name].use_count = db_t.use_count
            
            # Return clean data
            return db_t.data
        finally:
            session.close()
    
    def get_names(self) -> List[str]:
        return [t.name for t in self.get_all()]

    def render_description(self, title: str, description: str, images: Optional[List[str]] = None, aspects: Optional[Dict[str, Any]] = None, condition: str = "") -> str:
        """
        Render clean, mobile-native 2026 description using semantic HTML (<p>, <b>, <ul>, <li>).
        Eliminates heavy HTML tables, inline style containers, and duplicate image embeds to ensure
        100% native editability in the official eBay mobile app.
        """
        try:
            desc_clean = (description or "").strip()
            cond_clean = (condition or "").strip()
            cond_html = f"<p><strong>Condition:</strong> {cond_clean}</p>" if cond_clean else ""

            template_path = Path(__file__).parent.parent.parent.parent / "templates" / "ebay_master.html"
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                
                # Replace tokens, omitting legacy image stacks and aspect tables
                html = html.replace('{{TITLE}}', title or '')
                html = html.replace('{{DESCRIPTION}}', desc_clean)
                html = html.replace('{{IMAGES}}', '')
                html = html.replace('{{ASPECTS}}', '')
                html = html.replace('{{CONDITION}}', cond_html)
                return html.strip()
            
            # Fallback when template file is absent
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

def get_template_manager() -> TemplateManager:
    global _instance
    if '_instance' not in globals():
        _instance = TemplateManager()
    return _instance

# (DEFAULT_TEMPLATES logic would be handled by migration script or first-run check)
