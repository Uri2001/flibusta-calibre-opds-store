# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2012, Sergey Kuznetsov <clk824@gmail.com>, 2022, Ed Ryzhov <ed.ryzhov@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
from contextlib import closing
from qt.core import QUrl
from calibre import (browser, guess_extension)
from calibre.gui2 import open_url
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.utils.opensearch.description import Description
from calibre.utils.opensearch.query import Query
from calibre.gui2.store.search_result import SearchResult

class FlibustaStore(StorePlugin):

    web_url = 'https://flibusta.site/'
    
    def __init__(self, *args, **kwargs):
        super(FlibustaStore, self).__init__(*args, **kwargs)
        # Путь к локальному файлу opds-opensearch.xml
        self.opensearch_file = os.path.join(os.path.dirname(__file__), '..', 'opds-opensearch.xml')

    def open(self, parent=None, detail_item=None, external=False):
        if not hasattr(self, 'web_url'):
            return

        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item if detail_item else self.web_url))
        else:
            d = WebStoreDialog(self.gui, self.web_url, parent, detail_item, create_browser=self.create_browser)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        if not os.path.exists(self.opensearch_file):
            return

        yield from FlibustaStore.open_search(self.opensearch_file, query, max_results, timeout)

    @staticmethod
    def open_search(opensearch_path, query, max_results, timeout):
        # Создаем Description из локального файла
        with open(opensearch_path, 'rb') as f:
            opensearch_content = f.read()
        
        description = Description(opensearch_content)
        url_template = description.get_best_template()
        if not url_template:
            return
        
        oquery = Query(url_template)

        # set up initial values
        oquery.searchTerms = query
        oquery.count = max_results
        url = oquery.url()

        counter = max_results
        br = browser()
        with closing(br.open(url, timeout=timeout)) as f:
            doc = safe_xml_fromstring(f.read())
            for data in doc.xpath('//*[local-name() = "entry"]'):
                if counter <= 0:
                    break

                counter -= 1
                s = SearchResult()
                s.detail_item = ''.join(data.xpath('./*[local-name() = "id"]/text()')).strip()

                for link in data.xpath('./*[local-name() = "link"]'):
                    rel = link.get('rel')
                    href = link.get('href')
                    type = link.get('type')

                    if rel and href and type:
                        if 'http://opds-spec.org/thumbnail' in rel:
                            s.cover_url = href
                        elif 'http://opds-spec.org/image/thumbnail' in rel:
                            s.cover_url = href
                        elif 'http://opds-spec.org/acquisition/buy' in rel:
                            s.detail_item = href
                        elif 'http://opds-spec.org/acquisition/sample' in rel:
                            pass
                        elif 'alternate' in rel:
                            s.detail_item = FlibustaStore.web_url + href
                        elif 'http://opds-spec.org/acquisition' in rel:
                            if type:
                                ext = FlibustaStore.custom_guess_extension(type)
                                if ext:
                                    s.downloads[ext] = FlibustaStore.web_url + href

                s.formats = ', '.join(s.downloads.keys()).strip()

                s.title = ' '.join(data.xpath('./*[local-name() = "title"]//text()')).strip()
                s.author = ', '.join(data.xpath('./*[local-name() = "author"]//*[local-name() = "name"]//text()')).strip()
                s.price = '$0.00'
                s.drm = SearchResult.DRM_UNLOCKED

                yield s

    @staticmethod
    def custom_guess_extension(type):
        ext = guess_extension(type)
        if ext:
            return ext[1:].upper().strip()
        elif 'application/fb2' in type:
            return 'FB2'
        elif 'application/epub' in type:
            return 'EPUB'
        else:
            return None