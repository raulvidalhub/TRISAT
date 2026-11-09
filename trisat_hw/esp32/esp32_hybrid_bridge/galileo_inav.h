#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

struct GalileoInavPage {
  uint8_t svid;
  uint8_t wordType;
  const char* band;
  uint8_t bytes[30];

  static constexpr size_t sentenceCapacity = 96;

  size_t formatSentence(char (&sentence)[sentenceCapacity]) const {
    char hex[61];
    for (size_t i = 0; i < sizeof(bytes); ++i) {
      snprintf(hex + 2 * i, 3, "%02X", static_cast<unsigned>(bytes[i]));
    }
    int length = snprintf(sentence, sizeof(sentence), "$GALINAV,%u,%u,%s,%s",
                          static_cast<unsigned>(svid), static_cast<unsigned>(wordType), hex, band);
    if (length < 0 || static_cast<size_t>(length) + 5 > sizeof(sentence)) return 0;
    uint8_t checksum = 0;
    for (int i = 1; i < length; ++i) checksum ^= static_cast<uint8_t>(sentence[i]);
    snprintf(sentence + length, sizeof(sentence) - length, "*%02X\n", static_cast<unsigned>(checksum));
    return static_cast<size_t>(length) + 4;
  }
};

class GalileoUbxDecoder {
 public:
  bool idle() const { return position == 0; }

  bool feed(uint8_t byte, GalileoInavPage& page) {
    if (position == 0) {
      if (byte == 0xB5) position = 1;
      return false;
    }
    if (position == 1) {
      if (byte == 0x62) {
        position = 2;
        ckA = ckB = 0;
      } else {
        position = byte == 0xB5 ? 1 : 0;
      }
      return false;
    }

    const uint16_t index = position++;
    if (index < 6) {
      header[index - 2] = byte;
      updateChecksum(byte);
      if (index == 5) {
        length = header[2] | (static_cast<uint16_t>(header[3]) << 8);
        if (length > 256) position = 0;
      }
    } else if (index < length + 6) {
      if (length == sizeof(payload)) payload[index - 6] = byte;
      updateChecksum(byte);
    } else if (index == length + 6) {
      receivedA = byte;
    } else {
      position = 0;
      return receivedA == ckA && byte == ckB && decode(page);
    }
    return false;
  }

 private:
  uint16_t position = 0;
  uint16_t length = 0;
  uint8_t header[4] = {};
  uint8_t payload[40] = {};
  uint8_t ckA = 0;
  uint8_t ckB = 0;
  uint8_t receivedA = 0;

  void updateChecksum(uint8_t byte) {
    ckA += byte;
    ckB += ckA;
  }

  static uint32_t pageBit(const uint8_t* bytes, size_t index) {
    return (bytes[index / 8] >> (7 - index % 8)) & 1;
  }

  bool decode(GalileoInavPage& page) const {
    if (header[0] != 2 || header[1] != 0x13 || length != sizeof(payload) ||
        payload[0] != 2 || payload[1] < 1 || payload[1] > 36 ||
        payload[4] != 8 || payload[6] != 2) return false;

    if (payload[2] == 1) page.band = "E1-B";
    else if (payload[2] == 5) page.band = "E5b-I";
    else return false;

    // Convert little-endian UBX words and skip each page part's pad byte.
    for (size_t i = 0; i < sizeof(page.bytes); ++i) {
      const size_t j = i + i / 15;
      page.bytes[i] = payload[8 + (j ^ 3)];
    }
    if (page.bytes[0] >> 6 != 0 || page.bytes[15] >> 6 != 2) return false;

    uint32_t crc = 0;
    for (size_t i = 0; i < 196; ++i) {
      const uint32_t feedback = (crc >> 23) ^ pageBit(page.bytes, i < 114 ? i : i + 6);
      crc = (crc << 1) & 0xFFFFFF;
      if (feedback) crc ^= 0x864CFB;
    }
    uint32_t received = 0;
    for (size_t i = 202; i < 226; ++i) received = (received << 1) | pageBit(page.bytes, i);
    if (crc != received) return false;

    page.svid = payload[1];
    page.wordType = page.bytes[0] & 0x3F;
    return true;
  }
};
