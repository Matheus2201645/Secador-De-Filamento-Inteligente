/**
 * Secadora Filamento para Raspberry Pi Pico 2 W
 * * Hardware:
 * - Load Cell (HX711): DT=GP16, SCK=GP17
 * - SHT31 (Temp/Hum): SDA=GP18, SCL=GP19 (I2C1)
 * - Fan (Ventoinha): GP20
 * - Heater (SSR): GP22
 */

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/gpio.h"

// --- Definições de Pinos ---
#define HX711_DT_PIN  16
#define HX711_SCK_PIN 17
#define I2C_SDA_PIN   19
#define I2C_SCL_PIN   18
#define FAN_PIN       20
#define HEATER_PIN    22

// --- Configurações do I2C (SHT31) ---
#define I2C_PORT      i2c1
uint8_t SHT31_ADDR = 0x44; 

// --- Parâmetros de Controle ---
float TARGET_TEMP = 85.0;       
float TEMP_HYSTERESIS = 5.0;    
float MAX_SAFE_TEMP = 95.0;     

// Variáveis globais para calibração da balança
long ZERO_OFFSET = 0;
float CALIBRATION_FACTOR = 426.0; 



int32_t hx711_read_raw() {
    uint32_t count = 0;
    // Aguarda o chip estar pronto
    while (gpio_get(HX711_DT_PIN));
    
    // Leitura dos bits
    for (int i = 0; i < 24; i++) {
        gpio_put(HX711_SCK_PIN, 1);
        sleep_us(1);
        gpio_put(HX711_SCK_PIN, 0);
        sleep_us(1);
        count = count << 1;
        if (gpio_get(HX711_DT_PIN)) count++;
    }
    
    // Utilizei Ganho 128 para redução de ruido
    gpio_put(HX711_SCK_PIN, 1);
    sleep_us(1);
    gpio_put(HX711_SCK_PIN, 0);
    sleep_us(1);
    
    if (count & 0x800000) count |= 0xFF000000;
    return (int32_t)count;
}

float get_weight_units() {
    int32_t val = hx711_read_raw();
    return (float)(val - ZERO_OFFSET) / CALIBRATION_FACTOR;
}

bool sht31_read(float *temp, float *hum) {
    uint8_t cmd[2] = {0x24, 0x00}; 
    uint8_t buf[6];

    int ret = i2c_write_blocking(I2C_PORT, SHT31_ADDR, cmd, 2, false);
    if (ret == PICO_ERROR_GENERIC) return false;


    sleep_ms(20);


    ret = i2c_read_blocking(I2C_PORT, SHT31_ADDR, buf, 6, false);

    uint16_t raw_temp = (buf[0] << 8) | buf[1];
    *temp = -45.0f + (175.0f * (float)raw_temp / 65535.0f);
    uint16_t raw_hum = (buf[3] << 8) | buf[4];
    *hum = 100.0f * ((float)raw_hum / 65535.0f);
    return true;
}
void setup() {
    stdio_init_all();
    
    gpio_init(HEATER_PIN);
    gpio_set_dir(HEATER_PIN, GPIO_OUT);
    gpio_put(HEATER_PIN, 0);

    gpio_init(FAN_PIN);
    gpio_set_dir(FAN_PIN, GPIO_OUT);
    gpio_put(FAN_PIN, 0);

    gpio_init(HX711_DT_PIN);
    gpio_set_dir(HX711_DT_PIN, GPIO_IN);
    gpio_init(HX711_SCK_PIN);
    gpio_set_dir(HX711_SCK_PIN, GPIO_OUT);
    gpio_put(HX711_SCK_PIN, 0);

    i2c_init(I2C_PORT, 100 * 1000); // 100kHz
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);

    sleep_ms(5000); 

    printf("\n=== Inicializando Sistema de Secagem ===\n");

    printf("Tarando balança (nao coloque peso agora)...\n");
    long soma = 0;
    for(int i=0; i<10; i++) {
        soma += hx711_read_raw();
        sleep_ms(50);
    }
    ZERO_OFFSET = soma / 10;
    printf("Tara definida em: %ld\n", ZERO_OFFSET);
}

int main() {
    setup();

    float current_temp = 0.0;
    float current_hum = 0.0;
    float weight = 0.0;
    bool heater_state = false;

    while (true) {
        bool sensor_ok = sht31_read(&current_temp, &current_hum);

        weight = get_weight_units();

        if (!sensor_ok) {
            
            gpio_put(HEATER_PIN, 0);
            heater_state = false;
            
            gpio_put(FAN_PIN, 1); 
            
            sleep_ms(2000);
        }
        if (current_temp >= MAX_SAFE_TEMP) {
            heater_state = false;
            printf("!!! PERIGO: Temperatura acima do limite de seguranca (%.1f C) !!!\n", current_temp);
        } 
        else {
            if (current_temp < (TARGET_TEMP - TEMP_HYSTERESIS)) {
                heater_state = true;
            } else if (current_temp > TARGET_TEMP) {
                heater_state = false;
            }
        }

        gpio_put(HEATER_PIN, heater_state);
        
        if (current_temp > 35.0 || heater_state) {
            gpio_put(FAN_PIN, 1);
        } else {
            gpio_put(FAN_PIN, 0);
        }

        printf("T: %.1f C | H: %.1f %% | Peso: %.0f | Aquecedor: %s\n", 
               current_temp, current_hum, weight, heater_state ? "ON" : "OFF");
        sleep_ms(1000);
    }
}