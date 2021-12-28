#include <Arduino.h>
#include <AsyncDelay.h>
#include <MHZ19.h>  // https://github.com/WifWaf/MH-Z19
#include <Wire.h>
#include <U8g2lib.h>
#include <analogWrite.h> // https://github.com/ERROPiX/ESP32_AnalogWrite
//#define analogWrite ledcWrite // ja lieto platform.io - TIL tam nepatīk analogWrite

U8G2_SSD1306_128X64_NONAME_1_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE);
MHZ19 sensors;

//#include "grafikas.h"

//Lai GAISA SARGA smadzenes zinātu, kur atrodas tā ķermeņa daļas- tās ir jādefinē
const int SARKANS = 33; //LED sarkanais
const int DZELTENS = 25; //LED dzeltenais
const int ZALS = 26; //LED zaljais
const int BALSS = 32; //piikstulis
const int GAISMA = 34; //fotorezistors
const int ROKA = 35; //poga uz rokas
const int EKRANS_DATI = 21; //OLED SDA
const int EKRANS_PULKSTENS = 22; //OLED SCL
const int KREISAA_ACS = 23; //LED kreisaa acs
const int LABAA_ACS = 19; //LED labaa acs

void personiba(int ppm, int gaisma){
  u8g2.setFont(u8g2_font_open_iconic_human_6x_t);
  u8g2.drawGlyph(1, 48, 66);	
  u8g2.setFont(u8g2_font_logisoso32_tf);
  if(ppm <= 1000){
    u8g2.setCursor(48+9, 42);
    u8g2.print(ppm);
  } else {
    u8g2.setCursor(49, 42);
    u8g2.print(ppm);
  }

  u8g2.setCursor(14,35);
  u8g2.setColorIndex(0);
  u8g2.setFont(u8g2_font_logisoso16_tf);
  u8g2.print("CO");
  u8g2.setCursor(33,22);
  u8g2.setColorIndex(0);
  u8g2.setFont(u8g2_font_8x13_tf);
  u8g2.print("2");

  u8g2.setFont(u8g2_font_logisoso16_tf);
  u8g2.setColorIndex(1);

  if(ppm == 0){
      analogWrite(BALSS, 0);
      digitalWrite(SARKANS, LOW);
      digitalWrite(DZELTENS, LOW);
      digitalWrite(ZALS , LOW);
      u8g2.setCursor(15,62);
      u8g2.print("Sensors iesilst");
      digitalWrite(ZALS, HIGH);
  }
  if(ppm > 0 && ppm <= 400){
      analogWrite(BALSS, 0);
      digitalWrite(SARKANS, LOW);
      digitalWrite(DZELTENS, LOW);
      digitalWrite(ZALS , LOW);
      u8g2.setCursor(15,62);
      u8g2.print("LABS GAISS!");
      digitalWrite(ZALS, HIGH);
  }
  if(ppm <= 999 && ppm >= 401){
      analogWrite(BALSS, 0);
      digitalWrite(SARKANS, LOW);
      digitalWrite(DZELTENS, LOW);
      digitalWrite(ZALS , LOW);
      u8g2.setCursor(15,62);
      u8g2.print("ATVER LOGU!");
      digitalWrite(DZELTENS, HIGH);
  }
  if(ppm <= 9999 && ppm >= 1000){
      digitalWrite(SARKANS, LOW);
      digitalWrite(DZELTENS, LOW);
      digitalWrite(ZALS , LOW);
      u8g2.setCursor(48,62);
      u8g2.print("AARRGH!");
      digitalWrite(SARKANS, HIGH);
      analogWrite(BALSS, 200);
  }
  

  //delay(3000);
  
  	
  //u8g2.print("ppm");	
}

void rita_rosme(){

  digitalWrite(SARKANS, HIGH);
  digitalWrite(DZELTENS, HIGH);
  digitalWrite(ZALS, HIGH);
  delay(1000);
  digitalWrite(SARKANS, LOW);
  digitalWrite(DZELTENS, LOW);
  digitalWrite(ZALS , LOW);
  delay(500);
  analogWrite(BALSS, 127);
  delay(200);
  analogWrite(BALSS, 200);
  delay(800);
  analogWrite(BALSS, 0);
  analogWrite(KREISAA_ACS, 200);
  analogWrite(LABAA_ACS, 200);
}

void setup() {
 pinMode(KREISAA_ACS, OUTPUT);
 pinMode(LABAA_ACS, OUTPUT);
 pinMode(SARKANS, OUTPUT);
 pinMode(DZELTENS, OUTPUT);
 pinMode(ZALS, OUTPUT);
 pinMode(BALSS, OUTPUT);
 pinMode(GAISMA, INPUT);
 pinMode(ROKA, INPUT);
 Serial.begin(115200);
 Serial2.begin(9600);
 sensors.begin(Serial2);
 sensors.autoCalibration(); //ieslēdzu auto kalibrāciju, izpētīt vai nevajag uztaisīt manuālas 400ppm kalibrācijas rutīnu. info libas git calibration example
 u8g2.begin();  
 u8g2.enableUTF8Print();

 rita_rosme();
}

void loop() {
 int co2_limenis = sensors.getCO2();
 int telpas_gaisums = analogRead(GAISMA);
 //char ppm_teksts[9];
 //sprintf(ppm_teksts, "%d", sensora_vertiba);
 Serial.println(co2_limenis);
  
  u8g2.firstPage();
  do {
    personiba(co2_limenis, telpas_gaisums);
  } while ( u8g2.nextPage() );

}
