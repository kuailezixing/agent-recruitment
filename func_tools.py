import requests
import datetime
import re
from config_file import amap_key

#自定义工具函数
#获取城市天气
def get_weather(city_adcode):
    '''
    city_adcode:城市的区域编码。
    播报城市的天气情况
    '''
    print('get_weather被调用了')
    key=amap_key
    url='https://restapi.amap.com/v3/weather/weatherInfo'
    params={'key':key,'city':city_adcode}
    res=requests.get(url=url,params=params)
    lives=res.json()['lives'][0]
    city_name=lives['city']
    weather=lives['weather']
    temperature=lives['temperature']
    winddirection=lives['winddirection']
    windpower=lives['windpower']
    city_weather_dict={'city_name':city_name,'weather':weather,'temperature':temperature,'winddirection':winddirection,'windpower':windpower}
    return city_weather_dict

#获取城市对应的编码
def get_adcode(city_name):
    '''
    根据参数city_name城市名称,获取city_name对应的adcode区域编码
    '''
    print('get_adcode工具被调用了')
    api_url='https://restapi.amap.com/v3/config/district'
    params={'key':amap_key,'keywords':city_name}
    res=requests.get(url=api_url,params=params)
    adcode_dict={'adcode':res.json()['districts'][0]['adcode'],'city_name':city_name}
    return adcode_dict

#口语日期格式化
def get_date(text):
    '''
    将口语化的日期描述转成年月日格式，
    例如9月1号转成当年的9月1号，即2026年09月01号
    '''
    date_str=None
    today=datetime.datetime.today()
    if '今天' in text:
        date_str=today
    elif '昨天' in text:
        date_str=today+datetime.timedelta(days=-1)
    elif '前天' in text:
        date_str=today+datetime.timedelta(days=-2)
    elif '大前天' in text:
        date_str=today+datetime.timedelta(days=-3)
    else:
        match = re.search(r'(\d{1,2})月(\d{1,2})[日号]?', text)
        if match:
            month, day = int(match.group(1)),int(match.group(2))
            # 假设是今年，如果已经过了则视为明年（可简化）
            return {text:f"{today.year}年{int(month):02d}月{int(day):02d}日"}
        return {text:'无法识别日期'}
    return {text:date_str.strftime('%Y年%m月%d日')}

