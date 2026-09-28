"""既存プロジェクトに適用後、Flaskと既存テンプレートがある環境で実行する。"""
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import kantei_main as k

ROOT=Path(__file__).resolve().parents[1]
READY=importlib.util.find_spec('flask') is not None and (ROOT/'templates/base.html').is_file()

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden={}; self.rows=[]; self.current=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        attr=dict(attrs)
        if tag=='input' and attr.get('type')=='hidden': self.hidden[attr['name']]=attr.get('value','')
        if tag=='tr': self.current=[]
        if tag=='td': self.cell=''
    def handle_data(self,data):
        if self.cell is not None: self.cell+=data
    def handle_endtag(self,tag):
        if tag=='td' and self.cell is not None:
            if self.current is not None: self.current.append(self.cell.strip())
            self.cell=None
        if tag=='tr' and self.current is not None:
            if self.current: self.rows.append(self.current)
            self.current=None

def parse(response):
    parser=Parser(); parser.feed(response.get_data(as_text=True)); return parser

@unittest.skipUnless(READY,'Flaskと既存base.html等がある実行環境で確認する統合テスト')
class FlaskRouteTests(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app=app; self.app.config['TESTING']=True; self.client=app.test_client()
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); directory=Path(tmp.name)
        shutil.copy(ROOT/'static/csv/kakusu-utf8.csv',directory/'kakusu-utf8.csv')
        shutil.copy(ROOT/'tests/fixtures/kanji_subset.csv',directory/'kanji_DATA_BASE.csv')
        patcher=patch.object(k,'CSV_DIR',directory); patcher.start(); self.addCleanup(patcher.stop)

    def test_get_routes(self):
        for route in ['/','/about','/kakusu_select','/kisyu_form','/uma_form']:
            self.assertEqual(self.client.get(route).status_code,200)

    def test_selections_do_not_keep_old_stars(self):
        self.client.post('/kakusu_select',data={'kusei_nen':'1','kusei_tuki':'1','kusei_hi':'8','select_form_id':'uma'})
        response=self.client.post('/kakusu_select',data={'kusei_nen':'2','kusei_tuki':'3','kusei_hi':'4','select_form_id':'uma'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(parse(response).hidden,{'kusei_nen':'2','kusei_tuki':'3','kusei_hi':'4'})

    def test_two_horse_posts(self):
        stars={'kusei_nen':'1','kusei_tuki':'1','kusei_hi':'8'}
        first=self.client.post('/uma_form',data={**stars,'uma1':'ピューロマジック'})
        second=self.client.post('/uma_form',data={**stars,'uma1':'ルガル'})
        self.assertEqual(parse(first).rows[0],['ピューロマジック','21','3','2','2','3'])
        self.assertEqual(parse(second).rows[0][:3],['ルガル','8','8'])

    def test_jockey_and_continue_to_horse(self):
        response=self.client.post('/kisyu_form',data={'kusei_nen':'1','kusei_tuki':'1','kusei_hi':'8','kisyu1':'岩田望来'})
        parser=parse(response)
        self.assertEqual(parser.rows[0],['岩田望来','31','4','2','2','3'])
        following=self.client.post('/kakusu_select',data={**parser.hidden,'select_form_id':'uma'})
        self.assertEqual(following.status_code,200)
        self.assertEqual(parse(following).hidden,{'kusei_nen':'1','kusei_tuki':'1','kusei_hi':'8'})

    def test_bad_input_uses_existing_error_screen(self):
        response=self.client.post('/uma_form',data={'kusei_nen':'0','kusei_tuki':'1','kusei_hi':'8','uma1':'ルガル'})
        self.assertEqual(response.status_code,200)
        self.assertIn('1〜9',response.get_data(as_text=True))
