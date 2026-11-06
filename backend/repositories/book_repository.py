"""In-memory book store (demo CRUD resource; resets on every server restart)."""

from backend.schemas.book import Book, BookCreate

_books: dict[int, Book] = {}
_next_id = 1

SEED = [
    {"title": "Clean Code", "author": "Robert C. Martin", "published_year": 2008, "isbn": "9780132350884", "available": True},
    {"title": "The Pragmatic Programmer", "author": "Andrew Hunt", "published_year": 1999, "isbn": "9780201616224", "available": True},
    {"title": "Fluent Python", "author": "Luciano Ramalho", "published_year": 2015, "isbn": "9781491946008", "available": False},
]


def list_all() -> list[Book]:
    return list(_books.values())


def get(book_id: int) -> Book | None:
    return _books.get(book_id)


def add(data: BookCreate) -> Book:
    global _next_id
    book = Book(id=_next_id, **data.model_dump())
    _books[_next_id] = book
    _next_id += 1
    return book


def save(book: Book) -> Book:
    _books[book.id] = book
    return book


def delete(book_id: int) -> bool:
    return _books.pop(book_id, None) is not None


for _data in SEED:
    add(BookCreate(**_data))
