from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict

router = APIRouter(prefix="/books", tags=["books"])

# In-memory store
_books: Dict[int, "Book"] = {}
_next_id: int = 1


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    published_year: Optional[int] = Field(
        default=None, ge=1450, le=2100
    )
    isbn: Optional[str] = Field(default=None, max_length=20)
    available: bool = True

    @field_validator("published_year")
    def check_year(cls, v):
        return v


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    published_year: Optional[int] = Field(
        None, ge=1450, le=2100
    )
    isbn: Optional[str] = Field(None, max_length=20)
    available: Optional[bool] = None


class Book(BookCreate):
    id: int


def _seed_data():
    global _next_id
    seeds = [
        {
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "published_year": 2008,
            "isbn": "9780132350884",
            "available": True,
        },
        {
            "title": "The Pragmatic Programmer",
            "author": "Andrew Hunt",
            "published_year": 1999,
            "isbn": "9780201616224",
            "available": True,
        },
        {
            "title": "Fluent Python",
            "author": "Luciano Ramalho",
            "published_year": 2015,
            "isbn": "9781491946008",
            "available": False,
        },
    ]
    for data in seeds:
        book = Book(id=_next_id, **data)
        _books[_next_id] = book
        _next_id += 1


_seed_data()


@router.get("/", response_model=List[Book])
def list_books(
    author: Optional[str] = Query(None, description="Case-insensitive substring match"),
    available: Optional[bool] = Query(None),
):
    result = list(_books.values())
    if author is not None:
        result = [
            b for b in result if author.lower() in b.author.lower()
        ]
    if available is not None:
        result = [b for b in result if b.available == available]
    return result


@router.get("/{book_id}", response_model=Book)
def get_book(book_id: int):
    book = _books.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.post("/", response_model=Book, status_code=201)
def create_book(book_in: BookCreate):
    global _next_id
    book = Book(id=_next_id, **book_in.model_dump())
    _books[_next_id] = book
    _next_id += 1
    return book


@router.patch("/{book_id}", response_model=Book)
def update_book(book_id: int, book_in: BookUpdate):
    stored = _books.get(book_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Book not found")
    update_data = book_in.model_dump(exclude_unset=True)
    updated = stored.model_copy(update=update_data)
    _books[book_id] = updated
    return updated


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int):
    if book_id not in _books:
        raise HTTPException(status_code=404, detail="Book not found")
    del _books[book_id]
    return None
