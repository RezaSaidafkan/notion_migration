from typing import Union

from common_libs.models.client_models import JournalPage, TaskPage


def count_leaves(page: Union[TaskPage, JournalPage], counter: int=0) -> int:
    if (
        page.Properties.Descendants is not None
        and len(page.Properties.Descendants.Items) > 0
    ):
        for desc in page.Properties.Descendants.Items:
            count_leaves(desc, counter)
    counter = +1
    return counter
