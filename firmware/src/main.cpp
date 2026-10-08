#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "DHT.h"
#include "credentials.h"
#include <PubSubClient.h>
#include <time.h>
#include <BearSSLHelpers.h>
#include "ca.h"

BearSSL::WiFiClientSecure espClient;
PubSubClient client(espClient);
BearSSL::X509List caCertGlobal(cert_pem); // ancre TLS globale (pas locale)

bool remoteBuzzer = false;
bool remoteLedRouge = false;
bool remoteLedVerte = false;

#define DHTPIN 14        // GPIO14 (D5) — DHT22
#define DHTTYPE DHT11
#define PIRPIN 12        // GPIO12 (D6) — PIR HC-SR501
#define BUZZER_PIN 13     // GPIO13 (D7) — buzzer actif
#define LED_ROUGE 15      // GPIO15 (D8) — LED alerte
#define LED_VERTE 16      // GPIO16 (D0) — LED connectée

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
  applyCommand(msg, "led_green", remoteLedVerte);
}

static int reconnectDelay = 5000; // 5s initial, double jusqu'a 60s

void reconnectMQTT() {
  if (!client.connected()) {
    delay(reconnectDelay);
    reconnectDelay = min(reconnectDelay * 2, 60000);
    Serial.print("MQTT connexion...");
    espClient.setX509Time(time(nullptr)); // heure mise a jour avant chaque connexion TLS
    yield();
    if (client.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)) {
      Serial.println("connecte");
      reconnectDelay = 2000; // reset
      client.subscribe(MQTT_TOPIC_COMMAND);
    } else {
      Serial.print("echec, rc=");
      Serial.println(client.state());
      char sslError[128];
      espClient.getLastSSLError(sslError, sizeof(sslError));
      Serial.printf("rc=%d | SSL: %s | heure: %lld\n", client.state(), sslError, (long long)time(nullptr));
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
  digitalWrite(LED_ROUGE, LOW);

  WiFi.config(IPAddress(192, 168, 10, 21), IPAddress(192, 168, 10, 10), IPAddress(255, 255, 255, 0));
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int wifiTimeout = 0;
  while (WiFi.status() != WL_CONNECTED && wifiTimeout < 20) {
    delay(500);
    yield();
    wifiTimeout++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WIFI FAIL"));
    display.println("WIFI: FAIL");
    display.display();
    delay(2000);
    ESP.restart();
  }

  Serial.println(F("WiFi OK"));
  tone(BUZZER_PIN, 1000);
  delay(500);
  noTone(BUZZER_PIN);

  configTime(0, 0, "192.168.10.10");
  espClient.setTrustAnchors(&caCertGlobal);
  int timeWait = 0;
  while (time(nullptr) < 1700000000 && timeWait < 20) {
    delay(500);
    yield();
    timeWait++;
  }
  Serial.printf("Heure: %lld - OK\n", (long long)time(nullptr));
  espClient.setBufferSizes(1024, 1024);

  client.setServer(IPAddress(192, 168, 10, 10), MQTT_PORT);
  client.setCallback(onCommand);
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

unsigned long lastDisplay = 0;

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  int gazValue = analogRead(A0);
  int pirState = digitalRead(PIRPIN);

  // Alerte : intrusion OU gaz élevé (sans seuil IA, seuil de démo)
  alertActive = (pirState == HIGH) || (gazValue > 700);

  // Motif alarme (intrusion / gaz)
  if (alertActive) {
    tone(BUZZER_PIN, 1200); delay(150); noTone(BUZZER_PIN); delay(100);
    tone(BUZZER_PIN, 1200); delay(150); noTone(BUZZER_PIN); delay(100);
    tone(BUZZER_PIN, 1200); delay(500); noTone(BUZZER_PIN);
  }

  // Cri de hibou (commande dashboard)
  if (remoteBuzzer) {
    tone(BUZZER_PIN, 400); delay(300); noTone(BUZZER_PIN); delay(100);
    tone(BUZZER_PIN, 800); delay(300); noTone(BUZZER_PIN); delay(200);
  }

  // Clignotement LED rouge (alerte) — gestion non bloquante
  if (alertActive || remoteLedRouge) {
    if (millis() - lastBlink > 300) {
      lastBlink = millis();
      blinkState = !blinkState;
      digitalWrite(LED_ROUGE, blinkState ? HIGH : LOW);
    }
  } else {
    digitalWrite(LED_ROUGE, LOW);
  }

  digitalWrite(LED_VERTE, remoteLedVerte ? HIGH : LOW);

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

  // LED verte : allumee si WiFi OK et MQTT connecte (ou commande remote)
  bool etatVerte = remoteLedVerte || (WiFi.status() == WL_CONNECTED && client.connected());
  digitalWrite(LED_VERTE, etatVerte ? HIGH : LOW);

  auto num = [](float v) { return isnan(v) ? String("null") : String(v, 1); };
  String payload = String("{\"device_id\":\"") + MQTT_CLIENT_ID + "\"" +
    ",\"temperature\":" + num(t) +
    ",\"humidity\":" + num(h) +
    ",\"gas\":" + String(gazValue) +
    ",\"presence\":" + (pirState == HIGH ? "true" : "false") + "}";
  client.publish(MQTT_TOPIC_TELEMETRY, payload.c_str());

  display.display();

  if (millis() - lastDisplay >= 2000) {
    lastDisplay = millis();
  }

  delay(100);
}
