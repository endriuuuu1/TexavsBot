from transliterate import translit
from fast_langdetect import detect
import re


class TextAnalyzer:
    def __init__(self):
        pass

    @staticmethod
    def __detect_language(text: str) -> str:
        try:
            if not text or not text.strip():
                return 'unknown'
            result = detect(text)
            return result[0]['lang']
        except Exception as e:
            return f'error: {e} -- unknown'

    def is_english(self, text: str) -> bool:
        if self.is_georgian(text):
            return False

        return self.__detect_language(text) == 'en'

    def is_georgian(self, text: str) -> bool:
        return bool(re.search(r'[\u10D0-\u10FA]', text))

    def is_other_language(self, text: str):
        return not self.is_georgian(text) and not self.is_english(text)

    # from English Text string to Georgian
    def to_georgian(self, text: str) -> str:
        transliteration = translit(text, 'ka')
        return transliteration

    # from Georgian Text string to English
    def to_english(self, text: str) -> str:
        transliteration = translit(text, 'ka', reversed=True)
        return transliteration

def main():
    analyzer = TextAnalyzer()
    arg = input()
    if analyzer.is_other_language(arg):
        print(analyzer.to_georgian(arg))
    elif analyzer.is_georgian(arg) or analyzer.is_english(arg):
        print(arg)

if __name__ == "__main__":
    main()