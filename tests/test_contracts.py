"""Flaskの実行とは別の、既存URL/テンプレート互換性の静的チェック。"""
import ast
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class InputParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.inputs=[]
    def handle_starttag(self,tag,attrs):
        if tag == 'input': self.inputs.append(dict(attrs))

class ContractTests(unittest.TestCase):
    def test_continue_forms_carry_three_stars(self):
        for filename in ['uma_kantei.html','kisyu_kantei.html']:
            with self.subTest(template=filename):
                parser=InputParser(); parser.feed((ROOT/'templates'/filename).read_text())
                hidden={x['name']:x['value'] for x in parser.inputs if x.get('type')=='hidden'}
                self.assertEqual(hidden,{'kusei_nen':'{{ kotae[0][3] }}','kusei_tuki':'{{ kotae[0][4] }}','kusei_hi':'{{ kotae[0][5] }}'})
                selected=[x['value'] for x in parser.inputs if x.get('name')=='select_form_id']
                self.assertEqual(selected,['kisyu','uma'])

    def test_result_templates_keep_six_columns(self):
        for filename in ['uma_kantei.html','kisyu_kantei.html']:
            text=(ROOT/'templates'/filename).read_text()
            self.assertEqual(text.count('<th scope='),6)
            self.assertEqual(text.count('<td'),6)
            self.assertEqual(text.count('<table '),text.count('</table>'))

    def test_six_original_routes_preserved(self):
        tree=ast.parse((ROOT/'app.py').read_text())
        actual={}
        for node in tree.body:
            if isinstance(node,ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr=='route':
                        actual[ast.literal_eval(dec.args[0])]=node.name
        self.assertEqual(actual,{'/':'home','/kakusu_select':'kakusu_select','/kisyu_form':'kisyu_form','/uma_form':'uma_form','/about':'about'})

    def test_python310_syntax_compatibility(self):
        for filename in ['app.py','kantei_main.py']:
            ast.parse((ROOT/filename).read_text(),feature_version=(3,10))

    def test_no_cgi_or_global_result_state(self):
        for filename in ['app.py','kantei_main.py']:
            tree=ast.parse((ROOT/filename).read_text())
            for node in ast.walk(tree):
                self.assertNotIsInstance(node,ast.Global)
                if isinstance(node,ast.Import):
                    self.assertFalse(any(x.name in ['cgi','cgitb'] for x in node.names))
