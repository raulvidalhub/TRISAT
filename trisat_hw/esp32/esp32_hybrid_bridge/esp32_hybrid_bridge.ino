#include <WiFi.h>
#include <WiFiUdp.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "galileo_inav.h"

// =========================================================================
// TRISAT ESP32 Hybrid Telemetry Bridge
// Single-Frequency NMEA + Paced Galileo I/NAV (OSNMA) Telemetry
// =========================================================================
// Verified hardware wiring:
// PIN 19: Orange Wire (u-blox TX -> ESP32 RX)
// PIN 18: White Wire  (u-blox RX <- ESP32 TX)
// Baud rate: 115200 bps
// =========================================================================
#define RXD2 19
#define TXD2 18
#define GNSS_BAUD 115200

// WiFi Configuration
const char* AP_SSID = "TRISAT-GNSS";
const char* AP_PASS = "trisat4ever";

WiFiUDP udp;
const int UDP_PORT = 9090;
IPAddress broadcastIp(192, 168, 4, 255);

// BLE Nordic UART Service (NUS)
#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

BLEServer *pServer = NULL;
BLECharacteristic *pTxCharacteristic = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      Serial.println("\n[BLE] Client connected (iPhone / iPad / macOS)!");
    };
    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      Serial.println("\n[BLE] Client disconnected.");
    }
};

// =========================================================================
// UBX-RXM-SFRBX Galileo I/NAV bridge
// =========================================================================
GalileoUbxDecoder galileoDecoder;
unsigned long lastInavBleMs = 0;

void forwardInav(const GalileoInavPage& page) {
  char sentence[GalileoInavPage::sentenceCapacity];
  const size_t length = page.formatSentence(sentence);
  if (!length) return;

  udp.beginPacket(broadcastIp, UDP_PORT);
  udp.write(reinterpret_cast<const uint8_t*>(sentence), length);
  udp.endPacket();
  Serial.print(sentence);

  // Preserve the existing BLE pacing and chunk size.
  if (deviceConnected && (millis() - lastInavBleMs >= 1200)) {
    lastInavBleMs = millis();
    for (size_t offset = 0; offset < length; offset += 20) {
      const size_t chunk = min(static_cast<size_t>(20), length - offset);
      pTxCharacteristic->setValue(reinterpret_cast<uint8_t*>(sentence + offset), chunk);
      pTxCharacteristic->notify();
      delay(4);
    }
  }
}

// =========================================================================
// Setup
// =========================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n==========================================");
  Serial.println("  TRISAT ESP32 Bridge (NMEA + I/NAV Paced) ");
  Serial.println("==========================================");

  // 1. Hardware UART2 towards u-blox at 115200 bps with expanded 4KB buffer
  Serial2.setRxBufferSize(4096);
  Serial2.begin(GNSS_BAUD, SERIAL_8N1, RXD2, TXD2);

  // 2. Initialize WiFi Access Point
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  udp.begin(UDP_PORT);
  Serial.printf("[+] UDP Streaming on port :%d\n", UDP_PORT);

  // 3. Initialize BLE (Nordic UART Service)
  BLEDevice::init("TRISAT-GNSS-BLE");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);
  pTxCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID_TX,
                        BLECharacteristic::PROPERTY_NOTIFY
                      );
  pTxCharacteristic->addDescriptor(new BLE2902());

  BLECharacteristic *pRxCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID_RX,
                        BLECharacteristic::PROPERTY_WRITE
                      );

  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  Serial.println("[+] BLE Advertising active as: TRISAT-GNSS-BLE");
  Serial.println("[+] System ready. Streaming NMEA + paced Galileo I/NAV...\n");
}

// =========================================================================
// Main Loop
// =========================================================================
String nmeaBuffer = "";
bool isNmea = false;

void loop() {
  while (Serial2.available()) {
    uint8_t c = (uint8_t)Serial2.read();

    const bool wasIdle = galileoDecoder.idle();
    GalileoInavPage page;
    if (galileoDecoder.feed(c, page)) forwardInav(page);

    // Exclude every UBX byte, including the final checksum byte, from NMEA.
    if (wasIdle && galileoDecoder.idle()) {
      if (c == '$') {
        nmeaBuffer = "$";
        isNmea = true;
      } else if (isNmea) {
        if (c == '\n' || c == '\r') {
          if (nmeaBuffer.length() > 6 && (nmeaBuffer.startsWith("$GP") || nmeaBuffer.startsWith("$GA") || nmeaBuffer.startsWith("$GL") || nmeaBuffer.startsWith("$GB") || nmeaBuffer.startsWith("$GN"))) {
            nmeaBuffer += "\n";
            // Echo to USB Serial
            Serial.print(nmeaBuffer);

            // Broadcast over WiFi UDP (:9090)
            udp.beginPacket(broadcastIp, UDP_PORT);
            udp.write((const uint8_t*)nmeaBuffer.c_str(), nmeaBuffer.length());
            udp.endPacket();

            // Stream essential NMEA over BLE (GGA, RMC, GSV)
            if (deviceConnected && (nmeaBuffer.startsWith("$GNGGA") || nmeaBuffer.startsWith("$GPGGA") ||
                nmeaBuffer.startsWith("$GNRMC") || nmeaBuffer.startsWith("$GAGSV") ||
                nmeaBuffer.startsWith("$GPGSV"))) {
              int len = nmeaBuffer.length();
              int offset = 0;
              while (offset < len) {
                int chunk = min(20, len - offset);
                pTxCharacteristic->setValue((uint8_t*)(nmeaBuffer.c_str() + offset), chunk);
                pTxCharacteristic->notify();
                offset += chunk;
                delay(3);
              }
            }
          }
          nmeaBuffer = "";
          isNmea = false;
        } else if (c >= 0x20 && c <= 0x7E && nmeaBuffer.length() < 120) {
          nmeaBuffer += (char)c;
        } else {
          nmeaBuffer = "";
          isNmea = false;
        }
      }
    }
  }

  // Handle BLE reconnection
  if (!deviceConnected && oldDeviceConnected) {
    delay(500);
    pServer->startAdvertising();
    Serial.println("\n[BLE] Restarting advertising...");
    oldDeviceConnected = deviceConnected;
  }
  if (deviceConnected && !oldDeviceConnected) {
    oldDeviceConnected = deviceConnected;
  }
}
