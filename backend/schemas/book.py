from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    published_year: int | None = Field(default=None, ge=1450, le=2100)
    isbn: str | None = Field(default=None, max_length=20)
    available: bool = True


class BookUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    author: str | None = Field(None, min_length=1, max_length=100)
    published_year: int | None = Field(None, ge=1450, le=2100)
    isbn: str | None = Field(None, max_length=20)
    available: bool | None = None


class Book(BookCreate):
    id: int
