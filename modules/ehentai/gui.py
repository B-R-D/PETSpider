# coding:utf-8
"""GUI components for ehentai tab."""
import os
import re
from functools import partial

import requests
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal, QThreadPool, QObject, QRunnable
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QFormLayout, QWidget, QGroupBox, QLineEdit, QPushButton,
                             QCheckBox, QLabel, QSplitter, QFileDialog, QFrame, QMessageBox, QTableWidget, QHeaderView,
                             QAbstractItemView, QTableWidgetItem, QSpinBox)

import modules.ehentai.core as core
from modules import misc, exception


class LoginWidget(QWidget):
    login_success = pyqtSignal(str, tuple)

    def __init__(self, glovar):
        super().__init__()
        self.glovar = glovar
        self.settings = QSettings(os.path.join(os.path.abspath('..'), 'settings.ini'), QSettings.IniFormat)

        self.ledit_un = QLineEdit()
        self.ledit_un.setContextMenuPolicy(Qt.NoContextMenu)
        self.ledit_pw = QLineEdit()
        self.ledit_pw.setContextMenuPolicy(Qt.NoContextMenu)
        self.ledit_pw.setEchoMode(QLineEdit.Password)
        self.cbox_cookie = QCheckBox('保存登陆状态')
        self.btn_ok = QPushButton('登陆')
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.login)
        self.login_thread = None
        self.verify_thread = None

        self.init_ui()

    def set_disabled(self, status: bool):
        self.ledit_pw.setDisabled(status)
        self.ledit_un.setDisabled(status)
        self.cbox_cookie.setDisabled(status)
        self.btn_ok.setDisabled(status)

    def init_ui(self):
        self.settings.beginGroup('Cookies')
        if self.settings.value('ehentai', ''):
            self.ledit_un.setPlaceholderText('(已保存)')
            self.ledit_pw.setPlaceholderText('(已保存)')
            self.cbox_cookie.setChecked(True)
        self.settings.endGroup()

        flay_input = QFormLayout()  # Input area layout
        flay_input.addRow('登陆名', self.ledit_un)
        flay_input.addRow('密码', self.ledit_pw)
        flay_input.addRow(self.cbox_cookie)

        vlay_ok = QVBoxLayout()  # GroupBox layout
        vlay_ok.addLayout(flay_input)
        vlay_ok.addWidget(self.btn_ok, alignment=Qt.AlignHCenter)
        gbox_login = QGroupBox()
        gbox_login.setLayout(vlay_ok)
        gbox_login.setFixedSize(gbox_login.sizeHint())

        vlay_login = QVBoxLayout()  # self layout
        vlay_login.addWidget(gbox_login, alignment=Qt.AlignCenter)
        self.setLayout(vlay_login)

    def login(self):
        """
        Login behavior.
        If cookies in setting is not NULL, test it by fetching limitation,
        or login by username and password.
        """
        self.set_disabled(True)
        password = self.ledit_pw.text()
        username = self.ledit_un.text()
        proxy = self.glovar.proxy

        self.settings.beginGroup('Cookies')
        cookies = self.settings.value('ehentai', '')
        self.settings.endGroup()
        if cookies and not password and not username:
            self.glovar.session.cookies.update(cookies)
            self.verify_thread = VerifyThread(self, self.glovar.session, self.glovar.proxy)
            self.verify_thread.verify_success.connect(self.set_cookies)
            self.verify_thread.except_signal.connect(misc.show_msgbox)
            self.verify_thread.finished.connect(partial(self.set_disabled, False))
            self.verify_thread.start()
        else:
            self.login_thread = LoginThread(self, self.glovar.session, proxy, password, username)
            self.login_thread.login_success.connect(self.set_cookies)
            self.login_thread.except_signal.connect(misc.show_msgbox)
            self.login_thread.finished.connect(partial(self.set_disabled, False))
            self.login_thread.start()

    def set_cookies(self, info):
        self.settings.beginGroup('Cookies')
        if self.cbox_cookie.isChecked():
            self.settings.setValue('ehentai', self.glovar.session.cookies)
        else:
            self.settings.setValue('ehentai', '')
        self.settings.sync()
        self.settings.endGroup()
        self.login_success.emit('ehentai', info)
        self.set_disabled(False)

    def clear_cookies(self):
        self.ledit_un.clear()
        self.ledit_un.setPlaceholderText('')
        self.ledit_pw.clear()
        self.ledit_pw.setPlaceholderText('')
        self.cbox_cookie.setChecked(False)


class LoginThread(QThread):
    login_success = pyqtSignal(tuple)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy, pw, uid):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.pw = pw
        self.uid = uid

    def run(self):
        try:
            core.login(self.session, proxy=self.proxy, pw=self.pw, uid=self.uid)
            info = core.account_info(self.session, self.proxy)
        except requests.exceptions.RequestException as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except exception.ValidationError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '错误', '登陆名或密码错误。')
        except exception.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.login_success.emit(info)


class VerifyThread(QThread):
    verify_success = pyqtSignal(tuple)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy

    def run(self):
        try:
            info = core.account_info(self.session, self.proxy)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except exception.IPBannedError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, 'IP被封禁',
                                    '当前IP已被封禁，将在{0}小时{1}分{2}秒后解封。'.format(e.args[0], e.args[1], e.args[2]))
        except exception.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.verify_success.emit(info)


class FetchDataThread(QThread):
    fetch_success = pyqtSignal(dict)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy: dict, addr: str):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.addr = addr

    def run(self):
        try:
            info = core.information(self.session, self.proxy, self.addr)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except exception.IPBannedError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, 'IP被封禁',
                                    '当前IP已被封禁，将在{0}小时{1}分{2}秒后解封。'.format(e.args[0], e.args[1], e.args[2]))
        except exception.WrongAddressError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '地址错误',
                                    '请输入正确的画廊地址。')
        except exception.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.fetch_success.emit(info)


class DownloadSignals(QObject):
    download_success = pyqtSignal(dict, dict, int, str, bool, bool)
    retry_signal = pyqtSignal(dict, dict, str, bool, bool, str)
    except_signal = pyqtSignal(object, int, str, str)


class DownloadPicThread(QRunnable):
    def __init__(self, parent, sess, proxy, info: dict, keys: dict, page: int, path: str, rename=False, rewrite=False):
        super().__init__()
        self.parent = parent
        self.sess = sess
        self.proxy = proxy
        self.info = info
        self.keys = keys
        self.path = path
        self.page = page
        self.rn = rename
        self.rw = rewrite
        self.signals = DownloadSignals()

    def run(self):  # Only do retrying when connection error occurs
        try:
            core.download(self.sess, self.proxy, self.info, self.keys, self.page, self.path, self.rn, self.rw)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            self.signals.retry_signal.emit(self.info, self.keys, self.path, self.rn, True, repr(e))
        except exception.LimitationReachedError:
            self.signals.except_signal.emit(self.parent, QMessageBox.Warning, '警告',
                                            '当前IP已达下载限额，请更换代理IP。')
        except (FileNotFoundError, PermissionError) as e:
            self.signals.except_signal.emit(self.parent, QMessageBox.Critical, '错误',
                                            '文件系统错误：\n' + repr(e))
        except exception.ResponseError as e:
            self.signals.except_signal.emit(self.parent, QMessageBox.Critical,
                                            '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.signals.download_success.emit(self.info, self.keys, self.page, self.path, self.rn, self.rw)


class DownloadThumbThread(QThread):
    download_success = pyqtSignal(dict)

    def __init__(self, session, proxy, info):
        super().__init__()
        self.session = session
        self.proxy = proxy
        self.info = info

    def run(self):
        path = misc.download_thumb(self.session, self.proxy, self.info['thumb'])
        if path:
            self.info['thumb_path'] = path
            self.download_success.emit(self.info)


class FetchKeyThread(QThread):
    fetch_success = pyqtSignal(dict, dict)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy: dict, info: dict):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.info = info

    def run(self):
        try:
            keys = core.fetch_keys(self.session, self.proxy, self.info)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except exception.IPBannedError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, 'IP被封禁',
                                    '当前IP已被封禁，将在{0}小时{1}分{2}秒后解封。'.format(e.args[0], e.args[1], e.args[2]))
        except exception.WrongAddressError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '地址错误',
                                    '请输入正确的画廊地址。')
        except exception.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.fetch_success.emit(self.info, keys)


class MainWidget(QWidget):
    logout_sig = pyqtSignal(str)

    def __init__(self, glovar, info):
        super().__init__()
        self.glovar = glovar
        self.settings = QSettings(os.path.join(os.path.abspath('..'), 'settings.ini'), QSettings.IniFormat)
        self.refresh_thread = QThread()
        self.fetch_thread = QThread()
        self.fetch_key_thread = QThread()
        self.thumb_thread = QThread()
        self.current = dict()  # Save current info
        self.current_line = dict()  # Save current downloading line
        self.que_dict = dict()  # Save all items in the queue, the key is addr
        self.remain = set()  # Save remaining/unsuccessful pages
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_count = 0
        self.cancel_download_flag = 0

        self.ledit_addr = misc.LineEditor()
        self.cbox_rename = QCheckBox('按序号重命名')
        self.cbox_rename.setToolTip('勾选后将以图片在画廊中的序号重命名而非使用原图片名。')
        self.cbox_rewrite = QCheckBox('覆盖模式')
        self.cbox_rewrite.setToolTip('勾选后将不会跳过同名文件而是覆盖它。')

        self.sbox_begin_page = QSpinBox()
        font_info = self.sbox_begin_page.fontMetrics()
        font_width = font_info.horizontalAdvance('9') * 8
        font_height = font_info.height()
        self.sbox_begin_page.setRange(1, 9999)
        self.sbox_begin_page.setContextMenuPolicy(Qt.NoContextMenu)
        self.sbox_begin_page.setMinimumSize(font_width, font_height)
        self.sbox_begin_page.setToolTip('将从画廊的该页数开始下载')
        self.sbox_begin_page.valueChanged.connect(self.set_end_page_range)
        self.sbox_end_page = QSpinBox()
        self.sbox_end_page.setRange(1, 9999)
        self.sbox_end_page.setValue(9999)
        self.sbox_end_page.setContextMenuPolicy(Qt.NoContextMenu)
        self.sbox_end_page.setMinimumSize(font_width, font_height)
        self.sbox_end_page.setToolTip('将下载至画廊的该页数')

        self.btn_get = QPushButton('获取信息')
        self.btn_get.clicked.connect(self.fetch_info)
        self.btn_add = QPushButton('加入队列')
        self.btn_add.clicked.connect(self.add_que)
        self.btn_remove = QPushButton('移除选定')
        self.btn_remove.clicked.connect(self.remove_row)
        self.btn_start = QPushButton('开始队列')
        self.btn_start.clicked.connect(self.start_que_before)

        self.user_info = QLabel('下载限额：{0}/{1}'.format(info[0], info[1]))
        self.btn_refresh = QPushButton('刷新限额')
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_logout = QPushButton('退出登陆')
        self.btn_logout.clicked.connect(self.logout_fn)

        self.thumbnail = QLabel()
        self.thumbnail.setFrameShape(QFrame.StyledPanel)
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumb_default = QPixmap(os.path.join(self.glovar.home, 'icon', 'ehentai.png'))
        self.thumb_default = self.thumb_default.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.settings.beginGroup('MiscSetting')
        self.show_thumb_flag = int(self.settings.value('thumbnail', True))
        self.settings.endGroup()

        self.info = QLabel()
        self.info.setFrameShape(QFrame.StyledPanel)
        self.info.setFixedWidth(250)
        self.info.setAlignment(Qt.AlignTop)
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.info.setContextMenuPolicy(Qt.NoContextMenu)

        self.que = QTableWidget()
        self.que.cellPressed.connect(self.change_info)
        self.que.itemSelectionChanged.connect(self.set_default_thumb)
        self.que.setColumnCount(5)
        self.que.setWordWrap(False)
        self.que.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.que.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.que.verticalScrollBar().setContextMenuPolicy(Qt.NoContextMenu)
        self.que.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.que.setHorizontalHeaderLabels(['画廊名', '大小', '页数', '状态', '地址'])
        self.que.setColumnHidden(4, True)
        self.que.horizontalHeader().setSectionsClickable(False)
        self.que.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.que.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.que.horizontalHeader().setStyleSheet('QHeaderView::section{background-color:#E3E0D1;}')
        self.que.horizontalHeader().setHighlightSections(False)

        self.init_ui()

    def init_ui(self):
        hlay_addr = QHBoxLayout()
        hlay_addr.addWidget(QLabel('画廊地址'))
        hlay_addr.addWidget(self.ledit_addr)
        hlay_addr.setStretch(0, 0)
        hlay_cbox = QHBoxLayout()
        hlay_cbox.addWidget(self.cbox_rename)
        hlay_cbox.addWidget(self.cbox_rewrite)
        hlay_cbox.addStretch(1)
        hlay_cbox.addWidget(QLabel('从'))
        hlay_cbox.addWidget(self.sbox_begin_page)
        hlay_cbox.addWidget(QLabel('下载至'))
        hlay_cbox.addWidget(self.sbox_end_page)
        hlay_cbox.addWidget(QLabel('页'))
        hlay_cbox.setAlignment(Qt.AlignLeft)
        hlay_acts = QHBoxLayout()
        hlay_acts.addStretch(1)
        hlay_acts.addWidget(self.btn_get)
        hlay_acts.addWidget(self.btn_add)
        hlay_acts.addWidget(self.btn_remove)
        hlay_acts.addWidget(self.btn_start)
        hlay_acts.addStretch(1)

        vlay_left = QVBoxLayout()
        vlay_left.addLayout(hlay_addr)
        vlay_left.addLayout(hlay_cbox)
        vlay_left.addLayout(hlay_acts)
        left_wid = QWidget()
        left_wid.setLayout(vlay_left)

        vlay_right = QVBoxLayout()
        vlay_right.addWidget(self.user_info, alignment=Qt.AlignHCenter)
        vlay_right.addWidget(self.btn_refresh)
        vlay_right.addWidget(self.btn_logout)
        right_wid = QWidget()
        right_wid.setLayout(vlay_right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.addWidget(left_wid)
        splitter.addWidget(right_wid)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.handle(1).setDisabled(True)

        vlay_info = QVBoxLayout()
        vlay_info.addWidget(self.thumbnail)
        vlay_info.addWidget(self.info)

        hlay_down = QHBoxLayout()
        hlay_down.addLayout(vlay_info)
        hlay_down.addWidget(self.que)

        vlay_main = QVBoxLayout()
        vlay_main.addWidget(splitter)
        vlay_main.addLayout(hlay_down)
        self.setLayout(vlay_main)

        self.thumbnail.setFixedHeight(left_wid.sizeHint().height())
        self.thumbnail.setFixedWidth(250)
        self.thumbnail.setFixedHeight(360)
        self.thumbnail.setPixmap(self.thumb_default)
        if self.show_thumb_flag:  # Cannot put code after show(), or flick
            self.thumbnail.show()
        else:
            self.thumbnail.hide()

    def fetch_info(self):
        """Fetch the info of gallery, using information function."""
        self.btn_get.setDisabled(True)
        origin = self.ledit_addr.text().strip()
        if origin:
            addr = origin + '/' if origin[-1] != '/' else origin
            if re.match(r'(https?://)?e[x-]hentai.org/g/\d{1,7}/\w{10}/', addr):  # Check legality
                self.fetch_thread = FetchDataThread(self, self.glovar.session, self.glovar.proxy, addr)
                self.fetch_thread.fetch_success.connect(self.fetch_info_succeed)
                self.fetch_thread.except_signal.connect(misc.show_msgbox)
                self.fetch_thread.finished.connect(self.fetch_info_finished)
                self.fetch_thread.start()
            else:
                misc.show_msgbox(self, QMessageBox.Warning, '错误', '画廊地址输入错误！')
                self.btn_get.setDisabled(False)
        else:
            misc.show_msgbox(self, QMessageBox.Warning, '错误', '请输入画廊地址！')
            self.btn_get.setDisabled(False)

    def show_info(self, info: dict):
        """Download thumbnail."""
        if self.show_thumb_flag:
            if 'thumb_path' in info:
                thumb = QPixmap()
                if thumb.load(info['thumb_path']):  # If thumbnail is deleted, redownload it
                    self.thumbnail.setPixmap(thumb)
                else:
                    self.thumb_thread = DownloadThumbThread(self.glovar.session, self.glovar.proxy, info)
                    self.thumb_thread.download_success.connect(self.show_thumb)
                    self.thumb_thread.start()
            else:
                self.thumb_thread = DownloadThumbThread(self.glovar.session, self.glovar.proxy, info)
                self.thumb_thread.download_success.connect(self.show_thumb)
                self.thumb_thread.start()
        # Set min height to 0 before text changed to avoid unchangeable sizeHint
        self.info.setMinimumHeight(0)
        self.info.setText(info['name'] + '\n大小：' + info['size'] + '\n页数：' + info['page'])
        self.info.setMinimumHeight(self.info.sizeHint().height())  # Set to sizeHint to change height autometically

    def show_thumb(self, info: dict):
        self.current = info  # Update current which includes thumb_path
        self.thumbnail.setPixmap(QPixmap(info['thumb_path']))

    def add_que(self, info: dict = None):
        """Add current info to queue. If don't have current info, fetch it."""
        if info:
            self.current = info
        origin = self.ledit_addr.text().strip()
        if origin:
            addr = origin + '/' if origin[-1] != '/' else origin
            if self.current and addr == self.current['addr']:  # Current info avaliable and address doesn't change
                self.show_info(self.current)
                row_count = self.que.rowCount()
                self.que.setRowCount(row_count + 1)

                self.que.setItem(row_count, 0, QTableWidgetItem(self.current['name']))
                size = QTableWidgetItem(self.current['size'])
                size.setTextAlignment(Qt.AlignCenter)
                self.que.setItem(row_count, 1, size)
                page = QTableWidgetItem(self.current['page'])
                page.setTextAlignment(Qt.AlignCenter)
                self.que.setItem(row_count, 2, page)
                self.que.setItem(row_count, 3, QTableWidgetItem('等待中'))
                self.que.setItem(row_count, 4, QTableWidgetItem(self.current['addr']))

                self.que.selectRow(row_count)
                self.que_dict[self.current['addr']] = self.current

            else:  # When current info has not fetched but addr served or changed, get info
                if self.ledit_addr.text():
                    self.btn_add.setDisabled(True)
                    self.btn_get.setDisabled(True)
                    if re.match(r'(https?://)?e[x-]hentai.org/g/\d{1,7}/\w{10}/', addr):  # Check legality
                        self.fetch_thread = FetchDataThread(self, self.glovar.session, self.glovar.proxy, addr)
                        self.fetch_thread.fetch_success.connect(self.add_que)
                        self.fetch_thread.except_signal.connect(misc.show_msgbox)
                        self.fetch_thread.finished.connect(self.fetch_info_finished)
                        self.fetch_thread.start()
                    else:
                        misc.show_msgbox(self, QMessageBox.Warning, '错误', '画廊地址输入错误！')
                        self.fetch_info_finished()
                else:
                    misc.show_msgbox(self, QMessageBox.Warning, '错误', '请输入画廊地址！')

    def fetch_info_succeed(self, info: dict):
        """After fetching info successfully, set Current variable."""
        self.current = info  # Set current in case of thumb is turned off
        self.show_info(info)

    def fetch_info_finished(self):
        self.btn_add.setDisabled(False)
        self.btn_get.setDisabled(False)

    def change_info(self, row):
        info = self.que_dict[self.que.item(row, 4).text()]
        self.show_info(info)

    def set_default_thumb(self):
        """Set default thumbnail when no item selected."""
        if not self.que.selectedItems() and self.show_thumb_flag:
            self.thumbnail.setPixmap(self.thumb_default)
            self.info.clear()

    def remove_row(self):
        if self.que.selectedRanges():
            del_row = self.que.selectedRanges()[0].rowCount()
            del_bottom = self.que.selectedRanges()[0].bottomRow()
            for i in range(del_row):
                status = self.que.item(del_bottom, 3).text()
                if status == '等待中' or status == '已完成':
                    self.que.removeRow(del_bottom)
                    del_bottom -= 1
                else:
                    misc.show_msgbox(self, QMessageBox.Warning, '错误', '不能移除下载中的任务，请先停止队列！')
                    break
            if not self.que.rowCount():  # When the queue is empty, clear dict of info,
                self.que_dict.clear()  # in case of one gallery is added repeatedly
            self.set_default_thumb()

    def get_line(self, status1: str, status2: str = '') -> int:
        """Return the first status line number."""
        for i in range(self.que.rowCount()):
            if self.que.item(i, 3).text() == status1 or self.que.item(i, 3).text() == status2:
                return i
        return -1

    def start_que_before(self):
        for i in range(self.que.rowCount()):
            self.que.item(i, 3).setText('等待中')  # Reset the status of all items to waiting
        self.start_que()

    def start_que(self, loop=False):
        if self.que.rowCount():
            if self.btn_start.text() == '开始队列':  # Do not change this when download line 2
                self.btn_start.setText('停止队列')
                self.btn_start.clicked.disconnect(self.start_que_before)
                self.btn_start.clicked.connect(self.stop_que)

            line = self.get_line('等待中') if loop else self.get_line('等待中', '已完成')
            if line >= 0:
                self.que.item(line, 3).setText('准备中')
                info = self.que_dict[self.que.item(line, 4).text()]
                self.current_line['info'] = info
                self.fetch_key_thread = FetchKeyThread(self, self.glovar.session, self.glovar.proxy, info)
                self.fetch_key_thread.except_signal.connect(misc.show_msgbox)
                self.fetch_key_thread.fetch_success.connect(self.fetch_finished)
                self.fetch_key_thread.start()
            else:
                self.current_line = dict()
                self.btn_start.setText('开始队列')
                self.btn_start.clicked.disconnect(self.stop_que)
                self.btn_start.clicked.connect(self.start_que_before)
                misc.show_msgbox(self, QMessageBox.Information, '完成', '队列下载完成！')
        else:
            misc.show_msgbox(self, QMessageBox.Warning, '警告', '下载队列为空！')

    def fetch_finished(self, info, keys):
        self.current_line['keys'] = keys
        line = self.get_line('准备中')
        self.que.item(line, 3).setText('下载中')

        self.settings.beginGroup('RuleSetting')
        root_path = self.settings.value('ehentai_root_path', os.path.abspath('..'))
        self.settings.endGroup()
        self.settings.beginGroup('MiscSetting')
        dl_sametime = int(self.settings.value('dl_sametime', 3))
        self.settings.endGroup()
        self.thread_pool.setMaxThreadCount(dl_sametime)

        rename = self.cbox_rename.checkState()
        rewrite = self.cbox_rewrite.checkState()
        start_page = self.sbox_begin_page.value()
        end_page = self.sbox_end_page.value() if self.sbox_end_page.value() <= int(info['page']) else int(info['page'])
        self.remain = set(range(start_page, end_page + 1))
        self.download(info, keys, root_path, rename, rewrite)

    def download(self, info, keys, root_path, rename, rewrite):
        for num in self.remain:
            thread = DownloadPicThread(self, self.glovar.session, self.glovar.proxy, info, keys, num,
                                       root_path, rename=rename, rewrite=rewrite)
            thread.signals.except_signal.connect(self.download_exception)
            thread.signals.retry_signal.connect(self.retry_exception)
            thread.signals.download_success.connect(self.download_finished)
            self.thread_count += 1
            self.thread_pool.start(thread)

    def retry_exception(self, *args):
        self.thread_count -= 1
        print('Thread error：', args[-1])
        print('Active thread：', self.thread_pool.activeThreadCount(), 'Thread count：', self.thread_count)
        if not self.thread_count and not self.cancel_download_flag:
            print('Redownloading：', self.remain)
            self.download(*args[:-1])

    def download_exception(self, *args):
        self.thread_count -= 1
        if not self.thread_count:
            self.stop_que()
            misc.show_msgbox(*args)

    def download_finished(self, info, keys, page, root_path, rename, rewrite):
        self.thread_count -= 1
        print('Active thread：', self.thread_pool.activeThreadCount(), 'Thread count：', self.thread_count)
        if not self.cancel_download_flag:
            self.remain.remove(page)
            if not self.thread_count:
                if self.remain:
                    print('Redownloading：', self.remain)
                    self.download(info, keys, root_path, rename, rewrite)
                else:
                    line = self.get_line('下载中')
                    self.que.item(line, 3).setText('已完成')
                    self.start_que(True)

    def cancel_download(self):
        self.btn_start.setDisabled(True)
        self.cancel_download_flag = 1
        self.thread_count = self.thread_pool.activeThreadCount()
        self.thread_pool.clear()
        self.fetch_thread.exit(0)
        self.fetch_key_thread.exit(0)
        self.remain = set()
        for i in range(self.que.rowCount()):
            if self.que.item(i, 3).text() == '准备中' or self.que.item(i, 3).text() == '下载中':
                self.que.item(i, 3).setText('等待中')

    def stop_que(self):
        self.cancel_download()
        self.btn_start.setText('开始队列')
        self.btn_start.clicked.disconnect(self.stop_que)
        self.btn_start.clicked.connect(self.start_que_before)
        self.btn_start.setDisabled(False)

    def change_thumb_state(self, new):
        """Change state of whether show thumbnail in setting."""
        self.show_thumb_flag = new
        if self.show_thumb_flag:
            self.thumbnail.show()
        else:
            self.thumbnail.hide()

    def refresh(self):
        """Refresh downloading limitation."""
        self.btn_refresh.setDisabled(True)
        self.refresh_thread = VerifyThread(self, self.glovar.session, self.glovar.proxy)
        self.refresh_thread.verify_success.connect(self.refresh_user_info)
        self.refresh_thread.except_signal.connect(misc.show_msgbox)
        self.refresh_thread.finished.connect(partial(self.btn_refresh.setDisabled, False))
        self.refresh_thread.start()

    def refresh_user_info(self, info: tuple):
        self.user_info.setText('下载限额：{0}/{1}'.format(info[0], info[1]))

    def logout_fn(self) -> bool:
        self.btn_logout.setDisabled(True)
        if self.thread_count:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('正在下载')
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText('下载任务正在进行中，是否退出？')
            msg_box.addButton('确定', QMessageBox.AcceptRole)
            msg_box.addButton('取消', QMessageBox.DestructiveRole)
            reply = msg_box.exec()
            if reply == QMessageBox.AcceptRole:
                self.cancel_download()
                self.thumb_thread.exit(-1)
                self.refresh_thread.exit(-1)
                self.fetch_thread.exit(-1)
                self.thread_pool.waitForDone()
                self.logout_sig.emit('ehentai')
                return True
            else:
                self.btn_logout.setDisabled(False)
                return False
        else:
            self.thumb_thread.exit(-1)
            self.refresh_thread.exit(-1)
            self.fetch_thread.exit(-1)
            self.thread_pool.waitForDone()
            self.logout_sig.emit('ehentai')
            return True

    def set_end_page_range(self, minimun):
        self.sbox_end_page.setRange(minimun, 9999)


class SaveRuleSettingTab(QWidget):

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.root_path = None
        self.ledit_prev = misc.LineEditor()
        self.ledit_prev.setReadOnly(True)
        self.ledit_prev.setContextMenuPolicy(Qt.NoContextMenu)

        self.restore()
        self.init_ui()

    def init_ui(self):
        btn_root = QPushButton('浏览')
        btn_root.clicked.connect(self.choose_dir)
        hlay_root = QHBoxLayout()
        hlay_root.addWidget(QLabel('根目录'))
        hlay_root.addWidget(btn_root)
        vlay_ehentai = QVBoxLayout()
        vlay_ehentai.addLayout(hlay_root)
        vlay_ehentai.addWidget(self.ledit_prev)
        vlay_ehentai.setAlignment(Qt.AlignTop)
        self.setLayout(vlay_ehentai)
        self.setMinimumSize(self.sizeHint())

    def choose_dir(self):
        self.settings.beginGroup('RuleSetting')
        setting_root_path = self.settings.value('ehentai_root_path', os.path.abspath('..'))
        root_path = QFileDialog.getExistingDirectory(self, '选择目录', setting_root_path)
        self.settings.endGroup()
        if root_path:  # When click Cancel, root_path is None
            self.root_path = root_path
            self.previewer()

    def previewer(self):
        if misc.PLATFORM == 'Windows':
            root_path = self.root_path.replace('/', '\\')
        else:
            root_path = self.root_path
        self.ledit_prev.setText(root_path)

    def store(self):
        self.settings.beginGroup('RuleSetting')
        self.settings.setValue('ehentai_root_path', self.root_path)
        self.settings.sync()
        self.settings.endGroup()

    def restore(self):
        self.settings.beginGroup('RuleSetting')
        self.root_path = self.settings.value('ehentai_root_path', os.path.abspath('..'))
        self.settings.endGroup()
        self.ledit_prev.setText(self.root_path)
        self.previewer()
