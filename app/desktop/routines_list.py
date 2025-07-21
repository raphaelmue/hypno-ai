import logging
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView
)

from app.config import LANGUAGES, OUTPUT_FOLDER
from app.models.routine import list_routines, delete_routine, get_routine


class RoutinesListWidget(QWidget):
    """Widget for displaying and managing the list of routines"""

    # Define signals
    new_routine_requested = pyqtSignal()
    edit_routine_requested = pyqtSignal(str)  # routine_id
    routine_selected = pyqtSignal(str)  # routine_id

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing RoutinesListWidget")

        # Set up the layout
        self.layout = QVBoxLayout(self)

        # Create the button bar
        self.setup_button_bar()

        # Create the routines table
        self.setup_routines_table()

        # Load routines
        self.refresh()

        self.logger.info("RoutinesListWidget initialized")

    def setup_button_bar(self):
        """Set up the button bar at the top of the widget"""
        button_layout = QHBoxLayout()

        # Add spacer to push button to the right
        button_layout.addStretch()

        # Add the button layout to the main layout
        self.layout.addLayout(button_layout)

    def setup_routines_table(self):
        """Set up the table for displaying routines"""
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Language", "Created"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMouseTracking(True)
        self.table.clicked.connect(self.on_table_clicked)

        # Connect selection change signal
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        # Store routine IDs for each row
        self.routine_ids = []

        self.layout.addWidget(self.table)

    def refresh(self):
        """Refresh the routines list"""
        self.logger.info("Refreshing routines list")

        # Get all routines
        routines = list_routines()

        # Clear the table and routine IDs
        self.table.setRowCount(0)
        self.routine_ids = []

        if not routines:
            self.logger.info("No routines found")
            # Add a single row with a message
            self.table.setRowCount(1)
            no_routines_item = QTableWidgetItem("No saved routines yet. Click 'Create New Routine' to get started.")
            no_routines_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setSpan(0, 0, 1, 3)  # Span all columns
            self.table.setItem(0, 0, no_routines_item)
            return

        # Add routines to the table
        self.table.setRowCount(len(routines))

        for row, (routine_id, routine) in enumerate(routines.items()):
            # Store the routine ID for this row
            self.routine_ids.append(routine_id)
            # Name
            name_item = QTableWidgetItem(routine.get('name', 'Unnamed'))
            self.table.setItem(row, 0, name_item)

            # Language
            language_code = routine.get('language', 'en')
            language_name = LANGUAGES.get(language_code, language_code)
            language_item = QTableWidgetItem(language_name)
            self.table.setItem(row, 1, language_item)

            # Created date
            created_at = routine.get('created_at', '').split('T')[0]
            created_item = QTableWidgetItem(created_at)
            self.table.setItem(row, 2, created_item)

        self.logger.info(f"Loaded {len(routines)} routines into table")

    def on_new_clicked(self):
        """Handle click on the New Routine button"""
        self.logger.info("New routine button clicked")
        self.new_routine_requested.emit()


    def on_selection_changed(self):
        """Handle selection change in the routines table"""
        selected_rows = self.table.selectionModel().selectedRows()
        self.logger.debug(f"Selection changed: {len(selected_rows)} rows selected, {len(self.routine_ids)} routine IDs available")

        if selected_rows and len(self.routine_ids) > 0:
            row = selected_rows[0].row()
            self.logger.debug(f"Selected row index: {row}")

            if 0 <= row < len(self.routine_ids):
                routine_id = self.routine_ids[row]
                self.logger.info(f"Routine selected: {routine_id}")
                self.routine_selected.emit(routine_id)
            else:
                self.logger.warning(f"Invalid row index: {row}, routine_ids length: {len(self.routine_ids)}")
        elif not selected_rows:
            self.logger.debug("No rows selected")
        elif len(self.routine_ids) == 0:
            self.logger.debug("No routine IDs available")

    def on_table_clicked(self, index):
        """Handle click on the table"""
        row = index.row()
        self.logger.debug(f"Table clicked at row {row}")

        if 0 <= row < len(self.routine_ids):
            routine_id = self.routine_ids[row]
            self.logger.info(f"Routine selected from table click: {routine_id}")
            self.routine_selected.emit(routine_id)
        else:
            self.logger.warning(f"Invalid row index from click: {row}, routine_ids length: {len(self.routine_ids)}")

