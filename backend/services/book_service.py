"""Book rules: filtering and partial updates. Returns None when a book doesn't exist."""

from backend.repositories import book_repository
from backend.schemas.book import Book, BookCreate, BookUpdate


def list_books(author: str | None = None, available: bool | None = None) -> list[Book]:
    books = book_repository.list_all()
    if author is not None:
        books = [b for b in books if author.lower() in b.author.lower()]
    if available is not None:
        books = [b for b in books if b.available == available]
    return books


def get_book(book_id: int) -> Book | None:
    return book_repository.get(book_id)


def create_book(data: BookCreate) -> Book:
    return book_repository.add(data)


def update_book(book_id: int, data: BookUpdate) -> Book | None:
    stored = book_repository.get(book_id)
    if not stored:
        return None
    return book_repository.save(stored.model_copy(update=data.model_dump(exclude_unset=True)))


def delete_book(book_id: int) -> bool:
    return book_repository.delete(book_id)
