# coding:utf-8
"""Pixiv components."""
import json
import os
import random
import re
import sqlite3
from datetime import date

import requests
from bs4 import BeautifulSoup

from modules import exception
from modules.misc import GlobalVar, name_verify

# Define misc
_LOGIN_URL = 'https://accounts.pixiv.net/'
_USER_URL = 'https://www.pixiv.net/ajax/user/'
_ILLUST_URL = 'https://www.pixiv.net/ajax/illust/'
_ROOT_URL = 'https://www.pixiv.net/'
_SAUCENAO_URL = 'https://saucenao.com/search.php'


def login(se, c) -> bool:
    """Resolve string-like cookies and set it to session."""
    cookie = c.split('; ')
    cookie_jar = requests.cookies.RequestsCookieJar()
    for item in cookie:
        [name, value] = item.split('=')
        cookie_jar.set(name, value, domain='pixiv.net')
    se.cookies.update(cookie_jar)
    return True
    # try:
    #     with se.get(_LOGIN_URL + 'login',
    #                 proxies=proxy,
    #                 timeout=5) as pk_res:
    #         pk_html = BeautifulSoup(pk_res.text, 'lxml')
    #     pk_node = pk_html.find('input', attrs={'name': 'post_key'})
    #     if not pk_node:
    #         raise globj.ResponseError('Cannot fetch post key.')
    #
    #     login_form = {'password': pw,
    #                   'pixiv_id': uid,
    #                   'post_key': pk_node['value'],
    #                   'User-Agent': random.choice(globj.GlobalVar.user_agent)}
    #     with requests.post(_LOGIN_URL + 'api/login',
    #                        proxies=proxy,
    #                        data=login_form,
    #                        cookies=se.cookies,
    #                        timeout=5) as login_res:
    #         login_json = json.loads(login_res.text)['body']
    #         print(login_json)
    #         if 'validation_errors' in login_json:
    #             raise globj.ValidationError(login_json['validation_errors'])
    #         elif 'success' in login_json:
    #             se.cookies.update(login_res.cookies)
    #             return True
    #         else:
    #             return False
    # except requests.Timeout:
    #     raise requests.Timeout('Timeout during login.')
    # except (globj.ResponseError, globj.ValidationError):
    #     raise


def get_user(se, proxy: dict) -> tuple:
    """Get username and pixiv id."""
    try:
        with se.get(_ROOT_URL,
                    proxies=proxy,
                    timeout=5,
                    headers={
                        'Referer': 'https://www.pixiv.net/',
                        'User-Agent': random.choice(GlobalVar.user_agent)}
                    ) as user_res:
            user_info = re.findall(r'"userData":{"id":"(\d{1,10})","pixivId":"(.*)","name":"(.*)","profileImg":',
                                   user_res.text)

        if not user_info:
            raise exception.ResponseError('Cannot fetch user info.')

        user_id = user_info[0][0]
        user_name = user_info[0][2]
        return user_id, user_name
    except requests.Timeout:
        raise requests.Timeout('Timeout during getting user info.')
    except exception.ResponseError:
        raise


def get_following(se, proxy: dict) -> dict:
    """Get the list of loginned user's following."""
    try:
        with se.get(_ROOT_URL + 'bookmark.php',
                    params={'type': 'user'},
                    headers={'User-Agent': random.choice(GlobalVar.user_agent)},
                    proxies=proxy,
                    timeout=5) as fo_res:
            fo_html = BeautifulSoup(fo_res.text, 'lxml')
        fo_node = fo_html.find_all('div', class_='userdata')
        if not fo_node:
            raise exception.ResponseError('Cannot fetch following info.')

        fo_info = {ele.a['data-user_id']: ele.a['data-user_name'] for ele in fo_node}
        return fo_info
    except requests.Timeout:
        raise requests.Timeout('Timeout during getting following info.')
    except exception.ResponseError:
        raise


def get_new(se, proxy: dict = None, num: int = 0, user_id: str = None) -> set:
    """
    Get new items of following or specified user.
    Args:
        se: Session instance.
        proxy: (optinal) the proxy used.
        num: (optinal when user_id specified) the number of illustration
            will be downloaded. If user_id specified and num omitted,
            all illustration will be downloaded.
        user_id: (optinal) the id of the aimed user. If not given, the new
            illustration will be fetched from following.
    Return:
        A set of pixiv ids fetched.
    """
    try:
        item_dic = {}
        if user_id:  # Fetch user's new illustration
            with se.get(_USER_URL + user_id + '/profile/all',
                        headers={'User-Agent': random.choice(GlobalVar.user_agent)},
                        proxies=proxy,
                        timeout=5) as user_res:
                user_json = json.loads(user_res.text)
            if user_json['error']:
                raise exception.ResponseError(user_json['message'] + '(user pic)')
            user_json = user_json['body']
            if user_json['manga'] and user_json['illusts']:  # Combine illustration and comic into one dict
                item_dic = {**user_json['illusts'], **user_json['manga']}
            else:
                item_dic = user_json['manga'] if user_json['manga'] else user_json['illusts']

        else:  # Fetch following's new illustration
            if num // 20 + 1 > 100:  # the limitation of page number is 100
                pn = 100
            else:
                pn = num // 20 + 1 if num else 0
            for p in range(pn):
                with se.get(_ROOT_URL + 'bookmark_new_illust.php',
                            params={'p': str(p + 1)},
                            headers={'User-Agent': random.choice(GlobalVar.user_agent)},
                            proxies=proxy,
                            timeout=5) as new_res:
                    new_html = BeautifulSoup(new_res.text, 'lxml')
                new_node = new_html.find(id='js-mount-point-latest-following')
                if not new_node:
                    raise exception.ResponseError('Cannot fetch new following items.')
                p_json = json.loads(new_node['data-items'])
                item_dic.update({item['illustId']: None for item in p_json})

        item_set = set()
        for item in item_dic:
            item_set.add(item)
            if len(item_set) == num:
                return item_set
        return item_set

    except requests.Timeout:
        raise requests.Timeout('Timeout during getting new items.')
    except exception.ResponseError:
        raise


def get_detail(se, pid: str, proxy: dict = None) -> dict:
    """
    Get detail of specified illustration.
    Args:
        se: Session instance.
        pid: An id of illustration.
        proxy: (optinal) the proxy used.
    Return:
        A dict contains detail of the illustration.
    """
    re_thumb = re.compile(r'540x540_70')

    try:
        with se.get(_ILLUST_URL + pid,
                    headers={'User-Agent': random.choice(GlobalVar.user_agent)},
                    proxies=proxy,
                    timeout=5) as item_detail:
            item_json = json.loads(item_detail.text)
        if item_json['error']:
            raise exception.ResponseError(item_json['message'] + '(illust detail)')

        item_json = item_json['body']
        create_date = item_json['createDate'].split('T')[0]
        return {
            'illustId': item_json['illustId'],
            'illustTitle': item_json['illustTitle'],
            'createDate': create_date,
            'url': item_json['urls']['original'],
            'thumb': re_thumb.sub('150x150', item_json['urls']['small']),
            'userId': item_json['userId'],
            'userName': item_json['userName'],
            'pageCount': item_json['pageCount']
        }
    except requests.Timeout:
        raise requests.Timeout('Timeout during getting illust detail.')
    except exception.ResponseError:
        raise


def saucenao(path: str, sim: float):
    """Search pixiv id by picture, use sauceNAO engine."""
    try:
        with open(path, 'rb') as pic:
            files = {'file': ('file_name', pic)}  # Avoid requests cannot upload non-ascii filename
            res = requests.post(_SAUCENAO_URL, files=files)
        res_html = BeautifulSoup(res.text, 'lxml')
        for item in res_html.find_all('td', class_='resulttablecontent'):
            similarity = item.find('div', class_='resultsimilarityinfo').string
            title = item.find('div', class_='resultcontentcolumn')
            if float(similarity[:-1]) >= sim and title.strong.string == 'Pixiv ID: ':
                return title.a.string
        return None
    except FileNotFoundError:
        raise
    except requests.Timeout:
        raise requests.Timeout('Timeout during searching id by picture.')


def path_name(item: dict, save_path: str, folder_rule: dict = None, file_rule: dict = None) -> tuple:
    """
    Create file name and path.
    Args:
        item: An instance generated by get_new().
        save_path: Save path.
        folder_rule: A pattern dictionary to describe how to create folder tree.
        file_rule: A pattern dictionary to describe how to create file name.
            Rule dict should like this: {0: 'id', 1: 'name', ...}
    Return:
        A tuple. The first value is save path, the second one is file name.
    """
    if folder_rule is None:
        folder_name = item['userId']  # Default folder name: userId
    else:
        folder_name = ''
        for i in range(len(folder_rule)):
            next_name = name_verify(str(item[folder_rule[i]]), item['userId'])
            folder_name = os.path.join(folder_name, next_name)
        folder_name = os.path.join(save_path, folder_name)

    if file_rule is None:
        file_name = item['illustId']  # Default folder name: illustId
    else:
        raw = (name_verify(str(item[file_rule[i]]), item['userId']) for i in range(len(file_rule)))
        file_name = '_'.join(raw)  # File name without page number and ext

    return folder_name, file_name


def download_pic(se, proxy: dict, item: dict, path: tuple, page: int):
    """
    Download illustration.
    Args:
        se: Session instance.
        proxy: (Optinal) The proxy used.
        item: An instance generated by get_new().
        path: Save path. A tuple generated by path_name().
        page: The current page number.
    """
    referer = 'https://www.pixiv.net/member_illust.php?mode=medium&illust_id=' + item['illustId']
    re_page = re.compile(r'_p0')

    real_url = re_page.sub('_p' + str(page), item['url']) if item['pageCount'] > 1 else item['url']
    try:  # Prevent threads starting at same time
        os.makedirs(path[0])
        print('mkdir:', path[0])
    except FileExistsError:
        pass
    file_name = ''.join((path[1], '_p', str(page), os.path.splitext(real_url)[1]))
    file_path = os.path.join(path[0], file_name)
    if not os.path.exists(file_path):  # If file exists, skip it
        print('downloading', file_path)
        header = {'Referer': referer,
                  'User-Agent': random.choice(GlobalVar.user_agent)}
        se.headers.update(header)
        try:
            with se.get(real_url,
                        headers=header,
                        proxies=proxy,
                        stream=True,
                        timeout=5) as pic_res:
                with open(file_path, 'ab') as data:
                    for chunk in pic_res.iter_content():
                        data.write(chunk)
        except requests.Timeout:
            raise requests.Timeout('Timeout during retrieving', item['url'])
    else:
        print('skip', file_path)


################
# 数据库操作函数 #
################


def fetcher(pid: str = None, pname: str = None, uid: str = None,
            uname: str = None, t_upper: str = '2007-01-01', t_lower: str = str(date.today())):
    """
    Fetch illustration info out of database. Run it in thread.
    At least one parameter must be passed in.
    Args:
        pid: Illustration id. Once pid is specified, the other args are ignored.
            Return a dictionary of illustration info.
        pname: (optinal) The name of illustration. Support wildcard.
        uid: (optinal) The id of user.
        uname: (optinal) The name of user. Support wildcard.
        t_upper: (optinal) Fetch illustration AFTER this time. Format: YYYY-MM-DD.
        t_lower: (optinal) Fetch illustration BEFORE this time. Format: YYYY-MM-DD.
    Return:
        If pid specified, return a dictionary, or return a generator of required illustration info.
    """
    try:
        pdb = sqlite3.connect('database.db')
        cursor = pdb.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS PIXIV(
                ILLUSTID    TEXT    PRIMARY KEY NOT NULL,
                ILLUSTTITLE TEXT    NOT NULL,
                CREATEDATE  TEXT    NOT NULL,
                URL         TEXT    NOT NULL,
                THUMB       TEXT    NOT NULL,
                USERID      TEXT    NOT NULL,
                USERNAME    TEXT    NOT NULL,
                PAGECOUNT   INT     NOT NULL);''')

        if pid:  # If pid specified, the other args are ignored
            cursor.execute("SELECT * FROM PIXIV WHERE ILLUSTID = '{0}'".format(pid))
            result = cursor.fetchone()
            return {
                'illustId': result[0],
                'illustTitle': result[1],
                'createDate': result[2],
                'url': result[3],
                'thumb': result[4],
                'userId': result[5],
                'userName': result[6],
                'pageCount': result[7]
            } if result else None
        else:
            select_str = "CREATEDATE >= '{0}' AND CREATEDATE <= '{1}'".format(t_upper, t_lower)
            if pname:
                select_str = "{0} AND ILLUSTTITLE GLOB '{1}'".format(select_str, pname)
            if uid:
                select_str = "{0} AND USERID = '{1}'".format(select_str, uid)
            if uname:
                select_str = "{0} AND USERNAME GLOB '{1}'".format(select_str, uname)
            cursor.execute('SELECT * FROM PIXIV WHERE ' + select_str)
            return ({
                'illustId': row[0],
                'illustTitle': row[1],
                'createDate': row[2],
                'url': row[3],
                'thumb': row[4],
                'userId': row[5],
                'userName': row[6],
                'pageCount': row[7]
            } for row in cursor)
    except sqlite3.OperationalError as e:
        print(repr(e))
        return None


def pusher(all_item: list):
    """
    Push illustration info into database. Run it in thread.
    Args:
        all_item: A list of dictionary that contains the illustration info.
    """
    pdb = sqlite3.connect('database.db')
    cursor = pdb.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS PIXIV(
        ILLUSTID    TEXT    PRIMARY KEY NOT NULL,
        ILLUSTTITLE TEXT    NOT NULL,
        CREATEDATE  TEXT    NOT NULL,
        URL         TEXT    NOT NULL,
        THUMB       TEXT    NOT NULL,
        USERID      TEXT    NOT NULL,
        USERNAME    TEXT    NOT NULL,
        PAGECOUNT   INT     NOT NULL);''')

    data = ((
        item['illustId'],
        item['illustTitle'],
        str(item['createDate']),
        item['url'],
        item['thumb'],
        item['userId'],
        item['userName'],
        item['pageCount']
    ) for item in all_item)
    cursor.executemany('INSERT INTO PIXIV VALUES (?, ?, ?, ?, ?, ?, ?, ?)', data)
    pdb.commit()
    pdb.close()


def cleaner():
    """Clear database info cache."""
    pdb = sqlite3.connect('database.db')
    cursor = pdb.cursor()
    cursor.execute('''SELECT NAME FROM SQLITE_MASTER WHERE TYPE='table';''')
    tables = cursor.fetchall()
    for name in tables[0]:
        cursor.execute('''DELETE FROM {0};'''.format(name))
    pdb.commit()
    pdb.close()


if __name__ == '__main__':
    pass
