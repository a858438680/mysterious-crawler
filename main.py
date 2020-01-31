#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import functools
import json
import os
import random
import requests
import sqlite3
import sys
import time
from CustomParser import ListParser


class relax(object):
    def sleep(self, base=0.3, rand=True, ratio=0.3, relax_seg=((120, 10), (900, 120), (3600, 1200))):
        self.base = base
        self.rand = rand
        self.ratio = ratio
        self.relax_seg = relax_seg = reversed(relax_seg)
        self.time = 0
        self.count = [0 for x in relax_seg]

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kw):
                if rand:
                    r = self.ratio * self.base
                    base = self.base - r
                    t = base + 2 * r * random.random()
                    time.sleep(t)
                else:
                    time.sleep(self.base)
                start = time.time()
                ret = func(*args, **kw)
                end = time.time()
                delta = end - start
                self.time = self.time + delta
                print('total: ', self.time, 's')
                for i in range(len(self.count)):
                    self.count[i] = self.count[i] + delta
                for i, total, sleep_time in enumerate(relax_seg):
                    if self.count[i] > total:
                        for j in range(i+1, len(self.count)):
                            self.count[j] = 0
                        print('sleep for ', sleep_time, 's')
                        time.sleep(sleep_time)
                return ret
            return wrapper
        return decorator


r = relax()


def get_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0'}
    success = False
    while not success:
        try:
            ret = requests.get(url, headers=headers, timeout=5)
            success = True
        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.ProxyError:
            pass
    return ret


def get_collects(url):
    main_page = get_url(url)
    main_page.encoding = 'utf-8'

    paths = [
        ['html', 'body', 'div', 'ul', 'li', 'p', 'a'],
        ['html', 'body', 'div', 'ul', 'li', 'p', 'a'],
        ['html', 'body', 'div', 'ul', 'li', 'span'],
        ['html', 'body', 'center', 'div', 'a']
    ]
    path_attrs = [
        [{}, {}, {'class': 'hezi'}, {}, {}, {'class': 'biaoti'}, {}],
        [{}, {}, {'class': 'hezi'}, {}, {}, {'class': 'biaoti'}, {}],
        [{}, {}, {'class': 'hezi'}, {}, {}, {'class': 'shuliang'}],
        [{}, {}, {}, {'id': 'pages', 'class': 'text-c'}, {}]
    ]
    dests = [None, 'href', None, 'href']
    main_parser = ListParser(paths, path_attrs, dests)
    main_parser.feed(main_page.text)

    collects = main_parser.result[0][:]
    urls = main_parser.result[1][:]
    totals = [int(count[:-1]) for count in main_parser.result[2][:]]

    domain = 'https://www.meituri.com'
    for page in main_parser.result[3][1:-1]:
        page_url = domain + page
        page_response = get_url(page_url)
        page_response.encoding = 'utf-8'

        page_parser = ListParser(paths, path_attrs, dests)
        page_parser.feed(page_response.text)

        collects.extend(page_parser.result[0])
        urls.extend(page_parser.result[1])
        totals.extend([int(count[:-1]) for count in page_parser.result[2][:]])

    return (collects, urls, totals)


def get_imgs(url):
    first_response = get_url(url)
    first_response.encoding = 'utf-8'

    paths = [
        ['html', 'body', 'div', 'img'],
        ['html', 'body', 'div', 'img'],
        ['html', 'body', 'center', 'div', 'a']
    ]
    path_attrs = [
        [{}, {}, {'class': 'content'}, {}],
        [{}, {}, {'class': 'content'}, {}],
        [{}, {}, {}, {'id': 'pages'}, {}]
    ]
    dests = ['src', 'alt', 'href']
    first_parser = ListParser(paths, path_attrs, dests)
    first_parser.feed(first_response.text)

    img_urls = first_parser.result[0][:]
    img_names = first_parser.result[1][:]
    pages = first_parser.result[1][1:-1]

    def add_page(page_url):
        page_response = get_url(page_url)
        page_response.encoding = 'utf-8'

        page_parser = ListParser(paths, path_attrs, dests)
        page_parser.feed(page_response.text)

        img_urls.extend(page_parser.result[0])
        img_names.extend(page_parser.result[1])

        for new_url in page_parser.result[2][1:-1]:
            if new_url not in pages:
                pages.append(new_url)
                add_page(new_url)

    for page_url in first_parser.result[2][1:-1]:
        add_page(page_url)

    return (img_names, img_urls)


def download_img(path, url):
    img = get_url(url)
    with open(path, 'wb') as f:
        for chunk in img.iter_content(4096):
            f.write(chunk)
    print('download complete: ' + path)


def validate(name):
    specials = '/\\:*?"<>|'
    ret = name
    for c in specials:
        ret = ret.replace(c, '-')
    ret = ret.strip()
    return ret


class MetaData(object):
    def __init__(self, filename):
        self.filename = filename
        self.conn = sqlite3.connect('meta.db')
        self.count = 0
        cursor = self.conn.cursor()
        cursor.execute('''
        create table if not exists collections(
            name varchar(256) primary key not null,
            url varchar(256) not null,
            total integer not null)
        ''')
        cursor.execute('''
        create table if not exists images(
            collect_name varchar(256) not null,
            name varchar(256) not null,
            url varchar(256) not null,
            ok boolean not null default false,
            primary key (collect_name, name),
            foreign key (collect_name) references collections(name)
        )''')
        self.conn.commit()

    def add_collect(self, names, urls, totals):
        data = [(names[i], urls[i], totals[i]) for i in range(len(names))]
        cursor = self.conn.cursor()
        cursor.executemany('''
            insert or replace into collections(name, url, total) values(?, ?, ?)
        ''', data)
        self.conn.commit()

    def add_image(self, collect_name, names, urls):
        data = [(collect_name, names[i], urls[i]) for i in range(len(names))]
        cursor = self.conn.cursor()
        cursor.executemany('''
            insert or ignore into images(collect_name, name, url) values(?, ?, ?)
        ''', data)
        self.conn.commit()

    def finish(self):
        cursor = self.conn.cursor()
        cursor.execute('select name, url, total from collections')
        for name, url, total in cursor:
            count = self.conn.cursor()
            count.execute('''
            select count(*)
            from images
            where collect_name = ?
            ''', (name, ))
            count = count.fetchone()[0]
            if count < total:
                img_names, img_urls = get_imgs(url)
                self.add_image(name, img_names, img_urls)
            ok_count = self.conn.cursor()
            ok_count.execute('''
            select count(*)
            from images
            where collect_name = ?
            and ok = true
            ''', (name, ))
            ok_count = ok_count.fetchone()[0]
            if ok_count == total:
                continue
            imgs = self.conn.cursor()
            imgs.execute('''
            select name, url
            from images
            where collect_name = ?
            and ok = false
            ''', (name, ))
            v_name = validate(name)
            if not os.path.exists(v_name):
                os.mkdir(v_name)
            for img_name, img_url in imgs:
                v_img_name = validate(img_name)
                download_img(os.path.join(v_name, v_img_name+'.jpg'), img_url)
                update = self.conn.cursor()
                update.execute('''
                update images
                set ok = true
                where collect_name = ?
                and name = ?''', (name, img_name))
                self.count = self.count + 1
                if (self.count % 10 == 0):
                    self.conn.commit()
                    self.count = 0
            self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()


if __name__ == '__main__':
    try:
        meta = MetaData('meta.db')
        collect_urls = [
            'https://www.meituri.com/x/37/',
            'https://www.meituri.com/x/82/',
            'https://www.meituri.com/x/86/',
            'https://www.meituri.com/x/95/',
            'https://www.meituri.com/t/459/',
            'https://www.meituri.com/t/786/',
            'https://www.meituri.com/t/797/',
            'https://www.meituri.com/t/2434/',
            'https://www.meituri.com/t/4640/',
            'https://www.meituri.com/t/5105/',
            'https://www.meituri.com/t/5108/',
            'https://www.meituri.com/t/5109/',
            'https://www.meituri.com/t/5110/',
            'https://www.meituri.com/t/5178/',
            'https://www.meituri.com/t/5495/',
            'https://www.meituri.com/t/5496/',
            'https://www.meituri.com/t/5497/',
            'https://www.meituri.com/t/5498/',
            'https://www.meituri.com/t/5499/',
            'https://www.meituri.com/t/5500/',
            'https://www.meituri.com/t/5501/',
            'https://www.meituri.com/t/5502/',
            'https://www.meituri.com/t/5503/',
            'https://www.meituri.com/t/5504/',
            'https://www.meituri.com/t/5505/',
            'https://www.meituri.com/t/5506/',
            'https://www.meituri.com/t/5507/',
            'https://www.meituri.com/t/5508/',
            'https://www.meituri.com/t/5509/',
            'https://www.meituri.com/t/5510/',
            'https://www.meituri.com/t/5511/',
            'https://www.meituri.com/t/5512/',
            'https://www.meituri.com/t/5513/',
            'https://www.meituri.com/t/5514/',
            'https://www.meituri.com/t/5515/',
            'https://www.meituri.com/t/5516/',
            'https://www.meituri.com/t/5521/'
        ]
        for collect_url in collect_urls:
            collects, urls, totals = get_collects(collect_url)
            meta.add_collect(collects, urls, totals)
        meta.finish()
        meta.close()
    except KeyboardInterrupt:
        meta.close()
