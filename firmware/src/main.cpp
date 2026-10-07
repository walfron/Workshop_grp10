#include <Arduino.h>
#include <ESP8266WiFi.h> 
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "DHT.h"

#define DHTPIN 14        // GPIO14 (D5) pour le DHT22
#define DHTTYPE DHT11
#define PIRPIN 12        // GPIO12 (D6) — capteur PIR HC-SR501
#define BUZZERPIN 7       // GPIO7 (D7) — buzzer actif

DHT dht(DHTPIN, DHTTYPE);

// Dimensions de l'écran OLED (généralement 128x64 ou 128x32)
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Initialisation de l'écran (adresse I2C généralement 0x3C)
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

const char* ssid = "myDiL";
const char* password = "myDiL@LILLE";

void setup() {
  Serial.begin(115200);

  // Démarrer l'écran
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("Échec de l'allocation SSD1306"));
    for(;;); // Bloque le programme si l'écran n'est pas détecté
  }
  
  // Nettoyer l'écran et configurer le texte
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("Connexion au Wi-Fi...");
  display.display(); // Toujours appeler display() pour mettre à jour l'écran

  dht.begin();
  pinMode(PIRPIN, INPUT);
  pinMode(BUZZERPIN, OUTPUT);

  // Connexion Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  // Bip après connexion WiFi réussie (buzzer actif)
  digitalWrite(BUZZERPIN, HIGH);
  delay(200);
  digitalWrite(BUZZERPIN, LOW);

  // Mettre à jour l'écran avec l'IP
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Connecte !");
  display.println("Adresse IP :");
  display.println(WiFi.localIP());
  display.display();
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Sentinel-X");
  display.println("IP: ");
  display.println(WiFi.localIP());
  display.println("----------------");
  if (isnan(h) || isnan(t)) {
    display.println("Erreur DHT11");
  } else {
    display.print("Temp: ");
    display.print(t);
    display.println(" C");
    display.print("Hum: ");
    display.print(h);
    display.println(" %");
  }

  // Logique capteur PIR (D6)
  int pirState = digitalRead(PIRPIN);
  if (pirState == HIGH) {
    display.println("INTRUSION !");
  } else {
    display.println("Calme");
  }

  display.display();
  delay(2000);
}