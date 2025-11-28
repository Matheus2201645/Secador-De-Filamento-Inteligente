import sys
import serial
import serial.tools.list_ports
import re
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QComboBox, 
                               QTextEdit, QFrame, QGroupBox)
from PySide6.QtCore import QThread, Signal, Qt, Slot
from PySide6.QtGui import QFont, QColor

# --- Thread de Trabalho (Serial Worker) ---
class SerialWorker(QThread):
    # Sinais para comunicar com a interface principal
    data_received = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, port_name, baud_rate=115200):
        super().__init__()
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.is_running = True
        self.serial_port = None

    def run(self):
        try:
            self.serial_port = serial.Serial(self.port_name, self.baud_rate, timeout=1)
            print(f"Conectado a {self.port_name}")
            
            while self.is_running:
                if self.serial_port.in_waiting:
                    # Lê a linha, decodifica bytes para string e remove espaços extras
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self.data_received.emit(line)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

    def stop(self):
        self.is_running = False
        self.wait()

# --- Janela Principal ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor de Secagem de Filamento")
        self.resize(800, 500)
        
        # Variável para a thread
        self.worker = None

        # Regex para capturar os dados do seu printf:
        # Padrão: "T: %.1f C | H: %.1f %% | Peso: %.0f | Aquecedor: %s"
        self.regex_pattern = re.compile(r"T:\s*([\d.]+)\s*C\s*\|\s*H:\s*([\d.]+)\s*%\s*\|\s*Peso:\s*([-\d.]+)\s*\|\s*Aquecedor:\s*(ON|OFF)")

        self.setup_ui()
        self.refresh_ports()

    def setup_ui(self):
        # Layout Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Área de Conexão ---
        conn_layout = QHBoxLayout()
        
        self.combo_ports = QComboBox()
        self.btn_refresh = QPushButton("Atualizar Portas")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        
        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setCheckable(True) # Botão funciona como Toggle (Liga/Desliga)
        self.btn_connect.clicked.connect(self.toggle_connection)

        conn_layout.addWidget(QLabel("Porta Serial:"))
        conn_layout.addWidget(self.combo_ports)
        conn_layout.addWidget(self.btn_refresh)
        conn_layout.addWidget(self.btn_connect)
        
        main_layout.addLayout(conn_layout)

        # --- Dashboard (Displays) ---
        dash_layout = QHBoxLayout()

        # Widget Temperatura
        self.lbl_temp = self.create_card("Temperatura", "--- °C", "#FF5722") # Laranja
        dash_layout.addWidget(self.lbl_temp['frame'])

        # Widget Umidade
        self.lbl_hum = self.create_card("Umidade", "--- %", "#2196F3") # Azul
        dash_layout.addWidget(self.lbl_hum['frame'])

        # Widget Peso
        self.lbl_weight = self.create_card("Peso", "--- g", "#4CAF50") # Verde
        dash_layout.addWidget(self.lbl_weight['frame'])

        # Widget Aquecedor (Status)
        self.lbl_heater = self.create_card("Aquecedor", "OFF", "#9E9E9E") # Cinza
        dash_layout.addWidget(self.lbl_heater['frame'])

        main_layout.addLayout(dash_layout)

        # --- Log de Texto (Terminal) ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        main_layout.addWidget(QLabel("Log Serial:"))
        main_layout.addWidget(self.log_view)

    def create_card(self, title, default_val, color_hex):
        """Cria um cartão visual para exibir dados"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(f"QFrame {{ background-color: {color_hex}; border-radius: 10px; }}")
        
        layout = QVBoxLayout(frame)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        lbl_title.setAlignment(Qt.AlignCenter)
        
        lbl_value = QLabel(default_val)
        lbl_value.setStyleSheet("color: white; font-weight: bold; font-size: 28px;")
        lbl_value.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        
        return {'frame': frame, 'label': lbl_value}

    def refresh_ports(self):
        self.combo_ports.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.combo_ports.addItem(port.device)

    def toggle_connection(self):
        if self.btn_connect.isChecked():
            # Iniciar Conexão
            port = self.combo_ports.currentText()
            if not port:
                self.log_message("Selecione uma porta serial!")
                self.btn_connect.setChecked(False)
                return

            self.worker = SerialWorker(port)
            self.worker.data_received.connect(self.process_data)
            self.worker.error_occurred.connect(self.handle_error)
            self.worker.start()
            
            self.btn_connect.setText("Desconectar")
            self.btn_connect.setStyleSheet("background-color: #ffcccc; color: red;")
            self.combo_ports.setEnabled(False)
            self.btn_refresh.setEnabled(False)
            self.log_message(f"Conectando a {port}...")
        else:
            # Parar Conexão
            if self.worker:
                self.worker.stop()
                self.worker = None
            
            self.btn_connect.setText("Conectar")
            self.btn_connect.setStyleSheet("")
            self.combo_ports.setEnabled(True)
            self.btn_refresh.setEnabled(True)
            self.log_message("Desconectado.")

    @Slot(str)
    def process_data(self, line):
        # 1. Mostrar linha crua no log
        self.log_message(line)

        # 2. Tentar parsear a string formatada do seu C code
        # Formato esperado: T: 85.0 C | H: 20.0 % | Peso: 150 | Aquecedor: ON
        match = self.regex_pattern.search(line)
        
        if match:
            temp = match.group(1)
            hum = match.group(2)
            weight = match.group(3)
            heater = match.group(4)

            # Atualizar Interface
            self.lbl_temp['label'].setText(f"{temp} °C")
            self.lbl_hum['label'].setText(f"{hum} %")
            self.lbl_weight['label'].setText(f"{weight} g")
            self.lbl_heater['label'].setText(heater)

            # Mudar cor do card do aquecedor dinamicamente
            if heater == "ON":
                self.lbl_heater['frame'].setStyleSheet("QFrame { background-color: #F44336; border-radius: 10px; }") # Vermelho Quente
            else:
                self.lbl_heater['frame'].setStyleSheet("QFrame { background-color: #9E9E9E; border-radius: 10px; }") # Cinza

    @Slot(str)
    def handle_error(self, error_msg):
        self.log_message(f"ERRO: {error_msg}")
        # Força desconexão visual
        self.btn_connect.click() 

    def log_message(self, msg):
        self.log_view.append(msg)
        # Scroll automático para o fim
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

if __name__ == "__main__":
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Estilo geral Fusion (mais bonito que o padrão do Windows/Linux)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())