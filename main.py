import minecraft_launcher_lib
import subprocess

minecraft_directory=minecraft_launcher_lib.utils.get_minecraft_directory().replace('minecraft', 'asetlauncher')

version = input('Enter Minecraft version: ')
username = input('Enter username: ')

#Установка версии майнкрафт
minecraft_launcher_lib.install.install_minecraft_version(versionid=version, minecraft_directory=minecraft_directory)

#Переменные для команды запуска
options = {
    'username': username,
    'uuid': '',
    'token': ''
}

#Запуск майнкрафта
subprocess.call(minecraft_launcher_lib.command.get_minecraft_command(version=version, minecraft_directory=minecraft_directory, options=options))