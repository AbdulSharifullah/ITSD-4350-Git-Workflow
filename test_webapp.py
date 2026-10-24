import json
import threading
import unittest
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from webapp import Handler


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def test_home(self):
        with urlopen(self.url) as response:
            self.assertIn(b'CI Calculator', response.read())

    def test_add(self):
        with urlopen(self.url + '/api/add?a=-2.5&b=4') as response:
            self.assertEqual(json.load(response), {'result': 1.5})

    def test_invalid(self):
        for query in ('a=x&b=2', 'a=nan&b=2', 'a=1', 'a=1e308&b=1e308'):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + '/api/add?' + query)
            self.assertEqual(error.exception.code, 400)

    def test_not_found(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + '/missing')
        self.assertEqual(error.exception.code, 404)
