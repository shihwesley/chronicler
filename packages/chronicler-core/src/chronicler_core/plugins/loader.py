"""Dynamic plugin discovery and loading via entry points."""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

from chronicler_core.interfaces.graph import GraphPlugin
from chronicler_core.interfaces.queue import QueuePlugin
from chronicler_core.interfaces.rbac import RBACPlugin
from chronicler_core.interfaces.storage import StoragePlugin

if TYPE_CHECKING:
    from chronicler_core.config.models import ChroniclerConfig


class PluginNotFoundError(Exception):
    """Raised when a requested plugin cannot be found."""

    def __init__(self, plugin_type: str, name: str | None = None):
        self.plugin_type = plugin_type
        self.name = name
        msg = f"No {plugin_type} plugin found"
        if name:
            msg += f" with name '{name}'"
        super().__init__(msg)


class PluginLoader:
    """Discovers and loads plugins via entry points or config."""

    # Entry point group names
    GROUPS = {
        "queue": "chronicler.plugins.queue",
        "graph": "chronicler.plugins.graph",
        "rbac": "chronicler.plugins.rbac",
        "storage": "chronicler.plugins.storage",
    }

    # Lite defaults (lazy import paths)
    LITE_DEFAULTS = {
        "queue": ("chronicler_lite.queue.sqlite_queue", "SQLiteQueue"),
        "storage": ("chronicler_lite.storage.memvid_storage", "MemVidStorage"),
    }

    def __init__(self, config: ChroniclerConfig):
        self._config = config

    def discover(self) -> dict[str, list[str]]:
        """Scan entry_points for registered plugins. Returns {type: [name, ...]}."""
        result: dict[str, list[str]] = {}
        for plugin_type, group in self.GROUPS.items():
            eps = importlib.metadata.entry_points(group=group)
            result[plugin_type] = [ep.name for ep in eps]
        return result

    def _resolve_name(self, plugin_type: str, name: str | None) -> str | None:
        """Resolve plugin name: explicit arg > config > None."""
        if name is not None:
            return name
        return getattr(self._config.plugins, plugin_type, None)

    def _load_from_entry_point(self, plugin_type: str, name: str) -> object | None:
        """Try to load a specific named entry point."""
        group = self.GROUPS[plugin_type]
        eps = importlib.metadata.entry_points(group=group)
        for ep in eps:
            if ep.name == name:
                return ep.load()
        return None

    def _load_lite_default(self, plugin_type: str) -> object | None:
        """Try to import the Lite default for this plugin type."""
        if plugin_type not in self.LITE_DEFAULTS:
            return None
        module_path, class_name = self.LITE_DEFAULTS[plugin_type]
        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError):
            return None

    def _load_plugin(self, plugin_type: str, name: str | None) -> object | None:
        """Fallback chain: name/config > entry_points > Lite defaults."""
        resolved = self._resolve_name(plugin_type, name)
        if resolved is not None:
            result = self._load_from_entry_point(plugin_type, resolved)
            if result is not None:
                return result
            # Name was explicit but not found -- don't fallback silently
            raise PluginNotFoundError(plugin_type, resolved)

        # No explicit name -- try Lite defaults
        return self._load_lite_default(plugin_type)

    def load_queue(self, name: str | None = None) -> QueuePlugin:
        plugin_cls = self._load_plugin("queue", name)
        if plugin_cls is None:
            raise PluginNotFoundError("queue", name)
        return plugin_cls

    def load_graph(self, name: str | None = None) -> GraphPlugin:
        plugin_cls = self._load_plugin("graph", name)
        if plugin_cls is None:
            raise PluginNotFoundError("graph", name)
        return plugin_cls

    def load_storage(self, name: str | None = None) -> StoragePlugin:
        plugin_cls = self._load_plugin("storage", name)
        if plugin_cls is None:
            raise PluginNotFoundError("storage", name)
        return plugin_cls

    def load_rbac(self, name: str | None = None) -> RBACPlugin | None:
        """Load RBAC plugin. Returns None if not found (RBAC is optional)."""
        try:
            return self._load_plugin("rbac", name)
        except PluginNotFoundError:
            return None
