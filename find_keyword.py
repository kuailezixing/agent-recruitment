import jieba
from collections import Counter
from knowledge import init_knowledge
from config_file import KB_DIR,cache_file

knowledge_list=init_knowledge(KB_DIR=KB_DIR,cache_file=cache_file)
all_words=Counter()
docs=[]
for item in knowledge_list:
    words=[w for w in jieba.cut_for_search(item['text']) if len(w)>1]
    docs.append((item,set(words)))
    all_words.update(words)
for item,words in docs:
    unique=sorted([w for w in words if all_words[w]==1],key=len,reverse=True)
    print(f"第{item.get('num','?')}条 | 推荐: {unique[:3]} | 内容: {item['text'][:30]}...")