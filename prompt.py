
#system_content='''
#你是一个智能查询助手，同时你也是一个超级大脑，对于常识问题，直接回答就行。
#如果任何不确定答案的问题、涉及具体技术细节的问题、涉及框架/工具/API用法的问题，必须优先调用get_embedding检索知识库,
#不得直接说“超出能力范围”或“我没有相关资料”。
#对于用户提问涉及到关键词“我”、“我的”、密钥、key、个人笔记等私人信息类时，必须在知识库中检索。
#如果有时间的口语化描述，请按照工具返回的格式
#禁止回复“我没有检索工具，无法检索知识库”——你有get_embedding工具
#只有当检索知识库后，没有找到匹配的答案，才可以回复未在知识库中找到相关记录,同时禁止扩展解释说明其他无关信息
#【系统标记处理规则】
#当看到工具返回的结果是【系统标记:NO_RESULT】时，必须只回复：
#"知识库中未找到与您的问题相关的记录"
#禁止补充任何解释，建议，常识或扩展内容
#'''


system_content='''
你是一个专业的招聘助手，负责帮助 HR 从简历库中筛选候选人。


你的能力：
1. 根据技能、经验年限、学历等条件筛选候选人
2. 对比多个候选人，推荐最匹配的
3. 根据 JD（职位描述）匹配候选人
4. 生成面试问题建议

【禁止推测规则】
1. 只有当候选人的"技能"部分明确写出某技能（如"Python（精通）"），才能说他"会 Python"。
2. 禁止根据"教育背景"（如计算机专业）推测他"应该会某技能"。
3. 禁止用"应该"、"可能"、"从 XX 看"这类推测性表达。
4. 如果检索到的内容里没有明确提到某技能，就回复"简历库中未找到明确提到 XXX 的候选人"，不要编造。

【输出格式强制规则】
1. 每个候选人只列：姓名 + 匹配依据（一句话），不展开。
2. 禁止重复"根据简历库检索结果"这类开场白。
3. 禁止在末尾重复完整列表。
4. 总输出不超过 300 字。
5. 分类统计只给一次，不要重复。

【强制规则】
1. 所有候选人信息必须从简历库中检索（调用 get_embedding 工具），禁止凭空编造。
2. 涉及"有没有"、"找一下"、"筛选"、"推荐"等查询时，必须调用 get_embedding。
3. 回答时必须注明候选人姓名，以及匹配的依据（如"5 年 Python 经验"）。
4. 如果简历库中没有匹配的候选人，明确说"未找到符合条件的候选人"，不要编造。

【系统标记处理规则】
当看到工具返回结果是【系统标记:NO_RESULT】时，必须只回复：
"简历库中未找到符合条件的候选人。"
禁止补充任何解释或建议。


'''


#自定义工具集
tools=[
    {
        'type':'function',
        'function':{
            'name':'get_weather',
            'description':'播报城市的天气情况,当用户查询多个城市时，可以为每个城市分别调用此工具,且可以一次返回多个调用',
            'parameters':{
                'type':'object',
                'properties':{
                    'city_adcode':{
                        'type':'string',
                        'description':'城市区域编码'
                    }
                },
                'required':['city_adcode'],
                'additionalProperties':False,
            },
            'strict':True
        }
    },
    {
        'type':'function',
        'function':{
            'name':'get_adcode',
            'description':'根据参数city_name城市名称,获取city_name对应的adcode区域编码,当用户查询多个城市时，可以为每个城市分别调用此工具,且可以一次返回多个调用',
            'parameters':{
                'type':'object',
                'properties':{
                    'city_name':{
                        'type':'string',
                        'description':'城市名称'
                    }
                },
                'required':['city_name'],
                'additionalProperties':False,
            },
            'strict':True
        }
    },
    {
        'type':'function',
        'function':{
            'name':'get_embedding',
            #'description':'从本地知识库检索信息。当用户需要查询自己的学习记录，私人信息，历史笔记，API密钥，配置参数，个人文档等无法从公共尝试获取时，需要从本地知识库检索相关信息时，必须调用此工具。',
            'description':'从简历库中检索候选人信息。当用户需要筛选候选人、查询候选人技能、经验、学历等信息时，必须调用此工具。支持按技能（如 Python）、经验年限（如 3 年以上）、学历（如本科）等条件检索',
            'parameters':{
                'type':'object',
                'properties':{
                    'text':{
                        'type':'string',
                        'description':'查询条件，如"3年以上Python经验的候选人"'
                    }
                },
                'required':['text'],
                'additionalProperties':False,
            },
            'strict':True
        }
    },
#    {
#        'type':'function',
#        'function':{
#            'name':'cosine_similarity',
#            'description':'计算向量参数vec1和vec2之间的余弦相似度',
#            'parameters':{
#                'type':'object',
#                'properties':{
#                    'vec1':{
#                        'type':'dict',
#                        'description':'数值向量'
#                    },
#                    'vec2':{
#                        'type':'dict',
#                        'description':'数值向量'
#                    },
#                },
#                'required':['vec1','vec2'],
#                'additionalProperties':False,
#            },
#            'strict':True
#        }
#    },
    {
            'type':'function',
            'function':{
                'name':'get_date',
                'description':'将口语化的时间描述转成YYYY年mm月dd日格式，例如今天，昨天，或者是9月1号',
                'parameters':{
                    'type':'object',
                    'properties':{
                        'text':{
                            'type':'string',
                            'description':'用户问题'
                        },
                    },
                    'required':['text'],
                    'additionalProperties':False,
                },
                'strict':True
            }
        },
]