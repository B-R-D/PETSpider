# coding:utf-8
"""Global objects."""
import os
import platform
import re

from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QWidget, QLineEdit, QGroupBox, QPushButton, QCheckBox, QMessageBox, QTabWidget,
                             QDoubleSpinBox, QSpinBox, QFormLayout, QHBoxLayout, QVBoxLayout, QGridLayout, QMenu)

from modules import pixiv_gui, ehentai_gui

_RE_SYMBOL = re.compile(r'[/\\|*?<>":]')
_RE_PROXY = re.compile(r'.*:([1-9]\d{0,3}|[1-5]\d{4}|6[0-4]\d{4}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$')
PLATFORM = platform.system()


class GlobalVar(object):
    user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:65.0) Gecko/20100101 Firefox/65.0',
                  ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/73.0.3683.86 Safari/537.36'),
                  ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/64.0.3282.140 Safari/537.36 Edge/18.17763'))

    def __init__(self, session, proxy: dict, home: str):
        self._session = session
        self._proxy = proxy
        self._home = home

    @property
    def session(self):
        return self._session

    @session.deleter
    def session(self):
        self._session.close()

    @property
    def proxy(self):
        return self._proxy

    @proxy.setter
    def proxy(self, new: dict):
        self._proxy = new

    @property
    def home(self):
        return self._home

    @home.setter
    def home(self, new: str):
        self._home = new


class MiscSettingDialog(QWidget):
    """MiscSetting dialog class."""
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.cbox_pixiv = QCheckBox('Pixiv')  # Proxy availability
        self.cbox_ehentai = QCheckBox('Ehentai')  # Proxy availability
        self.ledit_http = LineEditor()  # Http proxy
        self.ledit_https = LineEditor()  # Https proxy

        self.sbox_simi = QDoubleSpinBox()
        self.sbox_simi.setToolTip('只有相似度高于该值的识图结果会被显示。')
        self.sbox_simi.setContextMenuPolicy(Qt.NoContextMenu)
        self.sbox_simi.setRange(0, 100)
        self.sbox_simi.setSingleStep(0.5)
        self.sbox_simi.setDecimals(2)
        self.sbox_simi.setSuffix(' %')
        self.sbox_dlcount = QSpinBox()
        self.sbox_dlcount.setToolTip('可同时下载的图片数，过大可能会导致连接中断或IP被ban。')
        self.sbox_dlcount.setContextMenuPolicy(Qt.NoContextMenu)
        self.sbox_dlcount.setRange(1, 5)
        self.sbox_dlcount.setWrapping(True)
        self.cbox_thumb = QCheckBox()

        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.init_ui()

    def init_ui(self):
        self.restore()
        self.ledit_http.setPlaceholderText('服务器地址:端口号')
        self.ledit_https.setPlaceholderText('服务器地址:端口号')

        btn_ok = QPushButton('确定', self)
        btn_ok.clicked.connect(self.store)
        btn_canc = QPushButton('取消', self)
        btn_canc.clicked.connect(self.close)

        gbox_proxy = QGroupBox('代理设置')
        hlay_cbox = QHBoxLayout()  # Checkbox for different website
        hlay_cbox.addWidget(self.cbox_pixiv)
        hlay_cbox.addWidget(self.cbox_ehentai)

        flay_proxy = QFormLayout()  # Lineedit for server_ip:port
        flay_proxy.setSpacing(20)
        flay_proxy.addRow('http://', self.ledit_http)
        flay_proxy.addRow('https://', self.ledit_https)

        vlay_cbox = QVBoxLayout()  # Combine into GroupBox
        vlay_cbox.setSpacing(20)
        vlay_cbox.addLayout(hlay_cbox)
        vlay_cbox.addLayout(flay_proxy)
        gbox_proxy.setLayout(vlay_cbox)

        gbox_misc = QGroupBox('杂项')
        flay_misc = QFormLayout()
        flay_misc.setSpacing(20)
        flay_misc.addRow('图片相似度', self.sbox_simi)
        flay_misc.addRow('并发线程数', self.sbox_dlcount)
        flay_misc.addRow('开启预览图', self.cbox_thumb)
        gbox_misc.setLayout(flay_misc)

        glay_all = QGridLayout()
        glay_all.addWidget(gbox_proxy, 0, 0)
        glay_all.addWidget(gbox_misc, 0, 1)

        hlay_btn = QHBoxLayout()  # Confirm and cancel button
        hlay_btn.addStretch(1)
        hlay_btn.addWidget(btn_ok)
        hlay_btn.addWidget(btn_canc)
        hlay_btn.addStretch(1)

        vlay_perf = QVBoxLayout()  # All component
        vlay_perf.addLayout(glay_all)
        vlay_perf.addLayout(hlay_btn)
        self.setLayout(vlay_perf)

        self.setMinimumWidth(self.sizeHint().width())
        self.setFixedHeight(self.sizeHint().height())
        self.setWindowTitle('首选项')

    def store(self):
        http_proxy = self.ledit_http.text()
        https_proxy = self.ledit_https.text()
        if (_RE_PROXY.match(http_proxy) or not http_proxy) and (_RE_PROXY.match(https_proxy) or not https_proxy):
            self.settings.beginGroup('MiscSetting')
            self.settings.setValue('pixiv_proxy', int(self.cbox_pixiv.isChecked()))
            self.settings.setValue('ehentai_proxy', int(self.cbox_ehentai.isChecked()))
            self.settings.setValue('proxy', {'http': http_proxy, 'https': https_proxy})
            self.settings.setValue('similarity', self.sbox_simi.value())
            self.settings.setValue('dl_sametime', self.sbox_dlcount.value())
            self.settings.setValue('thumbnail', int(self.cbox_thumb.isChecked()))
            self.settings.sync()
            self.settings.endGroup()
            self.close()
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('错误')
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText('请输入正确的代理地址。')
            msg_box.addButton('确定', QMessageBox.AcceptRole)
            msg_box.exec()

    def restore(self):
        self.settings.beginGroup('MiscSetting')
        setting_pixiv_proxy = int(self.settings.value('pixiv_proxy', False))
        setting_ehentai_proxy = int(self.settings.value('ehentai_proxy', False))
        setting_proxy = self.settings.value('proxy', {'http': '', 'https': ''})
        setting_similarity = float(self.settings.value('similarity', 60.0))
        setting_dlcount = int(self.settings.value('dl_sametime', 3))
        setting_thumbnail = int(self.settings.value('thumbnail', True))
        self.settings.endGroup()

        self.cbox_pixiv.setChecked(setting_pixiv_proxy)
        self.cbox_ehentai.setChecked(setting_ehentai_proxy)
        self.ledit_http.setText(setting_proxy['http'])
        self.ledit_https.setText(setting_proxy['https'])
        self.sbox_simi.setValue(setting_similarity)
        self.sbox_dlcount.setValue(setting_dlcount)
        self.cbox_thumb.setChecked(setting_thumbnail)

    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        """Restore settings in the ini file, for the setting window will not be destroyed."""
        self.restore()
        self.closed.emit()


class SaveRuleDialog(QWidget):
    """Save rule dialog class."""

    def __init__(self):
        super().__init__()
        self.setFont(QFont('Arial', 10))
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.settings = QSettings(os.path.join(os.path.abspath('.'), 'settings.ini'), QSettings.IniFormat)
        self.pixiv_tab = pixiv_gui.SaveRuleSettingTab(self.settings)
        self.ehentai_tab = ehentai_gui.SaveRuleSettingTab(self.settings)
        self.init_ui()

    def init_ui(self):
        main_wid = QTabWidget()
        main_wid.addTab(self.pixiv_tab, 'Pixiv')
        main_wid.addTab(self.ehentai_tab, 'Ehentai')
        main_wid.setCurrentIndex(0)
        main_wid.setMinimumWidth(self.pixiv_tab.size().width())

        btn_ok = QPushButton('确定', self)
        btn_canc = QPushButton('取消', self)
        btn_ok.clicked.connect(self.store)
        btn_canc.clicked.connect(self.close)

        hlay_btn = QHBoxLayout()  # Confirm and cancel button
        hlay_btn.addStretch(1)
        hlay_btn.addWidget(btn_ok, alignment=Qt.AlignTop)
        hlay_btn.addWidget(btn_canc, alignment=Qt.AlignTop)
        hlay_btn.addStretch(1)

        vlay = QVBoxLayout()
        vlay.addWidget(main_wid)
        vlay.addLayout(hlay_btn)

        self.setLayout(vlay)
        self.setMinimumWidth(self.sizeHint().width())
        self.setFixedHeight(self.sizeHint().height())
        self.setWindowTitle('保存规则')

    def store(self):
        self.pixiv_tab.store()
        self.ehentai_tab.store()
        self.close()

    def keyPressEvent(self, k):
        if k.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.pixiv_tab.restore()
        self.ehentai_tab.restore()


class LineEditor(QLineEdit):
    """Custom QLineEdit. Support cut, copy, paste and select all."""

    def __init__(self):
        super().__init__()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_select_all = menu.addAction('全选')
        act_cut = menu.addAction('剪切')
        act_copy = menu.addAction('复制')
        act_paste = menu.addAction('粘贴')
        if not self.text():
            act_select_all.setEnabled(False)
            act_cut.setEnabled(False)
            act_copy.setEnabled(False)
        else:
            act_cut.setEnabled(self.hasSelectedText())
            act_copy.setEnabled(self.hasSelectedText())
        action = menu.exec(self.mapToGlobal(event.pos()))
        if action == act_cut:
            self.cut()
        elif action == act_copy:
            self.copy()
        elif action == act_select_all:
            self.selectAll()
        elif action == act_paste:
            self.paste()

def show_messagebox(parent, style, title: str, message: str):
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setIcon(style)
    msg_box.setText(message)
    msg_box.addButton('确定', QMessageBox.AcceptRole)
    msg_box.exec()


def name_verify(name: str, default: str = 'NoName') -> str:
    """
    Normalize file/folder name.
    Args:
        name: A string of file/folder name.
        default: When the illegal name leads to an empty string, return this.
    Returns:
        A legal string for file/folder name.
    """
    if PLATFORM == 'Windows':
        illegal_name = {'con', 'aux', 'nul', 'prn', 'com0', 'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7',
                        'com8', 'com9', 'lpt0', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'}
        step1 = _RE_SYMBOL.sub('', name)  # Remove illegal symbol
        step2 = step1.strip('.')  # Remove '.' at the beginning and end
        if step2 in illegal_name or not step2:
            return default
        return step2
    elif PLATFORM == 'Linux':
        step1 = name.replace('/', '')  # Remove illegal '/'
        step2 = step1.lstrip('.')  # Remove '.' at the beginning
        if not step2:
            return default
        return step2


if __name__ == '__main__':
    pass
    # print('/con?:', name_verify('/con?', 'IllegalName'))
    # print('.hack"thank:', name_verify('.hack"thank', 'IllegalName'))
    # print('...aux*Myname...:', name_verify('...aux*Myname...', 'IllegalName'))
    # print('...:', name_verify('...', 'IllegalName'))
