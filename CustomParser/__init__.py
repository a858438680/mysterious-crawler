#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from html.parser import HTMLParser

'parse list in html response'

__author__ = 'Alan Lee'

class ListParser(HTMLParser):
    empty_ele = {'area', 'base', 'br', 'col', 'colgroup',
                 'command', 'embed', 'hr', 'img', 'input', 'keygen',
                 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, paths, path_attrs, dests):
        HTMLParser.__init__(self)
        self.stage = []
        self.attrs = []
        self.result = []
        self.paths = paths
        self.path_attrs = path_attrs
        self.dests = dests
        self.f = [False for path in paths]
        self.match = self.f[:]
        self.result = [[] for path in paths]

    def handle_starttag(self, tag, attrs):
        attrs_dict = {}
        for name, value in attrs:
            attrs_dict[name] = value
        self.stage.append(tag)
        self.attrs.append(attrs_dict)
        for i, path in enumerate(self.paths):
            if path == self.stage:
                match = True
                for j, path_attr in enumerate(self.path_attrs[i]):
                    for name, value in path_attr.items():
                        if name not in self.attrs[j] or self.attrs[j][name] != value:
                            match = False
                if match:
                    self.match[i] = True
                    if self.dests[i]:
                        self.result[i].append(attrs_dict[self.dests[i]])
        if tag in self.empty_ele:
            self.stage.pop()
            self.attrs.pop()
            self.match = self.f[:]

    def handle_endtag(self, tag):
        if tag not in self.empty_ele and self.stage and self.stage[-1] == tag:
            self.stage.pop()
            self.attrs.pop()
            self.match = self.f[:]

    def handle_data(self, data):
        for i, m in enumerate(self.match):
            if m and not self.dests[i]:
                self.result[i].append(data)
