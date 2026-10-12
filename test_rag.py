from knowledge import retrieve,init_knowledge
from config_file import KB_DIR,cache_file

knowledge_list=init_knowledge(KB_DIR,cache_file)

#TEST_CASES = [
#    {"query": "我收集的问题第1个问题是什么", "expected_keyword": "messages传参"},
#    {"query": "第2个问题是什么",              "expected_keyword": "ChatOpenAI"},
#    {"query": "第3个问题是什么",              "expected_keyword": "completions"},
#    {"query": "第5个问题是什么",              "expected_keyword": "@tool"},
#    {"query": "第9个问题是什么",              "expected_keyword": "大脑"},
#    {"query": "第12个问题是什么",             "expected_keyword": "tool_call_id"},
#    {"query": "高德地图的Key是什么",           "expected_keyword": "未找到","expected_behavior":"honest"},
#    {"query": "关于agent的角色定位",          "expected_keyword": "大脑"},
#    {"query": "什么是2-step RAG",             "expected_keyword": "2-step RAG"},
#    {"query": "什么是Agentic RAG",            "expected_keyword": "Agentic RAG"},
#    {"query": "什么是RRF",                    "expected_keyword": "RRF"},
#    {"query": "什么是Pre-filtering",          "expected_keyword": "Pre-filtering"},
#]

TEST_CASES = [
    {"query": "有没有会 Python 的候选人", "expected_keyword": "Python"},
    {"query": "有没有会 Rust 的候选人", "expected_keyword": "未找到", "expected_behavior": "honest"},
    {"query": "3 年以上经验的候选人", "expected_keyword": "工作年限"},
    {"query": "有没有会 Docker 的", "expected_keyword": "Docker"},
    {"query": "找 5 年以上 Python 经验的", "expected_keyword": "Python"},
    {"query": "谁是架构师", "expected_keyword": "架构师"},
    {"query": "会 Go 的候选人", "expected_keyword": "Go"},
    {"query": "会 Java 的候选人", "expected_keyword": "Java"},
]

def evaluate_retrival():
    hits=0
    mrr_sum=0
    for case in TEST_CASES:
        results=retrieve(case['query'],knowledge_list,top_k=3)
        if case.get('expected_behavior')=='honest':
            if results is None:
                hits+=1
                mrr_sum+=1
            else:
                print(f"应未找到但返回了内容{case['query']}")
            continue
        if results is None:
            results= ""
        if case['expected_keyword'] in results:
            hits+=1
            segments=[s for s in results.split('【来源') if s.strip()]
            for rank,seg in enumerate(segments):
                if case["expected_keyword"] in seg:
                    print(f"{case['query']:30s}的排名是：第{rank}名")
                    mrr_sum+=1.0/(rank+1)
                    break
        else:
            print(f"检索失败：{case['query']}")
            print(f"期望关键词：{case['expected_keyword']}")
            print(f"实际返回：{results[:100]}...")
    hit_rate=hits/len(TEST_CASES)
    mrr=mrr_sum/len(TEST_CASES)
    print('检索评估结果')
    print(f"Hit@3: {hits}/{len(TEST_CASES)}={hit_rate*100:.1f}%")
    print(f"MRR: {mrr:.3f}")

evaluate_retrival()