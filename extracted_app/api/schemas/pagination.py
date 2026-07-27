from pydantic import BaseModel


class PaginationMetadata(BaseModel):

    page: int

    page_size: int

    total_items: int

    total_pages: int

    has_next: bool

    has_previous: bool