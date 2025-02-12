import minecraft_launcher_lib
import subprocess
from uuid import uuid1
from random_username.generate import generate_username
from PyQt5 import QtCore, QtGui, QtWidgets
import os
import json
import shutil  # Для копирования файлов
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory().replace('minecraft', 'asetlauncher')  # !!! ВАЖНО: Уберите .replace, если хотите использовать стандартную папку .minecraft !!!

def create_optifine_version(minecraft_version, optifine_file, minecraft_directory):
    """
    Создает новую версию Minecraft с OptiFine.
    """
    optifine_version_id = f"{minecraft_version}-OptiFine"
    #Извлекаем версию OptiFine из имени файла
    optifine_version = os.path.splitext(os.path.basename(optifine_file))[0].replace("OptiFine_", "")
    version_dir = os.path.join(minecraft_directory, "versions", optifine_version_id)

    if os.path.exists(version_dir):
        print(f"Версия {optifine_version_id} уже существует!")
        return optifine_version_id

    os.makedirs(version_dir, exist_ok=True)

    #Копируем OptiFine
    source_path = optifine_file
    dest_path = os.path.join(version_dir, f"{optifine_version_id}.jar")
    try:
        shutil.copy2(source_path, dest_path)
    except Exception as e:
        print(f"Ошибка при копировании OptiFine: {e}")
        return None

    #Создаем JSON файл версии
    version_json = {
        "id": optifine_version_id,
        "inheritsFrom": minecraft_version,
        "time": "2022-03-13T02:39:29+03:00", #Пример даты
        "releaseTime": "2022-03-13T02:39:29+03:00", #Пример даты
        "type": "release",
        "libraries": [
            {
                "name": f"optifine:OptiFine:{optifine_version}"
            },
            {
                "name": "optifine:launchwrapper-of:2.3"
            }
        ],
        "mainClass": "net.minecraft.launchwrapper.Launch",
        "arguments": {
            "game": [
                "--tweakClass",
                "optifine.OptiFineTweaker"
            ]
        },
        "minimumLauncherVersion": 21
    }

    json_path = os.path.join(version_dir, f"{optifine_version_id}.json")
    with open(json_path, "w") as f:
        json.dump(version_json, f, indent=4)

    print(f"Версия {optifine_version_id} успешно создана!")
    return optifine_version_id

def get_classpath(version_id, minecraft_directory):
    """
    Генерирует classpath для запуска Minecraft.
    """
    version_dir = os.path.join(minecraft_directory, "versions", version_id)
    version_json_path = os.path.join(version_dir, f"{version_id}.json")

    try:
        with open(version_json_path, "r") as f:
            version_json = json.load(f)
    except FileNotFoundError:
        print(f"Файл {version_json_path} не найден!")
        return []
    except json.JSONDecodeError:
        print(f"Ошибка при чтении JSON файла {version_json_path}!")
        return []

    classpath = []
    #Добавляем libraries
    for lib in version_json.get("libraries", []):
        if "downloads" in lib and "artifact" in lib["downloads"]:
            artifact = lib["downloads"]["artifact"]
            path = os.path.join(minecraft_directory, "libraries", *artifact["path"].split("/"))
            classpath.append(path)
    #Добавляем jar файл самой версии
    classpath.append(os.path.join(version_dir, f"{version_id}.jar"))

    return classpath

class LaunchThread(QtCore.QThread):
    launch_setup_signal = QtCore.pyqtSignal(str, str, str)
    progress_update_signal = QtCore.pyqtSignal(int, int, str)
    state_update_signal = QtCore.pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.version_id = ''
        self.username = ''
        self.instance_type = ''
        self.optifine_file = None #Может быть None
        self.progress = 0
        self.progress_max = 0
        self.progress_label = ''

    def launch_setup(self, version_id, username, instance_type):
        self.version_id = version_id
        self.username = username
        self.instance_type = instance_type

    def update_progress_label(self, value):
        self.progress_label = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def update_progress(self, value):
        self.progress = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def update_progress_max(self, value):
        self.progress_max = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def run(self):
        self.state_update_signal.emit(True)

        # Получаем базовую версию Minecraft (до знака -)
        base_version = self.version_id.split('-')[0]

        minecraft_launcher_lib.install.install_minecraft_version(
            versionid=base_version,
            minecraft_directory=minecraft_directory,
            callback={
                'setStatus': self.update_progress_label,
                'setProgress': self.update_progress,
                'setMax': self.update_progress_max
            }
        )

        if self.instance_type == "vanilla":
            command = self.get_vanilla_command()
        elif self.instance_type == "forge":
            if not self.install_forge():
                self.state_update_signal.emit(False)
                return
            command = self.get_forge_command()
        elif self.instance_type == "optifine":
            optifine_version_id = create_optifine_version(base_version, self.optifine_file, minecraft_directory)

            if not optifine_version_id:
                self.state_update_signal.emit(False)
                return

            command = self.get_optifine_command(optifine_version_id)
        else:
            print("Неизвестный тип установки: " + self.instance_type)
            self.state_update_signal.emit(False)
            return

        subprocess.call(command)
        self.state_update_signal.emit(False)

    def get_vanilla_command(self):
        # Получаем базовую версию Minecraft (до знака -)
        base_version = self.version_id.split('-')[0]
        
        options = {
            'username': self.username,
            'uuid': str(uuid1()),
            'token': ''
        }

        return minecraft_launcher_lib.command.get_minecraft_command(
            version=base_version,
            minecraft_directory=minecraft_directory,
            options=options
        )

    def get_forge_command(self):
        # Получаем только базовую версию Minecraft (до знака -)
        base_version = self.version_id.split('-')[0]
        
        # Находим версию Forge
        forge_version = minecraft_launcher_lib.forge.find_forge_version(base_version)
            
        if not forge_version:
            print(f"Не удалось получить версию Forge для {base_version}!")
            return None

        options = {
            'username': self.username,
            'uuid': str(uuid1()),
            'token': ''
        }

        return minecraft_launcher_lib.command.get_minecraft_command(
            version=base_version,  # Используем базовую версию
            minecraft_directory=minecraft_directory,
            options=options
        )

    def get_optifine_command(self, optifine_version_id): #Теперь принимает optifine_version_id
        options = {
            'username': self.username,
            'uuid': str(uuid1()),
            'token': ''
        }

        return minecraft_launcher_lib.command.get_minecraft_command(
            version=optifine_version_id, #Используем ID созданной версии
            minecraft_directory=minecraft_directory,
            options=options,
        )

    def get_forge_version(self):
        # Получаем базовую версию Minecraft (до знака -)
        base_version = self.version_id.split('-')[0]
        
        try:
            # Пытаемся найти версию Forge
            forge_version = minecraft_launcher_lib.forge.find_forge_version(base_version)
            if forge_version:
                return forge_version
        except Exception as e:
            print(f"Ошибка при поиске версии Forge: {e}")
        
        return None

    def install_forge(self):
        # Получаем только основную версию Minecraft (до знака -)
        base_version = self.version_id.split('-')[0]
        
        try:
            # Находим последнюю версию forge для выбранной версии Minecraft
            forge_version = minecraft_launcher_lib.forge.find_forge_version(base_version)
            
            # Проверяем, существует ли версия forge для этой версии
            if forge_version is None:
                print(f"Forge не поддерживается для версии Minecraft {base_version}")
                return False
                
            # Проверяем, может ли версия быть установлена автоматически
            if minecraft_launcher_lib.forge.supports_automatic_install(forge_version):
                callback = {
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max
                }
                
                # Устанавливаем Forge
                minecraft_launcher_lib.forge.install_forge_version(forge_version, minecraft_directory, callback=callback)
                
                # После установки Forge устанавливаем его версию
                minecraft_launcher_lib.install.install_minecraft_version(
                    versionid=base_version,  # Используем базовую версию
                    minecraft_directory=minecraft_directory,
                    callback={
                        'setStatus': self.update_progress_label,
                        'setProgress': self.update_progress,
                        'setMax': self.update_progress_max
                    }
                )
                return True
            else:
                print(f"Forge {forge_version} не может быть установлен автоматически.")
                minecraft_launcher_lib.forge.run_forge_installer(forge_version)
                return True
                
        except Exception as e:
            print(f"Ошибка при установке Forge: {e}")
            return False

    def install_optifine(self):
        """
        Копирует OptiFine в папку с версией и создает JSON.
        """
        optifine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "optifine") #Папка с лаунчером
        minecraft_version = self.version_id

        if not os.path.isdir(optifine_dir):
            print("Папка optifine не найдена!")
            return False

        #Ищем подходящий файл
        optifine_file = None
        for file in os.listdir(optifine_dir):
            if file.endswith(".jar") and "optifine" in file.lower() and minecraft_version in file.lower():
                optifine_file = os.path.join(optifine_dir, file)
                break

        if not optifine_file:
            print(f"Файл OptiFine для версии {minecraft_version} не найден в папке optifine!")
            return False

        self.optifine_file = optifine_file #Сохраняем путь к файлу

        return True

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setWindowModality(QtCore.Qt.NonModal)
        MainWindow.resize(361, 471)
        MainWindow.setUnifiedTitleAndToolBarOnMac(False)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setContentsMargins(25, 25, 25, 25)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName("verticalLayout")

        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setText("")
        self.label.setPixmap(QtGui.QPixmap("images/Аватарка лаунчера.png"))
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label, 0, QtCore.Qt.AlignHCenter)

        spacerItem = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)

        self.lineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit.setObjectName("lineEdit")
        self.lineEdit.setPlaceholderText("Имя Игрока")
        self.verticalLayout.addWidget(self.lineEdit)

        self.version_comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.version_comboBox.setObjectName("version_comboBox")
        for version in minecraft_launcher_lib.utils.get_version_list():
            self.version_comboBox.addItem(version['id'])
        self.verticalLayout.addWidget(self.version_comboBox)

        self.instance_type_comboBox = QtWidgets.QComboBox(self.centralwidget)
        self.instance_type_comboBox.setObjectName("instance_type_comboBox")
        self.instance_type_comboBox.addItem("vanilla")
        self.instance_type_comboBox.addItem("forge")
        self.instance_type_comboBox.addItem("optifine")
        self.verticalLayout.addWidget(self.instance_type_comboBox)

        spacerItem1 = QtWidgets.QSpacerItem(20, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.verticalLayout.addItem(spacerItem1)

        self.start_progress = QtWidgets.QProgressDialog(self.centralwidget)
        self.start_progress.setProperty("value", 0)
        self.start_progress.setObjectName("progressBar")
        self.start_progress.setVisible(False)
        self.verticalLayout.addWidget(self.start_progress)

        self.start_button = QtWidgets.QPushButton(self.centralwidget)
        self.start_button.setObjectName("pushButton")
        self.start_button.setText("Запустить")
        self.start_button.clicked.connect(self.launch_game)
        self.verticalLayout.addWidget(self.start_button)

        self.horizontalLayout.addLayout(self.verticalLayout)
        MainWindow.setCentralWidget(self.centralwidget)

        self.launch_thread = LaunchThread()
        self.launch_thread.launch_setup_signal.connect(self.launch_thread.launch_setup)
        self.launch_thread.state_update_signal.connect(self.state_update)
        self.launch_thread.progress_update_signal.connect(self.update_progress)

        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def state_update(self, value):
        self.start_button.setDisabled(value)
        self.start_progress.setVisible(value)

    def update_progress(self, progress, maxprogress, label):
        self.start_progress.setValue(progress)
        self.start_progress.setMaximum(maxprogress)
        self.start_progress.setLabelText(label)

    def launch_game(self):
        username = self.lineEdit.text()
        if not username:
            username = generate_username()[0]
        version_id = self.version_comboBox.currentText()
        instance_type = self.instance_type_comboBox.currentText()

        # Получаем базовую версию Minecraft (до знака -)
        base_version = version_id.split('-')[0]

        # Проверяем доступность Forge для выбранной версии
        if instance_type == "forge":
            forge_version = minecraft_launcher_lib.forge.find_forge_version(base_version)
            if not forge_version:
                QtWidgets.QMessageBox.warning(None, "Ошибка", 
                    f"Forge не доступен для версии Minecraft {base_version}.\n"
                    f"Пожалуйста, выберите другую версию Minecraft.\n"
                    f"Рекомендуемые версии: 1.20.1, 1.19.4, 1.18.2")
                return
            
            # Проверяем, поддерживается ли автоматическая установка
            if not minecraft_launcher_lib.forge.supports_automatic_install(forge_version):
                QtWidgets.QMessageBox.warning(None, "Предупреждение",
                    f"Forge {forge_version} требует ручной установки.\n"
                    f"После нажатия OK откроется установщик Forge.\n"
                    f"Пожалуйста, следуйте инструкциям установщика.")

        # Теперь передаем версию Optifine в поток
        if instance_type == "optifine":
            self.launch_thread.optifine_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "optifine", f"OptiFine_{base_version}_HD_U_H9.jar")
        else:
            self.launch_thread.optifine_file = None

        self.launch_thread.version_id = version_id
        self.launch_thread.username = username
        self.launch_thread.instance_type = instance_type

        self.launch_thread.launch_setup_signal.emit(version_id, username, instance_type)
        self.launch_thread.start()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())