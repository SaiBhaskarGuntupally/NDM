import os
from pathlib import Path
import re
base = Path(__file__).resolve().parent
pdf = base / 'NDM_Enterprise_Report.pdf'
md = base / 'NDM_Enterprise_Report.md'
print(md.name, md.stat().st_size)
# word count for markdown
with open(md,'r',encoding='utf-8') as f:
    text = f.read()
    words = re.findall(r"\w+", text)
    print('md_words', len(words))
print(pdf.name, pdf.stat().st_size)
# page count - prefer PDF /Count field
with open(pdf,'rb') as f:
    data = f.read().decode('latin1', errors='ignore')
    m = re.search(r'/Count\s+(\d+)', data)
    if m:
        print('pages', int(m.group(1)))
    else:
        pages = data.count('/Type /Page')
        print('pages(heuristic)', pages)
