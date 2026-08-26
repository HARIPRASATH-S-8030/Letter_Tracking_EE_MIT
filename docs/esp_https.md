# ESP32 and ESP8266 HTTPS status updates

The deployed application is the HTTPS server. Each ESP board should post directly to it after it scans a QR code. Do not expect a cloud host such as Render to call a private `192.168.x.x` device: it cannot reach your Wi-Fi network.

Both boards use the same API. Use either endpoint below:

- `POST https://your-app.example.com/esp_submit` for input-box scans
- `POST https://your-app.example.com/esp_approve` for output-box scans
- `POST https://your-app.example.com/esp_action` with `action=submit` or `action=approve`

The server accepts JSON or `application/x-www-form-urlencoded`. Send the scanned QR text as `code`; it may be a full `/submit?id=...` URL or just the application ID. Configure the same `ESP_TOKEN` value in the host and send it in the `X-ESP-Token` header.

## ESP32 (Arduino-ESP32)

```cpp
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

bool postScan(const String& qrText) {
  WiFiClientSecure client;
  client.setInsecure(); // Demo only. Use the CA certificate in production.
  HTTPClient https;
  if (!https.begin(client, "https://your-app.example.com/esp_submit")) return false;
  https.addHeader("Content-Type", "application/json");
  https.addHeader("X-ESP-Token", "replace-with-ESP_TOKEN");
  String body = "{\"code\":\"" + qrText + "\"}";
  int status = https.POST(body);
  https.end();
  return status == 200;
}
```

## ESP8266 (ESP8266Arduino)

```cpp
#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#include <ESP8266HTTPClient.h>

bool postScan(const String& appId) {
  BearSSL::WiFiClientSecure client;
  client.setInsecure(); // Demo only. Use BearSSL trust anchors in production.
  HTTPClient https;
  if (!https.begin(client, "https://your-app.example.com/esp_submit")) return false;
  https.addHeader("Content-Type", "application/x-www-form-urlencoded");
  https.addHeader("X-ESP-Token", "replace-with-ESP_TOKEN");
  int status = https.POST("app_id=" + appId); // Send the ID extracted from the QR URL.
  https.end();
  return status == HTTP_CODE_OK;
}
```

`setInsecure()` is useful only to isolate connectivity problems during development. Before deployment, pin a trusted CA certificate or a server certificate/fingerprint appropriate to the board library. Do not embed SMTP, Twilio, or other provider credentials in the ESP firmware.
