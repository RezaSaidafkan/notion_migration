from typing_extensions import Self
from common_libs.models.tracing import Body
import httpx
from typing import Optional

class TracingException(Exception):
    pass


class Tracing:
    singleton = None
    
    def __init__(self, address: Optional[str]=None, port: Optional[int]=None) -> None:
        self._address = address
        self._port = port
        self._url = f"http://{self._address}:{self._port}"
    
    def __new__(cls, address: Optional[str]=None, port: Optional[int]=None) -> Self:
        if not cls.singleton:
            cls.singleton = super().__new__(cls)
        return cls.singleton


    def send_trace_page(self, body: Body):
        try:
            with httpx.Client() as client:
                response = client.post(f"{self._url}/trace_page", json=body.model_dump(mode="json"))
                response.raise_for_status()
        except httpx.HTTPError as t_e:
            raise TracingException(
                f"Failed to send tracing for:\t{body.page.id}\t{body.trace.function_name}") from t_e
        except Exception as e:
            raise TracingException(
                f"Unknown issue is sending tracing for:\
                    \t{body.page.id}\t{body.trace.function_name}") from e
