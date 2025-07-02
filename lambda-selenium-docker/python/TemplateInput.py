import re

class TemplateInput:
    def __init__(self, raw_text):
        self.raw_text = raw_text
        self.date = ""
        self.start = ""
        self.end = ""
        self.break_start = ""
        self.rakuraku1 = ""
        self.rakuraku2 = ""
        self.zaitaku = False
        self.parse()

    def parse(self):
        lines = self.raw_text.splitlines()
        for line in lines:
            # 全角・半角の「:」「：」両対応させる
            key_value = re.split(r"[:：]", line, maxsplit=1)
            if len(key_value) != 2:
                continue
            key, value = key_value[0].strip(), key_value[1].strip()

            if key == "日付":
                self.date = value
            elif key == "開始":
                self.start = value
            elif key == "終了":
                self.end = value
            elif key == "休憩開始":
                self.break_start = value
            elif key == "楽楽精算1":
                self.rakuraku1 = value
            elif key == "楽楽精算2":
                self.rakuraku2 = value
    @staticmethod
    def create(raw_text):
        return TemplateInput(raw_text)

    def is_valid(self):
        return all([self.date.strip(), self.start.strip(), self.end.strip()])
    
    def __str__(self):
        return (
            f"日付: {self.date}\n"
            f"開始: {self.start}\n"
            f"終了: {self.end}\n"
            f"休憩開始: {self.break_start}\n"
            f"楽楽精算1: {self.rakuraku1}\n"
            f"楽楽精算2: {self.rakuraku2}"
        )