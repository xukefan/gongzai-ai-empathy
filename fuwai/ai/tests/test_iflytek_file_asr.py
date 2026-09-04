import base64
import hashlib
import hmac
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parents[1]))

from iflytek_file_asr import IflytekFileASR, build_signature, parse_order_result


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.payload


class FakeOpener:
    def __init__(self):
        self.requests = []
        self.responses = [
            {"code": "000000", "content": {"orderId": "order-1"}},
            {"code": "000000", "content": {"orderInfo": {"status": 3}, "orderResult": ""}},
            {
                "code": "000000",
                "content": {
                    "orderInfo": {"status": 4},
                    "orderResult": json.dumps({
                        "lattice": [{"json_1best": json.dumps({
                            "st": {"rt": [{"ws": [{"cw": [{"w": " 你好 ", "wp": "n"}]}, {"cw": [{"w": "。", "wp": "p"}]}]}]}
                        })}]
                    }),
                },
            },
        ]

    def __call__(self, request, timeout):
        self.requests.append(request)
        return FakeResponse(self.responses.pop(0))


class IflytekTests(unittest.TestCase):
    def test_signature_matches_hmac_sha1(self):
        params = {"b": "two words", "a": "中文", "empty": "", "signature": "ignored"}
        canonical = "a=%E4%B8%AD%E6%96%87&b=two+words"
        expected = base64.b64encode(hmac.new(b"secret", canonical.encode(), hashlib.sha1).digest()).decode()
        self.assertEqual(build_signature("secret", params), expected)

    def test_parse_nested_result(self):
        result = {"lattice": [{"json_1best": json.dumps({"st": {"rt": [{"ws": [{"cw": [{"w": "你"}]}, {"cw": [{"w": "好"}]}]}]}})}]}
        self.assertEqual(parse_order_result(json.dumps(result)), "你好")

    def test_upload_poll_and_result(self):
        opener = FakeOpener()
        client = IflytekFileASR("app", "key", "secret", poll_interval=0, opener=opener)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            path.write_bytes(b"audio")
            self.assertEqual(client.transcribe(path), "你好。")
        self.assertEqual(len(opener.requests), 3)
        upload_query = parse_qs(urlparse(opener.requests[0].full_url).query)
        self.assertEqual(upload_query["language"], ["autodialect"])
        self.assertNotIn("signature", upload_query)
        self.assertTrue(opener.requests[0].get_header("Signature"))
        self.assertEqual(opener.requests[2].data, b"{}")


if __name__ == "__main__":
    unittest.main()
