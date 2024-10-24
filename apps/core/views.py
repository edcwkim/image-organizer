import datetime
import hashlib
import hmac
import os
import requests
import time
from django.http import QueryDict
from django.views import generic
from urllib.parse import urlparse, urlunparse

CLOUDFLARE_ACCOUNT_ID = os.environ['CLOUDFLARE_ACCOUNT_ID']
CLOUDFLARE_API_TOKEN = os.environ['CLOUDFLARE_API_TOKEN']
CLOUDFLARE_API_HEADERS = {'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}'}
CLOUDFLARE_IMAGES_PRIVATE_KEY = os.environ['CLOUDFLARE_IMAGES_PRIVATE_KEY']
CLOUDFLARE_IMAGES_PRIVATE_EXPIRY = 7 * 24 * 60 * 60

SCREEN_NAME_MAP = {
    (640, 1136): '5s',
    (750, 1334): '6s',
    (1125, 2436): '10',
    (1170, 2532): '11',
    (1206, 2622): '16',
}

IMAGE_SIZE_MAP = {
    '5s': {
        'width': 320,
        'height': 568,
    },
    '6s': {
        'width': 375,
        'height': 667,
    },
    '10': {
        'width': 375,
        'height': 812,
    },
    '11': {
        'width': 390,
        'height': 844,
    },
    '16': {
        'width': 402,
        'height': 874,
    },
}


class Main(generic.ListView):
    context_object_name = 'image_list'
    template_name = 'core/main.html.j2'

    def get_queryset(self):
        url = f'https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/images/v2'
        r = requests.get(url, headers=CLOUDFLARE_API_HEADERS)
        r.raise_for_status()
        response = r.json()
        assert response['success']

        object_list = map(self.get_object, response['result']['images'])
        if 'screen' in self.request.GET:
            object_list = filter(lambda obj: obj['screen'] == self.request.GET['screen'], object_list)

        return object_list

    def get_object(self, data):
        md = data['meta']
        screen_name = SCREEN_NAME_MAP[(md['size']['width'], md['size']['height'])]
        optimized_image_url = self.get_optimized_image_url(data, screen_name)

        return {
            'url': self.get_signed_url(optimized_image_url),
            'size': IMAGE_SIZE_MAP[screen_name],
            'screen': screen_name,
            'category': md['category'],
            'app': md['captureEvent']['appName'],
            'global_ts': datetime.datetime.fromisoformat(md['captureEvent']['timestamp']),
            'local_ts': datetime.datetime.strptime(md['exif']['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S'),
        }

    @staticmethod
    def get_optimized_image_url(data, variant_name):
        for url in data['variants']:
            if url.split('/')[-1] == variant_name:
                return url

        raise KeyError

    @staticmethod
    def get_signed_url(url):
        parsed_url = list(urlparse(url))
        qd = QueryDict(parsed_url[4], mutable=True)
        qd['exp'] = str(int(time.time()) + CLOUDFLARE_IMAGES_PRIVATE_EXPIRY)
        url_full_path = f'{parsed_url[2]}?{qd.urlencode()}'
        qd['sig'] = hmac.new(CLOUDFLARE_IMAGES_PRIVATE_KEY.encode(), url_full_path.encode(), hashlib.sha256).hexdigest()
        parsed_url[4] = qd.urlencode()

        return urlunparse(parsed_url)
