#!/usr/bin/env python3
"""
Theme Manager Module for MDviewer

Centralized theme registry and management system for both UI and content themes.
Provides extensible architecture for adding new themes with proper validation.

Author: MDviewer Project
v1.0.0
Created: 2026-01-30
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import QSettings


@dataclass
class ThemeColors:
    """Data class for content theme colors"""

    heading_color: str = "#58a6ff"
    body_text_color: str = "#c9d1d9"
    background_color: str = "#0d1117"
    link_color: str = "#58a6ff"
    blockquote_color: str = "#8b949e"
    code_bg_color: str = "#161b22"
    border_color: str = "#30363d"


@dataclass
class UIPalette:
    """Data class for UI theme palette colors"""

    window_color: str = "#2d2d2d"
    window_text_color: str = "#bbbbbb"
    base_color: str = "#1e1e1e"
    alternate_base_color: str = "#2d2d2d"
    text_color: str = "#bbbbbb"
    button_color: str = "#2d2d2d"
    button_text_color: str = "#bbbbbb"
    highlight_color: str = "#ffd700"
    highlighted_text_color: str = "#000000"


@dataclass
class Theme:
    """Complete theme definition including UI and content components"""

    name: str
    display_name: str
    content_colors: ThemeColors
    ui_palette: UIPalette
    description: str = ""
    is_built_in: bool = True
    category: str = "Custom"  # Built-in, Popular, Custom


class ThemeRegistry:
    """Centralized theme registry with validation and discovery"""

    def __init__(self):
        self._themes: Dict[str, Theme] = {}
        self._initialize_builtin_themes()

    def _initialize_builtin_themes(self):
        """Initialize built-in themes"""

        # Dark Theme
        self.register_theme(
            Theme(
                name="dark",
                display_name="Dark",
                content_colors=ThemeColors(
                    heading_color="#58a6ff",
                    body_text_color="#c9d1d9",
                    background_color="#0d1117",
                    link_color="#58a6ff",
                    blockquote_color="#8b949e",
                    code_bg_color="#161b22",
                    border_color="#30363d",
                ),
                ui_palette=UIPalette(
                    window_color="#2d2d2d",
                    window_text_color="#bbbbbb",
                    base_color="#1e1e1e",
                    alternate_base_color="#2d2d2d",
                    text_color="#bbbbbb",
                    button_color="#2d2d2d",
                    button_text_color="#bbbbbb",
                    highlight_color="#ffd700",
                    highlighted_text_color="#000000",
                ),
                description="Dark theme with GitHub-inspired colors",
                category="Built-in",
            )
        )

        # Light Theme
        self.register_theme(
            Theme(
                name="light",
                display_name="Light",
                content_colors=ThemeColors(
                    heading_color="#0366d8",
                    body_text_color="#24292e",
                    background_color="#ffffff",
                    link_color="#0366d8",
                    blockquote_color="#6a737d",
                    code_bg_color="#f6f8fa",
                    border_color="#e1e4e8",
                ),
                ui_palette=UIPalette(
                    window_color="#f0f0f0",
                    window_text_color="#000000",
                    base_color="#ffffff",
                    alternate_base_color="#f5f5f5",
                    text_color="#000000",
                    button_color="#f0f0f0",
                    button_text_color="#000000",
                    highlight_color="#0366d8",
                    highlighted_text_color="#ffffff",
                ),
                description="Light theme with GitHub-inspired colors",
                category="Built-in",
            )
        )

        # Solarized Light Theme
        self.register_theme(
            Theme(
                name="solarized_light",
                display_name="Solarized Light",
                content_colors=ThemeColors(
                    heading_color="#586e75",
                    body_text_color="#657b83",
                    background_color="#fdf6e3",
                    link_color="#268bd2",
                    blockquote_color="#93a1a1",
                    code_bg_color="#eee8d5",
                    border_color="#93a1a1",
                ),
                ui_palette=UIPalette(
                    window_color="#fdf6e3",
                    window_text_color="#657b83",
                    base_color="#ffffff",
                    alternate_base_color="#f5f5dc",
                    text_color="#657b83",
                    button_color="#eee8d5",
                    button_text_color="#657b83",
                    highlight_color="#268bd2",
                    highlighted_text_color="#ffffff",
                ),
                description="Solarized light theme for comfortable reading",
                category="Popular",
            )
        )

        # Dracula Theme
        self.register_theme(
            Theme(
                name="dracula",
                display_name="Dracula",
                content_colors=ThemeColors(
                    heading_color="#f8f8f2",
                    body_text_color="#e2e2e2",
                    background_color="#282a36",
                    link_color="#8be9fd",
                    blockquote_color="#6272a4",
                    code_bg_color="#44475a",
                    border_color="#6272a4",
                ),
                ui_palette=UIPalette(
                    window_color="#282a36",
                    window_text_color="#f8f8f2",
                    base_color="#1e1f29",
                    alternate_base_color="#44475a",
                    text_color="#f8f8f2",
                    button_color="#44475a",
                    button_text_color="#f8f8f2",
                    highlight_color="#8be9fd",
                    highlighted_text_color="#282a36",
                ),
                description="Popular Dracula theme with vibrant colors",
                category="Popular",
            )
        )

        # GitHub Theme
        self.register_theme(
            Theme(
                name="github",
                display_name="GitHub",
                content_colors=ThemeColors(
                    heading_color="#24292f",
                    body_text_color="#24292f",
                    background_color="#ffffff",
                    link_color="#0969da",
                    blockquote_color="#57606a",
                    code_bg_color="#f6f8fa",
                    border_color="#d0d7de",
                ),
                ui_palette=UIPalette(
                    window_color="#ffffff",
                    window_text_color="#24292f",
                    base_color="#f6f8fa",
                    alternate_base_color="#ffffff",
                    text_color="#24292f",
                    button_color="#f6f8fa",
                    button_text_color="#24292f",
                    highlight_color="#0969da",
                    highlighted_text_color="#ffffff",
                ),
                description="Official GitHub theme colors",
                category="Popular",
            )
        )

    def register_theme(self, theme: Theme) -> bool:
        """Register a new theme"""
        if not self._validate_theme(theme):
            return False

        self._themes[theme.name] = theme
        return True

    def _validate_theme(self, theme: Theme) -> bool:
        """Validate theme definition"""

        # Check color format (hex codes)
        def validate_color(color: str) -> bool:
            return bool(re.match(r"^#[0-9A-Fa-f]{6}$", color))

        import re

        # Validate content colors
        for color_value in theme.content_colors.__dict__.values():
            if not validate_color(color_value):
                return False

        # Validate UI palette colors
        for color_value in theme.ui_palette.__dict__.values():
            if not validate_color(color_value):
                return False

        return True

    def get_theme(self, name: str) -> Optional[Theme]:
        """Get theme by name"""
        return self._themes.get(name)

    def get_all_themes(self) -> Dict[str, Theme]:
        """Get all registered themes"""
        return self._themes.copy()

    def get_theme_names(self) -> List[str]:
        """Get list of theme names"""
        return list(self._themes.keys())

    def get_themes_by_category(self, category: str) -> List[Theme]:
        """Get themes filtered by category"""
        return [theme for theme in self._themes.values() if theme.category == category]

    def remove_theme(self, name: str) -> bool:
        """Remove a theme (only non-built-in themes)"""
        theme = self._themes.get(name)
        if theme and not theme.is_built_in:
            del self._themes[name]
            return True
        return False


# Global theme registry instance
_theme_registry = None


def get_theme_registry() -> ThemeRegistry:
    """Get the global theme registry instance"""
    global _theme_registry
    if _theme_registry is None:
        _theme_registry = ThemeRegistry()
    return _theme_registry


def get_fusion_palette(theme_name: str) -> QPalette:
    """Get Qt Fusion palette for theme"""
    registry = get_theme_registry()
    theme = registry.get_theme(theme_name)

    if not theme:
        # Fallback to dark theme
        theme = registry.get_theme("dark")

    palette = QPalette()
    ui_colors = theme.ui_palette

    # Window colors
    palette.setColor(QPalette.ColorRole.Window, QColor(ui_colors.window_color))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(ui_colors.window_text_color))

    # Base colors (text input areas)
    palette.setColor(QPalette.ColorRole.Base, QColor(ui_colors.base_color))
    palette.setColor(
        QPalette.ColorRole.AlternateBase, QColor(ui_colors.alternate_base_color)
    )

    # Text colors
    palette.setColor(QPalette.ColorRole.Text, QColor(ui_colors.text_color))

    # Button colors
    palette.setColor(QPalette.ColorRole.Button, QColor(ui_colors.button_color))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(ui_colors.button_text_color))

    # Highlight colors
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ui_colors.highlight_color))
    palette.setColor(
        QPalette.ColorRole.HighlightedText, QColor(ui_colors.highlighted_text_color)
    )

    return palette


def get_search_css(theme_name: str) -> str:
    """Get CSS for search highlighting based on theme"""
    registry = get_theme_registry()
    theme = registry.get_theme(theme_name)

    if not theme:
        theme = registry.get_theme("dark")

    highlight_color = theme.ui_palette.highlight_color
    highlighted_text_color = theme.ui_palette.highlighted_text_color

    # Create complementary colors for other matches
    return f"""
        QTextBrowser {{
            selection-background-color: {highlight_color} !important;
            selection-color: {highlighted_text_color} !important;
            font-weight: bold !important;
            border-radius: 2px !important;
        }}
        .search-current {{
            background-color: {highlight_color} !important;
            color: {highlighted_text_color} !important;
            font-weight: bold !important;
        }}
        .search-other {{
            background-color: #ff8c00 !important;
            color: #000000 !important;
        }}
    """


# Backward compatibility - expose existing constants
DEFAULT_THEME_COLORS = {
    "dark": get_theme_registry().get_theme("dark").content_colors.__dict__,
    "light": get_theme_registry().get_theme("light").content_colors.__dict__,
}
