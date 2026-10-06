#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <PubSubClient.h>
#include "DHT.h"
#include "config.h"

#define DHTPIN 14        // GPIO14 (D5) — DHT
#define DHTTYPE DHT11
#define PIRPIN 12        // GPIO12 (D6) — PIR HC-SR501
#define BUZZER_PIN 13    // GPIO13 (D7) — buzzer actif
#define LED_ROUGE 15     // GPIO15 (D8) — LED alerte
#define LED_VERTE 16     // GPIO16 (D0) — LED connectée
#define GAZ_SEUIL_DEMO 700

WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHTPIN, DHTTYPE);
Adafruit_SSD1306 display(128, 64, &Wire, -1);

unsigned long lastBlink = 0;
bool blinkState = false;
bool remoteBuzzer = false;
bool remoteLedRouge = false;

void applyCommand(const String& msg, const char* key, bool& target) {
  if (msg.indexOf(String("\"") + key + "\":true") >= 0) target = true;
  if (msg.indexOf(String("\"") + key + "\":false") >= 0) target = false;
}

void onCommand(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.println("Commande recue : " + msg);
  applyCommand(msg, "buzzer", remoteBuzzer);
  applyCommand(msg, "led_red", remoteLedRouge);
}

void reconnectMQTT() {
  Serial.print("MQTT connexion...");
  if (client.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)) {
    Serial.println("connecte a " MQTT_HOST);
    client.subscribe(MQTT_TOPIC_COMMAND);
  } else {
    Serial.print("echec, rc=");
    Serial.println(client.state());
  }
}

String jsonNumber(float value) {
  return isnan(value) ? String("null") : String(value, 1);
}

void publishTelemetry(float t, float h, int gaz, bool presence) {
  String payload = String("{\"device_id\":\"") + MQTT_CLIENT_ID + "\"" +
    ",\"temperature\":" + jsonNumber(t) +
    ",\"humidity\":" + jsonNumber(h) +
    ",\"gas\":" + String(gaz) +
    ",\"presence\":" + (presence ? "true" : "false") + "}";
  client.publish(MQTT_TOPIC_TELEMETRY, payload.c_str());
  Serial.println(payload);
}

void playAlarm() {
  tone(BUZZER_PIN, 1200); delay(150); noTone(BUZZER_PIN); delay(100);
  tone(BUZZER_PIN, 1200); delay(150); noTone(BUZZER_PIN); delay(100);
  tone(BUZZER_PIN, 1200); delay(500); noTone(BUZZER_PIN);
}

void updateLeds(bool alertActive) {
  if (alertActive && millis() - lastBlink > 300) {
    lastBlink = millis();
    blinkState = !blinkState;
  }
  digitalWrite(LED_ROUGE, (alertActive && blinkState) || remoteLedRouge ? HIGH : LOW);
  digitalWrite(LED_VERTE, client.connected() ? HIGH : LOW);
}

void showHeader() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("SENTINEL-X");
  display.println("AETHER / SN-001");
  display.println("----------------");
}

void updateDisplay(float t, float h, int gaz, bool presence) {
  showHeader();
  display.println("WIFI: OK");
  display.println(WiFi.localIP());
  if (presence) display.println("! INTRUSION !");
  if (gaz > GAZ_SEUIL_DEMO) display.println("* GAZ ELEVE *");
  display.println("----------------");
  if (isnan(h) || isnan(t)) {
    display.println("Erreur DHT");
  } else {
    display.printf("T: %.1fC  H: %.1f%%\n", t, h);
  }
  display.printf("GAZ: %d\n", gaz);
  display.println(presence ? "PIR: INTRUSION" : "PIR: CALME");
  display.display();
}

void setup() {
  Serial.begin(115200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("Echec SSD1306"));
    for (;;);
  }
  display.setTextSize(1);
  display.setTextColor(WHITE);
  showHeader();
  display.println("Connexion WiFi...");
  display.display();

  dht.begin();
  pinMode(PIRPIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_ROUGE, OUTPUT);
  pinMode(LED_VERTE, OUTPUT);
  digitalWrite(LED_ROUGE, LOW);
  digitalWrite(LED_VERTE, LOW);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int attempt = 0; attempt < 20 && WiFi.status() != WL_CONNECTED; attempt++) delay(500);
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WIFI FAIL"));
    display.println("WIFI: FAIL");
    display.display();
    for (;;);
  }

  Serial.println(F("WiFi OK"));
  tone(BUZZER_PIN, 1000);
  delay(500);
  noTone(BUZZER_PIN);

  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setCallback(onCommand);
  reconnectMQTT();
}

void loop() {
  if (!client.connected()) reconnectMQTT();
  client.loop();

  float h = dht.readHumidity();
  float t = dht.readTemperature();
  int gazValue = analogRead(A0);
  bool presence = digitalRead(PIRPIN) == HIGH;
  bool alertActive = presence || gazValue > GAZ_SEUIL_DEMO;

  if (alertActive || remoteBuzzer) playAlarm();
  updateLeds(alertActive);
  updateDisplay(t, h, gazValue, presence);
  publishTelemetry(t, h, gazValue, presence);

  delay(2000);
}
