# Book Explorer - CS200 Project 1

Scrapes 15,000+ books from the Open Library API and lets you sort and search them in a PyQt5 window.

## Run
```
pip install -r requirements.txt
python main.py
```
Press **Start** on the Scraper tab (15,000 books by default). Data is saved to `data.csv` and loaded again next time.

## Files
- `main.py` - the window (table, tabs, buttons)
- `scraper.py` - scraping thread with start / pause / resume / stop
- `sorting.py` - 9 sorting algorithms with comparison + swap counters
- `searching.py` - linear / binary search, contains / starts with / ends with, AND / OR / NOT
- `config.py` - column definitions
