#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "DHT.h"
#include "credentials.h"
#include <PubSubClient.h>

WiFiClient espClient;
PubSubClient client(espClient);

#define DHTPIN 14        // GPIO14 (D5) — DHT22
#define DHTTYPE DHT11
#define PIRPIN 12        // GPIO12 (D6) — PIR HC-SR501
#define BUZZER_PIN 13     // GPIO13 (D7) — buzzer actif
#define LED_ROUGE 15      // GPIO15 (D8) — LED alerte
#define LED_VERTE 16      // GPIO16 (D0) — LED connectée

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message [");
  Serial.print(topic);
  Serial.print("] ");
  String msg;
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.println(msg);
}

void reconnectMQTT() {
  if (!client.connected()) {
    Serial.print("MQTT connexion...");
    if (client.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)) {
      Serial.println("connecte");
      client.subscribe("sentinel/+/telemetry");
    } else {
      Serial.print("echec, rc=");
      Serial.println(client.state());
    }
  }
}

DHT dht(DHTPIN, DHTTYPE);

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

unsigned long lastBlink = 0;
bool blinkState = false;
bool alertActive = false;

void setup() {
  Serial.begin(115200);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("Echec SSD1306"));
    for (;;);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("SENTINEL-X");
  display.println("AETHER CORP");
  display.println("SN-001");
  display.println("----------------");
  display.println("Connexion WiFi...");
  display.display();

  dht.begin();
  pinMode(PIRPIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_ROUGE, OUTPUT);
  pinMode(LED_VERTE, OUTPUT);

  digitalWrite(LED_VERTE, LOW);
  digitalWrite(LED_ROUGE, LOW);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int wifiTimeout = 0;
  while (WiFi.status() != WL_CONNECTED && wifiTimeout < 20) {
    delay(500);
    wifiTimeout++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WIFI FAIL"));
    display.println("WIFI: FAIL");
    display.display();
    for (;;); // Arrêt avec affichage erreur
  }

  Serial.println(F("WiFi OK"));
  tone(BUZZER_PIN, 1000);
  delay(500);
  noTone(BUZZER_PIN);

  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setCallback(callback);
  reconnectMQTT();

  digitalWrite(LED_VERTE, HIGH);
  digitalWrite(LED_ROUGE, LOW);

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("SENTINEL-X");
  display.println("AETHER CORP");
  display.println("SN-001");
  display.println("----------------");
  display.println("WIFI: OK");
  display.println(WiFi.localIP());
  display.display();
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  int gazValue = analogRead(A0);
  int pirState = digitalRead(PIRPIN);

  // Alerte : intrusion OU gaz élevé (sans seuil IA, seuil de démo)
  alertActive = (pirState == HIGH) || (gazValue > 700);

  // Buzzer : 2 courts + 1 long
  if (alertActive) {
    tone(BUZZER_PIN, 1200); delay(150); noTone(BUZZER_PIN); delay(100);
    tone(BUZZER_PIN, 1200); delay(150); noTone(BUZZER_PIN); delay(100);
    tone(BUZZER_PIN, 1200); delay(500); noTone(BUZZER_PIN);
  }

  // Clignotement LED rouge (alerte) — gestion non bloquante
  if (alertActive) {
    if (millis() - lastBlink > 300) {
      lastBlink = millis();
      blinkState = !blinkState;
      digitalWrite(LED_ROUGE, blinkState ? HIGH : LOW);
    }
  } else {
    digitalWrite(LED_ROUGE, LOW);
  }

  // Affichage OLED
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("SENTINEL-X");
  display.println("AETHER / SN-001");
  display.println("----------------");
  display.println("WIFI: OK");
  display.println(WiFi.localIP());

  // Format conditionnel stylé direct dans loop()
  if (pirState == HIGH) {
    display.println(">>> PRESENCE <<<");
    display.println("! INTRUSION !");
  }
  if (gazValue > 700) {
    display.println("* GAZ ELEVEE *");
  }

  display.println("----------------");
  if (isnan(h) || isnan(t)) {
    display.println("Erreur DHT11");
  } else {
    display.print("T: ");
    display.print(t);
    display.println("C");
    display.print("H: ");
    display.print(h);
    display.println("%");
  }
  display.print("GAZ: ");
  display.println(gazValue);

  if (pirState == HIGH) {
    display.println("PIR: INTRUSION");
  } else {
    display.println("PIR: CALME");
  }

  // Gestion MQTT
  if (!client.connected()) reconnectMQTT();
  client.loop();

  // Publication données sur sentinel/data
  String payload = "{\"ip\":\"" + WiFi.localIP().toString() +
    "\",\"temp\":" + String(t, 1) +
    ",\"hum\":" + String(h, 1) +
    ",\"gaz\":" + String(gazValue) +
    ",\"pir\":" + String(pirState) +
    ",\"alert\":" + String(alertActive ? 1 : 0) + "}";
  client.publish(MQTT_TOPIC_TELEMETRY, payload.c_str());

  display.display();
  delay(2000);
}
