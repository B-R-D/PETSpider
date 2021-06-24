# coding:utf-8
"""E(x)hentai components."""
import os
import re

import requests
from bs4 import BeautifulSoup

import modules.misc as misc
from modules import exception

_LOGIN_URL = 'https://forums.e-hentai.org/index.php'
_ACCOUNT_URL = 'https://e-hentai.org/home.php'
_EXHENTAI_URL = 'https://exhentai.org/'


def _ban_checker(html: BeautifulSoup):
    if not html.head and 'Your IP address has been' in html.body.p.string:
        msg = html.body.p.string
        match_h = re.match(r'.* (\d{1,2}) hours', msg)
        match_m = re.match(r'.* (\d{1,2}) minutes', msg)
        match_s = re.match(r'.* (\d{1,2}) seconds', msg)
        h = match_h.group(1) if match_h else 0
        m = match_m.group(1) if match_m else 0
        s = match_s.group(1) if match_s else 0
        raise exception.IPBannedError(h, m, s)


def login(se, proxy: dict, uid: str, pw: str) -> bool:
    """
    Login and set cookies for exhentai.
    Exceptions:
        globj.ValidationError: Raised when username/pw is wrong, or have no permission to get into exhentai.
        globj.ResponseError: Raised when server sends abnormal response(include AttributeError).
    """
    try:
        with se.post(_LOGIN_URL,
                     params={'act': 'Login', 'CODE': '01'},
                     data={'CookieDate': '1', 'UserName': uid, 'PassWord': pw},
                     headers={'User-Agent': misc.USER_AGENT},
                     proxies=proxy,
                     timeout=5) as login_res:
            login_html = BeautifulSoup(login_res.text, 'lxml')
            se.cookies.update(login_res.cookies)  # Set cookies

        if login_html.head.title.string == 'Please stand by...':
            with se.get(_EXHENTAI_URL,
                        proxies=proxy,
                        headers={'User-Agent': misc.USER_AGENT},
                        timeout=5) as ex_res:
                ex_html = BeautifulSoup(ex_res.text, 'lxml')
                if ex_html.head.title.string == 'ExHentai.org':
                    se.cookies.update(ex_res.cookies)  # Set cookies for exhentai
                    return True
                else:
                    raise exception.ValidationError('Login: Cannot get into exhentai.')
        elif login_html.head.title.string == 'Log In':
            raise exception.ValidationError('Login: Incorrect username or password.')
        else:
            raise exception.ResponseError('Login: Abnormal response.')

    except requests.Timeout:
        raise requests.Timeout('Login: Timeout.')
    except AttributeError as e:
        raise exception.ResponseError('Login: ' + repr(e))


def account_info(se, proxy: dict) -> tuple:
    """
    Get download limitation(used/all).
    Exceptions:
        globj.ResponseError: Raised when server sends abnormal response.
    """
    try:
        with se.get(_ACCOUNT_URL,
                    headers={'User-Agent': misc.USER_AGENT},
                    proxies=proxy,
                    timeout=5) as info_res:
            info_html = BeautifulSoup(info_res.text, 'lxml')
        _ban_checker(info_html)
        info_node = info_html.find('div', class_='homebox')
        if info_node:
            limit = info_node('strong')
            return limit[0].string, limit[1].string
        else:
            raise exception.ResponseError('Account_info: Abnormal response.')
    except requests.Timeout:
        raise requests.Timeout('Account_info: Timeout.')


def information(se, proxy: dict, addr: str) -> dict:
    """
    Fetch gallery information, include misc info and thumbnail.
    Args:
        se: Session instance.
        proxy: (Optional) The proxy used.
        addr: Gallery address.
    Exceptions:
        globj.ResponseError: Raised when server sends abnormal response.
    """
    re_thumb = re.compile(r'.*url\((.*)\).*')
    try:
        with se.get(addr,
                    params={'inline_set': 'ts_m'},
                    headers={'User-Agent': misc.USER_AGENT},
                    proxies=proxy,
                    timeout=5) as gallery_res:
            gallery_html = BeautifulSoup(gallery_res.text, 'lxml')
        _ban_checker(gallery_html)
        if 'Gallery not found.' in gallery_html.body.get_text() or 'Key missing' in gallery_html.body.get_text():
            raise exception.WrongAddressError('Wrong address provided.')
        name: str = gallery_html.find('h1', id='gj').string  # Japanese name is prior
        if not name:
            name = gallery_html.find('h1', id='gn').string
        info = gallery_html.find_all('td', class_='gdt2')
        thumb = re_thumb.match(gallery_html.find('div', id='gd1').div['style']).group(1)
        if name and info and thumb:
            return {
                'addr': addr,
                'name': name,
                'size': info[4].string,
                'page': info[5].string[:-6],
                'thumb': thumb
            }
        else:
            raise exception.ResponseError('Information: Abnormal response.')

    except requests.Timeout:
        raise requests.Timeout('Information: Timeout.')
    except AttributeError as e:
        raise exception.ResponseError('Information: ' + repr(e))


def fetch_keys(se, proxy: dict, info: dict) -> dict:
    """
    Fetch keys(imgkeys and showkey) from gallery.
    Args:
        se: Session instance.
        proxy: (Optional) The proxy used.
        info: Information of the gallery.
    Return:
        A dictionary. {'page': imgkey, '0': showkey}
    Exceptions:
        globj.ResponseError: Raised when server sends abnormal response.
    """
    re_imgkey = re.compile(r'https://exhentai\.org/s/(\w{10})/\d*-(\d{1,4})')
    re_showkey = re.compile(r'[\S\s]*showkey="(\w{11})"[\S\s]*')
    gid = info['addr'].split('/')[-3]
    pn = int(info['page']) // 40 + 1  # range(0) has no element
    keys = dict()
    try:
        for p in range(pn):
            with se.get(info['addr'],
                        params={'inline_set': 'ts_m', 'p': p},
                        headers={'User-Agent': misc.USER_AGENT},
                        proxies=proxy,
                        timeout=5) as gallery_res:
                gallery_html = BeautifulSoup(gallery_res.text, 'lxml')
            _ban_checker(gallery_html)

            # Fetch imgkey from every picture
            pics = gallery_html.find_all('div', class_='gdtm')
            for item in pics:
                match = re_imgkey.match(item.a['href'])
                keys[match.group(2)] = match.group(1)

        # Fetch showkey from first picture
        showkey_url = '/'.join(['https://exhentai.org/s', keys['1'], gid + '-1'])
        with se.get(showkey_url,
                    headers={'User-Agent': misc.USER_AGENT},
                    proxies=proxy,
                    timeout=5) as showkey_res:
            showkey_html = BeautifulSoup(showkey_res.text, 'lxml')
        _ban_checker(showkey_html)
        keys['0'] = re_showkey.match(showkey_html('script')[1].string).group(1)
        return keys

    except requests.Timeout:
        raise requests.Timeout('Fetch_keys: Timeout.')
    except AttributeError as e:
        raise exception.ResponseError('Fetch_keys: ' + repr(e))


def download(se, proxy: dict, info: dict, keys: dict, page: int, path: str, rename=False, rewrite=False):
    """
    Download one picture.
    Args:
        se: Session instance.
        proxy: (Optional) The proxy used.
        info: Information of the gallery.
        keys: Keys include imgkeys and showkey.
        page: Page number.
        path: Save root path.
        rename: Control whether rename to origin name/image number.
        rewrite: Overwrite image instead of skipping it.
    Exceptions:
        globj.ResponseError: Raised when server sends abnormal response.
        globj.LimitationReachedError: Raised when reach view limitation.
    """
    gid = info['addr'].split('/')[-3]
    try:
        with se.post(_EXHENTAI_URL + 'api.php',
                     json={'method': 'showpage',
                           'gid': int(gid),
                           'page': int(page),
                           'imgkey': keys[str(page)],
                           'showkey': keys['0']},
                     headers={'User-Agent': misc.USER_AGENT},
                     proxies=proxy,
                     timeout=5) as dl_res:  # Fetch original url of picture
            dl_json = dl_res.json()

        if dl_json.get('error'):  # Wrong imgkey or showkey
            raise exception.ResponseError('Download: ' + dl_json['error'])
        if dl_json.get('i3'):  # Whether Reach limitation
            url_html = BeautifulSoup(dl_json['i3'], 'lxml')
            if url_html.a.img['src'] == 'https://exhentai.org/img/509.gif':
                raise exception.LimitationReachedError(page)

        if dl_json.get('i7'):
            url_html = BeautifulSoup(dl_json['i7'], 'lxml')  # Origin image
            origin = url_html.a['href']
        elif dl_json.get('i3'):
            url_html = BeautifulSoup(dl_json['i3'], 'lxml')  # Showing image is original
            origin = url_html.a.img['src']
        else:
            raise exception.ResponseError('Download: No plenty elements.')

        folder_name = misc.name_verify(info['name'])
        folder_path = os.path.join(path, folder_name)
        try:  # Prevent threads starting at same time
            os.makedirs(folder_path)
            print('mkdir:', folder_path)
        except FileExistsError:
            pass
        with se.get(origin,
                    headers={'User-Agent': misc.USER_AGENT},
                    proxies=proxy,
                    stream=True,
                    timeout=5) as pic_res:
            url = pic_res.url
            if url.split('/')[2] == 'exhentai.org':  # If response cannot redirect(302), raise exception
                raise exception.LimitationReachedError(page)
            file_name = os.path.split(pic_res.url)[-1].rstrip('?dl=1')  # Get file name from url
            if rename:
                file_name = str(page) + os.path.splitext(file_name)[1]
            real_path = os.path.join(folder_path, file_name)
            if not os.path.exists(real_path) or rewrite:  # If file exists or not rewrite, skip it
                if os.path.exists(real_path):
                    os.remove(real_path)
                print('Downloading page {0} to {1}'.format(page, real_path))
                with open(real_path, 'ab') as data:
                    for chunk in pic_res.iter_content():
                        data.write(chunk)
            else:
                print('Skip:', file_name)
    except requests.Timeout:
        raise requests.Timeout('Download: Timeout.')
    except AttributeError as e:
        raise exception.ResponseError('Download: ' + repr(e))


if __name__ == '__main__':
    pass
