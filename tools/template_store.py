import json
import uuid
import threading
from pathlib import Path
from typing import List, Dict, Optional

class TemplateStore:
    """
    Manages listing templates with JSON persistence.
    """
    def __init__(self, data_dir: Path):
        self.file_path = data_dir / "templates.json"
        self._lock = threading.Lock()
        self._templates: List[Dict] = []
        self.load()
        
        # Initial seed if empty
        if not self._templates:
            self._seed_defaults()

    def load(self):
        with self._lock:
            if self.file_path.exists():
                try:
                    with open(self.file_path, 'r') as f:
                        self._templates = json.load(f)
                except Exception as e:
                    print(f"Error loading templates: {e}")
                    self._templates = []
            else:
                self._templates = []

    def save(self):
        with self._lock:
            try:
                with open(self.file_path, 'w') as f:
                    json.dump(self._templates, f, indent=2)
            except Exception as e:
                print(f"Error saving templates: {e}")

    def get_all(self) -> List[Dict]:
        return self._templates

    def add(self, template: Dict) -> Dict:
        if 'id' not in template:
            template['id'] = uuid.uuid4().hex[:8]
        
        # Ensure only one default if this is set to default
        if template.get('isDefault'):
            self._clear_defaults()
            
        self._templates.append(template)
        self.save()
        return template

    def update(self, template_id: str, updates: Dict) -> Optional[Dict]:
        for i, t in enumerate(self._templates):
            if t['id'] == template_id:
                # Handle default toggle
                if updates.get('isDefault') and not t.get('isDefault'):
                    self._clear_defaults()
                
                self._templates[i].update(updates)
                self.save()
                return self._templates[i]
        return None

    def delete(self, template_id: str) -> bool:
        initial_len = len(self._templates)
        self._templates = [t for t in self._templates if t['id'] != template_id]
        if len(self._templates) < initial_len:
            self.save()
            return True
        return False

    def _clear_defaults(self):
        for t in self._templates:
            t['isDefault'] = False

    def _seed_defaults(self):
        defaults = [
            {
                'id': '1', 'name': 'Industrial Electronics', 'category': 'Electronics',
                'description': 'For sensors, controllers, and industrial components',
                'fields': {'condition': 'Used', 'returns': '30 days', 'shipping': 'USPS Priority'},
                'isDefault': True, 'isFavorite': True, 'usageCount': 0
            },
            {
                'id': '2', 'name': 'Vintage Computer Parts', 'category': 'Computers',
                'description': 'Retro computing hardware and peripherals',
                'fields': {'condition': 'For Parts', 'returns': 'No Returns', 'shipping': 'Calculated'},
                'isDefault': False, 'isFavorite': True, 'usageCount': 0
            }
        ]
        self._templates = defaults
        self.save()
