# CS200 Project 1 - Book Explorer (PyQt5)
# Run with:  python main.py

import os
import sys
import time

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableView, QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QProgressBar, QRadioButton, QButtonGroup, QListWidget, QMessageBox, QDialog,
    QTableWidget, QTableWidgetItem, QGroupBox, QFileDialog,
)

from config import COLUMN_KEYS, COLUMN_HEADERS, NUMBER_COLUMNS, CSV_FILE
from scraper import ScraperThread, DEFAULT_TOPICS, topics_from_url, save_csv, load_csv
from sorting import ALGORITHMS, run_sort, multi_level_sort
from searching import STRING_OPS, NUMBER_OPS, SEARCH_ALGORITHMS, search_rows


class TableModel(QAbstractTableModel):
    """Feeds the rows to the table. (Much faster than QTableWidget for 15k rows.)"""

    def __init__(self):
        super().__init__()
        self.rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def add_rows(self, new_rows):
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(new_rows) - 1)
        self.rows.extend(new_rows)
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMN_KEYS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        key = COLUMN_KEYS[index.column()]
        if role == Qt.DisplayRole:
            return str(self.rows[index.row()][key])
        if role == Qt.TextAlignmentRole and key in NUMBER_COLUMNS:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return COLUMN_HEADERS[section]
        return str(section + 1)


class Worker(QThread):
    """Runs a slow function (sorting / benchmark) so the window doesn't freeze."""
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            self.result.emit(self.job())
        except Exception as e:
            self.error.emit(str(e))


class BenchmarkDialog(QDialog):
    def __init__(self, parent, title, results):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 380)
        layout = QVBoxLayout(self)
        headers = ["Algorithm", "Complexity", "Stable", "Time (ms)", "Comparisons", "Swaps"]
        table = QTableWidget(len(results), len(headers))
        table.setHorizontalHeaderLabels(headers)
        fastest = min(r[3] for r in results)
        for i, (name, complexity, stable, ms, comps, swaps) in enumerate(results):
            values = [name, complexity, "Yes" if stable else "No",
                      f"{ms:.2f}", f"{comps:,}", f"{swaps:,}"]
            for j, v in enumerate(values):
                item = QTableWidgetItem(v)
                if ms == fastest:
                    item.setBackground(Qt.green)
                    item.setForeground(Qt.black)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        layout.addWidget(QLabel("Green row = fastest."))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Book Explorer - CS200 Project 1")

        self.all_rows = []                  # every scraped row
        self.view_rows = self.all_rows      # rows currently shown (same list = no filter)
        self.scraper = None
        self.worker = None
        self.on_done = None
        self.scraping = False
        self.levels = []                    # multi-level sort: [(column, descending)]
        self.conditions = []                # search: [(connector, column, op, text)]

        self.model = TableModel()
        self.build_ui()

        if os.path.exists(CSV_FILE):        # reuse data from last time
            try:
                self.all_rows = load_csv(CSV_FILE)
                self.view_rows = self.all_rows
                self.model.set_rows(self.view_rows)
                self.progress.setMaximum(max(len(self.all_rows), 1))
                self.progress.setValue(len(self.all_rows))
                self.status_label.setText("Loaded " + str(len(self.all_rows)) + " books from " + CSV_FILE)
            except Exception:
                pass
        self.update_count()

    # ------------------------------------------------------------ building UI
    def build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_scraper_tab(), "Scraper")
        self.sort_tab = self.build_sort_tab()
        self.tabs.addTab(self.sort_tab, "Sort")
        self.search_tab = self.build_search_tab()
        self.tabs.addTab(self.search_tab, "Search")
        layout.addWidget(self.tabs)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 180)
        layout.addWidget(self.table, 1)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)
        self.setCentralWidget(central)

    def build_scraper_tab(self):
        tab = QWidget()
        g = QGridLayout(tab)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Optional: paste an Open Library search link, e.g. https://openlibrary.org/search?q=dragons")
        self.target_spin = QSpinBox()
        self.target_spin.setRange(100, 100000)
        self.target_spin.setValue(15000)

        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Resume")
        self.stop_btn = QPushButton("Stop")
        self.start_btn.clicked.connect(self.start_scrape)
        self.pause_btn.clicked.connect(self.pause_scrape)
        self.resume_btn.clicked.connect(self.resume_scrape)
        self.stop_btn.clicked.connect(self.stop_scrape)

        self.progress = QProgressBar()
        self.status_label = QLabel("Ready.")
        save_btn = QPushButton("Save CSV")
        load_btn = QPushButton("Load CSV")
        save_btn.clicked.connect(self.save_clicked)
        load_btn.clicked.connect(self.load_clicked)

        g.addWidget(QLabel("Search URL (bonus):"), 0, 0)
        g.addWidget(self.url_input, 0, 1, 1, 5)
        g.addWidget(QLabel("Books to scrape:"), 1, 0)
        g.addWidget(self.target_spin, 1, 1)
        g.addWidget(self.start_btn, 1, 2)
        g.addWidget(self.pause_btn, 1, 3)
        g.addWidget(self.resume_btn, 1, 4)
        g.addWidget(self.stop_btn, 1, 5)
        g.addWidget(self.progress, 2, 0, 1, 6)
        g.addWidget(self.status_label, 3, 0, 1, 4)
        g.addWidget(save_btn, 3, 4)
        g.addWidget(load_btn, 3, 5)
        self.set_scrape_state("idle")
        return tab

    def build_sort_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        row1 = QHBoxLayout()
        self.sort_col = QComboBox()
        self.sort_col.addItems(COLUMN_HEADERS)
        self.sort_algo = QComboBox()
        self.sort_algo.addItems(list(ALGORITHMS.keys()))
        self.sort_algo.currentTextChanged.connect(self.update_algo_info)
        self.sort_order = QComboBox()
        self.sort_order.addItems(["Ascending", "Descending"])
        self.algo_info = QLabel()
        row1.addWidget(QLabel("Column:"))
        row1.addWidget(self.sort_col)
        row1.addWidget(QLabel("Algorithm:"))
        row1.addWidget(self.sort_algo)
        row1.addWidget(self.sort_order)
        row1.addWidget(self.algo_info)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.scope_full = QRadioButton("Full dataset")
        self.scope_filtered = QRadioButton("Only filtered results")
        self.scope_full.setChecked(True)
        group = QButtonGroup(tab)
        group.addButton(self.scope_full)
        group.addButton(self.scope_filtered)
        sort_btn = QPushButton("Sort")
        sort_btn.clicked.connect(self.do_sort)
        bench_btn = QPushButton("Benchmark all")
        bench_btn.clicked.connect(self.do_benchmark)
        self.bench_size = QSpinBox()
        self.bench_size.setRange(100, 100000)
        self.bench_size.setValue(2000)
        row2.addWidget(QLabel("Sort scope:"))
        row2.addWidget(self.scope_full)
        row2.addWidget(self.scope_filtered)
        row2.addWidget(sort_btn)
        row2.addWidget(bench_btn)
        row2.addWidget(QLabel("Benchmark rows:"))
        row2.addWidget(self.bench_size)
        row2.addStretch()
        layout.addLayout(row2)

        box = QGroupBox("Multi-level sort (uses Merge Sort because it is stable)")
        mrow = QHBoxLayout(box)
        self.multi_col = QComboBox()
        self.multi_col.addItems(COLUMN_HEADERS)
        self.multi_order = QComboBox()
        self.multi_order.addItems(["Ascending", "Descending"])
        add_btn = QPushButton("Add level")
        add_btn.clicked.connect(self.add_level)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_levels)
        run_btn = QPushButton("Run multi-level sort")
        run_btn.clicked.connect(self.do_multi_sort)
        self.levels_list = QListWidget()
        self.levels_list.setMaximumHeight(60)
        for w in (self.multi_col, self.multi_order, add_btn, clear_btn, self.levels_list, run_btn):
            mrow.addWidget(w)
        layout.addWidget(box)

        self.sort_result = QLabel("")
        layout.addWidget(self.sort_result)
        self.update_algo_info()
        return tab

    def build_search_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        row1 = QHBoxLayout()
        self.search_col = QComboBox()
        self.search_col.addItems(COLUMN_HEADERS)
        self.search_col.currentIndexChanged.connect(self.update_operators)
        self.op_combo = QComboBox()
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("value...")
        self.value_input.returnPressed.connect(self.do_search)
        self.connector = QComboBox()
        self.connector.addItems(["AND", "OR", "NOT"])
        self.connector.setToolTip("NOT means AND NOT")
        add_btn = QPushButton("Add condition")
        add_btn.clicked.connect(self.add_condition)
        for w in (QLabel("Column:"), self.search_col, self.op_combo, self.value_input,
                  QLabel("Join with:"), self.connector, add_btn):
            row1.addWidget(w)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.search_algo = QComboBox()
        self.search_algo.addItems(SEARCH_ALGORITHMS)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.do_search)
        clear_btn = QPushButton("Clear search")
        clear_btn.clicked.connect(self.clear_search)
        self.cond_list = QListWidget()
        self.cond_list.setMaximumHeight(60)
        row2.addWidget(QLabel("Algorithm:"))
        row2.addWidget(self.search_algo)
        row2.addWidget(search_btn)
        row2.addWidget(clear_btn)
        row2.addWidget(self.cond_list, 1)
        layout.addLayout(row2)
        self.update_operators()
        return tab

    # ---------------------------------------------------------------- scraping
    def set_scrape_state(self, state):
        self.scraping = state != "idle"
        self.start_btn.setEnabled(state == "idle")
        self.pause_btn.setEnabled(state == "running")
        self.resume_btn.setEnabled(state == "paused")
        self.stop_btn.setEnabled(state in ("running", "paused"))
        self.url_input.setEnabled(state == "idle")
        self.target_spin.setEnabled(state == "idle")

    def start_scrape(self):
        url = self.url_input.text().strip()
        topics = DEFAULT_TOPICS
        if url:
            try:
                topics = topics_from_url(url)
            except ValueError as e:
                QMessageBox.warning(self, "Bad URL", str(e))
                return
        target = self.target_spin.value()

        self.all_rows = []
        self.view_rows = self.all_rows
        self.model.set_rows(self.view_rows)
        self.progress.setMaximum(target)
        self.progress.setValue(0)

        self.scraper = ScraperThread(topics, target)
        self.scraper.got_rows.connect(self.on_new_rows)
        self.scraper.status.connect(self.status_label.setText)
        self.scraper.finished_scraping.connect(self.on_scrape_done)
        self.scraper.start()
        self.set_scrape_state("running")

    def on_new_rows(self, new_rows):
        # model.rows is the same list as self.all_rows, so this updates both
        self.model.add_rows(new_rows)
        self.progress.setValue(len(self.all_rows))
        self.update_count()

    def pause_scrape(self):
        self.scraper.pause()
        self.set_scrape_state("paused")
        self.status_label.setText("Paused.")

    def resume_scrape(self):
        self.scraper.resume()
        self.set_scrape_state("running")

    def stop_scrape(self):
        self.scraper.stop()
        self.status_label.setText("Stopping...")

    def on_scrape_done(self, message):
        self.set_scrape_state("idle")
        if self.all_rows:
            save_csv(self.all_rows, CSV_FILE)
            message += " Saved " + str(len(self.all_rows)) + " books to " + CSV_FILE + "."
        self.status_label.setText(message)
        self.update_count()

    def save_clicked(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", CSV_FILE, "CSV files (*.csv)")
        if path:
            save_csv(self.all_rows, path)

    def load_clicked(self):
        if self.scraping:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load CSV", "", "CSV files (*.csv)")
        if path:
            try:
                self.all_rows = load_csv(path)
            except Exception as e:
                QMessageBox.warning(self, "Could not load", str(e))
                return
            self.view_rows = self.all_rows
            self.model.set_rows(self.view_rows)
            self.progress.setMaximum(max(len(self.all_rows), 1))
            self.progress.setValue(len(self.all_rows))
            self.update_count()

    # ----------------------------------------------------------------- helpers
    def update_count(self):
        self.count_label.setText("Showing " + format(len(self.view_rows), ",") +
                                 " of " + format(len(self.all_rows), ",") + " books")

    def can_work(self):
        if self.scraping:
            QMessageBox.information(self, "Busy", "Stop the scraper (or wait for it) first.")
            return False
        if not self.all_rows:
            QMessageBox.information(self, "No data", "Scrape or load some data first.")
            return False
        return True

    def start_job(self, job, on_done):
        """Run job() in a background thread, then call on_done(result)."""
        self.sort_tab.setEnabled(False)
        self.search_tab.setEnabled(False)
        self.statusBar().showMessage("Working... slow O(n²) algorithms can take a while on big data.")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.on_done = on_done
        self.worker = Worker(job)
        self.worker.result.connect(self.job_finished)
        self.worker.error.connect(self.job_failed)
        self.worker.start()

    def end_job(self):
        QApplication.restoreOverrideCursor()
        self.sort_tab.setEnabled(True)
        self.search_tab.setEnabled(True)
        self.statusBar().clearMessage()

    def job_finished(self, result):
        self.end_job()
        self.on_done(result)

    def job_failed(self, message):
        self.end_job()
        QMessageBox.warning(self, "Error", message)

    # ----------------------------------------------------------------- sorting
    def update_algo_info(self):
        _, complexity, stable = ALGORITHMS[self.sort_algo.currentText()]
        self.algo_info.setText("Time: " + complexity + "  |  Stable: " + ("Yes" if stable else "No"))

    def rows_for_scope(self):
        if self.scope_filtered.isChecked():
            return self.view_rows
        return self.all_rows

    def show_sorted(self, sorted_rows, was_full_scope):
        if was_full_scope:
            self.all_rows = sorted_rows
            self.view_rows = self.all_rows      # (this also clears any filter)
            self.cond_list.clear()
            self.conditions = []
        else:
            self.view_rows = sorted_rows
        self.model.set_rows(self.view_rows)
        self.update_count()

    def do_sort(self):
        if not self.can_work():
            return
        full = self.scope_full.isChecked() or self.view_rows is self.all_rows
        rows = self.rows_for_scope()
        column = COLUMN_KEYS[self.sort_col.currentIndex()]
        header = self.sort_col.currentText()
        algo = self.sort_algo.currentText()
        desc = self.sort_order.currentIndex() == 1
        _, complexity, stable = ALGORITHMS[algo]

        def finished(result):
            sorted_rows, comps, swaps, ms = result
            self.show_sorted(sorted_rows, full)
            self.sort_result.setText(
                f"{algo} on '{header}' ({len(rows):,} rows)  ->  Time: {ms:.2f} ms  |  "
                f"Comparisons: {comps:,}  |  Swaps: {swaps:,}  |  {complexity}  |  "
                f"Stable: {'Yes' if stable else 'No'}")

        self.start_job(lambda: run_sort(rows, column, algo, desc), finished)

    def do_benchmark(self):
        if not self.can_work():
            return
        rows = self.rows_for_scope()[:self.bench_size.value()]
        column = COLUMN_KEYS[self.sort_col.currentIndex()]
        header = self.sort_col.currentText()
        desc = self.sort_order.currentIndex() == 1

        def job():
            results = []
            for name, (func, complexity, stable) in ALGORITHMS.items():
                _, comps, swaps, ms = run_sort(rows, column, name, desc)
                results.append((name, complexity, stable, ms, comps, swaps))
            return results

        def finished(results):
            title = f"Benchmark - '{header}' - {len(rows):,} rows"
            BenchmarkDialog(self, title, results).exec_()

        self.start_job(job, finished)

    def add_level(self):
        column = COLUMN_KEYS[self.multi_col.currentIndex()]
        desc = self.multi_order.currentIndex() == 1
        self.levels.append((column, desc))
        self.levels_list.addItem(str(len(self.levels)) + ". " + self.multi_col.currentText() +
                                 (" (desc)" if desc else " (asc)"))

    def clear_levels(self):
        self.levels = []
        self.levels_list.clear()

    def do_multi_sort(self):
        if not self.can_work():
            return
        if not self.levels:
            QMessageBox.information(self, "No levels", "Add at least one level first.")
            return
        full = self.scope_full.isChecked() or self.view_rows is self.all_rows
        rows = self.rows_for_scope()
        levels = list(self.levels)

        def finished(result):
            sorted_rows, comps, swaps, ms = result
            self.show_sorted(sorted_rows, full)
            self.sort_result.setText(
                f"Multi-level sort ({len(levels)} levels, {len(rows):,} rows)  ->  "
                f"Time: {ms:.2f} ms  |  Comparisons: {comps:,}  |  Swaps: {swaps:,}")

        self.start_job(lambda: multi_level_sort(rows, levels), finished)

    # --------------------------------------------------------------- searching
    def update_operators(self):
        column = COLUMN_KEYS[self.search_col.currentIndex()]
        self.op_combo.clear()
        self.op_combo.addItems(NUMBER_OPS if column in NUMBER_COLUMNS else STRING_OPS)

    def add_condition(self):
        text = self.value_input.text().strip()
        if not text:
            QMessageBox.information(self, "Empty", "Type a value first.")
            return False
        column = COLUMN_KEYS[self.search_col.currentIndex()]
        if column in NUMBER_COLUMNS:
            try:
                float(text)
            except ValueError:
                QMessageBox.warning(self, "Not a number", "'" + text + "' is not a number.")
                return False
        connector = self.connector.currentText() if self.conditions else ""
        op = self.op_combo.currentText()
        self.conditions.append((connector, column, op, text))
        shown = (connector + " " if connector else "") + self.search_col.currentText() + \
                " " + op + " '" + text + "'"
        self.cond_list.addItem(shown)
        self.value_input.clear()
        return True

    def do_search(self):
        if not self.can_work():
            return
        if self.value_input.text().strip():
            if not self.add_condition():
                return
        if not self.conditions:
            QMessageBox.information(self, "No condition", "Type a value and press Search.")
            return
        algo = self.search_algo.currentText()
        start = time.perf_counter()
        try:
            found, note = search_rows(self.all_rows, self.conditions, algo)
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        ms = (time.perf_counter() - start) * 1000
        self.view_rows = found
        self.model.set_rows(found)
        self.update_count()
        self.statusBar().showMessage(f"Found {len(found):,} rows in {ms:.2f} ms with {algo}{note}", 10000)

    def clear_search(self):
        self.conditions = []
        self.cond_list.clear()
        self.view_rows = self.all_rows
        self.model.set_rows(self.view_rows)
        self.update_count()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1250, 800)
    window.show()
    sys.exit(app.exec_())
   