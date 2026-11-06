"""/books CRUD (demo resource, in-memory)."""

from fastapi import APIRouter, HTTPException, Query

from backend.schemas.book import Book, BookCreate, BookUpdate
from backend.services import book_service

router = APIRouter(prefix="/books", tags=["books"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Book not found")


@router.get("/", response_model=list[Book])
def list_books(
    author: str | None = Query(None, description="Case-insensitive substring match"),
    available: bool | None = Query(None),
):
    return book_service.list_books(author, available)


@router.get("/{book_id}", response_model=Book)
def get_book(book_id: int):
    if book := book_service.get_book(book_id):
        return book
    raise _not_found()


@router.post("/", response_model=Book, status_code=201)
def create_book(book_in: BookCreate):
    return book_service.create_book(book_in)


@router.patch("/{book_id}", response_model=Book)
def update_book(book_id: int, book_in: BookUpdate):
    if book := book_service.update_book(book_id, book_in):
        return book
    raise _not_found()


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int):
    if not book_service.delete_book(book_id):
        raise _not_found()
