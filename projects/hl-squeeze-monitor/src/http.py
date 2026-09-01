import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PublicClient:
    def __init__(self, base: str, timeout: int = 12):
        self.base, self.timeout = base, timeout

    def request(self, method: str, path: str, **kwargs):
        last = None
        for attempt in range(3):
            try:
                params=kwargs.get("params") or {}; url=self.base+path+("?"+urlencode(params) if params else "")
                body=json.dumps(kwargs["json"]).encode() if "json" in kwargs else None
                request=Request(url,data=body,method=method,headers={"User-Agent":"base-lab-hl-squeeze-monitor/1.0","Content-Type":"application/json"})
                with urlopen(request,timeout=self.timeout) as response: return json.loads(response.read())
            except (TimeoutError, URLError, HTTPError) as exc:
                last = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"API request failed: {path}: {last}")
