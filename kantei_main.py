#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""馬名・騎手名の画数鑑定。既存テンプレートの6列配列を維持する。

計数規約: 小書きカナは通常サイズと同画数、濁点は2画、半濁点は1画、
長音・中点は各1画。漢字は既存CSVの表記を使用し、旧字体を置換しない。
この計算は当アプリの相性規則であり、競走能力・的中確率を表すものではない。
"""
from pathlib import Path
import csv
import logging
import re
import unicodedata
from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)
CSV_DIR = Path(__file__).resolve().parent / "static" / "csv"
MAX_ENTRIES = 18

# 既存の相性規則は変更しない（0は従来のダミー値）。
list1 = [
    [0, 0, 0], [6, 7, 0], [9, 0, 0], [1, 0, 0], [1, 0, 0],
    [9, 0, 0], [2, 5, 8], [2, 5, 8], [2, 9, 0], [3, 4, 0],
]
list2 = [
    [0, 0, 0, 0], [1, 3, 4, 0], [5, 6, 7, 8], [3, 4, 9, 0],
    [3, 4, 9, 0], [2, 6, 7, 8], [1, 7, 0, 0], [1, 6, 7, 0],
    [5, 6, 7, 0], [2, 5, 8, 0],
]
# 元の漢字辞書に未登録の場合だけ補う。既存の登録値を上書きしない。
# 鮫17画: https://kanji.sljfaq.org/k/u9BAB.html
KANJI_ADDITIONS = {"鮫": 17}
SMALL_KANA = dict(zip("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ"))


class InputError(ValueError):
    """既存エラー画面に表示する入力エラー。"""

    def __init__(self, message, value=""):
        super().__init__(message)
        self.value = value


def validate_kusei(kusei_nen, kusei_tuki, kusei_hi):
    """年・月・日の値を1〜9の整数として確認する。暦の自動算出はしない。"""
    result = []
    for label, value in zip(("年", "月", "日"), (kusei_nen, kusei_tuki, kusei_hi)):
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise InputError(f"{label}の九星は1〜9から選択してください。")
        text = str(value).strip()
        if not re.fullmatch(r"[1-9]", text):
            raise InputError(f"{label}の九星は1〜9から選択してください。", text)
        result.append(int(text))
    return tuple(result)


def _load_strokes(path, *, strict_duplicates=True):
    """UTF-8 CSVをリクエストごとに読み込み、共有の可変状態を作らない。"""
    strokes = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.reader(handle), 1):
            if not row or all(not cell.strip() for cell in row):
                continue
            if [cell.strip().lower() for cell in row] == ["kanji", "kakusu"]:
                continue
            if len(row) != 2:
                raise ValueError(f"画数辞書の列数が不正: {path.name}:{line_no}")
            char, value = (cell.strip() for cell in row)
            if len(char) != 1 or not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
                raise ValueError(f"画数辞書の値が不正: {path.name}:{line_no}")
            number = int(value)
            if char in strokes and strokes[char] != number:
                if strict_duplicates:
                    raise ValueError(f"異なる画数が重複: {char} ({path.name}:{line_no})")
                # 既存漢字辞書については従来と同じ先頭一致を維持する。
                LOGGER.warning("漢字辞書の重複 %s: 先頭の%d画を使用", char, strokes[char])
            strokes.setdefault(char, number)
    if not strokes:
        raise ValueError(f"画数辞書が空: {path.name}")
    return strokes


def kantei_int():
    """従来の初期化名を維持。呼び出しごとに独立した辞書を返す。"""
    kana = _load_strokes(CSV_DIR / "kakusu-utf8.csv")
    kanji = _load_strokes(CSV_DIR / "kanji_DATA_BASE.csv", strict_duplicates=False)
    for char, count in KANJI_ADDITIONS.items():
        kanji.setdefault(char, count)
    return kana, kanji


def normalize_name(name):
    """空白とカナの幅・結合濁点だけを整える。漢字の字体は保持する。"""
    if not isinstance(name, str):
        raise InputError("名前は文字列で入力してください。")
    name = re.sub(r"\s+", "", name)
    name = re.sub(r"[\uff61-\uff9f]+", lambda m: unicodedata.normalize("NFKC", m[0]), name)
    return re.sub(r"[\u30a0-\u30ff\u3099\u309a]+", lambda m: unicodedata.normalize("NFC", m[0]), name)


def _prepare_names(names):
    if isinstance(names, (str, bytes)) or not isinstance(names, Sequence):
        raise InputError("名前を配列で指定してください。")
    if len(names) > MAX_ENTRIES:
        raise InputError("一度に入力できる名前は18件までです。")
    prepared = [normalize_name(name) for name in names]
    # 末尾の未使用欄は従来どおり許可する。
    while prepared and not prepared[-1]:
        prepared.pop()
    if not prepared:
        raise InputError("名前を1件以上入力してください。")
    for index, name in enumerate(prepared, 1):
        if not name:
            raise InputError("途中に空欄があります。先頭から順に入力してください。", f"{index}番目の入力欄")
    return prepared


def _count_strokes(name, kind, kana, kanji):
    if kind == "kisyu" and any(char.isdigit() for char in name):
        raise InputError("騎手名に数字が入っています。", name)
    if kind == "kisyu" and re.search(r"[A-Za-zＡ-Ｚａ-ｚ.]", name):
        raise InputError("騎手名の英字・略称には対応していません。カタカナのフルネームで入力してください。", name)
    total = 0
    unknown = []
    for original in name:
        char = SMALL_KANA.get(original, original)
        if kind == "uma":
            # 馬名はこれまでどおりカタカナと長音に限定する。
            count = kana.get(char) if ("ァ" <= char <= "ヶ" or char == "ー") else None
        else:
            # 漢字とカナの混在でも、文字ごとに辞書を選ぶ。
            count = kana.get(char)
            if count is None:
                count = kanji.get(char)
        if count is None:
            if original not in unknown:
                unknown.append(original)
        else:
            total += count
    if unknown:
        label = "馬名" if kind == "uma" else "騎手名"
        raise InputError(f"{label}に画数未登録または非対応の文字があります: {'・'.join(unknown)}", name)
    return total


def reduce_strokes(total):
    """従来どおり桁を加算して1〜9にする。"""
    if isinstance(total, bool) or not isinstance(total, int) or total < 1:
        raise ValueError("画数は正の整数で指定してください。")
    while total > 9:
        total = sum(int(digit) for digit in str(total))
    return total


def compatibility(number, star):
    """既存の判定コード: 1=最上位、2=良い、3=該当しない。"""
    if number in list1[star]:
        return 1
    if number in list2[star]:
        return 2
    return 3


def _kantei(names, kusei_nen, kusei_tuki, kusei_hi, kind):
    try:
        stars = validate_kusei(kusei_nen, kusei_tuki, kusei_hi)
        prepared = _prepare_names(names)
        kana, kanji = kantei_int()
        result = [[len(prepared), 0, 0, *stars]]
        for name in prepared:
            total = _count_strokes(name, kind, kana, kanji)
            number = reduce_strokes(total)
            # 年/月/日はそれぞれ対応する星で評価する。前回の配列は参照しない。
            result.append([name, total, number, *[compatibility(number, star) for star in stars]])
        return result
    except InputError as exc:
        # 綴りも含め、既存のapp.py・errer.htmlとの互換性を維持。
        return ["errer", str(exc), exc.value]
    except (OSError, UnicodeError, csv.Error, ValueError):
        LOGGER.exception("画数辞書の読み込み・検証に失敗しました")
        return ["errer", "画数辞書を読み込めません。管理者に確認してください。", ""]


def kantei_uma(uma, kusei_nen, kusei_tuki, kusei_hi):
    return _kantei(uma, kusei_nen, kusei_tuki, kusei_hi, "uma")


def kantei_kisyu(kisyu, kusei_nen, kusei_tuki, kusei_hi):
    return _kantei(kisyu, kusei_nen, kusei_tuki, kusei_hi, "kisyu")


if __name__ == "__main__":
    print("馬鑑定結果")
