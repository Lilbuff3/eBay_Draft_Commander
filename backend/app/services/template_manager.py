"""
Listing Template Manager for eBay Draft Commander Pro
Now powered by SQLite database.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from backend.app.core.database import init_db, TemplateModel

class ListingTemplate:
    """Represents a saved listing template (Data Wrapper)"""
    def __init__(self, name: str, data: dict, created_at=None, updated_at=None, use_count=0):
        self.name = name
        self.data = data
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()
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
                db_t.updated_at = datetime.utcnow()
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
                
            # 1. Render Images (Grid)
            img_html = ""
            for img in images[:12]: # Max 12
                img_html += f'<div class="img-box"><img src="{img}" alt="{title}"></div>'
            
            # 2. Render Aspects (Table)
            aspects_html = '<table class="specs-table">'
            for k, v in aspects.items():
                val_str = ", ".join(v) if isinstance(v, list) else str(v)
                aspects_html += f'<tr><th>{k}</th><td>{val_str}</td></tr>'
            aspects_html += '</table>'
            
            # 3. Replace Token
            html = html.replace('{{TITLE}}', title)
            html = html.replace('{{DESCRIPTION}}', description)
            html = html.replace('{{IMAGES}}', img_html)
            html = html.replace('{{ASPECTS}}', aspects_html)
            html = html.replace('{{CONDITION}}', condition)
            
            return html
            
        except Exception as e:
            print(f"Template Render Error: {e}")
            return f"<h1>{title}</h1><p>{description}</p>"

def get_template_manager() -> TemplateManager:
    global _instance
    if '_instance' not in globals():
        _instance = TemplateManager()
    return _instance

# (DEFAULT_TEMPLATES logic would be handled by migration script or first-run check)
