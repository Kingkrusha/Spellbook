"""
Base data model and manager classes for D&D 5e Spellbook Application.
Provides common functionality to reduce code duplication.
"""

from dataclasses import dataclass, field, asdict
from typing import TypeVar, Type, Generic, List, Optional, Dict, Any, Callable
import json
import os
import sys

T = TypeVar('T', bound='BaseModel')


def get_data_path(filename: str) -> str:
    """Get the path to a data file, handling PyInstaller bundling."""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


@dataclass
class BaseModel:
    """Base class for all D&D content data models with common fields."""
    name: str
    description: str = ""
    source: str = ""
    is_official: bool = True
    is_custom: bool = False
    is_legacy: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary. Override for custom serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls: Type[T], data: dict) -> T:
        """Create instance from dictionary. Override for custom deserialization."""
        # Get valid field names for this class
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        
        # Filter data to only include valid fields
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)


class BaseDataManager(Generic[T]):
    """
    Base class for all data managers with common CRUD operations.
    
    Subclasses should:
    1. Set data_key class attribute (e.g., "lineages", "feats")
    2. Set model_class class attribute (e.g., Lineage, Feat)
    3. Set default_file class attribute (e.g., "lineages.json")
    4. Call super().__init__() in __init__
    """
    
    data_key: str = "items"  # Override in subclass
    model_class: Optional[Type[T]] = None  # Override in subclass
    default_file: str = "data.json"  # Override in subclass
    
    def __init__(self, file_path: Optional[str] = None):
        self._items: List[T] = []
        self._file_path = file_path or get_data_path(self.default_file)
        self._listeners: List[Callable[[], None]] = []
    
    @property
    def items(self) -> List[T]:
        """Get all items."""
        return self._items.copy()
    
    def add_listener(self, callback: Callable[[], None]):
        """Add a listener to be notified when data changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[], None]):
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of data changes."""
        for listener in self._listeners:
            try:
                listener()
            except Exception as e:
                print(f"Error notifying listener: {e}")
    
    def load(self) -> bool:
        """Load items from file."""
        if not os.path.exists(self._file_path):
            self._items = []
            return True
        
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._items = []
            items_data = data.get(self.data_key, [])
            
            for item_data in items_data:
                try:
                    if self.model_class:
                        item = self.model_class.from_dict(item_data)
                        self._items.append(item)
                except Exception as e:
                    print(f"Error loading {self.data_key} item: {e}")
            
            return True
        except Exception as e:
            print(f"Error loading {self.data_key}: {e}")
            self._items = []
            return False
    
    def save(self) -> bool:
        """Save items to file."""
        try:
            data = {
                self.data_key: [item.to_dict() for item in self._items]
            }
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving {self.data_key}: {e}")
            return False
    
    def get(self, name: str) -> Optional[T]:
        """Get an item by name."""
        for item in self._items:
            if item.name.lower() == name.lower():
                return item
        return None
    
    def get_names(self) -> List[str]:
        """Get sorted list of all item names."""
        return sorted([item.name for item in self._items])
    
    def add(self, item: T, save: bool = True) -> bool:
        """Add a new item. Returns False if item with same name exists."""
        if self.get(item.name):
            return False
        
        self._items.append(item)
        if save:
            self.save()
        self._notify_listeners()
        return True
    
    def update(self, name: str, updated_item: T, save: bool = True) -> bool:
        """Update an existing item."""
        for i, item in enumerate(self._items):
            if item.name.lower() == name.lower():
                self._items[i] = updated_item
                if save:
                    self.save()
                self._notify_listeners()
                return True
        return False
    
    def remove(self, name: str, save: bool = True) -> bool:
        """Remove an item by name."""
        for i, item in enumerate(self._items):
            if item.name.lower() == name.lower():
                del self._items[i]
                if save:
                    self.save()
                self._notify_listeners()
                return True
        return False
    
    def get_all_sources(self) -> List[str]:
        """Get sorted list of all unique sources."""
        sources = set()
        for item in self._items:
            if item.source:
                sources.add(item.source)
        return sorted(sources)
    
    def get_official(self) -> List[T]:
        """Get all official items."""
        return [item for item in self._items if item.is_official]
    
    def get_unofficial(self) -> List[T]:
        """Get all unofficial/custom items."""
        return [item for item in self._items if not item.is_official or item.is_custom]
    
    def get_custom(self) -> List[T]:
        """Get all custom items."""
        return [item for item in self._items if item.is_custom]
    
    def get_legacy(self) -> List[T]:
        """Get all legacy items."""
        return [item for item in self._items if item.is_legacy]
    
    def filter_by_source(self, source: str) -> List[T]:
        """Get all items from a specific source."""
        return [item for item in self._items if item.source == source]
    
    def export_to_json(self, file_path: str, items: Optional[List[T]] = None) -> int:
        """Export items to a JSON file. Returns count of exported items."""
        items_to_export = items if items is not None else self._items
        
        try:
            data = {
                self.data_key: [item.to_dict() for item in items_to_export]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return len(items_to_export)
        except Exception as e:
            print(f"Error exporting {self.data_key}: {e}")
            return 0
    
    def import_from_json(self, file_path: str, mark_as_custom: bool = True) -> int:
        """Import items from a JSON file. Returns count of imported items."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            count = 0
            items_data = data.get(self.data_key, [])
            
            for item_data in items_data:
                try:
                    if self.model_class:
                        item = self.model_class.from_dict(item_data)
                        if mark_as_custom:
                            item.is_custom = True
                            item.is_official = False
                        
                        if self.add(item, save=False):
                            count += 1
                except Exception as e:
                    print(f"Error importing item: {e}")
            
            if count > 0:
                self.save()
            
            return count
        except Exception as e:
            print(f"Error importing {self.data_key}: {e}")
            return 0
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[T]:
        """Search items by query string in specified fields (default: name, description)."""
        if not query:
            return self._items.copy()
        
        query_lower = query.lower()
        fields = fields or ['name', 'description']
        results = []
        
        for item in self._items:
            for field_name in fields:
                value = getattr(item, field_name, None)
                if value and query_lower in str(value).lower():
                    results.append(item)
                    break
        
        return results


def create_singleton_getter(manager_class: Type[BaseDataManager]):
    """
    Factory function to create a singleton getter for a manager class.
    
    Usage:
        get_feat_manager = create_singleton_getter(FeatManager)
    """
    _instance: Optional[BaseDataManager] = None
    
    def get_instance() -> BaseDataManager:
        nonlocal _instance
        if _instance is None:
            _instance = manager_class()
            _instance.load()
        return _instance
    
    return get_instance
