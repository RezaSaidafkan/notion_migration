from src.models.client_models import Page, JournalPage
from typing import Union

def count_leaves(page: Union[Page, JournalPage], counter = 0) -> int:
    if page.Relations is not None and page.Relations.Descendants is not None and len(page.Relations.Descendants) > 0:
        for desc in page.Relations.Descendants:
            count_leaves(desc, counter)
    counter =+ 1
    return counter
    