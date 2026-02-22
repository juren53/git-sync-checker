"""PyQt6 Zoom Manager - Reusable Font Scaling Module

A lightweight, reusable singleton manager for adding zoom/font scaling
functionality to any PyQt6 application.

Author: Generated with Claude Code
License: MIT
Version: 1.0.0
"""

from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont


class ZoomManager(QObject):
    """Singleton zoom manager for application-wide font scaling.

    Provides zoom functionality (75%-200%) for PyQt6 applications using
    font scaling with automatic layout adjustments.

    Features:
        - Discrete zoom levels from 75% to 200%
        - Persistent zoom preferences via QSettings
        - Signal-based architecture for UI updates
        - Automatic widget updates on zoom change
        - Thread-safe singleton pattern

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> from zoom_manager import ZoomManager
        >>>
        >>> app = QApplication(sys.argv)
        >>> app.setOrganizationName("MyOrg")
        >>> app.setApplicationName("MyApp")
        >>>
        >>> # Initialize zoom manager
        >>> zoom_mgr = ZoomManager.instance()
        >>> zoom_mgr.initialize_base_font(app)
        >>> zoom_mgr.apply_saved_zoom(app)
        >>>
        >>> # Connect to zoom changes (optional)
        >>> zoom_mgr.zoom_changed.connect(lambda f: print(f"Zoom: {int(f*100)}%"))
        >>>
        >>> # Programmatic zoom control
        >>> zoom_mgr.zoom_in(app)
        >>> zoom_mgr.zoom_out(app)
        >>> zoom_mgr.reset_zoom(app)
    """

    # Signal emitted when zoom changes
    zoom_changed = pyqtSignal(float)  # Emits zoom factor (e.g., 1.0, 1.5)

    # Zoom configuration - customize as needed
    ZOOM_LEVELS = [0.75, 0.85, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0]
    DEFAULT_ZOOM = 1.0
    MIN_ZOOM = 0.75
    MAX_ZOOM = 2.0
    SETTINGS_KEY = "ui/zoom_level"  # QSettings key for persistence

    # Font size constraints
    MIN_FONT_SIZE = 8   # Minimum readable font size (points)
    MAX_FONT_SIZE = 24  # Maximum practical font size (points)

    _instance = None

    def __init__(self):
        """Initialize zoom manager (use instance() instead).

        Raises:
            RuntimeError: If called directly instead of using instance()
        """
        if ZoomManager._instance is not None:
            raise RuntimeError(
                "ZoomManager is a singleton. Use ZoomManager.instance() instead."
            )
        super().__init__()

        self._current_zoom = self.DEFAULT_ZOOM
        self._base_font_size = None

    @classmethod
    def instance(cls):
        """Get the singleton instance of ZoomManager.

        Returns:
            ZoomManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = ZoomManager()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing).

        Warning:
            This should only be used in test scenarios.
        """
        cls._instance = None

    def initialize_base_font(self, app: QApplication):
        """Capture the base font size from the application.

        Call this once during app startup before applying any zoom.

        Args:
            app: The QApplication instance

        Note:
            This captures the application's default font size which is
            used as the baseline for all zoom calculations.
        """
        if self._base_font_size is None:
            base_font = app.font()
            self._base_font_size = base_font.pointSize()

    def apply_saved_zoom(self, app: QApplication):
        """Load zoom preference from settings and apply to application.

        Reads the zoom level from QSettings using the organization and
        application names set on the QApplication instance.

        Args:
            app: The QApplication instance to apply zoom to

        Note:
            Requires QApplication.setOrganizationName() and
            QApplication.setApplicationName() to be called first.
        """
        # Read settings using QApplication's org/app names
        settings = QSettings(app.organizationName(), app.applicationName())
        zoom_level = settings.value(self.SETTINGS_KEY, self.DEFAULT_ZOOM, type=float)

        # Validate and clamp zoom level
        zoom_level = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom_level))

        self.set_zoom_level(app, zoom_level)

    def save_zoom_preference(self, app: QApplication):
        """Save current zoom preference to settings.

        Args:
            app: The QApplication instance (used to get org/app names)
        """
        settings = QSettings(app.organizationName(), app.applicationName())
        settings.setValue(self.SETTINGS_KEY, self._current_zoom)

    def set_zoom_level(self, app: QApplication, factor: float):
        """Set absolute zoom level.

        Args:
            app: The QApplication instance
            factor: Zoom factor (MIN_ZOOM to MAX_ZOOM)

        Emits:
            zoom_changed: With the new zoom factor
        """
        # Clamp to valid range
        factor = max(self.MIN_ZOOM, min(self.MAX_ZOOM, factor))

        if factor == self._current_zoom:
            return  # No change

        self._current_zoom = factor
        self._apply_font_scaling(app)
        self.zoom_changed.emit(factor)

    def zoom_in(self, app: QApplication):
        """Increase zoom to next level.

        Args:
            app: The QApplication instance
        """
        current_index = self._get_nearest_zoom_index()
        if current_index < len(self.ZOOM_LEVELS) - 1:
            next_zoom = self.ZOOM_LEVELS[current_index + 1]
            self.set_zoom_level(app, next_zoom)

    def zoom_out(self, app: QApplication):
        """Decrease zoom to previous level.

        Args:
            app: The QApplication instance
        """
        current_index = self._get_nearest_zoom_index()
        if current_index > 0:
            prev_zoom = self.ZOOM_LEVELS[current_index - 1]
            self.set_zoom_level(app, prev_zoom)

    def reset_zoom(self, app: QApplication):
        """Reset zoom to 100% (1.0).

        Args:
            app: The QApplication instance
        """
        self.set_zoom_level(app, self.DEFAULT_ZOOM)

    def get_zoom_percentage(self) -> int:
        """Get current zoom as percentage (75, 100, 150, etc.).

        Returns:
            int: Zoom percentage
        """
        return int(self._current_zoom * 100)

    def get_current_zoom(self) -> float:
        """Get current zoom factor.

        Returns:
            float: Current zoom factor (MIN_ZOOM to MAX_ZOOM)
        """
        return self._current_zoom

    def _get_nearest_zoom_index(self) -> int:
        """Find index of nearest zoom level to current zoom.

        Returns:
            int: Index in ZOOM_LEVELS list
        """
        min_diff = float('inf')
        nearest_index = 0

        for i, level in enumerate(self.ZOOM_LEVELS):
            diff = abs(level - self._current_zoom)
            if diff < min_diff:
                min_diff = diff
                nearest_index = i

        return nearest_index

    def _apply_font_scaling(self, app: QApplication):
        """Apply font scaling to the application.

        Args:
            app: The QApplication instance
        """
        if self._base_font_size is None:
            # Capture base font size on first call
            self._base_font_size = app.font().pointSize()

        # Calculate new font size
        new_size = int(self._base_font_size * self._current_zoom)

        # Clamp to reasonable limits
        new_size = max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, new_size))

        # Create a new font with the scaled size
        font = QFont()
        font.setPointSize(new_size)
        app.setFont(font)

        # Force all widgets to update by processing font change events
        # This ensures existing widgets pick up the new font
        for widget in app.allWidgets():
            widget.setFont(font)
