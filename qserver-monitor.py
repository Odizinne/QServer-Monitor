import paramiko
import configparser
import os
from PyQt6 import QtWidgets, uic, QtGui, QtCore

class SSHWorker(QtCore.QThread):
    data_ready = QtCore.pyqtSignal(object)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        self.get_server_info()

    def get_server_info(self):
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.config['SSH']['hostname'],
                port=int(self.config['SSH']['port']),
                username=self.config['SSH']['username'],
                password=self.config['SSH']['password']
            )

            stdin, stdout, stderr = ssh.exec_command('free -m')
            ram_info = stdout.readlines()[1].split()
            total_ram = int(ram_info[1])
            used_ram = int(ram_info[2])

            stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep '%Cpu(s)'")
            cpu = stdout.read().decode().split()
            cpu_load = float(cpu[1].strip('%us,'))

            stdin, stdout, stderr = ssh.exec_command("df -h --total | grep total")
            storage_info = stdout.read().decode('UTF-8').strip().split()
            total_storage = storage_info[1]
            used_storage = storage_info[2]

            services = self.config['SSH']['services'].split(',')
            service_statuses = {}
            for service in services:
                stdin, stdout, stderr = ssh.exec_command(f"systemctl is-active {service}")
                service_status = stdout.read().decode('UTF-8').strip()
                service_statuses[service] = service_status

            stdin, stdout, stderr = ssh.exec_command("cat /etc/os-release | grep PRETTY_NAME")
            distro_name = stdout.read().decode().split('=')[1].strip().strip('"')

            stdin, stdout, stderr = ssh.exec_command("uname -r")
            kernel_version = stdout.read().decode().strip()

            stdin, stdout, stderr = ssh.exec_command("uptime -p")
            uptime = stdout.read().decode().strip()

        self.data_ready.emit((total_ram, used_ram, cpu_load, total_storage, used_storage, service_statuses, distro_name, kernel_version, uptime))

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        script_dir = os.path.dirname(os.path.realpath(__file__))
        ui_path = os.path.join(script_dir, 'design.ui')
        uic.loadUi(ui_path, self)
        self.setWindowTitle("QServer Monitor")
        config_path = os.path.join(script_dir, 'config.ini')
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.worker = SSHWorker(self.config)
        self.worker.data_ready.connect(self.update_infos)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.fetch_info)
        self.timer.start(5000)
        self.fetch_info()

    def fetch_info(self):
        if not self.worker.isRunning():
            self.worker.start()

    def update_infos(self, data):
        total_ram, used_ram, cpu_load, total_storage, used_storage, service_statuses, distro_name, kernel_version, uptime = data

        self.distroLabel.setText(distro_name)
        self.uptimeLabel.setText(uptime)

        ram_usage_percentage = int((used_ram / total_ram) * 100)
        self.ramProgressBar.setValue(ram_usage_percentage)
        self.ramProgressBar.setTextVisible(False)

        self.ramValueLabel.setText(f"{used_ram}M / {total_ram}M ({ram_usage_percentage}%)")

        self.cpuProgressBar.setValue(round(cpu_load))
        self.cpuProgressBar.setTextVisible(False)

        self.cpuValueLabel.setText(f"{round(cpu_load)}%")

        storage_usage_percentage = int((float(used_storage[:-1]) / float(total_storage[:-1])) * 100)
        self.storageProgressBar.setValue(storage_usage_percentage)
        self.storageProgressBar.setTextVisible(False)

        self.storageValueLabel.setText(f"{used_storage} / {total_storage} ({storage_usage_percentage}%)")

        self.tableWidget.setRowCount(len(service_statuses))
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels(["Service", "Status"])
        for i, (service, status) in enumerate(service_statuses.items()):
            self.tableWidget.setItem(i, 0, QtWidgets.QTableWidgetItem(service))
            status_item = QtWidgets.QTableWidgetItem(status)
            if status == 'active':
                status_item.setForeground(QtGui.QBrush(QtGui.QColor('green')))
            else:
                status_item.setForeground(QtGui.QBrush(QtGui.QColor('red')))
            self.tableWidget.setItem(i, 1, status_item)

        self.tableWidget.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
