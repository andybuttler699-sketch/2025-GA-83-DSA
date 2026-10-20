# Shared settings for the whole project.

# (key used in the row dictionary, header shown in the table, is it a number?)
COLUMNS = [
    ("title",         "Title",           False),
    ("author",        "Author",          False),
    ("year",          "First Published", True),
    ("editions",      "Editions",        True),
    ("pages",         "Pages",           True),
    ("rating",        "Rating",          True),
    ("ratings_count", "Ratings Count",   True),
    ("want_to_read",  "Want To Read",    True),
    ("language",      "Language",        False),
]

COLUMN_KEYS = [c[0] for c in COLUMNS]
COLUMN_HEADERS = [c[1] for c in COLUMNS]
NUMBER_COLUMNS = {c[0] for c in COLUMNS if c[2]}
FLOAT_COLUMNS = {"rating"}      # every other number column is a whole number

CSV_FILE = "data.csv"           # scraped data is saved here automatically
