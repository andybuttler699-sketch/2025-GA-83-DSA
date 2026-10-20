# Scraper: collects books from the Open Library search API.
# It runs in its own thread so the window doesn't freeze.

import csv
import threading
import time
from urllib.parse import urlparse, parse_qs

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from config import COLUMN_KEYS, NUMBER_COLUMNS, FLOAT_COLUMNS

API_URL = "https://openlibrary.org/search.json"
FIELDS = ("title,author_name,first_publish_year,edition_count,"
          "number_of_pages_median,ratings_average,ratings_count,"
          "want_to_read_count,language")
HEADERS = {"User-Agent": "UET-DSA-Student-Project/1.0"}
PAGE_SIZE = 100
MAX_PAGES_PER_TOPIC = 100

# We go through these topics one by one until we have enough books
DEFAULT_TOPICS = [
    "love", "war", "history", "science", "magic", "world", "life", "night",
    "dragon", "king", "death", "time", "garden", "city", "mystery",
    "adventure", "art", "music", "journey", "secret", "house", "river",
    "mountain", "ocean", "star", "fire", "dream", "shadow", "family", "school",
]


def topics_from_url(url):
    """Pull the search word out of a link like https://openlibrary.org/search?q=dragons"""
    parsed = urlparse(url)
    if "openlibrary.org" not in parsed.netloc:
        raise ValueError("Only openlibrary.org search links are supported.")
    query = parse_qs(parsed.query).get("q")
    if not query:
        raise ValueError("That link has no search word (?q=...) in it.")
    return [query[0]]


def clean_book(doc):
    """Turn one raw API result into a row with our 9 columns."""
    authors = doc.get("author_name") or ["Unknown"]
    languages = doc.get("language") or ["unknown"]
    return {
        "title": (doc.get("title") or "Untitled").strip(),
        "author": authors[0],
        "year": int(doc.get("first_publish_year") or 0),
        "editions": int(doc.get("edition_count") or 0),
        "pages": int(doc.get("number_of_pages_median") or 0),
        "rating": round(float(doc.get("ratings_average") or 0), 2),
        "ratings_count": int(doc.get("ratings_count") or 0),
        "want_to_read": int(doc.get("want_to_read_count") or 0),
        "language": languages[0],
    }


class ScraperThread(QThread):
    got_rows = pyqtSignal(list)          # a batch of new rows
    status = pyqtSignal(str)             # text for the status label
    finished_scraping = pyqtSignal(str)  # final message

    def __init__(self, topics, target):
        super().__init__()
        self.topics = topics
        self.target = target
        self._stop = False
        self._running = threading.Event()   # set = running, cleared = paused
        self._running.set()

    def pause(self):
        self._running.clear()

    def resume(self):
        self._running.set()

    def stop(self):
        self._stop = True
        self._running.set()              # wake it up if it was paused

    def fetch_page(self, topic, page):
        """Download one page of results. Returns a list, or None if the network failed."""
        params = {"q": topic, "page": page, "limit": PAGE_SIZE, "fields": FIELDS}
        for attempt in range(3):
            if self._stop:
                return None
            try:
                response = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
                response.raise_for_status()
                return response.json().get("docs", [])
            except Exception as error:
                self.status.emit("Network problem, retrying... (" + str(error)[:60] + ")")
                time.sleep(2)
        return None

    def run(self):
        seen = set()        # (title, author) pairs so we don't store duplicates
        total = 0
        message = "Done."

        for topic in self.topics:
            for page in range(1, MAX_PAGES_PER_TOPIC + 1):
                self._running.wait()                 # waits here while paused
                if self._stop or total >= self.target:
                    break

                docs = self.fetch_page(topic, page)
                if docs is None:
                    if not self._stop:
                        message = "Stopped: could not reach Open Library."
                        self._stop = True
                    break
                if len(docs) == 0:                   # no more pages for this topic
                    break

                new_rows = []
                for doc in docs:
                    book = clean_book(doc)
                    ident = (book["title"].lower(), book["author"].lower())
                    if ident in seen:
                        continue
                    seen.add(ident)
                    new_rows.append(book)
                    if total + len(new_rows) >= self.target:
                        break

                total += len(new_rows)
                self.got_rows.emit(new_rows)
                self.status.emit("Scraping '" + topic + "' (page " + str(page) + ")... "
                                 + str(total) + " books so far")
                time.sleep(0.2)                      # be nice to the server

            if self._stop or total >= self.target:
                break

        if self._stop and message == "Done.":
            message = "Stopped by user."
        elif total < self.target and message == "Done.":
            message = "Ran out of results before reaching the target."
        self.finished_scraping.emit(message)


# ---------------------------------------------------------------- CSV helpers

def save_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMN_KEYS)
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = {}
            for key in COLUMN_KEYS:
                value = raw[key]
                if key in FLOAT_COLUMNS:
                    value = float(value)
                elif key in NUMBER_COLUMNS:
                    value = int(float(value))
                row[key] = value
            rows.append(row)
    return rows
