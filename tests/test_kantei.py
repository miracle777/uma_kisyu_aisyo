"""計算の回帰テスト。テスト用漢字辞書は本番の辞書を置換しない。"""
import contextlib
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import kantei_main as k

ROOT = Path(__file__).resolve().parents[1]
HORSES = [
    ("レッドモンレーヴ",20,2), ("アイサンサン",14,5), ("ママコチャ",11,2),
    ("ジューンブレア",16,7), ("サウンドモリアーナ",22,4), ("ワールズエンド",18,9),
    ("ペアポルックス",18,9), ("エーティーマクフィ",17,8), ("スターアニス",12,3),
    ("レイピア",8,8), ("ルガル",8,8), ("ブラックチャリス",19,1),
    ("パンジャタワー",18,9), ("ウインカーネリアン",20,2),
    ("フリッカージャブ",19,1), ("ピューロマジック",21,3),
]
JOCKEYS = [
    ("酒井学",22,4), ("幸英明",24,6), ("武豊",21,3), ("坂井瑠星",34,7),
    ("吉田隼人",23,5), ("津村明秀",31,4), ("岩田康誠",37,1), ("富田暁",29,2),
    ("クリストフ・ルメール",17,8), ("横山武史",31,4), ("鮫島克駿",51,6),
    ("浜中俊",23,5), ("松山弘平",21,3), ("三浦皇成",28,1), ("西村淳也",27,9),
    ("岩田望来",31,4),
]


class KanteiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        shutil.copy(ROOT/'static/csv/kakusu-utf8.csv', directory/'kakusu-utf8.csv')
        shutil.copy(ROOT/'tests/fixtures/kanji_subset.csv', directory/'kanji_DATA_BASE.csv')
        patcher = patch.object(k, 'CSV_DIR', directory)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_same_character_supplement(self):
        self.assertNotIn('鮫',k._load_strokes(k.CSV_DIR/'kanji_DATA_BASE.csv'))
        self.assertEqual(k.kantei_int()[1]['鮫'],17)
        self.assertEqual(k.kantei_kisyu(['鮫島克駿'],1,1,8)[1][1],51)

    def test_all_16_horse_counts(self):
        result = k.kantei_uma([x[0] for x in HORSES], 1, 1, 8)
        self.assertEqual(result[0], [16,0,0,1,1,8])
        self.assertEqual([r[:3] for r in result[1:]], [list(x) for x in HORSES])

    def test_all_16_jockey_counts(self):
        result = k.kantei_kisyu([x[0] for x in JOCKEYS], 1, 1, 8)
        self.assertEqual([r[:3] for r in result[1:]], [list(x) for x in JOCKEYS])

    def test_jockey_day_uses_day_not_year(self):
        self.assertEqual(k.kantei_kisyu(['岩田望来'],1,1,8)[1], ['岩田望来',31,4,2,2,3])
        self.assertEqual(k.kantei_kisyu(['吉田隼人'],1,1,8)[1], ['吉田隼人',23,5,3,3,2])

    def test_all_three_periods_are_independent(self):
        self.assertEqual(k.kantei_uma(['ワールズエンド'],1,3,8)[1][3:], [3,2,1])

    def test_repeated_horse_calls_have_no_old_results(self):
        first = k.kantei_uma(['ピューロマジック'],1,1,8)
        second = k.kantei_uma(['ルガル'],9,8,7)
        self.assertEqual(first[1][1:3], [21,3])
        self.assertEqual(second[1][1:3], [8,8])
        self.assertEqual(len(second),2)
        self.assertEqual(second[0][3:],[9,8,7])

    def test_repeated_jockey_calls_have_no_old_results(self):
        k.kantei_kisyu(['岩田望来'],1,1,8)
        self.assertEqual(k.kantei_kisyu(['幸英明'],8,1,9)[1], ['幸英明',24,6,2,1,3])

    def test_return_value_mutation_does_not_leak(self):
        first = k.kantei_uma(['ママコチャ'],1,1,8)
        first[1][1] = 999
        self.assertEqual(k.kantei_uma(['ママコチャ'],1,1,8)[1][1],11)

    def test_concurrent_calls(self):
        def run(i):
            name, count, reduced = HORSES[i % 16]
            row = k.kantei_uma([name],1,1,(i % 9)+1)[1]
            return row[:3] == [name,count,reduced]
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(run,range(64))))

    def test_all_small_kana_equal_large_kana(self):
        for small, large in k.SMALL_KANA.items():
            with self.subTest(small=small):
                self.assertEqual(k.kantei_uma([small],1,1,8)[1][1:3], k.kantei_uma([large],1,1,8)[1][1:3])

    def test_bu_exists_and_bi_not_duplicated(self):
        self.assertEqual(k.kantei_uma(['ブビ'],1,1,8)[1][1:3], [7,7])
        with (ROOT/'static/csv/kakusu-utf8.csv').open(encoding='utf-8') as handle:
            chars = [row[0] for row in csv.reader(handle)]
        self.assertEqual(len(chars),len(set(chars)))

    def test_voicing_counts(self):
        self.assertEqual(k.kantei_uma(['ウヴ'],1,1,8)[1][1:3], [8,8])
        self.assertEqual(k.kantei_uma(['フブプ'],1,1,8)[1][1:3], [6,6])

    def test_halfwidth_kana(self):
        self.assertEqual(k.kantei_uma(['ﾋﾟｭｰﾛﾏｼﾞｯｸ'],1,1,8)[1][:3], ['ピューロマジック',21,3])

    def test_combining_voicing(self):
        self.assertEqual(k.kantei_uma(['ウ\u3099'],1,1,8)[1][:3], ['ヴ',5,5])

    def test_kanji_variant_not_normalized(self):
        self.assertEqual(k.kantei_kisyu(['神','神'],1,1,8)[1][1],10)
        self.assertEqual(k.kantei_kisyu(['神','神'],1,1,8)[2][1],9)

    def test_mixed_kanji_and_kana(self):
        self.assertEqual(k.kantei_kisyu(['岩田・ルメール'],1,1,8)[1][1],21)

    def test_middle_dot_and_long_mark(self):
        self.assertEqual(k.kantei_kisyu(['ルメール','ル・メール'],1,1,8)[1][1],7)
        self.assertEqual(k.kantei_kisyu(['ルメール','ル・メール'],1,1,8)[2][1],8)

    def test_initial_abbreviation_rejected(self):
        for name in ['C.ルメール','Ｃ.ルメール']:
            with self.subTest(name=name):
                self.assertEqual(k.kantei_kisyu([name],1,1,8)[0],'errer')

    def test_unregistered_character_is_not_silently_zero(self):
        for fn,name in [(k.kantei_uma,'アヿ'),(k.kantei_kisyu,'岩田🦄')]:
            with self.subTest(name=name):
                self.assertEqual(fn([name],1,1,8)[0],'errer')

    def test_horse_non_kana_rejected(self):
        for name in ['あ','horse','馬','ル・ガル']:
            with self.subTest(name=name):
                self.assertEqual(k.kantei_uma([name],1,1,8)[0],'errer')

    def test_jockey_digit_rejected(self):
        self.assertEqual(k.kantei_kisyu(['岩田1'],1,1,8)[0],'errer')

    def test_error_followed_by_valid_input(self):
        k.kantei_uma(['!'],1,1,8)
        self.assertEqual(k.kantei_uma(['ルガル'],1,1,8)[1][1],8)

    def test_whitespace_normalization(self):
        self.assertEqual(k.kantei_kisyu([' 岩田　望来 '],1,1,8)[1][0],'岩田望来')

    def test_trailing_empty_slots_allowed(self):
        self.assertEqual(k.kantei_uma(['ルガル']+['']*17,1,1,8)[0][0],1)

    def test_gap_explicit_error_not_silent_truncation(self):
        self.assertEqual(k.kantei_uma(['ルガル','','ママコチャ'],1,1,8)[0],'errer')

    def test_no_names_error(self):
        for names in [[],[''],[' ']*18]:
            with self.subTest(names=names):
                self.assertEqual(k.kantei_uma(names,1,1,8)[0],'errer')

    def test_wrong_input_container_error(self):
        for names in ['ルガル',None,[None],5]:
            with self.subTest(names=names):
                self.assertEqual(k.kantei_uma(names,1,1,8)[0],'errer')

    def test_18_entries_preserved(self):
        self.assertEqual(len(k.kantei_uma(['ルガル']*18,1,1,8)),19)

    def test_19_entries_error(self):
        self.assertEqual(k.kantei_uma(['ルガル']*19,1,1,8)[0],'errer')

    def test_invalid_stars_error_not_server_crash(self):
        for bad in [None,'',0,10,-1,'1.0','x',1.5,True,False,[],{}]:
            for index in range(3):
                stars=[1,1,8]; stars[index]=bad
                with self.subTest(bad=bad,index=index):
                    self.assertEqual(k.kantei_uma(['ルガル'],*stars)[0],'errer')

    def test_valid_star_strings(self):
        self.assertEqual(k.validate_kusei('1',' 1 ','8'),(1,1,8))

    def test_reduction_repeated_digits(self):
        for total,reduced in [(8,8),(9,9),(18,9),(19,1),(99,9),(199,1)]:
            self.assertEqual(k.reduce_strokes(total),reduced)

    def test_reduction_rejects_invalid(self):
        for bad in [0,-1,True,1.1,'12']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                k.reduce_strokes(bad)

    def test_original_compatibility_tables_preserved(self):
        expected1=[[],[6,7],[9],[1],[1],[9],[2,5,8],[2,5,8],[2,9],[3,4]]
        expected2=[[],[1,3,4],[5,6,7,8],[3,4,9],[3,4,9],[2,6,7,8],[1,7],[1,6,7],[5,6,7],[2,5,8]]
        for star in range(1,10):
            for number in range(1,10):
                expected=1 if number in expected1[star] else 2 if number in expected2[star] else 3
                self.assertEqual(k.compatibility(number,star),expected)

    def test_different_working_directory(self):
        old=os.getcwd()
        try:
            os.chdir('/')
            self.assertEqual(k.kantei_uma(['ルガル'],1,1,8)[1][1],8)
        finally:
            os.chdir(old)

    def test_utf8_bom_and_blank_rows(self):
        p=k.CSV_DIR/'test.csv'
        p.write_text('\ufeffkanji,kakusu\n\n岩,8\n',encoding='utf-8')
        self.assertEqual(k._load_strokes(p),{'岩':8})

    def test_conflicting_kana_dictionary_error(self):
        p=k.CSV_DIR/'test.csv'
        p.write_text('ビ,4\nビ,3\n',encoding='utf-8')
        with self.assertRaises(ValueError): k._load_strokes(p)

    def test_kanji_first_match_policy_preserved(self):
        p=k.CSV_DIR/'test.csv'
        p.write_text('岩,8\n岩,9\n',encoding='utf-8')
        with self.assertLogs(k.LOGGER,level='WARNING'):
            self.assertEqual(k._load_strokes(p,strict_duplicates=False),{'岩':8})

    def test_bad_dictionary_rows_rejected(self):
        for text in ['岩,0\n','岩,x\n','岩,8,9\n','岩田,8\n','']:
            p=k.CSV_DIR/'test.csv'; p.write_text(text,encoding='utf-8')
            with self.subTest(text=text),self.assertRaises(ValueError): k._load_strokes(p)

    def test_missing_dictionary_error_is_readable(self):
        (k.CSV_DIR/'kakusu-utf8.csv').unlink()
        with self.assertLogs(k.LOGGER,level='ERROR'):
            result=k.kantei_uma(['ルガル'],1,1,8)
        self.assertEqual(result[0],'errer')
        self.assertNotIn(str(k.CSV_DIR),result[1])

    def test_reinitialization_does_not_grow_arrays(self):
        first=k.kantei_int(); second=k.kantei_int()
        self.assertEqual(first,second)
        self.assertIsNot(first[0],second[0])


if __name__ == '__main__': unittest.main()
