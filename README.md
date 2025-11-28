Desenvolvido por Matheus Milani, Thiago moraes, Kassem hamdoun, Vinicius Rodriges
Alunos instituto maua de tecnologia
Projeto ECA407 e ECA409

  Funcionalidades

Leitura de temperatura e umidade (SHT31)

Leitura de peso via HX711 + célula de carga

Controle automático:

Aquecedor (GPIO22)

Ventoinha (GPIO20)

Comunicação via USB Serial

Dashboard em PySide6 para monitoramento em tempo real

  Arquivos do Projeto

SecadoraInteligenteFinal.c – Firmware do Pico (leitura dos sensores, controle e envio serial)

Ui.py – Dashboard PySide6

CMakeLists.txt – Configuração do projeto

   Instalar Dashboard
pip install pyserial PySide6
python Ui.py
