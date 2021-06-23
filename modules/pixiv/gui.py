# coding:utf-8
"""GUI components for Pixiv tab."""
import os
import re
from functools import partial

import requests
from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal, QVariant, QRunnable, QObject, QThreadPool, QTimer
from PyQt5.QtGui import QBrush, QColor, QPixmap
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QHeaderView, QTableWidgetItem,
                             QSplitter, QButtonGroup, QWidget, QGroupBox, QTextEdit, QPushButton, QCheckBox, QFrame,
                             QMessageBox, QTableWidget, QLabel, QAbstractItemView, QSpinBox, QComboBox, QFileDialog)

import core
from modules import misc, exception


class LoginWidget(QWidget):
    login_success = pyqtSignal(str, tuple)

    def __init__(self, glovar):
        super().__init__()
        self.glovar = glovar
        self.settings = QSettings(os.path.join(os.path.abspath('..'), 'settings.ini'), QSettings.IniFormat)

        # self.ledit_un = QLineEdit()
        # self.ledit_un.setContextMenuPolicy(Qt.NoContextMenu)
        # self.ledit_pw = QLineEdit()
        # self.ledit_pw.setContextMenuPolicy(Qt.NoContextMenu)
        # self.ledit_pw.setEchoMode(QLineEdit.Password)
        self.tedit_cookies = QTextEdit()
        self.cbox_cookie = QCheckBox('保存登陆状态')
        self.btn_ok = QPushButton('登陆')
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.login)
        self.login_thread = None
        self.verify_thread = None

        self.init_ui()

    def set_disabled(self, status: bool):
        # self.ledit_pw.setDisabled(status)
        # self.ledit_un.setDisabled(status)
        self.tedit_cookies.setDisabled(status)
        self.cbox_cookie.setDisabled(status)
        self.btn_ok.setDisabled(status)

    def init_ui(self):
        self.settings.beginGroup('Cookies')
        if self.settings.value('pixiv', ''):
            # self.ledit_un.setPlaceholderText('(已保存)')
            # self.ledit_pw.setPlaceholderText('(已保存)')
            self.tedit_cookies.setPlaceholderText('(已保存)')
            self.cbox_cookie.setChecked(True)
        self.settings.endGroup()

        flay_input = QFormLayout()  # Input area layout
        # flay_input.addRow('登陆名', self.ledit_un)
        # flay_input.addRow('密码', self.ledit_pw)
        flay_input.addRow('Cookies', self.tedit_cookies)
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
        If cookies in setting is not NULL, test it by fetching user's info,
        or login by username and password.
        """
        self.set_disabled(True)
        # password = self.ledit_pw.text()
        # username = self.ledit_un.text()
        cookies = self.tedit_cookies.toPlainText()
        proxy = self.glovar.proxy

        self.settings.beginGroup('Cookies')
        saved_cookies = self.settings.value('pixiv', '')
        self.settings.endGroup()
        # if cookies and not password and not username:
        if saved_cookies:
            self.glovar.session.cookies.update(saved_cookies)
            self.verify_thread = VerifyThread(self, self.glovar.session, self.glovar.proxy)
            self.verify_thread.verify_success.connect(self.set_cookies)
            self.verify_thread.except_signal.connect(misc.show_messagebox)
            self.verify_thread.finished.connect(partial(self.set_disabled, False))
            self.verify_thread.start()
        else:
            self.login_thread = LoginThread(self, self.glovar.session, proxy, cookies)
            self.login_thread.login_success.connect(self.set_cookies)
            self.login_thread.except_signal.connect(misc.show_messagebox)
            self.login_thread.finished.connect(partial(self.set_disabled, False))
            self.login_thread.start()

    def set_cookies(self, info):
        self.settings.beginGroup('Cookies')
        if self.cbox_cookie.isChecked():
            self.settings.setValue('pixiv', self.glovar.session.cookies)
        else:
            self.settings.setValue('pixiv', '')
        self.settings.sync()
        self.settings.endGroup()
        self.login_success.emit('pixiv', info)
        self.set_disabled(False)

    def clear_cookies(self):
        # self.ledit_un.clear()
        # self.ledit_un.setPlaceholderText('')
        # self.ledit_pw.clear()
        # self.ledit_pw.setPlaceholderText('')
        self.tedit_cookies.setPlaceholderText('请从浏览器复制cookies到此处')
        self.cbox_cookie.setChecked(False)


class LoginThread(QThread):
    login_success = pyqtSignal(tuple)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy, cookies):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.cookies = cookies
        # self.pw = pw
        # self.uid = uid

    def run(self):
        try:
            core.login(self.session, self.cookies)
            info = core.get_user(self.session, self.proxy)
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
            info = core.get_user(self.session, self.proxy)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except exception.ResponseError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '登陆失败', '请尝试清除cookies重新登陆。')
        else:
            self.verify_success.emit(info)


class FetchThread(QThread):
    fetch_success = pyqtSignal(list)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy: dict, pid: str, uid: str, num: int):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.pid = pid
        self.uid = uid
        self.num = num

    def run(self):
        try:
            if self.pid:
                new_set = {self.pid}
            else:
                new_set = core.get_new(self.session, self.proxy, user_id=self.uid, num=self.num)
            updater = []
            results = []
            for pid in new_set:
                fet_pic = core.fetcher(pid)
                if not fet_pic:
                    print('Not in database.')
                    fet_pic = core.get_detail(self.session, pid=pid, proxy=self.proxy)
                    updater.append(fet_pic)
                else:
                    print('Fetch from database')
                results.append(fet_pic)
            core.pusher(updater)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            self.except_signal.emit(self.parent, QMessageBox.Warning, '连接失败', '请检查网络或使用代理。\n' + repr(e))
        except exception.ResponseError as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical,
                                    '未知错误', '返回值错误，请向开发者反馈\n{0}'.format(repr(e)))
        else:
            self.fetch_success.emit(results)


class SauceNAOThread(QThread):
    search_success = pyqtSignal(list)
    except_signal = pyqtSignal(object, int, str, str)

    def __init__(self, parent, session, proxy, path):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.path = path
        self.fetch_thread = None
        self.settings = QSettings(os.path.join(os.path.abspath('..'), 'settings.ini'), QSettings.IniFormat)

    def run(self):
        self.settings.beginGroup('MiscSetting')
        similarity = float(self.settings.value('similarity', 60.0))
        self.settings.endGroup()
        try:
            pid = core.saucenao(self.path, similarity)
            if pid:
                self.fetch_thread = FetchThread(self.parent, self.session, self.proxy, pid, '', 0)
                self.fetch_thread.fetch_success.connect(self.emit)
                self.fetch_thread.except_signal.connect(misc.show_messagebox)
                self.fetch_thread.start()
            else:
                self.except_signal.emit(self.parent, QMessageBox.Information,
                                        '未找到', 'Pixiv不存在这张图或相似率过低，请尝试在首选项中降低相似度阈值。')
        except FileNotFoundError:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '错误', '文件不存在')
        except requests.Timeout as e:
            self.except_signal.emit(self.parent, QMessageBox.Critical, '连接失败', '请检查网络或使用代理。\n' + repr(e))

    def emit(self, arg):
        self.search_success.emit(arg)


class DownloadSignals(QObject):
    download_success = pyqtSignal()
    except_signal = pyqtSignal(object, int, str, str)


class DownloadPicThread(QRunnable):
    def __init__(self, parent, session, proxy, info, path, page):
        super().__init__()
        self.parent = parent
        self.session = session
        self.proxy = proxy
        self.info = info
        self.path = path
        self.page = page
        self.signals = DownloadSignals()

    def run(self):
        try:
            core.download_pic(self.session, self.proxy, self.info, self.path, self.page)
        except (requests.exceptions.ProxyError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            self.signals.except_signal.emit(self.parent, QMessageBox.Critical, '连接失败',
                                            '请检查网络或使用代理：\n' + repr(e))
        except (FileNotFoundError, PermissionError) as e:
            self.signals.except_signal.emit(self.parent, QMessageBox.Critical, '错误',
                                            '文件系统错误：\n' + repr(e))
        else:
            self.signals.download_success.emit()


class DownloadThumbThread(QThread):
    download_success = pyqtSignal(tuple)

    def __init__(self, session, proxy, pid):
        super().__init__()
        self.session = session
        self.proxy = proxy
        self.pid = pid

    def run(self):
        item = core.fetcher(self.pid)
        if item:
            path = misc.download_thumb(self.session, self.proxy, item['thumb'])
            if path:
                self.download_success.emit((self.pid, path))


class MainWidget(QWidget):
    logout_sig = pyqtSignal(str)

    def __init__(self, glovar, info):
        super().__init__()
        self.glovar = glovar
        self.settings = QSettings(os.path.join(os.path.abspath('..'), 'settings.ini'), QSettings.IniFormat)
        self.fetch_thread = QThread()
        self.sauce_thread = QThread()
        self.thumb_thread = QThread()
        self.thread_pool = QThreadPool.globalInstance()
        self.ATC_monitor = QTimer()  # Use QTimer to monitor ACT when exception catched
        self.ATC_monitor.setInterval(500)
        self.ATC_monitor.timeout.connect(self.except_checker)
        self.except_info = None  # Store message box function instance
        self.thread_count = 0
        self.cancel_download_flag = 0

        self.thumb_dict = dict()  # Store pid and corresponding thumbnail path
        self.settings.beginGroup('MiscSetting')
        self.show_thumb_flag = int(self.settings.value('thumbnail', True))
        self.settings.endGroup()

        self.ledit_pid = misc.LineEditor()
        self.ledit_uid = misc.LineEditor()
        self.ledit_num = QSpinBox()
        self.ledit_num.setContextMenuPolicy(Qt.NoContextMenu)
        self.ledit_num.setMaximum(999)
        self.ledit_num.clear()

        self.btn_snao = QPushButton('以图搜图')
        self.btn_snao.clicked.connect(self.search_pic)
        self.user_info = QLabel('{0}({1})'.format(info[1], info[0]))
        self.btn_logout = QPushButton('退出登陆')
        self.btn_logout.clicked.connect(self.logout_fn)
        self.btn_get = QPushButton('获取信息')
        self.btn_get.clicked.connect(self.fetch_new)
        self.btn_dl = QPushButton('下载')
        self.btn_dl.clicked.connect(self.download)

        self.thumbnail = QLabel()
        self.thumbnail.setFrameShape(QFrame.StyledPanel)
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumb_default = QPixmap(os.path.join(self.glovar.home, 'icon', 'pixiv.png'))
        self.thumb_default = self.thumb_default.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.btn_fo = QPushButton('关注的更新')
        self.btn_fo.setCheckable(True)
        self.btn_pid = QPushButton('按PID搜索')
        self.btn_pid.setCheckable(True)
        self.btn_uid = QPushButton('按UID搜索')
        self.btn_uid.setCheckable(True)
        self.btn_group = QButtonGroup()
        self.btn_group.addButton(self.btn_fo, 1)
        self.btn_group.addButton(self.btn_pid, 2)
        self.btn_group.addButton(self.btn_uid, 3)
        self.btn_group.buttonClicked[int].connect(self.change_stat)

        self.table_viewer = QTableWidget()  # Detail viewer of fetched info
        self.table_viewer.cellPressed.connect(self.change_thumb)
        self.table_viewer.itemSelectionChanged.connect(self.set_default_thumb)
        self.table_viewer.setWordWrap(False)
        self.table_viewer.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_viewer.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_viewer.verticalScrollBar().setContextMenuPolicy(Qt.NoContextMenu)
        self.table_viewer.setColumnCount(6)
        self.table_viewer.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table_viewer.setHorizontalHeaderLabels(['PID', '画廊名', '画师ID', '画师名', '页数', '创建日期'])
        self.table_viewer.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_viewer.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_viewer.horizontalHeader().setStyleSheet('QHeaderView::section{background-color:#66CCFF;}')
        self.table_viewer.horizontalHeader().setHighlightSections(False)

        self.ledit_pid.setDisabled(True)
        self.ledit_num.setDisabled(True)
        self.ledit_uid.setDisabled(True)
        self.init_ui()

    def init_ui(self):
        glay_lup = QHBoxLayout()
        glay_lup.addWidget(self.btn_fo)
        glay_lup.addWidget(self.btn_pid)
        glay_lup.addWidget(self.btn_uid)
        glay_lup.addWidget(self.btn_snao)

        glay_ldown = QGridLayout()
        glay_ldown.addWidget(QLabel('画廊ID'), 0, 0, 1, 1)
        glay_ldown.addWidget(self.ledit_pid, 0, 1, 1, 5)
        glay_ldown.addWidget(QLabel('用户ID'), 1, 0, 1, 1)
        glay_ldown.addWidget(self.ledit_uid, 1, 1, 1, 5)
        glay_ldown.addWidget(QLabel('数量'), 2, 0, 1, 1)
        glay_ldown.addWidget(self.ledit_num, 2, 1, 1, 1)
        glay_ldown.setColumnStretch(1, 1)
        glay_ldown.setColumnStretch(2, 5)

        vlay_left = QVBoxLayout()
        vlay_left.addLayout(glay_lup)
        vlay_left.addLayout(glay_ldown)
        hlay_thumb = QHBoxLayout()
        hlay_thumb.addLayout(vlay_left)
        hlay_thumb.addWidget(self.thumbnail)
        left_wid = QWidget()
        left_wid.setLayout(hlay_thumb)

        self.thumbnail.setFixedHeight(left_wid.sizeHint().height())
        self.thumbnail.setFixedWidth(150)
        self.thumbnail.setPixmap(self.thumb_default)
        if self.show_thumb_flag:
            self.thumbnail.show()
        else:
            self.thumbnail.hide()

        vlay_right = QVBoxLayout()
        vlay_right.addWidget(self.user_info, alignment=Qt.AlignHCenter)
        vlay_right.addWidget(self.btn_logout)
        vlay_right.addWidget(self.btn_get)
        vlay_right.addWidget(self.btn_dl)
        right_wid = QWidget()
        right_wid.setLayout(vlay_right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.addWidget(left_wid)
        splitter.addWidget(right_wid)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.handle(1).setDisabled(True)

        vlay_main = QVBoxLayout()
        vlay_main.addWidget(splitter)
        vlay_main.addWidget(self.table_viewer)
        self.setLayout(vlay_main)

    def change_stat(self, bid):
        """Change states of three exclusive buttons by bid."""
        func = {1: self.new_stat,
                2: self.pid_stat,
                3: self.uid_stat}
        self.ledit_num.clear()
        self.ledit_pid.clear()
        self.ledit_uid.clear()
        func[bid]()

    def new_stat(self):
        self.btn_uid.setChecked(False)
        self.btn_pid.setChecked(False)
        self.btn_fo.setChecked(True)
        self.ledit_uid.setDisabled(True)
        self.ledit_pid.setDisabled(True)
        self.ledit_num.setDisabled(False)

    def pid_stat(self):
        self.btn_fo.setChecked(False)
        self.btn_uid.setChecked(False)
        self.btn_pid.setChecked(True)
        self.ledit_uid.setDisabled(True)
        self.ledit_num.setDisabled(True)
        self.ledit_pid.setDisabled(False)

    def uid_stat(self):
        self.btn_fo.setChecked(False)
        self.btn_pid.setChecked(False)
        self.btn_uid.setChecked(True)
        self.ledit_pid.setDisabled(True)
        self.ledit_uid.setDisabled(False)
        self.ledit_num.setDisabled(False)

    def tabulate(self, items):
        """Construct list of items."""
        self.table_viewer.setSortingEnabled(False)
        self.table_viewer.clearContents()
        self.table_viewer.setRowCount(len(items))
        index = 0
        for item in items:
            illust_id = QTableWidgetItem()
            illust_id.setTextAlignment(Qt.AlignCenter)
            illust_id.setData(Qt.EditRole, QVariant(int(item['illustId'])))
            illust_id.setBackground(QBrush(QColor('#CCFFFF')))
            self.table_viewer.setItem(index, 0, illust_id)

            self.table_viewer.setItem(index, 1, QTableWidgetItem(item['illustTitle']))

            user_id = QTableWidgetItem()
            user_id.setTextAlignment(Qt.AlignCenter)
            user_id.setData(Qt.EditRole, QVariant(int(item['userId'])))
            user_id.setBackground(QBrush(QColor('#CCFFFF')))
            self.table_viewer.setItem(index, 2, user_id)

            self.table_viewer.setItem(index, 3, QTableWidgetItem(item['userName']))

            page_count = QTableWidgetItem()
            page_count.setTextAlignment(Qt.AlignCenter)
            page_count.setData(Qt.EditRole, QVariant(item['pageCount']))
            page_count.setBackground(QBrush(QColor('#CCFFFF')))
            self.table_viewer.setItem(index, 4, page_count)

            create_date = QTableWidgetItem()
            create_date.setTextAlignment(Qt.AlignCenter)
            create_date.setData(Qt.EditRole, QVariant(item['createDate']))
            self.table_viewer.setItem(index, 5, create_date)
            index += 1
        self.table_viewer.setSortingEnabled(True)

    def fetch_new(self):
        self.btn_get.setDisabled(True)
        self.btn_dl.setDisabled(True)
        pid = self.ledit_pid.text().strip()
        uid = self.ledit_uid.text().strip()
        num = self.ledit_num.value() if self.ledit_num.value() else 0
        if pid or uid:
            if re.match(r'^\d{2,9}$', pid) or re.match(r'^\d{2,9}$', uid):
                self.fetch_thread = FetchThread(self, self.glovar.session, self.glovar.proxy, pid, uid, num)
                self.fetch_thread.fetch_success.connect(self.tabulate)
                self.fetch_thread.except_signal.connect(misc.show_messagebox)
                self.fetch_thread.finished.connect(self.fetch_new_finished)
                self.fetch_thread.start()
            else:
                misc.show_messagebox(self, QMessageBox.Warning, '错误', 'ID号输入错误！')
                self.btn_get.setDisabled(False)
                self.btn_dl.setDisabled(False)
        elif num:
            self.fetch_thread = FetchThread(self, self.glovar.session, self.glovar.proxy, pid, uid, num)
            self.fetch_thread.fetch_success.connect(self.tabulate)
            self.fetch_thread.except_signal.connect(misc.show_messagebox)
            self.fetch_thread.finished.connect(self.fetch_new_finished)
            self.fetch_thread.start()
        else:
            misc.show_messagebox(self, QMessageBox.Warning, '错误', '请输入查询信息！')
            self.btn_get.setDisabled(False)
            self.btn_dl.setDisabled(False)

    def fetch_new_finished(self):
        self.btn_get.setDisabled(False)
        self.btn_dl.setDisabled(False)

    def change_thumb(self, row):
        if self.show_thumb_flag:
            pid = self.table_viewer.item(row, 0).text()
            if pid in self.thumb_dict:
                thumb = QPixmap()
                if thumb.load(self.thumb_dict[pid]):  # If thumbnail is deleted, redownload it
                    self.thumbnail.setPixmap(thumb)
                else:
                    self.thumb_thread = DownloadThumbThread(self.glovar.session, self.glovar.proxy, pid)
                    self.thumb_thread.download_success.connect(self.show_thumb)
                    self.thumb_thread.start()
            else:
                self.thumb_thread = DownloadThumbThread(self.glovar.session, self.glovar.proxy, pid)
                self.thumb_thread.download_success.connect(self.show_thumb)
                self.thumb_thread.start()

    def show_thumb(self, info):
        self.thumb_dict[info[0]] = info[1]
        thumb = QPixmap(info[1])
        self.thumbnail.setPixmap(thumb)

    def change_thumb_state(self, new):
        """Change state of whether show thumbnail in setting."""
        self.show_thumb_flag = new
        if self.show_thumb_flag:
            self.thumbnail.show()
        else:
            self.thumbnail.hide()

    def set_default_thumb(self):
        """Set default thumbnail when no item selected."""
        if not self.table_viewer.selectedItems() and self.show_thumb_flag:
            self.thumbnail.setPixmap(self.thumb_default)

    def download(self):
        items = self.table_viewer.selectedItems()
        if items:
            self.btn_dl.setText('取消下载')
            self.btn_dl.clicked.disconnect(self.download)
            self.btn_dl.clicked.connect(self.cancel_download)

            self.settings.beginGroup('RuleSetting')
            root_path = self.settings.value('pixiv_root_path', os.path.abspath('..'))
            folder_rule = self.settings.value('pixiv_folder_rule', {0: 'illustId'})
            file_rule = self.settings.value('pixiv_file_rule', {0: 'illustId'})
            self.settings.endGroup()
            self.settings.beginGroup('MiscSetting')
            dl_sametime = int(self.settings.value('dl_sametime', 3))
            self.settings.endGroup()

            self.thread_pool.setMaxThreadCount(dl_sametime)
            for i in range(len(items) // 6):
                info = core.fetcher(items[i * 6].text())
                path = core.path_name(info, root_path, folder_rule, file_rule)
                for page in range(info['pageCount']):
                    thread = DownloadPicThread(self, self.glovar.session, self.glovar.proxy, info, path, page)
                    thread.signals.except_signal.connect(self.except_download)
                    thread.signals.download_success.connect(self.finish_download)
                    self.thread_count += 1
                    self.thread_pool.start(thread)
        else:
            misc.show_messagebox(self, QMessageBox.Warning, '警告', '请选择至少一行！')

    def cancel_download(self):
        self.btn_dl.setDisabled(True)
        self.cancel_download_flag = 1
        self.thread_count = self.thread_pool.activeThreadCount()
        self.thread_pool.clear()

    def except_download(self, *args):
        """Cancel download threads when exceptions raised."""
        self.cancel_download()
        if not self.except_info:
            self.except_info = args
            if self.thread_pool.maxThreadCount() == 1:
                self.ATC_monitor.start()

    def except_checker(self):
        """Check whether all thread in pool has ended."""
        if not self.thread_pool.activeThreadCount():
            self.ATC_monitor.stop()
            misc.show_messagebox(*self.except_info)
            self.btn_dl.setDisabled(False)
            self.btn_dl.setText('下载')  # Single thread needs this
            self.btn_dl.clicked.disconnect(self.cancel_download)
            self.btn_dl.clicked.connect(self.download)

    def finish_download(self):
        """Do some clearing stuff when thread has finished."""
        self.thread_count -= 1
        print('Thread finished:', self.thread_count)
        if not self.thread_count:
            if self.cancel_download_flag:
                self.btn_dl.setDisabled(False)
            elif self.except_info:
                self.except_info()
            else:
                misc.show_messagebox(self, QMessageBox.Information, '下载完成', '下载成功完成！')
            self.btn_dl.setText('下载')
            self.btn_dl.clicked.disconnect(self.cancel_download)
            self.btn_dl.clicked.connect(self.download)

    def search_pic(self):
        path = QFileDialog.getOpenFileName(self, '选择图片', os.path.abspath('..'), '图片文件(*.gif *.jpg *.png *.bmp)')
        if path[0]:
            self.btn_snao.setDisabled(True)
            self.btn_snao.setText('正在上传')
            self.sauce_thread = SauceNAOThread(self, self.glovar.session, self.glovar.proxy, path[0])
            self.sauce_thread.search_success.connect(self.tabulate)
            self.sauce_thread.except_signal.connect(misc.show_messagebox)
            self.sauce_thread.finished.connect(self.search_pic_finished)
            self.sauce_thread.start()

    def search_pic_finished(self):
        self.btn_snao.setText('以图搜图')
        self.btn_snao.setDisabled(False)

    def logout_fn(self):
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
                self.fetch_thread.exit(-1)
                self.sauce_thread.exit(-1)
                self.thumb_thread.exit(-1)
                self.thread_pool.waitForDone()  # Close all threads before logout
                self.logout_sig.emit('pixiv')
                return True
            else:
                self.btn_logout.setDisabled(False)
                return False
        else:
            self.fetch_thread.exit(-1)
            self.sauce_thread.exit(-1)
            self.thumb_thread.exit(-1)
            self.thread_pool.waitForDone()
            self.logout_sig.emit('pixiv')
            return True


class SaveRuleSettingTab(QWidget):
    _name_dic = {'PID': 'illustId',
                 '画廊名': 'illustTitle',
                 '画师ID': 'userId',
                 '画师名': 'userName',
                 '创建日期': 'createDate'}

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.root_path = None
        self.folder_rule = {}
        self.file_rule = {}

        self.sbox_folder = QSpinBox()
        self.sbox_folder.setMinimum(0)
        self.sbox_folder.setMaximum(5)
        self.sbox_folder.setContextMenuPolicy(Qt.NoContextMenu)
        self.sbox_folder.valueChanged.connect(self.folder_cbox_updater)
        self.sbox_file = QSpinBox()
        self.sbox_file.setMinimum(1)
        self.sbox_file.setMaximum(5)
        self.sbox_file.setContextMenuPolicy(Qt.NoContextMenu)
        self.sbox_file.valueChanged.connect(self.file_cbox_updater)

        self.hlay_folder_cbox = QHBoxLayout()
        self.hlay_file_cbox = QHBoxLayout()
        self.cbox_folder_list = [LayerSelector() for _ in range(5)]
        self.cbox_file_list = [LayerSelector() for _ in range(5)]
        for wid in self.cbox_folder_list:
            wid.currentIndexChanged.connect(self.folder_rule_updater)
            self.hlay_folder_cbox.addWidget(wid)
        for wid in self.cbox_file_list:
            wid.currentIndexChanged.connect(self.file_rule_updater)
            self.hlay_file_cbox.addWidget(wid)

        self.ledit_prev = misc.LineEditor()
        self.ledit_prev.setReadOnly(True)
        self.ledit_prev.setContextMenuPolicy(Qt.NoContextMenu)

        self.restore()
        self.folder_cbox_updater(len(self.folder_rule))
        self.file_cbox_updater(len(self.file_rule))
        self.init_ui()

    def init_ui(self):
        btn_root = QPushButton('浏览')
        btn_root.clicked.connect(self.choose_dir)

        glay_folder = QGridLayout()
        glay_folder.addWidget(QLabel('根目录'), 0, 0, 1, 1)
        glay_folder.addWidget(btn_root, 0, 1, 1, 2)
        glay_folder.addWidget(QLabel('文件夹层级'), 1, 0, 1, 1)
        glay_folder.addWidget(self.sbox_folder, 1, 1, 1, 2)

        glay_file = QGridLayout()
        glay_file.addWidget(QLabel('文件名层级'), 0, 0, 1, 1)
        glay_file.addWidget(self.sbox_file, 0, 1, 1, 2)

        vlay_pixiv = QVBoxLayout()
        vlay_pixiv.addLayout(glay_folder)
        vlay_pixiv.addLayout(self.hlay_folder_cbox)
        vlay_pixiv.addLayout(glay_file)
        vlay_pixiv.addLayout(self.hlay_file_cbox)
        vlay_pixiv.addWidget(self.ledit_prev)
        self.setLayout(vlay_pixiv)
        self.setMinimumSize(self.sizeHint())

    def choose_dir(self):
        self.settings.beginGroup('RuleSetting')
        setting_root_path = self.settings.value('pixiv_root_path', os.path.abspath('..'))
        root_path = QFileDialog.getExistingDirectory(self, '选择目录', setting_root_path)
        self.settings.endGroup()
        if root_path:  # When click Cancel, root_path is None
            self.root_path = root_path
            self.previewer()

    def folder_cbox_updater(self, new):
        now = self.hlay_folder_cbox.count()
        if now <= new:  # When folder rule increases, 0 to 1 is special
            if not self.cbox_folder_list[0].isEnabled():
                self.cbox_folder_list[0].setDisabled(False)
            for i in range(now, new):
                self.hlay_folder_cbox.addWidget(self.cbox_folder_list[i])
                self.cbox_folder_list[i].show()
        else:
            if new:  # When folder rule decreases, new-1 cannot lower than 0
                for i in range(4, new - 1, -1):
                    self.hlay_folder_cbox.removeWidget(self.cbox_folder_list[i])
                    self.cbox_folder_list[i].hide()
            else:
                for i in range(4, 0, -1):
                    self.hlay_folder_cbox.removeWidget(self.cbox_folder_list[i])
                    self.cbox_folder_list[i].hide()
                self.cbox_folder_list[0].setDisabled(True)
        self.folder_rule = {i: self._name_dic[self.cbox_folder_list[i].currentText()]
                            for i in range(new)}
        self.previewer()

    def file_cbox_updater(self, new):
        now = self.hlay_file_cbox.count()
        if now < new:
            for i in range(now, new):
                self.hlay_file_cbox.addWidget(self.cbox_file_list[i])
                self.cbox_file_list[i].show()
        else:
            for i in range(4, new - 1, -1):
                self.hlay_file_cbox.removeWidget(self.cbox_file_list[i])
                self.cbox_file_list[i].hide()
        self.file_rule = {i: self._name_dic[self.cbox_file_list[i].currentText()]
                          for i in range(new)}
        self.previewer()

    def folder_rule_updater(self):
        self.folder_rule = {i: self._name_dic[self.cbox_folder_list[i].currentText()]
                            for i in range(self.sbox_folder.value())}
        self.previewer()

    def file_rule_updater(self):
        self.file_rule = {i: self._name_dic[self.cbox_file_list[i].currentText()]
                          for i in range(self.sbox_file.value())}
        self.previewer()

    def previewer(self):
        if misc.PLATFORM == 'Windows':
            path = self.root_path.replace('/', '\\')
        else:
            path = self.root_path
        for i in range(len(self.folder_rule)):
            path = os.path.join(path, self.cbox_folder_list[i].currentText())
        all_name = [self.cbox_file_list[i].currentText() for i in range(len(self.file_rule))]
        name = '_'.join(all_name)
        path = os.path.join(path, name + '.jpg')
        self.ledit_prev.setText(path)

    def store(self):
        self.settings.beginGroup('RuleSetting')
        self.settings.setValue('pixiv_root_path', self.root_path)
        self.settings.setValue('pixiv_folder_rule', self.folder_rule)
        self.settings.setValue('pixiv_file_rule', self.file_rule)
        self.settings.sync()
        self.settings.endGroup()

    def restore(self):
        name_dic = {'illustId': 'PID',
                    'illustTitle': '画廊名',
                    'userId': '画师ID',
                    'userName': '画师名',
                    'createDate': '创建日期'}
        self.settings.beginGroup('RuleSetting')
        self.root_path = self.settings.value('pixiv_root_path', os.path.abspath('..'))
        # Set two folder_rule vars, in case of global var modified.
        self.folder_rule = folder_rule = self.settings.value('pixiv_folder_rule', {0: 'illustId'})
        self.file_rule = file_rule = self.settings.value('pixiv_file_rule', {0: 'illustId'})
        self.settings.endGroup()
        self.sbox_folder.setValue(len(folder_rule))
        self.sbox_file.setValue(len(file_rule))
        # Set cbox's value to default PID, when *_rule shorter than 5.
        for i in range(5):
            try:
                self.cbox_folder_list[i].setCurrentText(name_dic[folder_rule[i]])
            except KeyError:
                self.cbox_folder_list[i].setCurrentText('PID')
            try:
                self.cbox_file_list[i].setCurrentText(name_dic[file_rule[i]])
            except KeyError:
                self.cbox_file_list[i].setCurrentText('PID')
        if not len(folder_rule):
            self.cbox_folder_list[0].setDisabled(True)
        self.previewer()  # Necessary when select root path without clicking Confirm


class LayerSelector(QComboBox):
    def __init__(self):
        super().__init__()
        self.addItems(['PID', '画廊名', '画师ID', '画师名', '创建日期'])
