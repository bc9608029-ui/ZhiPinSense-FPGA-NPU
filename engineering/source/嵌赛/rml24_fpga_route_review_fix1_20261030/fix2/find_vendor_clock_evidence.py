from pathlib import Path
import fitz,json,re
HERE=Path(__file__).resolve().parent
files=list(Path('F:/嵌赛/03_FMQL30TAI-悟净开发板手册').glob('*.pdf'))
files += [Path('D:/fudanwei/Procise/documents')/n for n in ['Procise原语手册.pdf','Procise用户使用手册.pdf','Procise时序分析手册.pdf']]
terms=re.compile(r'1\s*GHz|1000\s*MHz|AI_CORE_CLK|BUFG|PLLE2_ADV|NPU|神经网络|人工智能',re.I)
records=[]
for p in files:
 if not p.exists():continue
 doc=fitz.open(p)
 for i,page in enumerate(doc):
  text=page.get_text()
  for match in list(terms.finditer(text))[:5]:
   records.append({'file':str(p),'page':i+1,'term':match.group(),'excerpt':text[max(0,match.start()-180):match.end()+500]})
(HERE/'VENDOR_CLOCK_SEARCH.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('PDF_FILES',len(files),'MATCHES',len(records))
for r in records:
 if re.search(r'1\s*GHz|1000\s*MHz|NPU|神经网络|人工智能',r['term'],re.I):
  print(str(Path(r['file']).name),'PAGE',r['page'],r['excerpt'][:700].replace('\n',' '))
