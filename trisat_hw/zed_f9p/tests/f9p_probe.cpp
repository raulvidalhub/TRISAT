#include <iostream>
#include <string>
#include "galileo_inav.h"

int main() {
  GalileoUbxDecoder decoder;
  std::string hex;
  while (std::getline(std::cin, hex)) {
    bool emitted = false;
    for (size_t i = 0; i + 1 < hex.size(); i += 2) {
      GalileoInavPage page;
      const auto byte = static_cast<uint8_t>(std::stoul(hex.substr(i, 2), nullptr, 16));
      if (decoder.feed(byte, page)) {
        char sentence[GalileoInavPage::sentenceCapacity];
        const auto length = page.formatSentence(sentence);
        std::cout.write(sentence, length);
        emitted = true;
      }
    }
    if (!emitted) std::cout << "-\n";
  }
}
