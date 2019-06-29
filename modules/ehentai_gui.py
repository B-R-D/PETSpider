# coding:utf-8
"""GUI components for Ehentai tab."""
import os
import re
from functools import partial

import requests
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QFormLayout, QWidget, QGroupBox, QLineEdit, QPushButton,
                             QCheckBox, QLabel, QSplitter, QFileDialog, QFrame, QMessageBox, QTableWidget, QHeaderView,
                             QAbstractItemView, QTableWidgetItem)

from modules import globj, ehentai


class LoginWidget(QWidget):
    login_success = pyqtSignal(str, tuple)

    def __init__(self, glovar):
        super().__init__()
        self.glovar = glovar
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)

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
            self.verify_thread.except_signal.connect(globj.show_messagebox)
            self.verify_thread.finished.connect(partial(self.set_disabled, False))
            self.verify_thread.start()
        else:
            self.login_thread = LoginThread(self, self.glovar.session, proxy, password, username)
            self.login_thread.login_success.connect(self.set_cookies)
            self.login_thread.except_signal.connect(globj.show_messagebox)
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
            ehentai.login(self.session, proxy=self.proxy, pw=self.pw, uid=self.uid)
            info = ehentai.account_info(self.session, self.proxy)
        except requests.exceptions.RequestException as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except globj.ValidationError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '错误', '登陆名或密码错误。')
        except globj.ResponseError as e:
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
            info = ehentai.account_info(self.session, self.proxy)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except globj.IPBannedError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, 'IP被封禁',
                                    '当前IP已被封禁，将在{0}小时{1}分{2}秒后解封。'.format(e.args[0], e.args[1], e.args[2]))
        except globj.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.verify_success.emit(info)


class FetchInfoThread(QThread):
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
            info = ehentai.information(self.session, self.proxy, self.addr)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except globj.IPBannedError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, 'IP被封禁',
                                    '当前IP已被封禁，将在{0}小时{1}分{2}秒后解封。'.format(e.args[0], e.args[1], e.args[2]))
        except globj.WrongAddressError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '地址错误',
                                    '请输入正确的画廊地址。')
        except globj.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.fetch_success.emit(info)


class AddQueueThread(QThread):
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
            info = ehentai.information(self.session, self.proxy, self.addr)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except globj.IPBannedError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, 'IP被封禁',
                                    '当前IP已被封禁，将在{0}小时{1}分{2}秒后解封。'.format(e.args[0], e.args[1], e.args[2]))
        except globj.WrongAddressError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '地址错误',
                                    '请输入正确的画廊地址。')
        except globj.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.fetch_success.emit(info)


class DownloadThumbThread(QThread):
    download_success = pyqtSignal(dict)

    def __init__(self, session, proxy, info):
        super().__init__()
        self.session = session
        self.proxy = proxy
        self.info = info

    def run(self):
        path = ehentai.download_thumb(self.session, self.proxy, self.info)
        if path:
            self.info['thumb_path'] = path
            self.download_success.emit(self.info)


class MainWidget(QWidget):
    logout_sig = pyqtSignal(str)

    def __init__(self, glovar, info):
        super().__init__()
        self.glovar = glovar
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.refresh_thread = QThread()
        self.fetch_thread = QThread()
        self.thumb_thread = QThread()
        self.current = dict()
        self.que_dict = dict()

        self.ledit_addr = globj.LineEditor()
        self.btn_get = QPushButton('获取信息')
        self.btn_get.clicked.connect(self.fetch_info)
        self.btn_add = QPushButton('加入队列')
        self.btn_add.clicked.connect(self.add_que)
        self.btn_del = QPushButton('移除选定')
        self.btn_start = QPushButton('开始队列')

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
        hlay_acts = QHBoxLayout()
        hlay_acts.addStretch(1)
        hlay_acts.addWidget(self.btn_get)
        hlay_acts.addWidget(self.btn_add)
        hlay_acts.addWidget(self.btn_del)
        hlay_acts.addWidget(self.btn_start)
        hlay_acts.addStretch(1)

        vlay_left = QVBoxLayout()
        vlay_left.addLayout(hlay_addr)
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
                self.fetch_thread = FetchInfoThread(self, self.glovar.session, self.glovar.proxy, addr)
                self.fetch_thread.fetch_success.connect(self.fetch_info_succeed)
                self.fetch_thread.except_signal.connect(globj.show_messagebox)
                self.fetch_thread.finished.connect(self.fetch_info_finished)
                self.fetch_thread.start()
            else:
                globj.show_messagebox(self, QMessageBox.Warning, '错误', '画廊地址输入错误！')
                self.btn_get.setDisabled(False)
        else:
            globj.show_messagebox(self, QMessageBox.Warning, '错误', '请输入画廊地址！')
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
        addr = origin + '/' if origin[-1] != '/' else origin

        if addr == self.current['addr']:  # Current info avaliable and address doesn't change
            self.current['status'] = 'pending'  # Add key to describe status
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

            self.que_dict[self.current['addr']] = self.current

        else:  # When current info has not fetched but addr served or changed, get info
            if self.ledit_addr.text():
                self.btn_add.setDisabled(True)
                self.btn_get.setDisabled(True)
                if re.match(r'(https?://)?e[x-]hentai.org/g/\d{1,7}/\w{10}/', addr):  # Check legality
                    self.fetch_thread = FetchInfoThread(self, self.glovar.session, self.glovar.proxy, addr)
                    self.fetch_thread.fetch_success.connect(self.add_que)
                    self.fetch_thread.except_signal.connect(globj.show_messagebox)
                    self.fetch_thread.finished.connect(self.fetch_info_finished)
                    self.fetch_thread.start()
                else:
                    globj.show_messagebox(self, QMessageBox.Warning, '错误', '画廊地址输入错误！')
                    self.fetch_info_finished()
            else:
                globj.show_messagebox(self, QMessageBox.Warning, '错误', '请输入画廊地址！')

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
        self.refresh_thread.except_signal.connect(globj.show_messagebox)
        self.refresh_thread.finished.connect(partial(self.btn_refresh.setDisabled, False))
        self.refresh_thread.start()

    def refresh_user_info(self, info: tuple):
        self.user_info.setText('下载限额：{0}/{1}'.format(info[0], info[1]))

    def logout_fn(self) -> bool:
        self.btn_logout.setDisabled(True)
        self.thumb_thread.exit(-1)
        self.refresh_thread.exit(-1)
        self.fetch_thread.exit(-1)
        self.logout_sig.emit('ehentai')
        return True


class SaveRuleSettingTab(QWidget):

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.root_path = None
        self.cbox_rename = QCheckBox('按序号重命名')
        self.cbox_rename.setToolTip('勾选后将以图片在画廊中的序号重命名而非使用原图片名。')
        self.ledit_prev = globj.LineEditor()
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
        vlay_ehentai.addWidget(self.cbox_rename)
        vlay_ehentai.addWidget(self.ledit_prev)
        vlay_ehentai.setAlignment(Qt.AlignTop)
        self.setLayout(vlay_ehentai)
        self.setMinimumSize(self.sizeHint())

    def choose_dir(self):
        self.settings.beginGroup('RuleSetting')
        setting_root_path = self.settings.value('ehentai_root_path', os.path.abspath('.'))
        root_path = QFileDialog.getExistingDirectory(self, '选择目录', setting_root_path)
        self.settings.endGroup()
        if root_path:  # When click Cancel, root_path is None
            self.root_path = root_path
            self.previewer()

    def previewer(self):
        if globj.PLATFORM == 'Windows':
            root_path = self.root_path.replace('/', '\\')
        else:
            root_path = self.root_path
        self.ledit_prev.setText(root_path)

    def store(self):
        self.settings.beginGroup('RuleSetting')
        self.settings.setValue('ehentai_root_path', self.root_path)
        self.settings.setValue('ehentai_rename', int(self.cbox_rename.isChecked()))
        self.settings.sync()
        self.settings.endGroup()

    def restore(self):
        self.settings.beginGroup('RuleSetting')
        self.root_path = self.settings.value('ehentai_root_path', os.path.abspath('.'))
        setting_rename = int(self.settings.value('ehentai_rename', False))
        self.settings.endGroup()

        self.ledit_prev.setText(self.root_path)
        self.cbox_rename.setChecked(setting_rename)
        self.previewer()
