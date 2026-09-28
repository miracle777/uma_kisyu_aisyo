#!/usr/bin/env python3
"""全16頭を同一規則で検算する。公開サイト・GitHub・本番DBは変更しない。

この監査では出走馬の文字だけを収めたテスト用漢字辞書を使う。
旧結果は公開コードの先頭一致・未登録文字無視を独立再実装した比較値であり、
公開サイト上の実行結果や当時のアクセスログではない。
"""
from pathlib import Path
import csv
import json
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import kantei_main as k
from test_kantei import HORSES,JOCKEYS

# 着順はJRAの16-6-5と、テレ東の全着順表を照合。4/7は8着同着。
FINISH=[5,11,10,8,3,2,8,7,4,13,14,16,15,6,12,1]
RESULT_URL='https://www.jra.go.jp/datafile/seiseki/g1/sprint/result/sprint2026.html'
ALL_RESULTS_URL='https://www.tv-tokyo.co.jp/sports/smp/articles/2026/09/042439.html'
BASE_COMMIT='f885f7926dd5929d8109e334f3f531b01d0810ea'


def run():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir=Path(tmp)
        shutil.copy(ROOT/'static/csv/kakusu-utf8.csv',data_dir/'kakusu-utf8.csv')
        shutil.copy(ROOT/'tests/fixtures/kanji_subset.csv',data_dir/'kanji_DATA_BASE.csv')
        with patch.object(k,'CSV_DIR',data_dir):
            horse_result=k.kantei_uma([x[0] for x in HORSES],1,1,8)
            jockey_result=k.kantei_kisyu([x[0] for x in JOCKEYS],1,1,8)
    if horse_result[0]=='errer' or jockey_result[0]=='errer':
        raise RuntimeError((horse_result,jockey_result))
    # 旧CSVに戻した順序をそのまま使用し、最初に一致した文字の画数を採る。
    old_rows=list(csv.reader((ROOT/'static/csv/kakusu-utf8.csv').read_text().splitlines()))
    old_map={}
    for char,value in old_rows:
        if char=='ブ': char='ビ'   # 旧CSVはビが4画と3画で重複し、ブが未登録
        if char=='ヴ': value='3'
        old_map.setdefault(char,int(value))
    rows=[]
    for index,(horse,jockey) in enumerate(zip(horse_result[1:],jockey_result[1:]),1):
        legacy_total=sum(old_map.get(char,0) for char in horse[0])
        rows.append({
            'gate':(index+1)//2,'horse_number':index,'finish':FINISH[index-1],
            'horse_name':horse[0],'horse_strokes_legacy_emulation':legacy_total,
            'horse_number_legacy_emulation':k.reduce_strokes(legacy_total),
            'horse_strokes_fixed':horse[1],'horse_kyusei_number_fixed':horse[2],
            'horse_compatibility_year_month_day':horse[3:],
            'jockey_input':jockey[0],
            'jockey_entry_spelling':'C.ルメール' if index==9 else jockey[0],
            'jockey_strokes_fixed':jockey[1],'jockey_kyusei_number_fixed':jockey[2],
            'jockey_compatibility_year_month_day':jockey[3:],
            'jockey_day_using_wrong_year_reference_at_fixed_count':jockey[3],
            'note':'計数時の表記をクリストフ・ルメール（中点1画）と明示。略称は自動変換しない。' if index==9 else ('鮫は既存辞書にない場合17画で補完。' if index==11 else ''),
        })
    report={
        'race':'2026年9月27日 第60回スプリンターズステークス',
        'analysis_type':'結果判明後の全頭画数検算。事前予測・的中実績ではない。',
        'source_commit':BASE_COMMIT,'stroke_rule_version':'kakusu-20260928-v1',
        'stars':{'year':1,'month':1,'day':8},
        'legend':{'1':'既存アプリの最上位相性','2':'既存アプリの良い相性','3':'相性条件に該当しない（馬の能力評価ではない）'},
        'sources':{
            'race_result':RESULT_URL,'all_finish_positions':ALL_RESULTS_URL,
            'day_calendar':'https://yakumoin.info/daily/direction/date/20260927',
            'month_calendar':'https://yakumoin.info/kyusei/direction_month/id/1/1',
            'year_calendar':'https://bestcalendar.jp/tools/kyusei',
            'source_repository':'https://github.com/miracle777/uma_kisyu_aisyo',
            'same_strokes':'https://kanji.sljfaq.org/k/u9BAB.html',
            'lemaire_spelling':'https://keiba.rakuten.co.jp/jockey/detail/JOCKEYID/60339',
            'race_card':'ユーザーの保存済み accessD (4).pdf：2026/09/27・15:05時点、全16頭。'
        },
        'rules':['小書きカナは通常サイズと同じ画数','濁点2画・半濁点1画・長音1画・中点1画','漢字は字体を変えず登録値を使う','騎手の日評価には日を使用','未登録文字を0画で通さない','相性配列list1/list2は変更しない'],
        'caveats':['旧画数は旧集計ロジックの独立再実装であり、公開サイトの出力を取得したものではない。','本番漢字辞書の全件監査ではなく、今回使用する文字のテスト用部分辞書で検算した。','画数補正だけで的中や回収率の向上を立証できない。','公開サイトの現在の配備コードとGitHubの一致は未確認。'],
        'horse_count_changed':sum(r['horse_strokes_legacy_emulation']!=r['horse_strokes_fixed'] for r in rows),
        'rows':rows,
    }
    destination=ROOT/'docs'; destination.mkdir(exist_ok=True)
    (destination/'sprinters-20260927.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    symbols={1:'◎',2:'○',3:'－'}
    fmt=lambda values: '/'.join(symbols[v] for v in values)
    lines=[
        '# スプリンターズS：馬名・騎手名の画数再検証',
        '',
        '対象：2026年9月27日、第60回スプリンターズステークス。',
        'これは結果判明後の検算であり、事前予想の的中実績ではありません。',
        '',
        '## 結論',
        '',
        '全16頭のうち、馬名の総画数は9頭で旧コードの集計再現値と変わりました。小書きカナの未登録、「ブ」の欠落、「ヴ」の計数規約の不一致が原因です。騎手の「日」評価にも年の参照が残っていました。',
        '',
        'ただし、画数を直せば16→6→5を一意に選べた、という結果ではありません。16番の馬名・騎手名は年/月との相性がともに○ですが、日との相性はともに－です。6番の馬名は日との相性が◎、5番の騎手名は日との相性が○です。3頭に共通した日盤の強い条件はありません。',
        '',
        '同じ基準で全頭を比較すると、馬名の日評価が◎になるのは1・3・6・7・13・14の6頭です。そのうち3着以内は6番だけです。日評価の上位だけで絞ると、勝った16番を落とします。逆に4番は馬名・騎手名とも年/月が◎、日が○ですが8着です。画数は能力の代わりではなく、独立した記録項目として競馬情報と照合するのが適切です。',
        '',
        '保存出馬表には16番の近3走1着・1着・2着、15番との前走差0.1秒、馬体重464kg（+4）が記載されていました。したがって16番を候補に残す根拠は、名前の画数以前に競馬データにもありました。',
        '',
        '## 計数規約と表示',
        '',
        '年=一白水星、月=一白水星、日=八白土星。年月日の星は手動設定であり、この修正では暦を自動計算する機能は追加していません。',
        '小書きカナは通常サイズと同画数。濁点2画、半濁点1画、長音・中点は各1画。漢字は新字体/旧字体を自動置換しません。鮫は既存辞書に未登録の場合17画を補完します。C.ルメールはこの監査に限り「クリストフ・ルメール」の表記で算定しました。',
        '◎=アプリの最上位相性、○=良い相性、－=条件非該当。各欄は「年/月/日」。馬の能力、勝率、的中確率を表しません。',
        '相性表list1/list2自体は元の定義のままです。同じ星同士の扱いなど、相性表の占術上の妥当性を今回変更・保証してはいません。',
        '',
        '## 全16頭の検算',
        '',
        '| 枠-馬番 | 馬名 | 旧集計再現→修正版の画数 | 修正版の数 | 馬：年/月/日 | 騎手の計数表記 | 騎手画数→数 | 騎手：年/月/日 | 着順 |',
        '|---|---|---:|---:|---|---|---:|---|---:|',
    ]
    for r in rows:
        lines.append(f"| {r['gate']}-{r['horse_number']} | {r['horse_name']} | {r['horse_strokes_legacy_emulation']}→{r['horse_strokes_fixed']} | {r['horse_kyusei_number_fixed']} | {fmt(r['horse_compatibility_year_month_day'])} | {r['jockey_input']} | {r['jockey_strokes_fixed']}→{r['jockey_kyusei_number_fixed']} | {fmt(r['jockey_compatibility_year_month_day'])} | {r['finish']} |")
    lines.extend([
        '',
        '8着は4番と7番の同着です。旧集計再現欄は馬名についての再現値です。騎手欄は修正規則での計算であり、旧サイトの出力とは区別してください。',
        '',
        '## 上位3頭の内訳',
        '',
        '16 ピューロマジック：ピ3＋ュ2＋ー1＋ロ3＋マ2＋ジ5＋ッ3＋ク2＝21→3。岩8＋田5＋望11＋来7＝31→4。',
        '6 ワールズエンド：ワ2＋ー1＋ル2＋ズ4＋エ3＋ン2＋ド4＝18→9。津9＋村7＋明8＋秀7＝31→4。',
        '5 サウンドモリアーナ：サ3＋ウ3＋ン2＋ド4＋モ3＋リ2＋ア2＋ー1＋ナ2＝22→4。吉6＋田5＋隼10＋人2＝23→5。',
        '',
        '## 再現性と制限',
        '',
        '検算用コマンド：python tools/audit_sprinters_2026.py',
        'ソースの基準コミット：'+BASE_COMMIT,
        '使用した漢字の部分辞書は tests/fixtures/kanji_subset.csv。これはテスト専用であり、本番の漢字辞書に置き換えてはいけません。',
        '公開サイトの現行配備コードは直接取得できていません。旧結果欄はGitHubの元コードと元CSVの集計を独立再実装したものです。',
        '本番への反映、GitHubへのpush、PR作成、FlaskのHTTP/画面統合テストは、この報告作成時点では未実施です。',
        '',
        '## 出典',
        '',
    ])
    for label,source in report['sources'].items(): lines.extend([label,source,''])
    (destination/'sprinters-20260927.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('馬名の画数が変わった頭数:',report['horse_count_changed'],'/ 16')
    print('馬名の日評価◎:',[r['horse_number'] for r in rows if r['horse_compatibility_year_month_day'][2]==1])
    for i in [16,6,5]:
        r=rows[i-1]
        print(i,r['horse_name'],r['horse_strokes_legacy_emulation'],r['horse_strokes_fixed'],r['jockey_input'],r['jockey_strokes_fixed'])

if __name__=='__main__': run()
